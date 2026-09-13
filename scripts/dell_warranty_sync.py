
"""
Dell Warranty / Service Contract Sync — NetBox Script

Queries the Dell TechDirect Asset Entitlement API for every Dell asset that has
a serial number (Dell "Service Tag"), then updates Asset warranty fields and
Contract / ContractSKU / ContractAssignment records so that NetBox reflects
Dell's currently-reported coverage.

Unlike Cisco's Coverage Summary API, Dell's entitlement API has no durable
"contract number" shared across many assets — each service tag simply reports
a list of entitlement windows (the base hardware warranty plus any purchased
support upgrades/extensions such as ProSupport or ProSupport Plus). To fit
this plugin's Contract/ContractSKU/ContractAssignment model, coverage is
grouped by *service-level type* instead of by a vendor contract number: all
assets reported under "ProSupport Plus" share one Contract, all assets under
"Basic Hardware Service" share another, etc. — mirroring how a single Cisco
SNTC contract is shared across many assets.

Reconciliation with existing data
----------------------------------
This NetBox instance already has manually-created Dell coverage data (e.g. a
"VEP ProSupport" Contract + "ProSupport Plus" ContractSKU with per-asset
ContractAssignment rows). Before creating a new Contract/ContractSKU for a
service level, this script looks for an existing ContractSKU whose `sku` or
`description` case-insensitively matches the API's service level description,
and reuses whatever Contract that SKU is already assigned under. This is a
best-effort text match — if Dell's wording drifts from what's stored (e.g.
"ProSupport Plus" vs "Dell ProSupport Plus for VEP"), it will not match and a
new Contract/SKU pair will be created instead. Review the run's log output
(and, ideally, a dry run first) to confirm existing rows were matched as
expected.

Existing ContractAssignment rows for an asset+contract+sku combination are
*updated in place* (start/end dates) rather than only created-if-missing, so
that re-running this script keeps existing manually-entered coverage current
instead of leaving it to go stale.

How it fits the data model
---------------------------
  ContractVendor       "Dell" (created if missing; already exists in this DB)
  ContractSKU          keyed on Dell serviceLevelDescription, reconciled
                        against existing rows before creating a new one
  Contract             one per service-level type (not per Cisco-style
                        contract number), reconciled via existing
                        ContractAssignment rows for the resolved SKU
  ContractAssignment   per-asset link; start/end dates kept in sync on rerun
  Asset.warranty_*     warranty_end / warranty_type / warranty_start (derived
                        from vendor_ship_date, same convention as Cisco sync)
  Asset.vendor_ship_date  populated from Dell's shipDate if not already set
  Asset.support_state  updated from coverage + HardwareLifecycle (EoX), same
                        priority logic as the Cisco sync script

EoX / HardwareLifecycle
------------------------
If a HardwareLifecycle record exists for the asset's device_type and its
end_of_support date is in the past, the asset is marked Excluded with reason
"Past end of support" regardless of Dell-reported coverage — same behavior
as cisco_coverage_sync.py.

IMPORTANT — verify against your TechDirect account before first live run
--------------------------------------------------------------------------
This script targets Dell's published TechDirect Warranty / Asset Entitlement
API (OAuth2 client-credentials token endpoint + the asset-entitlements REST
endpoint). Unlike the Cisco/PANW scripts in this plugin, the exact response
envelope (a bare JSON array vs. a wrapped object) and field names can vary
slightly by TechDirect API version/subscription. `_fetch_entitlements_batch`
below handles the common shapes defensively and `log_api_response` will dump
the raw JSON for a batch so you can confirm field names against what your
account actually returns — check this on a small `asset_limit`/dry run
before trusting a full live sync.

Prerequisites
-------------
  PLUGINS_CONFIG["netbox_inventory"]["dell_techdirect_api_client_id"]
  PLUGINS_CONFIG["netbox_inventory"]["dell_techdirect_api_client_secret"]

Script parameters (all optional)
---------------------------------
  dry_run                 do not write to DB (default False)
  tag_filter               limit to assets with selected tag(s)
  skip_covered            skip assets that already have an active ContractAssignment
  site_filter             limit to assets whose device is in selected sites
  asset_filter             limit to specific assets
  device_type_filter      limit to specific device types
  purchase_filter         limit to assets belonging to selected purchases
  order_filter            limit to assets belonging to selected orders
  update_support_status   update support_state / reason / validated_at (default True)
  validated_at_threshold  skip assets validated within this many days (0 = disabled)
  verbose                 per-asset log lines
  log_api_response        log raw API JSON per batch (debug)
  log_limit               max verbose log lines
  asset_limit             cap total assets processed (0 = no limit)
"""
from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta
from typing import Optional

import requests
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from dcim.models import DeviceType, Manufacturer, Site
from extras.scripts import (
    BooleanVar,
    IntegerVar,
    MultiObjectVar,
    Script,
    StringVar,
)
from extras.models import Tag

