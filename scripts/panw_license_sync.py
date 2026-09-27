"""
PANW License Sync — NetBox Script

Queries the Palo Alto Networks license/support API for every Palo Alto asset
that has a serial number, then creates/updates ContractAssignment (support)
and AssetLicense (subscription) records so that NetBox reflects the vendor's
current license/coverage state.

How it fits the data model
---------------------------
  ContractVendor       "Palo Alto" (created if missing)
  Contract             one synthetic contract per CSP account per coverage
                        type: "PAN-ALC-<csp_id>" (support-alc) and
                        "PAN-ESA-<csp_id>" (support-ea) — PANW's API returns
                        no real contract/agreement number to key on.
  ContractSKU          keyed on the PANW part number (partidField), except
                        ESA which is keyed on "PAN-SVC-PREM-ESA-DL-<csp_id>"
                        (CSP baked into the SKU so the same physical SKU can
                        be tracked per account).
  ContractAssignment   per-asset support coverage (SUP records)
  LicenseSKU/          subscription entitlements (SUB/RENSUB records)
  AssetLicense

CSP accounts
------------
Palo Alto issues devices against one of several CSP (Customer Support
Portal) support accounts, each with its own API key. Querying the wrong CSP
for a serial returns an HTTP 400 ("does not belong to your support
account") rather than license data, so every configured CSP account is
tried in order until one claims the serial. Devices can move between CSPs
between syncs — see "CSP-move reconciliation" below.

CSP-move reconciliation
------------------------
ESA coverage is tracked per-CSP via a CSP-suffixed SKU
("PAN-SVC-PREM-ESA-DL-<csp_id>"). On every sync, any existing ESA
ContractAssignment on the asset whose SKU doesn't match the current run's
CSP-suffixed SKU is deleted as stale — this runs regardless of whether the
current run found an ESA record at all. Non-ESA support assignments don't
need this treatment since the SKU itself doesn't encode CSP, but a CSP
move there does re-point the assignment at the new CSP's contract.

Unowned assets (optional cleanup)
-----------------------------------
When a serial isn't claimed by any configured CSP account, that can mean
the vendor no longer covers the device — or a transient API/key problem.
With "Cleanup Unowned Assets" enabled, every existing ContractAssignment
and AssetLicense on that asset for the Palo Alto manufacturer is removed.
Off by default; enable deliberately, not routinely.

Not-registered tagging
------------------------
When PANW reports a serial as "not registered" (a distinct 400 response
from the CSP-ownership check above), the asset is tagged
"Asset > PAN - Not Registered" so it's visible without reading job logs.
The tag is removed automatically the next time that serial is found under
a CSP account.

Prerequisites
-------------
  PLUGINS_CONFIG["netbox_inventory"]["panw_csp_accounts"] — a list of at
  least two dicts, each {"id": "<CSP account id>", "api_key": "<API key>"}.
  In NetBox's configuration.py:

    PLUGINS_CONFIG = {
        "netbox_inventory": {
            ...
            "panw_csp_accounts": [
                {"id": "XXXXX", "api_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"},
                {"id": "YYYYY", "api_key": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"},
            ],
        },
    }

Script parameters (all optional)
---------------------------------
  dry_run                 do not write to DB (default False)
  cleanup_unowned          remove coverage for assets no CSP account claims
  asset_filter             limit to specific assets
  site_filter              limit to assets whose device is in selected sites
  tag_filter               limit to assets with selected tag(s)
  device_type_filter       limit to specific (Palo Alto) device types
  asset_limit              cap total assets processed (0 = no limit)
  verbose                  per-asset log lines
  log_limit                max verbose log lines
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q

from dcim.models import DeviceType, Manufacturer, Site
from extras.models import Tag
from extras.scripts import BooleanVar, IntegerVar, MultiObjectVar, Script

from netbox_inventory.models import (
    Asset,
    AssetLicense,
    Contract,
    ContractAssignment,
    ContractSKU,
    ContractVendor,
    LicenseSKU,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PANW_MANUFACTURER_NAME = "Palo Alto"
PANW_MANUFACTURER_SLUG = "palo-alto"
PANW_VENDOR_NAME = "Palo Alto"

PANW_LICENSE_API_URL = "https://api.paloaltonetworks.com/api/license/activate"
NOT_OWNED_MESSAGE = "does not belong to your support account"
NOT_REGISTERED_MESSAGE = "is not registered"
ESA_SKU_MARKER = "ESA"
ESA_BASE_SKU = "PAN-SVC-PREM-ESA-DL"

PANW_NOT_REGISTERED_TAG_NAME = "Asset > PAN - Not Registered"
PANW_NOT_REGISTERED_TAG_SLUG = "asset-pan-not-registered"


# ---------------------------------------------------------------------------
# PANW API client (no NetBox/Django dependency)
# ---------------------------------------------------------------------------

class PanwApiError(Exception):
    pass


class DeviceNotFoundError(Exception):
    """No configured CSP account reported ownership of this serial number."""


class DeviceNotRegisteredError(PanwApiError):
    """PANW reports this serial as not registered (distinct from CSP ownership)."""


def _parse_reg_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return datetime.fromisoformat(value).date()


def _parse_expiration_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return datetime.strptime(value, "%m/%d/%Y %I:%M:%S %p").date()


class LicenseRecord:
    def __init__(self, raw: dict):
        self.type = (raw.get("typeField") or "").strip().upper()
        self.sku = (raw.get("partidField") or "").strip()
        self.name = (raw.get("featureField") or "").strip()
        self.description = (raw.get("feature_descField") or "").strip()
        self.start_date = _parse_reg_date(raw.get("regDateField"))
        self.end_date = _parse_expiration_date(raw.get("expirationField"))
        self.license_key = (raw.get("auth_codeField") or "").strip()

    def __repr__(self):
        return f"LicenseRecord({self.type} {self.sku!r})"

    @property
    def is_support(self) -> bool:
        return self.type == "SUP"

    @property
    def is_subscription(self) -> bool:
        return self.type in ("SUB", "RENSUB")

    @property
    def is_esa(self) -> bool:
        return self.is_support and ESA_SKU_MARKER in self.sku.upper()


class CSPAccount:
    def __init__(self, id, api_key):
        self.id = id
        self.api_key = api_key


class PanwClient:
    def __init__(self, csp_accounts, timeout=30, session=None):
        self.csp_accounts = csp_accounts
        self.timeout = timeout
        self.session = session or requests.Session()

    def _query_csp(self, csp, serial):
        response = self.session.post(
            PANW_LICENSE_API_URL,
            headers={"apikey": csp.api_key},
            data={"serialNumber": serial},
            timeout=self.timeout,
        )

        if response.status_code == 400:
            body = {}
            if response.content:
                try:
                    body = response.json()
                except ValueError:
                    body = {}
            message = body.get("Message", "") if isinstance(body, dict) else ""
            if NOT_OWNED_MESSAGE in message:
                return None
            if NOT_REGISTERED_MESSAGE in message:
                raise DeviceNotRegisteredError(f"CSP {csp.id}: {response.status_code} {response.text}")
            raise PanwApiError(f"CSP {csp.id}: {response.status_code} {response.text}")

        if not response.ok:
            raise PanwApiError(f"CSP {csp.id}: {response.status_code} {response.text}")

        return response.json()

    def get_license_records(self, serial):
        """
        Returns (csp_id, [LicenseRecord, ...]) for whichever configured CSP
        account owns this serial, trying accounts in configured order.
        Raises DeviceNotFoundError if none of them own it.
        """
        for csp in self.csp_accounts:
            payload = self._query_csp(csp, serial)
            if payload is None:
                continue
            return csp.id, [LicenseRecord(raw) for raw in payload]

        raise DeviceNotFoundError(serial)


def _get_csp_accounts(script: Script) -> Optional[list]:
    cfg = settings.PLUGINS_CONFIG.get("netbox_inventory", {}) or {}
    raw_accounts = cfg.get("panw_csp_accounts") or []

    accounts = []
    for entry in raw_accounts:
        csp_id = str(entry.get("id", "")).strip()
        api_key = (entry.get("api_key") or "").strip()
        if csp_id and api_key:
            accounts.append(CSPAccount(id=csp_id, api_key=api_key))

    if len(accounts) < 2:
        script.log_failure(
            "PLUGINS_CONFIG['netbox_inventory']['panw_csp_accounts'] must define at "
            "least two {'id': ..., 'api_key': ...} entries."
        )
        return None

    return accounts


def esa_sku_for_csp(csp_id: str) -> str:
    return f"{ESA_BASE_SKU}-{csp_id}"


def is_esa_sku(sku: str) -> bool:
    return sku.upper().startswith(ESA_BASE_SKU)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_or_create_not_registered_tag(do_commit: bool, script: Script) -> Optional[Tag]:
    """
    Get or create the review tag for assets PANW reports as not registered.
    In dry-run mode the tag is not created; returns None if it doesn't exist yet.
    """
    try:
        return Tag.objects.get(slug=PANW_NOT_REGISTERED_TAG_SLUG)
    except Tag.DoesNotExist:
        if not do_commit:
            return None
        tag = Tag(
            name=PANW_NOT_REGISTERED_TAG_NAME,
            slug=PANW_NOT_REGISTERED_TAG_SLUG,
            color="d63939",  # red — needs action with the vendor before sync can proceed
            description=(
                "Palo Alto reports this device's serial as not registered. "
                "Requires registration with PANW before license/support data can sync."
            ),
        )
        tag.save()
        script.log_success(f"Created tag '{PANW_NOT_REGISTERED_TAG_NAME}'")
        return tag


def _add_not_registered_tag(
    asset: Asset, tag: Optional[Tag], do_commit: bool, script: Script, vlog,
) -> bool:
    if tag is not None and asset.tags.filter(pk=tag.pk).exists():
        return False
    if do_commit and tag is not None:
        asset.tags.add(tag)
    vlog(
        f"asset={asset.pk} '{asset}': "
        f"{'[DRY RUN] would add' if not do_commit else 'added'} tag '{PANW_NOT_REGISTERED_TAG_NAME}'"
    )
    return True


def _remove_not_registered_tag(
    asset: Asset, tag: Optional[Tag], do_commit: bool, script: Script, vlog,
) -> bool:
    if tag is None or not asset.tags.filter(pk=tag.pk).exists():
        return False
    if do_commit:
        asset.tags.remove(tag)
    vlog(
        f"asset={asset.pk} '{asset}': "
        f"{'[DRY RUN] would remove' if not do_commit else 'removed'} tag '{PANW_NOT_REGISTERED_TAG_NAME}'"
    )
    return True


def _get_or_create_vendor(script: Script) -> ContractVendor:
    vendor, created = ContractVendor.objects.get_or_create(name=PANW_VENDOR_NAME)
    if created:
        script.log_success(f"Created contract vendor: {PANW_VENDOR_NAME}")
    return vendor


def _get_or_create_contract(
    contract_id: str,
    contract_type: str,
    description: str,
    vendor: ContractVendor,
    do_commit: bool,
    script: Script,
) -> Contract:
    """
    Contract dates are intentionally left unset here — PANW's API has no real
    contract-level start/end, only per-asset coverage dates (carried on
    ContractAssignment instead).
    """
    if not do_commit:
        return Contract.objects.filter(contract_id=contract_id).first() or Contract(
            contract_id=contract_id,
            contract_type=contract_type,
            vendor=vendor,
            status="active",
            description=description,
        )

    contract, created = Contract.objects.get_or_create(
        contract_id=contract_id,
        defaults={
            "contract_type": contract_type,
            "vendor": vendor,
            "status": "active",
            "description": description,
        },
    )
    if created:
        script.log_success(f"Created contract: {contract_id}")
    return contract


def _get_or_create_contract_sku(
    sku_code: str,
    contract_type: str,
    name: str,
    description: str,
    manufacturer: Manufacturer,
    do_commit: bool,
    script: Script,
) -> ContractSKU:
    if not do_commit:
        return ContractSKU.objects.filter(sku=sku_code).first() or ContractSKU(
            sku=sku_code,
            manufacturer=manufacturer,
            contract_type=contract_type,
            service_level=name,
            description=description,
        )

    sku, created = ContractSKU.objects.get_or_create(
        sku=sku_code,
        defaults={
            "manufacturer": manufacturer,
            "contract_type": contract_type,
            "service_level": name,
            "description": description,
        },
    )
    if created:
        script.log_success(f"Created contract SKU: {sku_code}")
    else:
        update_fields = []
        if sku.description != description:
            sku.description = description
            update_fields.append("description")
        if sku.contract_type != contract_type:
            sku.contract_type = contract_type
            update_fields.append("contract_type")
        if update_fields:
            sku.save(update_fields=update_fields)
    return sku


def _get_or_create_license_sku(
    sku_code: str,
    name: str,
    description: str,
    manufacturer: Manufacturer,
    do_commit: bool,
    script: Script,
) -> LicenseSKU:
    if not do_commit:
        return LicenseSKU.objects.filter(sku=sku_code).first() or LicenseSKU(
            sku=sku_code,
            manufacturer=manufacturer,
            name=name,
            license_kind="subscription",
            description=description,
        )

    sku, created = LicenseSKU.objects.get_or_create(
        sku=sku_code,
        defaults={
            "manufacturer": manufacturer,
            "name": name,
            "license_kind": "subscription",
            "description": description,
        },
    )
    if created:
        script.log_success(f"Created license SKU: {sku_code}")
    else:
        update_fields = []
        if sku.name != name:
            sku.name = name
            update_fields.append("name")
        if sku.description != description:
            sku.description = description
            update_fields.append("description")
        if update_fields:
            sku.save(update_fields=update_fields)
    return sku


def _upsert_contract_assignment(
    asset: Asset,
    contract: Contract,
    sku: ContractSKU,
    start_date: Optional[date],
    end_date: Optional[date],
    do_commit: bool,
    script: Script,
) -> tuple[Optional[ContractAssignment], str]:
    """Matches on (asset, sku) — one active coverage record per asset+SKU."""
    existing = ContractAssignment.objects.filter(asset=asset, sku=sku).first()

    if existing:
        if (
            existing.contract_id == contract.pk
            and existing.start_date == start_date
            and existing.end_date == end_date
        ):
            return existing, "unchanged"
        if do_commit:
            existing.contract = contract
            existing.start_date = start_date
            existing.end_date = end_date
            existing.full_clean()
            existing.save()
        return existing, "updated"

    if not do_commit:
        return None, "created"

    assignment = ContractAssignment(
        asset=asset, contract=contract, sku=sku, start_date=start_date, end_date=end_date,
    )
    assignment.full_clean()
    assignment.save()
    return assignment, "created"


def _upsert_asset_license(
    asset: Asset,
    sku: LicenseSKU,
    start_date: Optional[date],
    end_date: Optional[date],
    license_key: str,
    do_commit: bool,
    script: Script,
) -> tuple[Optional[AssetLicense], str]:
    """Matches on (asset, sku) — one active entitlement record per asset+SKU."""
    existing = AssetLicense.objects.filter(asset=asset, sku=sku).first()

    if existing:
        if (
            existing.start_date == start_date
            and existing.end_date == end_date
            and (existing.license_key or "") == license_key
        ):
            return existing, "unchanged"
        if do_commit:
            existing.start_date = start_date
            existing.end_date = end_date
            existing.license_key = license_key
            existing.full_clean()
            existing.save()
        return existing, "updated"

    if not do_commit:
        return None, "created"

    asset_license = AssetLicense(
        asset=asset, sku=sku, start_date=start_date, end_date=end_date, license_key=license_key,
    )
    asset_license.full_clean()
    asset_license.save()
    return asset_license, "created"


def _prune_stale_esa_assignments(
    asset: Asset, current_esa_sku: Optional[str], do_commit: bool, script: Script, vlog,
) -> int:
    """
    ESA coverage is tracked per-CSP via a CSP-suffixed SKU. If a device has
    moved to a different CSP account (or lost ESA coverage) since the last
    sync, any leftover ESA assignment under the old SKU is now stale.
    """
    removed = 0
    for assignment in ContractAssignment.objects.filter(asset=asset).select_related("sku"):
        sku_code = assignment.sku.sku if assignment.sku else ""
        if is_esa_sku(sku_code) and sku_code != current_esa_sku:
            vlog(f"asset={asset.pk} '{asset}': removing stale ESA assignment ({sku_code})")
            removed += 1
            if do_commit:
                assignment.delete()
    return removed


def cleanup_unowned_asset(
    asset: Asset, manufacturer: Manufacturer, do_commit: bool, script: Script, vlog,
) -> int:
    """
    Called when neither configured CSP account claims this serial anymore.
    Removes every support contract assignment and subscription license tied
    to this asset for the Palo Alto manufacturer only — guards against ever
    touching a different manufacturer's records on the same asset.
    """
    removed = 0

    for assignment in ContractAssignment.objects.filter(asset=asset).select_related(
        "sku__manufacturer"
    ):
        if not assignment.sku or assignment.sku.manufacturer_id != manufacturer.pk:
            continue
        vlog(
            f"asset={asset.pk} '{asset}': removing contract assignment "
            f"{assignment.sku.sku} (unowned by any CSP)"
        )
        removed += 1
        if do_commit:
            assignment.delete()

    for asset_license in AssetLicense.objects.filter(asset=asset).select_related(
        "sku__manufacturer"
    ):
        if not asset_license.sku or asset_license.sku.manufacturer_id != manufacturer.pk:
            continue
        vlog(
            f"asset={asset.pk} '{asset}': removing asset license "
            f"{asset_license.sku.sku} (unowned by any CSP)"
        )
        removed += 1
        if do_commit:
            asset_license.delete()

    return removed


def sync_asset(
    asset: Asset,
    csp_id: str,
    records: list,
    manufacturer: Manufacturer,
    vendor: ContractVendor,
    do_commit: bool,
    script: Script,
    vlog,
    stats: dict,
) -> None:
    support_records = [r for r in records if r.is_support]
    subscription_records = [r for r in records if r.is_subscription]
    esa_records = [r for r in support_records if r.is_esa]
    other_support_records = [r for r in support_records if not r.is_esa]

    ea_contract = None
    if esa_records:
        ea_contract = _get_or_create_contract(
            f"PAN-ESA-{csp_id}", "support-ea",
            f"Palo Alto Networks Enterprise Agreement support — CSP {csp_id}",
            vendor, do_commit, script,
        )

    alc_contract = None
    if other_support_records:
        alc_contract = _get_or_create_contract(
            f"PAN-ALC-{csp_id}", "support-alc",
            f"Palo Alto Networks support — CSP {csp_id}",
            vendor, do_commit, script,
        )

    current_esa_sku = None
    if esa_records:
        record = esa_records[0]
        current_esa_sku = esa_sku_for_csp(csp_id)
        sku = _get_or_create_contract_sku(
            current_esa_sku, "support-ea", record.name, record.description,
            manufacturer, do_commit, script,
        )
        _, action = _upsert_contract_assignment(
            asset, ea_contract, sku, record.start_date, record.end_date, do_commit, script,
        )
        if action != "unchanged":
            stats["assignment_" + action] += 1
            vlog(f"asset={asset.pk} '{asset}': {action} ESA assignment ({current_esa_sku})")

    stats["esa_pruned"] += _prune_stale_esa_assignments(
        asset, current_esa_sku, do_commit, script, vlog
    )

    for record in other_support_records:
        sku = _get_or_create_contract_sku(
            record.sku, "support-alc", record.name, record.description,
            manufacturer, do_commit, script,
        )
        _, action = _upsert_contract_assignment(
            asset, alc_contract, sku, record.start_date, record.end_date, do_commit, script,
        )
        if action != "unchanged":
            stats["assignment_" + action] += 1
            vlog(f"asset={asset.pk} '{asset}': {action} support assignment ({record.sku})")

    for record in subscription_records:
        sku = _get_or_create_license_sku(
            record.sku, record.name, record.description, manufacturer, do_commit, script,
        )
        _, action = _upsert_asset_license(
            asset, sku, record.start_date, record.end_date, record.license_key,
            do_commit, script,
        )
        if action != "unchanged":
            stats["license_" + action] += 1
            vlog(f"asset={asset.pk} '{asset}': {action} subscription license ({record.sku})")


# ---------------------------------------------------------------------------
# Main Script
# ---------------------------------------------------------------------------

class SyncPanwLicenses(Script):
    class Meta:
        name = "License: Sync Palo Alto Networks license/support coverage"
        description = (
            "Queries the Palo Alto Networks license API to determine per-serial "
            "support/subscription coverage, then creates/updates Contract / "
            "ContractSKU / ContractAssignment / LicenseSKU / AssetLicense records "
            "for Palo Alto assets."
        )

    dry_run = BooleanVar(
        default=False,
        label="Dry Run",
        description="Preview changes without writing to the database.",
    )

    cleanup_unowned = BooleanVar(
        default=False,
        label="Cleanup Unowned Assets",
        description=(
            "If neither configured CSP account claims a serial, remove all of its "
            "existing support contract assignments and subscription licenses. "
            "Off by default — losing coverage under both CSPs can also mean a "
            "transient key/API problem, not necessarily lost vendor coverage."
        ),
    )

    site_filter = MultiObjectVar(
        model=Site,
        required=False,
        label="Sites",
        description="Limit sync to assets whose assigned device is in one of these sites.",
    )

    asset_filter = MultiObjectVar(
        model=Asset,
        required=False,
        label="Assets",
        description="Limit sync to these specific assets.",
    )

    tag_filter = MultiObjectVar(
        model=Tag,
        required=False,
        label="Tags",
        description="Limit sync to assets that have one or more of the selected tag(s).",
    )

    device_type_filter = MultiObjectVar(
        model=DeviceType,
        required=False,
        label="Device Types",
        description="Limit sync to assets of these device types.",
        query_params={
            'manufacturer': PANW_MANUFACTURER_SLUG,
        },
    )

    asset_limit = IntegerVar(
        default=0,
        required=False,
        label="Asset Limit",
        description="Process only the first N assets (0 = no limit). Useful for test runs.",
    )

    verbose = BooleanVar(
        default=False,
        label="Verbose Logging",
        description="Emit per-asset log lines (can be noisy for large inventories).",
    )

    log_limit = IntegerVar(
        default=500,
        label="Verbose Log Limit",
        description="Maximum per-asset log lines when verbose logging is enabled.",
    )

    @transaction.atomic
    def run(self, data, commit):
        do_commit = bool(commit) and not data["dry_run"]
        verbose = bool(data.get("verbose", False))
        log_limit = int(data.get("log_limit", 500))
        logged = 0

        def vlog(msg: str) -> None:
            nonlocal logged
            if not verbose or logged >= log_limit:
                return
            self.log_info(msg)
            logged += 1

        # ------------------------------------------------------------------
        # Resolve manufacturer + CSP accounts
        # ------------------------------------------------------------------
        try:
            manufacturer = Manufacturer.objects.get(name__iexact=PANW_MANUFACTURER_NAME)
        except Manufacturer.DoesNotExist:
            self.log_failure(
                f'Manufacturer "{PANW_MANUFACTURER_NAME}" not found in NetBox. '
                "Create it first under Devices → Manufacturers."
            )
            return

        csp_accounts = _get_csp_accounts(self)
        if not csp_accounts:
            return

        # ------------------------------------------------------------------
        # Build asset queryset
        # ------------------------------------------------------------------
        asset_qs = (
            Asset.objects
            .select_related("device_type__manufacturer", "module_type__manufacturer", "device")
            .filter(
                Q(device_type__manufacturer=manufacturer)
                | Q(module_type__manufacturer=manufacturer)
                | Q(inventoryitem_type__manufacturer=manufacturer)
            )
            .exclude(serial__isnull=True)
            .exclude(serial__exact="")
            .exclude(status="disposed")
        )

        selected_sites = data.get("site_filter")
        if selected_sites:
            asset_qs = asset_qs.filter(device__site__in=selected_sites)
            self.log_info(
                f"Site filter active — limiting to: {', '.join(s.name for s in selected_sites)}"
            )

        selected_assets = data.get("asset_filter")
        if selected_assets:
            asset_qs = asset_qs.filter(pk__in=[a.pk for a in selected_assets])
            self.log_info(f"Asset filter active — limiting to {selected_assets.count()} asset(s).")

        selected_tags = data.get("tag_filter")
        if selected_tags:
            asset_qs = asset_qs.filter(tags__in=selected_tags).distinct()
            self.log_info(
                f"Tag filter active — limiting to: {', '.join(t.name for t in selected_tags)}"
            )

        selected_device_types = data.get("device_type_filter")
        if selected_device_types:
            asset_qs = asset_qs.filter(device_type__in=selected_device_types)
            self.log_info(
                f"Device type filter active — limiting to: "
                f"{', '.join(dt.model for dt in selected_device_types)}"
            )

        all_assets = list(asset_qs)

        asset_limit = int(data.get("asset_limit") or 0)
        if asset_limit > 0:
            all_assets = all_assets[:asset_limit]
            self.log_info(f"Asset limit active — processing first {len(all_assets)} asset(s).")

        self.log_info(f"Found {len(all_assets)} {PANW_MANUFACTURER_NAME} asset(s) with a serial.")
        if not all_assets:
            self.log_info("Nothing to sync.")
            return

        # ------------------------------------------------------------------
        # Dedupe by serial (avoid querying the API twice for the same device)
        # ------------------------------------------------------------------
        serial_to_assets: dict[str, list[Asset]] = {}
        for asset in all_assets:
            sn = (asset.serial or "").strip().upper()
            if sn:
                serial_to_assets.setdefault(sn, []).append(asset)

        vendor = _get_or_create_vendor(self)
        panw = PanwClient(csp_accounts)

        not_registered_tag = _get_or_create_not_registered_tag(do_commit, self)
        if not_registered_tag is None and not do_commit:
            self.log_info(
                f"Dry run: tag '{PANW_NOT_REGISTERED_TAG_NAME}' does not exist yet "
                "and will be created on the first live run."
            )

        stats = {
            "found": 0,
            "not_found": 0,
            "not_registered": 0,
            "api_errors": 0,
            "assignment_created": 0,
            "assignment_updated": 0,
            "license_created": 0,
            "license_updated": 0,
            "esa_pruned": 0,
            "cleanup_removed": 0,
            "cleanup_errors": 0,
            "tag_added": 0,
            "tag_removed": 0,
        }

        # ------------------------------------------------------------------
        # Per-serial sync
        # ------------------------------------------------------------------
        for serial, assets_for_serial in serial_to_assets.items():
            try:
                csp_id, records = panw.get_license_records(serial)
            except DeviceNotFoundError:
                stats["not_found"] += 1
                vlog(f"serial={serial}: not found under any configured CSP account")
                if data.get("cleanup_unowned"):
                    for asset in assets_for_serial:
                        try:
                            stats["cleanup_removed"] += cleanup_unowned_asset(
                                asset, manufacturer, do_commit, self, vlog
                            )
                        except Exception as exc:
                            self.log_warning(f"asset={asset.pk} '{asset}': cleanup failed: {exc}")
                            stats["cleanup_errors"] += 1
                continue
            except DeviceNotRegisteredError as exc:
                stats["not_registered"] += 1
                self.log_warning(f"serial={serial}: not registered with PANW: {exc}")
                for asset in assets_for_serial:
                    if _add_not_registered_tag(asset, not_registered_tag, do_commit, self, vlog):
                        stats["tag_added"] += 1
                continue
            except PanwApiError as exc:
                self.log_warning(f"serial={serial}: PANW API error: {exc}")
                stats["api_errors"] += 1
                continue

            stats["found"] += 1
            vlog(f"serial={serial}: found under CSP {csp_id} ({len(records)} record(s))")

            for asset in assets_for_serial:
                if _remove_not_registered_tag(asset, not_registered_tag, do_commit, self, vlog):
                    stats["tag_removed"] += 1
                try:
                    sync_asset(
                        asset, csp_id, records, manufacturer, vendor, do_commit, self, vlog, stats,
                    )
                except Exception as exc:
                    self.log_warning(f"asset={asset.pk} '{asset}': failed to sync: {exc}")
                    stats["api_errors"] += 1

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        self.log_info(
            f"\n{'='*60}\n"
            f"SYNC COMPLETE {'(DRY RUN — no changes written)' if not do_commit else ''}\n"
            f"  Serials checked          : {len(serial_to_assets)}\n"
            f"  Found under a CSP account: {stats['found']}\n"
            f"  Not found under any CSP  : {stats['not_found']}\n"
            f"  Not registered with PANW : {stats['not_registered']}\n"
            f"  PANW API errors          : {stats['api_errors']}\n"
            f"  Contract assignments +   : {stats['assignment_created']}\n"
            f"  Contract assignments ~   : {stats['assignment_updated']}\n"
            f"  Asset licenses +         : {stats['license_created']}\n"
            f"  Asset licenses ~         : {stats['license_updated']}\n"
            f"  Stale ESA assignments -  : {stats['esa_pruned']}\n"
            f"  Unowned records removed  : {stats['cleanup_removed']}\n"
            f"  Cleanup errors           : {stats['cleanup_errors']}\n"
            f"  Not-registered tags +    : {stats['tag_added']}\n"
            f"  Not-registered tags -    : {stats['tag_removed']}\n"
            f"{'='*60}"
        )

        if verbose and logged >= log_limit:
            self.log_info(
                f"Verbose log limit reached ({log_limit}). Increase 'Verbose Log Limit' to see more."
            )