from netbox_inventory.models import (
    Asset,
    Contract,
    ContractAssignment,
    ContractSKU,
    ContractVendor,
    HardwareLifecycle,
    Order,
    Purchase,
    WarrantyType,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DELL_MANUFACTURER_NAME = "Dell"
DELL_VENDOR_NAME = "Dell"

# Dell TechDirect API — OAuth2 client-credentials token endpoint
TOKEN_URL = "https://apigtwb2c.us.dell.com/auth/oauth/v2/token"

# Dell TechDirect Asset Entitlement (warranty) API. Accepts a comma-separated
# list of service tags. Dell's documented per-request limit has varied by API
# version (100 has been common); kept conservative here — lower it further if
# your account enforces a smaller cap.
ENTITLEMENT_API_URL = (
    "https://apigtwb2c.us.dell.com/PROD/sbil/eapi/v5/asset-entitlements"
    "?servicetags={service_tags}"
)
ENTITLEMENT_BATCH_SIZE = 50

# Default contract_type applied to newly-created SKUs/Contracts when the
# service level can't be classified as a base warranty (see _infer_contract_type).
DEFAULT_SUPPORT_CONTRACT_TYPE = "support-alc"
WARRANTY_CONTRACT_TYPE = "warranty"

# Service level description substrings treated as base hardware warranty
# (as opposed to a purchased support plan like ProSupport).
WARRANTY_LEVEL_HINTS = ("basic hardware", "limited hardware", "warranty")

# Support state values (mirrors AssetSupportStateChoices / AssetSupportReasonChoices
# / AssetSupportSourceChoices in netbox_inventory.choices)
SUPPORT_STATE_COVERED = "covered"
SUPPORT_STATE_UNCOVERED = "uncovered"
SUPPORT_STATE_EXCLUDED = "excluded"
SUPPORT_REASON_EOX = "past_end_of_support"
SUPPORT_REASON_NO_CONTRACT = "contract_missing"
SUPPORT_REASON_COVERED_CONTRACT = "covered_contract"
SUPPORT_REASON_COVERED_WARRANTY = "covered_warranty"
SUPPORT_SOURCE_COMPUTED = "computed"


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _get_auth_headers(script: Script) -> Optional[dict]:
    """Return OAuth2 headers for the Dell TechDirect API.

    Credentials are read from PLUGINS_CONFIG["netbox_inventory"].
    """
    cfg = settings.PLUGINS_CONFIG.get("netbox_inventory", {}) or {}
    client_id = (cfg.get("dell_techdirect_api_client_id") or "").strip()
    client_secret = (cfg.get("dell_techdirect_api_client_secret") or "").strip()

    if not client_id or not client_secret:
        script.log_failure(
            "Dell TechDirect API credentials not configured. Set "
            "dell_techdirect_api_client_id / dell_techdirect_api_client_secret "
            "in PLUGINS_CONFIG['netbox_inventory']."
        )
        return None

    try:
        r = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        script.log_failure(f"Dell TechDirect token request error: {exc}")
        return None

    if r.status_code != 200:
        script.log_failure(f"Dell TechDirect token request failed ({r.status_code}): {r.text}")
        return None

    token = r.json().get("access_token")
    if not token:
        script.log_failure(f"Dell TechDirect token response missing access_token: {r.text}")
        return None

    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _parse_dell_date(value: Optional[str]) -> Optional[date]:
    """Parse a Dell API date/datetime string (ISO8601, typically with a 'Z'
    suffix and no fractional seconds) into a date. Tolerant of a few variants.
    """
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    # Last resort: fromisoformat handles offsets like +00:00
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _fetch_entitlements_batch(
    service_tags: list[str],
    headers: dict,
    script: Script,
) -> list[dict]:
    """Call the Asset Entitlement API for a batch of service tags.

    Handles the response defensively since Dell's exact envelope can vary by
    API version/account: a bare JSON array is the common case, but a wrapped
    object is tolerated too.
    """
    url = ENTITLEMENT_API_URL.format(service_tags=",".join(service_tags))
    script.log_info(f"Dell entitlement API request: {url}")
    try:
        r = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        script.log_warning(f"Dell entitlement API request error: {exc}")
        return []

    if r.status_code != 200:
        script.log_warning(f"Dell entitlement API error ({r.status_code}): {r.text[:300]}")
        return []

    try:
        data = r.json()
    except ValueError:
        script.log_warning("Dell entitlement API returned non-JSON response.")
        return []

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("assetEntitlementResponses", "entitlements", "data", "results"):
            if isinstance(data.get(key), list):
                return data[key]
    script.log_warning(
        "Dell entitlement API response shape not recognized — expected a JSON "
        "array or a wrapped list. Enable 'Log Raw API Response' to inspect it."
    )
    return []


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_or_create_vendor() -> ContractVendor:
    vendor, _ = ContractVendor.objects.get_or_create(name=DELL_VENDOR_NAME)
    return vendor


def _infer_contract_type(service_level_desc: str) -> str:
    """
    Classify a Dell service level description as a base hardware warranty
    ('warranty') or a purchased support plan ('support-alc'). Only used when
    creating a brand-new SKU/Contract — reconciled/existing rows keep whatever
    contract_type they already have.
    """
    lowered = (service_level_desc or "").lower()
    if any(hint in lowered for hint in WARRANTY_LEVEL_HINTS):
        return WARRANTY_CONTRACT_TYPE
    return DEFAULT_SUPPORT_CONTRACT_TYPE


def _resolve_sku(
    service_level_desc: str,
    dell_manufacturer: Manufacturer,
    do_commit: bool,
    script: Script,
) -> ContractSKU:
    """
    Resolve a ContractSKU for a Dell service level, reconciling with any
    pre-existing manually-created SKU first (case-insensitive match on `sku`
    or `description`) before creating a new normalized one. Reconciling avoids
    spawning a duplicate "ProSupport Plus"-equivalent SKU next to one a human
    already created.
    """
    level_desc = (service_level_desc or "Unknown").strip()

    existing = (
        ContractSKU.objects
        .filter(manufacturer=dell_manufacturer)
        .filter(
            Q(sku__iexact=level_desc)
            | Q(description__iexact=level_desc)
            | Q(description__iexact=f"Dell {level_desc}")
        )
        .first()
    )
    if existing:
        return existing

    sku_id = level_desc.upper().replace(" ", "_").replace("-", "_")[:64]
    contract_type = _infer_contract_type(level_desc)

    if not do_commit:
        return ContractSKU.objects.filter(sku=sku_id).first() or ContractSKU(
            sku=sku_id,
            manufacturer=dell_manufacturer,
            contract_type=contract_type,
            service_level=level_desc[:64],
            description=f"Dell {level_desc}",
        )

    sku, created = ContractSKU.objects.get_or_create(
        sku=sku_id,
        defaults={
            "manufacturer": dell_manufacturer,
            "contract_type": contract_type,
            "service_level": level_desc[:64],
            "description": f"Dell {level_desc}",
        },
    )
    if created:
        script.log_success(f"Created ContractSKU: {sku_id} (type={contract_type})")
    return sku


def _resolve_contract(
    sku: ContractSKU,
    vendor: ContractVendor,
    coverage_end: Optional[date],
    do_commit: bool,
    script: Script,
) -> Contract:
    """
    Resolve a Contract for a resolved ContractSKU. Dell has no durable
    contract-number equivalent to Cisco's SNTC number, so coverage is grouped
    per service-level type: reconcile via any existing ContractAssignment
    already using this SKU (picks up e.g. the manually-created "VEP
    ProSupport" contract), otherwise get-or-create a new Contract keyed
    deterministically off the SKU. contract_type always matches sku.contract_type
    so ContractAssignment.clean()'s cross-check never fails.
    """
    # An unsaved sku stub (dry-run preview of a brand-new SKU) can't be used in
    # a related filter — there's nothing to reconcile against yet either way.
    existing_assignment = None
    if sku.pk:
        existing_assignment = (
            ContractAssignment.objects
            .filter(sku=sku, contract__vendor=vendor)
            .select_related("contract")
            .exclude(contract__isnull=True)
            .first()
        )
    if existing_assignment:
        contract = existing_assignment.contract
        if coverage_end and (not contract.end_date or coverage_end > contract.end_date):
            if do_commit:
                contract.end_date = coverage_end
                contract.save(update_fields=["end_date"])
        return contract

    contract_id = f"DELL-{sku.sku}"[:64]
    default_start = date.today() - timedelta(days=1)
    default_end = coverage_end or date.today()

    if not do_commit:
        return Contract.objects.filter(contract_id=contract_id).first() or Contract(
            contract_id=contract_id,
            contract_type=sku.contract_type,
            vendor=vendor,
            status="active",
            description=f"Dell {sku.service_level or sku.sku} coverage",
            start_date=default_start,
            end_date=default_end,
        )

    contract, created = Contract.objects.get_or_create(
        contract_id=contract_id,
        defaults={
            "contract_type": sku.contract_type,
            "vendor": vendor,
            "status": "active",
            "description": f"Dell {sku.service_level or sku.sku} coverage",
            "start_date": default_start,
            "end_date": default_end,
        },
    )
    if created:
        script.log_success(
            f"Created contract: {contract_id} (type={sku.contract_type}, end={default_end})"
        )
    return contract


def _get_or_create_warranty_type(
    code: str,
    dell_manufacturer: Manufacturer,
    do_commit: bool,
    script: Script,
) -> Optional[WarrantyType]:
    """
    Resolve a Dell serviceLevelCode (e.g. "ND", "PS") to a WarrantyType
    catalog row, creating one if needed — same get-or-create pattern used by
    cisco_coverage_sync.py for Cisco warranty codes.
    """
    if not code:
        return None

    if not do_commit:
        return WarrantyType.objects.filter(sku=code).first() or WarrantyType(
            sku=code, name=code, manufacturer=dell_manufacturer,
        )

    warranty_type, created = WarrantyType.objects.get_or_create(
        sku=code,
        defaults={"name": code, "manufacturer": dell_manufacturer},
    )
    if created:
        script.log_success(f"Created warranty type: {code}")
    return warranty_type


def _update_warranty_fields(
    asset: Asset,
    ship_date: Optional[date],
    warranty_end: Optional[date],
    warranty_code: str,
    dell_manufacturer: Manufacturer,
    do_commit: bool,
    script: Script,
) -> bool:
    """
    Update vendor_ship_date (if not already set), warranty_end, warranty_type,
    and (when vendor_ship_date precedes warranty_end) warranty_start. Returns
    True if any field changed.
    """
    update_fields = []

    if ship_date and not asset.vendor_ship_date:
        asset.vendor_ship_date = ship_date
        update_fields.append("vendor_ship_date")

    if warranty_end and asset.warranty_end != warranty_end:
        asset.warranty_end = warranty_end
        update_fields.append("warranty_end")

    code = (warranty_code or "").strip()
    current_code = asset.warranty_type.sku if asset.warranty_type_id else None
    if code and code != current_code:
        warranty_type = _get_or_create_warranty_type(code, dell_manufacturer, do_commit, script)
        if warranty_type is not None:
            asset.warranty_type = warranty_type
            update_fields.append("warranty_type")

    if warranty_end and asset.vendor_ship_date and asset.vendor_ship_date < warranty_end:
        if asset.warranty_start != asset.vendor_ship_date:
            asset.warranty_start = asset.vendor_ship_date
            update_fields.append("warranty_start")

    if not update_fields:
        return False

    if do_commit:
        asset.save(update_fields=update_fields)

    script.log_info(
        f"{'[DRY RUN] Would update' if not do_commit else 'Updated'} "
        f"warranty on asset={asset.pk} '{asset}': "
        f"end={warranty_end}"
        + (f" type={code}" if "warranty_type" in update_fields else "")
        + (f" ship_date={ship_date}" if "vendor_ship_date" in update_fields else "")
        + (f" start={asset.warranty_start}" if "warranty_start" in update_fields else "")
    )
    return True


def _get_hardware_lifecycle(asset: Asset) -> Optional[HardwareLifecycle]:
    """
    Return the HardwareLifecycle record for the asset's device_type, if any.
    HardwareLifecycle uses a generic FK, so we must look up via ContentType.
    """
    if not asset.device_type_id:
        return None

    device_type_ct = ContentType.objects.get_for_model(DeviceType)
    return (
        HardwareLifecycle.objects
        .filter(
            assigned_object_type=device_type_ct,
            assigned_object_id=asset.device_type_id,
        )
        .first()
    )


def _update_support_state(
    asset: Asset,
    is_covered: bool,
    do_commit: bool,
    script: Script,
    vlog,
) -> bool:
    """
    Evaluate and update the asset's support state from HardwareLifecycle + coverage data.

    Priority:
      1. HardwareLifecycle.end_of_support in the past
              Excluded / 'Past end of support'
      2. is_covered = True (active Dell support contract)
              Covered / 'Covered by contract'
      3. is_covered = False but active warranty on asset
              Covered / 'Covered by warranty'
      4. is_covered = False, no warranty
              Uncovered / 'Contract missing'

    Always writes support_validated_at when a determination is made.
    Returns True if any field was changed.
    """
    today = date.today()

    lifecycle = _get_hardware_lifecycle(asset)
    past_eox = (
        lifecycle is not None
        and lifecycle.end_of_support is not None
        and lifecycle.end_of_support < today
    )

    if past_eox:
        desired_state = SUPPORT_STATE_EXCLUDED
        desired_reason = SUPPORT_REASON_EOX
    elif is_covered:
        desired_state = SUPPORT_STATE_COVERED
        desired_reason = SUPPORT_REASON_COVERED_CONTRACT
    else:
        has_active_warranty = (
            asset.warranty_end is not None
            and asset.warranty_end >= today
            and (asset.warranty_start is None or asset.warranty_start <= today)
        )
        if has_active_warranty:
            desired_state = SUPPORT_STATE_COVERED
            desired_reason = SUPPORT_REASON_COVERED_WARRANTY
        else:
            desired_state = SUPPORT_STATE_UNCOVERED
            desired_reason = SUPPORT_REASON_NO_CONTRACT

    changed_fields = []

    if asset.support_state != desired_state:
        asset.support_state = desired_state
        changed_fields.append("support_state")

    if getattr(asset, "support_reason", None) != desired_reason:
        asset.support_reason = desired_reason
        changed_fields.append("support_reason")

    if getattr(asset, "support_source", None) != SUPPORT_SOURCE_COMPUTED:
        asset.support_source = SUPPORT_SOURCE_COMPUTED
        changed_fields.append("support_source")

    asset.support_validated_at = today
    changed_fields.append("support_validated_at")

    if do_commit and changed_fields:
        asset.save(update_fields=changed_fields)

    eox_detail = f" (EoX end_of_support={lifecycle.end_of_support})" if past_eox else ""
    vlog(
        f"[SUPPORT_STATE] asset={asset.pk} '{asset}' "
        f"{'[DRY RUN] Would set' if not do_commit else 'Set'} "
        f"state={desired_state} reason='{desired_reason}'{eox_detail}"
    )
    return bool(changed_fields)


def _upsert_contract_assignment(
    asset: Asset,
    contract: Contract,
    sku: ContractSKU,
    start_date: Optional[date],
    end_date: Optional[date],
    do_commit: bool,
    script: Script,
) -> tuple[bool, str]:
    """
    Create a ContractAssignment for asset+contract+sku if missing, or update
    its start/end dates in place if they've changed. Unlike Cisco's
    create-only helper, Dell coverage needs ongoing reconciliation against
    pre-existing manually-entered rows, so existing assignments are kept current
    on rerun rather than left stale once created.
    Returns (changed, reason_string).
    """
    existing = ContractAssignment.objects.filter(asset=asset, sku=sku, contract=contract).first()

    if existing:
        changed_fields = []
        if end_date and existing.end_date != end_date:
            existing.end_date = end_date
            changed_fields.append("end_date")
        if start_date and not existing.start_date:
            existing.start_date = start_date
            changed_fields.append("start_date")

        if not changed_fields:
            return False, "unchanged"

        try:
            existing.full_clean()
        except ValidationError as exc:
            return False, f"validation_error: {exc}"

        if do_commit:
            existing.save(update_fields=changed_fields)
        return True, "updated"

    assignment = ContractAssignment(
        asset=asset,
        contract=contract,
        sku=sku,
        start_date=start_date or contract.start_date,
        end_date=end_date or contract.end_date,
    )

    try:
        assignment.full_clean()
    except ValidationError as exc:
        return False, f"validation_error: {exc}"

    if do_commit:
        assignment.save()

    return True, "created"


# ---------------------------------------------------------------------------
# Main Script
# ---------------------------------------------------------------------------

class SyncDellWarrantyStatus(Script):
    class Meta:
        name = "Coverage: Sync Dell warranty / service contract status from Dell API"
        description = (
            "Queries the Dell TechDirect Asset Entitlement API to determine per-serial "
            "warranty/support coverage, then creates/updates Contract / ContractSKU / "
            "ContractAssignment records grouped by service-level type. Updates asset "
            "warranty fields and support state from coverage results and "
            "HardwareLifecycle (EoX) records. Uncovered assets in active use are reported."
        )

    # --- Core options -------------------------------------------------------

    dry_run = BooleanVar(
        default=False,
        label="Dry Run",
        description="Preview changes without writing to the database.",
    )

    # --- Scope filters ------------------------------------------------------

    site_filter = MultiObjectVar(
        model=Site,
        required=False,
        label="Sites",
        description=(
            "Limit sync to assets whose assigned device is in one of these sites. "
            "Leave blank to process all sites. Note: assets not yet assigned to a "
            "device will be excluded when a site filter is active."
        ),
    )

    asset_filter = MultiObjectVar(
        model=Asset,
        required=False,
        label="Assets",
        description=(
            "Limit sync to these specific assets. "
            "Leave blank to process all assets (subject to other active filters)."
        ),
        query_params={
            'manufacturer_name': DELL_MANUFACTURER_NAME,
        },
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
        description=(
            "Limit sync to assets of these device types. "
            "Leave blank to process all Dell device types."
        ),
    )

    purchase_filter = MultiObjectVar(
        model=Purchase,
        required=False,
        label="Purchases",
        description="Limit sync to all Dell assets that belong to one of these purchases.",
    )

    order_filter = MultiObjectVar(
        model=Order,
        required=False,
        label="Orders",
        description="Limit sync to all Dell assets that belong to one of these orders.",
    )

    # --- Coverage options ---------------------------------------------------

    skip_covered = BooleanVar(
        default=True,
        label="Skip Already-Covered Assets",
        description=(
            "Skip assets that already have at least one active ContractAssignment. "
            "Disable to re-validate all assets against the API."
        ),
    )

    # --- Support status options ---------------------------------------------

    update_support_status = BooleanVar(
        default=True,
        label="Update Support Status",
        description=(
            "Update asset support_state, support_reason, and support_validated_at "
            "based on HardwareLifecycle (EoX) records and API coverage results."
        ),
    )

    validated_at_threshold = IntegerVar(
        default=0,
        required=False,
        label="Skip if Validated Within (days)",
        description=(
            "Skip assets whose support_validated_at is within this many days of today. "
            "Set to 0 to process all assets regardless of last validation date."
        ),
    )

    # --- Logging options ----------------------------------------------------

    verbose = BooleanVar(
        default=False,
        label="Verbose Logging",
        description="Emit per-asset log lines (can be noisy for large inventories).",
    )

    log_api_response = BooleanVar(
        default=False,
        label="Log Raw API Response",
        description=(
            "Log the raw JSON response from the Dell entitlement API for each batch. "
            "Very noisy — intended for confirming the response shape/field names "
            "against your TechDirect account before trusting a full live sync."
        ),
    )

    log_limit = IntegerVar(
        default=500,
        label="Verbose Log Limit",
        description="Maximum per-asset log lines when verbose or log_api_response is enabled.",
    )

    asset_limit = IntegerVar(
        default=0,
        required=False,
        label="Asset Limit",
        description="Process only the first N assets (0 = no limit). Useful for test runs.",
    )

    # -----------------------------------------------------------------------

    @transaction.atomic
    def run(self, data, commit):
        do_commit = bool(commit) and not data["dry_run"]
        verbose = bool(data.get("verbose", False))
        log_api_response = bool(data.get("log_api_response", False))
        log_limit = int(data.get("log_limit", 500))
        logged = 0

        def vlog(msg: str) -> None:
            nonlocal logged
            if not (verbose or log_api_response) or logged >= log_limit:
                return
            self.log_info(msg)
            logged += 1

        # ------------------------------------------------------------------
        # Resolve Dell manufacturer
        # ------------------------------------------------------------------
        try:
            dell_manufacturer = Manufacturer.objects.get(name__iexact=DELL_MANUFACTURER_NAME)
        except Manufacturer.DoesNotExist:
            self.log_failure(
                f'Manufacturer "{DELL_MANUFACTURER_NAME}" not found in NetBox. '
                "Create it first under Devices → Manufacturers."
            )
            return

        # ------------------------------------------------------------------
        # Authenticate
        # ------------------------------------------------------------------
        headers = _get_auth_headers(self)
        if not headers:
            return

        # ------------------------------------------------------------------
        # Build base asset queryset
        # ------------------------------------------------------------------
        asset_qs = (
            Asset.objects
            .select_related("device_type__manufacturer", "device__site", "warranty_type")
            .filter(device_type__manufacturer=dell_manufacturer)
            .exclude(serial__isnull=True)
            .exclude(serial__exact="")
        )

        selected_sites = data.get("site_filter")
        if selected_sites:
            asset_qs = asset_qs.filter(device__site__in=selected_sites)
            self.log_info(f"Site filter active — limiting to: {', '.join(s.name for s in selected_sites)}")
        else:
            self.log_info("No site filter — processing all sites.")

        selected_assets = data.get("asset_filter")
        if selected_assets:
            asset_qs = asset_qs.filter(pk__in=[a.pk for a in selected_assets])
            self.log_info(f"Asset filter active — limiting to {selected_assets.count()} specific asset(s).")

        selected_device_types = data.get("device_type_filter")
        if selected_device_types:
            asset_qs = asset_qs.filter(device_type__in=selected_device_types)
            self.log_info(f"Device type filter active — limiting to: {', '.join(dt.model for dt in selected_device_types)}")

        selected_purchases = data.get("purchase_filter")
        if selected_purchases:
            asset_qs = asset_qs.filter(purchase__in=selected_purchases)
            self.log_info(f"Purchase filter active — limiting to: {', '.join(str(p) for p in selected_purchases)}")

        selected_orders = data.get("order_filter")
        if selected_orders:
            asset_qs = asset_qs.filter(order__in=selected_orders)
            self.log_info(f"Order filter active — limiting to: {', '.join(str(o) for o in selected_orders)}")

        selected_tags = data.get("tag_filter")
        if selected_tags:
            asset_qs = asset_qs.filter(tags__in=selected_tags).distinct()
            self.log_info(f"Tag filter active — limiting to: {', '.join(t.name for t in selected_tags)}")

        all_assets = list(asset_qs)
        total = len(all_assets)
        self.log_info(f"Found {total} Dell assets with serial numbers.")

        if selected_assets:
            requested_pks = {a.pk for a in selected_assets}
            returned_pks = {a.pk for a in all_assets}
            dropped = requested_pks - returned_pks
            if dropped:
                self.log_warning(
                    f"{len(dropped)} selected asset(s) excluded — not Dell, no serial, "
                    "or filtered out by another active filter."
                )

        # ------------------------------------------------------------------
        # Skip already-covered assets
        # ------------------------------------------------------------------
        if data.get("skip_covered"):
            today = date.today()
            covered_pks = set(
                ContractAssignment.objects
                .filter(asset__in=all_assets, start_date__lte=today, end_date__gte=today)
                .values_list("asset_id", flat=True)
            )
            unchecked = [a for a in all_assets if a.pk not in covered_pks]
            self.log_info(
                f"{len(covered_pks)} already have active coverage — skipping. "
                f"Checking {len(unchecked)} assets against the API."
            )
            all_assets = unchecked

        # ------------------------------------------------------------------
        # Validated-at threshold filter
        # ------------------------------------------------------------------
        threshold_days = int(data.get("validated_at_threshold") or 0)
        if threshold_days > 0:
            cutoff = date.today() - timedelta(days=threshold_days)
            before_count = len(all_assets)
            all_assets = [
                a for a in all_assets
                if not getattr(a, "support_validated_at", None) or a.support_validated_at < cutoff
            ]
            self.log_info(
                f"Validated-at threshold: {threshold_days} days (cutoff={cutoff}). "
                f"Skipping {before_count - len(all_assets)} asset(s) validated recently — "
                f"{len(all_assets)} remaining."
            )

        if not all_assets:
            self.log_info("Nothing to sync.")
            return

        asset_limit = int(data.get("asset_limit") or 0)
        if asset_limit > 0:
            all_assets = all_assets[:asset_limit]
            self.log_info(f"Asset limit active — processing first {len(all_assets)} asset(s).")

        # ------------------------------------------------------------------
        # Build serial → asset map (handles duplicate serials)
        # ------------------------------------------------------------------
        serial_to_assets: dict[str, list[Asset]] = {}
        for asset in all_assets:
            sn = (asset.serial or "").strip().upper()
            if sn:
                serial_to_assets.setdefault(sn, []).append(asset)

        all_serials = list(serial_to_assets.keys())
        num_batches = math.ceil(len(all_serials) / ENTITLEMENT_BATCH_SIZE)
        self.log_info(
            f"Querying Dell entitlement API in {num_batches} batch(es) "
            f"({ENTITLEMENT_BATCH_SIZE} service tags each)..."
        )

        vendor = _get_or_create_vendor()

        stats = {
            "covered_api": 0,
            "uncovered_api": 0,
            "assignment_created": 0,
            "assignment_updated": 0,
            "assignment_unchanged": 0,
            "warranty_updated": 0,
            "support_state_updated": 0,
            "api_errors": 0,
            "validation_errors": 0,
        }

        uncovered_assets_in_use: list[Asset] = []

        # ------------------------------------------------------------------
        # Batch API calls
        # ------------------------------------------------------------------
        for batch_start in range(0, len(all_serials), ENTITLEMENT_BATCH_SIZE):
            batch = all_serials[batch_start: batch_start + ENTITLEMENT_BATCH_SIZE]
            batch_num = batch_start // ENTITLEMENT_BATCH_SIZE + 1
            records = _fetch_entitlements_batch(batch, headers, self)

            if log_api_response:
                if records:
                    vlog(
                        f"[API_RESPONSE] Batch {batch_num} ({len(batch)} service tags):\n"
                        + json.dumps(records, indent=2, default=str)
                    )
                else:
                    vlog(f"[API_RESPONSE] Batch {batch_num} — empty or error response.")

            if not records:
                stats["api_errors"] += 1
                self.log_warning(f"Batch {batch_num}: no records returned for {len(batch)} service tags.")
                continue

            api_by_serial: dict[str, dict] = {
                (rec.get("serviceTag") or "").strip().upper(): rec
                for rec in records
                if (rec.get("serviceTag") or "").strip()
            }

            today_date = date.today()

            for sn in batch:
                rec = api_by_serial.get(sn)
                assets_for_sn = serial_to_assets.get(sn, [])

                if rec is None:
                    vlog(f"[NO_DATA] service_tag={sn} — not in API response")
                    stats["uncovered_api"] += len(assets_for_sn)
                    for a in assets_for_sn:
                        if a.status == "used":
                            uncovered_assets_in_use.append(a)
                        if data.get("update_support_status"):
                            if _update_support_state(a, is_covered=False, do_commit=do_commit, script=self, vlog=vlog):
                                stats["support_state_updated"] += 1
                    continue

                if rec.get("invalid"):
                    vlog(f"[INVALID] service_tag={sn} — Dell reports this service tag as invalid")
                    stats["uncovered_api"] += len(assets_for_sn)
                    for a in assets_for_sn:
                        if a.status == "used":
                            uncovered_assets_in_use.append(a)
                        if data.get("update_support_status"):
                            if _update_support_state(a, is_covered=False, do_commit=do_commit, script=self, vlog=vlog):
                                stats["support_state_updated"] += 1
                    continue

                ship_date = _parse_dell_date(rec.get("shipDate"))
                entitlements = rec.get("entitlements") or []

                parsed_entitlements = []
                for ent in entitlements:
                    end = _parse_dell_date(ent.get("endDate"))
                    if end is None:
                        continue
                    parsed_entitlements.append({
                        "start": _parse_dell_date(ent.get("startDate")),
                        "end": end,
                        "code": (ent.get("serviceLevelCode") or "").strip(),
                        "desc": (ent.get("serviceLevelDescription") or "Unknown").strip(),
                    })

                if not parsed_entitlements:
                    vlog(f"[NO_ENTITLEMENTS] service_tag={sn} — no usable entitlement records")
                    stats["uncovered_api"] += len(assets_for_sn)
                    for a in assets_for_sn:
                        if _update_warranty_fields(a, ship_date, None, "", dell_manufacturer, do_commit, self):
                            stats["warranty_updated"] += 1
                        if a.status == "used":
                            uncovered_assets_in_use.append(a)
                        if data.get("update_support_status"):
                            if _update_support_state(a, is_covered=False, do_commit=do_commit, script=self, vlog=vlog):
                                stats["support_state_updated"] += 1
                    continue

                # Current coverage = the entitlement with the furthest-out end date
                # (an extended/upgraded support plan supersedes the base warranty).
                current = max(parsed_entitlements, key=lambda e: e["end"])
                coverage_end = current["end"]
                is_covered = coverage_end >= today_date

                vlog(
                    f"[{'COVERED' if is_covered else 'EXPIRED'}] service_tag={sn} "
                    f"level='{current['desc']}' end={coverage_end}"
                )

                if is_covered:
                    stats["covered_api"] += len(assets_for_sn)
                else:
                    stats["uncovered_api"] += len(assets_for_sn)

                sku = _resolve_sku(current["desc"], dell_manufacturer, do_commit, self)
                contract = _resolve_contract(sku, vendor, coverage_end, do_commit, self) if is_covered else None

                for asset in assets_for_sn:
                    if _update_warranty_fields(
                        asset, ship_date, coverage_end, current["code"], dell_manufacturer, do_commit, self,
                    ):
                        stats["warranty_updated"] += 1

                    has_active_warranty = (
                        asset.warranty_end is not None
                        and asset.warranty_end >= today_date
                        and (asset.warranty_start is None or asset.warranty_start <= today_date)
                    )
                    if asset.status == "used" and not is_covered and not has_active_warranty:
                        uncovered_assets_in_use.append(asset)

                    if data.get("update_support_status"):
                        if _update_support_state(asset, is_covered=is_covered, do_commit=do_commit, script=self, vlog=vlog):
                            stats["support_state_updated"] += 1

                    if not is_covered or contract is None:
                        continue

                    changed, reason = _upsert_contract_assignment(
                        asset, contract, sku, current["start"], coverage_end, do_commit, self,
                    )

                    if reason == "created":
                        stats["assignment_created"] += 1
                    elif reason == "updated":
                        stats["assignment_updated"] += 1
                    elif reason == "unchanged":
                        stats["assignment_unchanged"] += 1
                    elif reason.startswith("validation_error"):
                        stats["validation_errors"] += 1
                        self.log_warning(f"asset={asset.pk} '{asset}': {reason}")

                    vlog(
                        f"[{'DRY_RUN' if not do_commit else 'LIVE'}] "
                        f"service_tag={sn} asset={asset.pk} '{asset}' "
                        f"contract={contract.contract_id} sku={sku.sku} "
                        f"end={coverage_end} — {reason}"
                    )

        # ------------------------------------------------------------------
        # Report uncovered assets in active use
        # ------------------------------------------------------------------
        if uncovered_assets_in_use:
            self.log_warning(
                f"\n{'='*60}\n"
                f"UNCOVERED ASSETS IN ACTIVE USE ({len(uncovered_assets_in_use)})\n"
                f"These devices have status='used' but Dell reports NO active coverage.\n"
                f"{'='*60}"
            )
            for asset in uncovered_assets_in_use:
                device_info = ""
                if asset.device_id:
                    device_info = f" | device={asset.device}"
                elif asset.device_type_id:
                    device_info = f" | type={asset.device_type}"
                self.log_warning(f"  UNCOVERED — serial={asset.serial} asset={asset.pk} '{asset}'{device_info}")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        self.log_info(
            f"\n{'='*60}\n"
            f"SYNC COMPLETE {'(DRY RUN — no changes written)' if not do_commit else ''}\n"
            f"  Dell assets checked      : {len(all_assets)}\n"
            f"  Covered (API)            : {stats['covered_api']}\n"
            f"  Uncovered (API)          : {stats['uncovered_api']}\n"
            f"  Assignments created      : {stats['assignment_created']}\n"
            f"  Assignments updated      : {stats['assignment_updated']}\n"
            f"  Assignments unchanged    : {stats['assignment_unchanged']}\n"
            f"  Warranty fields updated  : {stats['warranty_updated']}\n"
            f"  Support states updated   : {stats['support_state_updated']}\n"
            f"  Validation errors        : {stats['validation_errors']}\n"
            f"  API batch errors         : {stats['api_errors']}\n"
            f"  Uncovered + in-use       : {len(uncovered_assets_in_use)}\n"
            f"{'='*60}"
        )

        if (verbose or log_api_response) and logged >= log_limit:
            self.log_info(f"Verbose log limit reached ({log_limit}). Increase 'Verbose Log Limit' to see more.")
