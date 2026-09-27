
"""
Cisco Coverage Sync  NetBox Script

Queries the Cisco Support API Coverage Summary endpoint for every Cisco asset
that has a serial number, then creates/updates ContractAssignment records so
that NetBox reflects the current coverage state.

How it fits the data model
--------------------------
  ContractVendor       "Cisco Systems" (created if missing)
  ContractSKU          keyed on Cisco service_line_descr (e.g. "Solution Support")
  Contract             keyed on service_contract_number from the API
  ContractAssignment   per-asset link; auto-sets VendorProgram via clean()
  AssetProgramCoverage activated by signal when ContractAssignment is saved
  Asset.support_state  updated directly by this script based on coverage + EoX

EA program linkage
------------------
If a contract is typed as "support-ea" (either by matching the ea_contract_ids
parameter or because it already exists in NetBox as that type), ContractAssignment
.clean() will auto-resolve the VendorProgram (e.g. "Cisco Enterprise Agreement"),
and the post_save signal will flip AssetProgramCoverage to ACTIVE.

EoX / HardwareLifecycle
------------------------
If a HardwareLifecycle record exists for the asset's device_type and its
end_of_support date is in the past, the asset is marked Uncovered with reason
"Past end of support" regardless of contract coverage. This takes priority over
the contract-based uncovered reason "Contract missing".

CX Cloud API fallback
----------------------
When the Coverage Summary API reports a device as covered but returns no
contract number (often because the device is not associated with our Cisco
account), the script can optionally query the CX Cloud API for contract
details. Configure cisco_cx_api_customer_id and CX client credentials in
PLUGINS_CONFIG or pass the cx_customer_id script parameter. If the CX API
returns a contract, the asset is processed normally; otherwise it is tagged
for manual review.

Prerequisites
-------------
  PLUGINS_CONFIG["netbox_inventory"]["cisco_support_api_client_id"]
  PLUGINS_CONFIG["netbox_inventory"]["cisco_support_api_client_secret"]
  PLUGINS_CONFIG["netbox_inventory"]["cisco_cx_api_client_id"] (optional, for CX fallback)
  PLUGINS_CONFIG["netbox_inventory"]["cisco_cx_api_client_secret"] (optional, for CX fallback)
  PLUGINS_CONFIG["netbox_inventory"]["cisco_cx_api_customer_id"] (optional, for CX fallback)

Script parameters (all optional)
---------------------------------
  dry_run                 do not write to DB (default False)
  ea_contract_ids         comma-separated contract numbers to treat as EA
  cx_customer_id          CX Cloud Customer ID for secondary coverage lookups
  tag_filter              limit to assets with selected tag(s)
  skip_covered            skip assets that already have an active ContractAssignment
  site_filter             limit to assets whose device is in selected sites
  asset_filter            limit to specific assets
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

from dcim.models import DeviceType, Manufacturer, Site
from extras.models import Tag
from extras.scripts import (
    BooleanVar,
    IntegerVar,
    MultiObjectVar,
    Script,
    StringVar,
)

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

CISCO_MANUFACTURER_NAME = "Cisco"
CISCO_VENDOR_NAME = "Cisco Systems"

# Cisco Coverage Summary API  accepts up to 75 serial numbers per request
COVERAGE_API_URL = (
    "https://apix.cisco.com/sn2info/v2/coverage/summary/serial_numbers/{serial_numbers}"
)
COVERAGE_BATCH_SIZE = 50

TOKEN_URL = "https://id.cisco.com/oauth2/default/v1/token"

# CX Cloud API — secondary lookup when Coverage Summary reports covered
# but returns no contract details. Uses separate client_id/client_secret.
CX_COVERAGE_API_URL = "https://apix.cisco.com/cs/api/v2/contracts/coverage"

# Support state values
SUPPORT_STATE_COVERED = "covered"
SUPPORT_STATE_UNCOVERED = "uncovered"
SUPPORT_STATE_EXCLUDED = "excluded"
SUPPORT_REASON_EOX = "past_end_of_support"
SUPPORT_REASON_NO_CONTRACT = "contract_missing"
SUPPORT_REASON_COVERED_CONTRACT = "covered_contract"
SUPPORT_REASON_COVERED_WARRANTY = "covered_warranty"
SUPPORT_SOURCE_COMPUTED = "computed"

# Tag applied when Cisco reports a device as covered but returns no contract number.
# This typically means the device is not associated with our Cisco account.
CISCO_NO_CONTRACT_TAG_NAME = "Asset > Review Cisco Customer Association"
CISCO_NO_CONTRACT_TAG_SLUG = "asset-review-cisco-customer-association"

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _get_auth_headers(script: Script, api: str = "support") -> Optional[dict]:
    """Return OAuth2 headers for Cisco APIs.

    api:
      - "support": Cisco Support APIs (Coverage Summary)
      - "cx": Cisco CX Cloud API (secondary coverage lookup)

    Credentials are read from PLUGINS_CONFIG["netbox_inventory"].
    """
    cfg = settings.PLUGINS_CONFIG.get("netbox_inventory", {}) or {}

    if api == "cx":
        client_id = (cfg.get("cisco_cx_api_client_id") or "").strip()
        client_secret = (cfg.get("cisco_cx_api_client_secret") or "").strip()
        api_name = "Cisco CX Cloud"
    else:
        client_id = (cfg.get("cisco_support_api_client_id") or "").strip()
        client_secret = (cfg.get("cisco_support_api_client_secret") or "").strip()
        api_name = "Cisco Support"

    if not client_id or not client_secret:
        script.log_failure(
            f"{api_name} API credentials not configured. "
            "Set the appropriate client_id / client_secret in "
            "PLUGINS_CONFIG['netbox_inventory']."
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
        script.log_failure(f"{api_name} token request error: {exc}")
        return None

    if r.status_code != 200:
        script.log_failure(f"{api_name} token request failed ({r.status_code}): {r.text}")
        return None

    token = r.json().get("access_token")
    if not token:
        script.log_failure(f"{api_name} token response missing access_token: {r.text}")
        return None

    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}



# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _parse_date(value: str) -> Optional[date]:
    if not value or value.strip() in ("", "N/A", "null"):
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _fetch_coverage_batch(
    serial_numbers: list[str],
    headers: dict,
    script: Script,
) -> list[dict]:
    """Call the Coverage Summary API for up to 50 serials. Returns raw records."""
    url = COVERAGE_API_URL.format(serial_numbers=",".join(serial_numbers))
    script.log_info(f"Coverage API request: {url}")
    try:
        r = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        script.log_warning(f"Coverage API request error: {exc}")
        return []

    if r.status_code != 200:
        script.log_warning(f"Coverage API error ({r.status_code}): {r.text[:300]}")
        return []

    return r.json().get("serial_numbers", [])


def _fetch_cx_coverage(
    serial_number: str,
    customer_id: str,
    headers: dict,
    script: Script,
    session: Optional[requests.Session] = None,
) -> Optional[dict]:
    """Secondary lookup via the Cisco CX Cloud API for a single serial number.

    Called when the Coverage Summary API reports a device as covered but
    returns no contract number — some assets still have full contract
    details available through CX Cloud.

    Returns the first coverage record that contains a contract number,
    or None if no usable data is found.
    """
    params = {
        "customerId": customer_id,
        "serialNumber": serial_number,
        "coverageStatus": "ACTIVE",
    }

    s = session or requests
    try:
        r = s.get(CX_COVERAGE_API_URL, headers=headers, params=params, timeout=30)
    except requests.RequestException as exc:
        script.log_warning(f"CX API request error for {serial_number}: {exc}")
        return None

    if r.status_code != 200:
        script.log_warning(
            f"CX API error ({r.status_code}) for {serial_number}: {r.text[:300]}"
        )
        return None

    data = r.json().get("data", [])
    if not data:
        return None

    for rec in data:
        cn = (rec.get("contractNumber") or "").strip()
        if cn:
            return rec
    return None


def _fetch_cx_coverage_batch(
    serial_numbers: list[str],
    customer_id: str,
    headers: dict,
    script: Script,
    max_workers: int = 6,
) -> dict[str, Optional[dict]]:
    """Batch CX Cloud lookups for multiple serial numbers.

    The CX Cloud coverage endpoint is queried per-serial, but this helper
    groups lookups for a batch and reuses connections. For larger lists it
    uses a small thread pool to speed up processing.

    Returns a dict mapping SERIAL -> coverage record (or None).
    """
    serials: list[str] = []
    seen: set[str] = set()
    for sn in serial_numbers:
        snn = (sn or "").strip().upper()
        if snn and snn not in seen:
            seen.add(snn)
            serials.append(snn)

    if not serials:
        return {}

    results: dict[str, Optional[dict]] = {sn: None for sn in serials}
    session = requests.Session()

    def worker(sn: str) -> tuple[str, Optional[dict]]:
        return sn, _fetch_cx_coverage(sn, customer_id, headers, script, session=session)

    # Small lists: keep sequential (simpler + easier to debug)
    if len(serials) <= 3 or max_workers <= 1:
        for sn in serials:
            k, rec = worker(sn)
            results[k] = rec
        session.close()
        return results

    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(worker, sn): sn for sn in serials}
            for fut in as_completed(futs):
                sn, rec = fut.result()
                results[sn] = rec
    finally:
        session.close()

    return results


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_or_create_no_contract_tag(do_commit: bool, script: Script) -> Optional[Tag]:
    """
    Get or create the review tag for assets covered by Cisco but with no contract number.
    In dry-run mode the tag is not created; returns None if it doesn't exist yet.
    """
    try:
        return Tag.objects.get(slug=CISCO_NO_CONTRACT_TAG_SLUG)
    except Tag.DoesNotExist:
        if not do_commit:
            return None
        tag = Tag(
            name=CISCO_NO_CONTRACT_TAG_NAME,
            slug=CISCO_NO_CONTRACT_TAG_SLUG,
            color="f0ad4e",  # amber — flags for attention without implying failure
            description=(
                "Cisco API reports this device as covered but returned no contract number. "
                "Device is likely not associated with our Cisco account. Requires review."
            ),
        )
        tag.save()
        script.log_success(f"Created tag '{CISCO_NO_CONTRACT_TAG_NAME}'")
        return tag


def _get_or_create_vendor(cisco_manufacturer: Manufacturer) -> ContractVendor:
    vendor, _ = ContractVendor.objects.get_or_create(name=CISCO_VENDOR_NAME)
    return vendor


def _resolve_contract_type(contract_number: str, ea_ids: set[str]) -> str:
    """
    Determine contract_type for a contract_number:
      1. Preserve type if it already exists in the DB.
      2. EA override set  support-ea.
      3. Default  support-alc.
    """
    existing = Contract.objects.filter(contract_id=contract_number).first()
    if existing:
        return existing.contract_type
    if contract_number in ea_ids:
        return "support-ea"
    return "support-alc"


def _get_or_create_contract(
    contract_number: str,
    contract_type: str,
    vendor: ContractVendor,
    coverage_end_date: Optional[date],
    script: Script,
) -> Contract:
    """
    Get or create a Contract keyed on contract_number + vendor.

    start_date defaults to yesterday so the contract is immediately active.
    The real start date is unknown from the Coverage API; update manually if needed.

    end_date uses the API value when present; falls back to today as a safe
    sentinel so status logic never sees start_date <= today with end_date=None.
    The end_date is extended as we process assets with later coverage dates.
    """
    default_start = date.today() - timedelta(days=1)
    default_end = coverage_end_date or date.today()

    contract, created = Contract.objects.get_or_create(
        contract_id=contract_number,
        vendor=vendor,
        defaults={
            "contract_type": contract_type,
            "status": "active",
            "description": f"Cisco support contract {contract_number}",
            "start_date": default_start,
            "end_date": default_end,
        },
    )

    if created:
        script.log_success(
            f"Created contract: {contract_number} "
            f"(type={contract_type}, start={default_start}, end={default_end})"
        )
    elif coverage_end_date:
        if not contract.end_date or coverage_end_date > contract.end_date:
            contract.end_date = coverage_end_date
            contract.save(update_fields=["end_date"])

    return contract


def _get_or_create_sku(
    service_level: str,
    contract_type: str,
    cisco_manufacturer: Manufacturer,
) -> ContractSKU:
    """
    Get or create a ContractSKU for the Cisco service level description.
    The SKU identifier is normalised to uppercase + underscores for stability.
    """
    sku_id = service_level.upper().replace(" ", "_").replace("-", "_")[:64]
    sku, _ = ContractSKU.objects.get_or_create(
        sku=sku_id,
        defaults={
            "manufacturer": cisco_manufacturer,
            "contract_type": contract_type,
            "service_level": service_level[:64],
            "description": f"Cisco {service_level}",
        },
    )
    return sku


def _get_or_create_warranty_type(
    sku: str,
    cisco_manufacturer: Manufacturer,
    do_commit: bool,
    script: Script,
) -> Optional[WarrantyType]:
    """
    Resolve a Cisco warranty_type code (e.g. "WARR-1YR-LTD-HW") from the Coverage API
    to a WarrantyType catalog row, creating one if it doesn't exist yet — same
    get-or-create pattern used for Contract/ContractSKU below. Unlike the old
    choices-based field, unrecognized codes are no longer collapsed into an "other"
    bucket; they become new catalog entries instead.
    """
    if not do_commit:
        return WarrantyType.objects.filter(sku=sku).first() or WarrantyType(
            sku=sku, name=sku, manufacturer=cisco_manufacturer,
        )

    warranty_type, created = WarrantyType.objects.get_or_create(
        sku=sku,
        defaults={"name": sku, "manufacturer": cisco_manufacturer},
    )
    if created:
        script.log_success(f"Created warranty type: {sku}")
    return warranty_type


def _update_warranty_fields(
    asset: Asset,
    warranty_end: Optional[date],
    warranty_type_raw: str,
    cisco_manufacturer: Manufacturer,
    do_commit: bool,
    script: Script,
) -> bool:
    """
    Update warranty_end, warranty_type, and (when vendor_ship_date is set and precedes
    warranty_end) warranty_start on the asset.  warranty_type is a FK to the WarrantyType
    catalog model, resolved from the Cisco SKU code.  Returns True if any field changed.
    """
    if not warranty_end:
        return False

    sku = (warranty_type_raw or "").strip()
    current_sku = asset.warranty_type.sku if asset.warranty_type_id else None
    update_fields = []

    if asset.warranty_end != warranty_end:
        asset.warranty_end = warranty_end
        update_fields.append("warranty_end")

    if sku and sku != current_sku:
        warranty_type = _get_or_create_warranty_type(sku, cisco_manufacturer, do_commit, script)
        if warranty_type is not None:
            asset.warranty_type = warranty_type
            update_fields.append("warranty_type")

    if asset.vendor_ship_date and asset.vendor_ship_date < warranty_end:
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
        + (f" type={sku}" if "warranty_type" in update_fields else "")
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
      2. is_covered = True (active contract)
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
        desired_source = SUPPORT_SOURCE_COMPUTED
    elif is_covered:
        desired_state = SUPPORT_STATE_COVERED
        desired_reason = SUPPORT_REASON_COVERED_CONTRACT
        desired_source = SUPPORT_SOURCE_COMPUTED
    else:
        has_active_warranty = (
            asset.warranty_end is not None
            and asset.warranty_end >= today
            and (asset.warranty_start is None or asset.warranty_start <= today)
        )
        if has_active_warranty:
            desired_state = SUPPORT_STATE_COVERED
            desired_reason = SUPPORT_REASON_COVERED_WARRANTY
            desired_source = SUPPORT_SOURCE_COMPUTED
        else:
            desired_state = SUPPORT_STATE_UNCOVERED
            desired_reason = SUPPORT_REASON_NO_CONTRACT
            desired_source = SUPPORT_SOURCE_COMPUTED

    changed_fields = []

    if asset.support_state != desired_state:
        asset.support_state = desired_state
        changed_fields.append("support_state")

    # Adjust field name below if your model uses a different attribute
    if getattr(asset, "support_reason", None) != desired_reason:
        asset.support_reason = desired_reason
        changed_fields.append("support_reason")

    if getattr(asset, "support_source", None) != desired_source:
        asset.support_source = desired_source
        changed_fields.append("support_source")

    # Always stamp validated_at when we make a determination
    asset.support_validated_at = today
    changed_fields.append("support_validated_at")

    if do_commit and changed_fields:
        asset.save(update_fields=changed_fields)

    eox_detail = (
        f" (EoX end_of_support={lifecycle.end_of_support})" if past_eox else ""
    )
    vlog(
        f"[SUPPORT_STATE] asset={asset.pk} '{asset}' "
        f" {'[DRY RUN] Would set' if not do_commit else 'Set'} "
        f"state={desired_state} reason='{desired_reason}'{eox_detail}"
    )
    return bool(changed_fields)


def _create_assignment_if_missing(
    asset: Asset,
    contract: Contract,
    sku: ContractSKU,
    end_date: Optional[date],
    do_commit: bool,
    script: Script,
) -> tuple[bool, str]:
    """
    Create a ContractAssignment for the asset if one doesn't already exist
    for this asset + contract + sku combination.
    Returns (created, reason_string).
    """
    effective_end = end_date or contract.end_date
    effective_start = contract.start_date

    if ContractAssignment.objects.filter(asset=asset, sku=sku, contract=contract).exists():
        return False, "already_exists"

    assignment = ContractAssignment(
        asset=asset,
        contract=contract,
        sku=sku,
        start_date=effective_start,
        end_date=effective_end,
    )

    try:
        assignment.full_clean()
    except ValidationError as exc:
        return False, f"validation_error: {exc}"

    if do_commit:
        assignment.save()   # signals update support_state + AssetProgramCoverage

    return True, "created"


# ---------------------------------------------------------------------------
# Main Script
# ---------------------------------------------------------------------------

class SyncCiscoCoverageStatus(Script):
    class Meta:
        name = "Coverage: Sync Cisco support coverage from Cisco API"
        description = (
            "Queries the Cisco Support API to determine per-serial coverage status, "
            "then creates Contract / ContractSKU / ContractAssignment records for "
            "covered assets. Updates asset support state from coverage results and "
            "HardwareLifecycle (EoX) records. Uncovered assets in active use are reported."
        )

    # --- Core options -------------------------------------------------------

    dry_run = BooleanVar(
        default=False,
        label="Dry Run",
        description="Preview changes without writing to the database.",
    )

    ea_contract_ids = StringVar(
        required=False,
        label="EA Contract IDs",
        description=(
            "Comma-separated Cisco contract numbers to classify as Enterprise Agreement "
            "(support-ea). All other discovered contracts default to support-alc. "
            "Example: 94012345,94099876"
        ),
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
            'manufacturer_name': CISCO_MANUFACTURER_NAME,
        },
    )

    tag_filter = MultiObjectVar(
        model=Tag,
        required=False,
        label="Tags",
        description=(
            "Limit sync to assets that have one or more of the selected tag(s). "
            "Useful for reprocessing previously-flagged assets (e.g. review tags)."
        ),
    )

    device_type_filter = MultiObjectVar(
        model=DeviceType,
        required=False,
        label="Device Types",
        description=(
            "Limit sync to assets of these device types. "
            "Leave blank to process all Cisco device types."
        ),
    )

    purchase_filter = MultiObjectVar(
        model=Purchase,
        required=False,
        label="Purchases",
        description=(
            "Limit sync to all Cisco assets that belong to one of these purchases. "
            "Leave blank to process all purchases."
        ),
    )

    order_filter = MultiObjectVar(
        model=Order,
        required=False,
        label="Orders",
        description=(
            "Limit sync to all Cisco assets that belong to one of these orders. "
            "Leave blank to process all orders."
        ),
    )

    cx_customer_id = StringVar(
        required=False,
        label="CX Cloud Customer ID",
        description=(
            "Cisco CX Cloud Customer ID for secondary coverage lookups. "
            "When the Coverage Summary API reports a device as covered but "
            "returns no contract details, this ID is used to query the CX "
            "Cloud API for contract information. Overrides the "
            "cisco_cx_api_customer_id plugin config setting. Leave blank to "
            "use the config value, or to skip CX lookups entirely."
        ),
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
            "based on HardwareLifecycle (EoX) records and API coverage results. "
            "EoX past end-of-support takes priority over contract coverage state."
        ),
    )

    validated_at_threshold = IntegerVar(
        default=0,
        required=False,
        label="Skip if Validated Within (days)",
        description=(
            "Skip assets whose support_validated_at is within this many days of today. "
            "Set to 0 to process all assets regardless of last validation date. "
            "Example: 30 = only re-check assets not validated in the last 30 days."
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
            "Log the raw JSON response from the Cisco Coverage API for each batch. "
            "Very noisy  intended for debugging unexpected API results. "
            "Respects the Verbose Log Limit setting."
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

        # Parse EA contract ID overrides
        raw_ea = (data.get("ea_contract_ids") or "").strip()
        ea_ids: set[str] = {s.strip() for s in raw_ea.split(",") if s.strip()}
        if ea_ids:
            self.log_info(f"Treating these contract IDs as EA: {', '.join(sorted(ea_ids))}")

        # Resolve CX Cloud Customer ID for secondary lookups
        cx_customer_id = (data.get("cx_customer_id") or "").strip()
        if not cx_customer_id:
            cx_cfg = settings.PLUGINS_CONFIG.get("netbox_inventory", {}) or {}
            cx_customer_id = (cx_cfg.get("cisco_cx_api_customer_id") or "").strip()
        if cx_customer_id:
            self.log_info("CX Cloud Customer ID configured — secondary lookups enabled.")
        else:
            self.log_info("No CX Cloud Customer ID configured — CX Cloud secondary lookups disabled.")

        def vlog(msg: str) -> None:
            nonlocal logged
            if not (verbose or log_api_response) or logged >= log_limit:
                return
            self.log_info(msg)
            logged += 1

        # ------------------------------------------------------------------
        # Resolve Cisco manufacturer
        # ------------------------------------------------------------------
        try:
            cisco_manufacturer = Manufacturer.objects.get(name__iexact=CISCO_MANUFACTURER_NAME)
        except Manufacturer.DoesNotExist:
            self.log_failure(
                f'Manufacturer "{CISCO_MANUFACTURER_NAME}" not found in NetBox. '
                "Create it first under Devices  Manufacturers."
            )
            return

        # ------------------------------------------------------------------
        # Authenticate
        # ------------------------------------------------------------------
        support_headers = _get_auth_headers(self, api="support")
        if not support_headers:
            return

        cx_headers = None
        if cx_customer_id:
            cx_headers = _get_auth_headers(self, api="cx")
            if not cx_headers:
                self.log_warning("CX API auth failed — CX lookups will be skipped.")
                cx_customer_id = ""

        # ------------------------------------------------------------------
        # Build base asset queryset
        # ------------------------------------------------------------------
        asset_qs = (
            Asset.objects
            .select_related(
                "device_type__manufacturer",
                "module_type__manufacturer",
                "device__site",
            )
            .filter(device_type__manufacturer=cisco_manufacturer)
            .exclude(serial__isnull=True)
            .exclude(serial__exact="")
        )

        # Site filter
        selected_sites = data.get("site_filter")
        if selected_sites:
            asset_qs = asset_qs.filter(device__site__in=selected_sites)
            site_names = ", ".join(s.name for s in selected_sites)
            self.log_info(f"Site filter active  limiting to: {site_names}")
        else:
            self.log_info("No site filter  processing all sites.")

        # Asset filter
        selected_assets = data.get("asset_filter")
        if selected_assets:
            asset_qs = asset_qs.filter(pk__in=[a.pk for a in selected_assets])
            self.log_info(
                f"Asset filter active  limiting to {selected_assets.count()} specific asset(s)."
            )

        # Device type filter
        selected_device_types = data.get("device_type_filter")
        if selected_device_types:
            asset_qs = asset_qs.filter(device_type__in=selected_device_types)
            dt_names = ", ".join(dt.model for dt in selected_device_types)
            self.log_info(f"Device type filter active  limiting to: {dt_names}")

        # Purchase filter
        selected_purchases = data.get("purchase_filter")
        if selected_purchases:
            asset_qs = asset_qs.filter(purchase__in=selected_purchases)
            purchase_names = ", ".join(str(p) for p in selected_purchases)
            self.log_info(f"Purchase filter active  limiting to: {purchase_names}")

        # Order filter
        selected_orders = data.get("order_filter")
        if selected_orders:
            asset_qs = asset_qs.filter(order__in=selected_orders)
            order_names = ", ".join(str(o) for o in selected_orders)
            self.log_info(f"Order filter active  limiting to: {order_names}")

        # Tag filter
        selected_tags = data.get("tag_filter")
        if selected_tags:
            asset_qs = asset_qs.filter(tags__in=selected_tags).distinct()
            tag_names = ", ".join(t.name for t in selected_tags)
            self.log_info(f"Tag filter active limiting to: {tag_names}")

        all_assets = list(asset_qs)
        total = len(all_assets)
        self.log_info(f"Found {total} Cisco assets with serial numbers.")

        # Warn if specific assets were silently dropped by upstream filters
        if selected_assets:
            requested_pks = {a.pk for a in selected_assets}
            returned_pks = {a.pk for a in all_assets}
            dropped = requested_pks - returned_pks
            if dropped:
                self.log_warning(
                    f"{len(dropped)} selected asset(s) excluded  not Cisco, no serial, "
                    "or filtered out by another active filter."
                )

        # ------------------------------------------------------------------
        # Skip already-covered assets
        # ------------------------------------------------------------------
        if data.get("skip_covered"):
            today = date.today()
            covered_pks = set(
                ContractAssignment.objects
                .filter(
                    asset__in=all_assets,
                    start_date__lte=today,
                    end_date__gte=today,
                )
                .values_list("asset_id", flat=True)
            )
            unchecked = [a for a in all_assets if a.pk not in covered_pks]
            self.log_info(
                f"  {len(covered_pks)} already have active coverage  skipping. "
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
                if (
                    not getattr(a, "support_validated_at", None)    # never validated
                    or a.support_validated_at < cutoff               # stale validation
                )
            ]
            skipped = before_count - len(all_assets)
            self.log_info(
                f"Validated-at threshold: {threshold_days} days (cutoff={cutoff}). "
                f"Skipping {skipped} asset(s) validated recently  "
                f"{len(all_assets)} remaining."
            )

        if not all_assets:
            self.log_info("Nothing to sync.")
            return

        # ------------------------------------------------------------------
        # Optional asset limit (for test / dry runs)
        # ------------------------------------------------------------------
        asset_limit = int(data.get("asset_limit") or 0)
        if asset_limit > 0:
            all_assets = all_assets[:asset_limit]
            self.log_info(
                f"Asset limit active  processing first {len(all_assets)} asset(s)."
            )

        # ------------------------------------------------------------------
        # Build serial  asset map (handles duplicate serials)
        # ------------------------------------------------------------------
        serial_to_assets: dict[str, list[Asset]] = {}
        for asset in all_assets:
            sn = (asset.serial or "").strip().upper()
            if sn:
                serial_to_assets.setdefault(sn, []).append(asset)

        all_serials = list(serial_to_assets.keys())
        num_batches = math.ceil(len(all_serials) / COVERAGE_BATCH_SIZE)
        self.log_info(
            f"Querying Cisco Coverage API in {num_batches} batch(es) "
            f"({COVERAGE_BATCH_SIZE} serials each)..."
        )

        # Ensure the Cisco ContractVendor exists before we start DB writes
        vendor = _get_or_create_vendor(cisco_manufacturer)

        # Ensure the "not on account" review tag exists (created on first live run)
        review_tag = _get_or_create_no_contract_tag(do_commit, self)
        if review_tag is None and not do_commit:
            self.log_info(
                f"Dry run: tag '{CISCO_NO_CONTRACT_TAG_NAME}' does not exist yet "
                "and will be created on the first live run."
            )

        # ------------------------------------------------------------------
        # Stats
        # ------------------------------------------------------------------
        stats = {
            "covered_api": 0,
            "uncovered_api": 0,
            "assignment_created": 0,
            "assignment_skipped": 0,
            "warranty_updated": 0,
            "support_state_updated": 0,
            "api_errors": 0,
            "cx_api_hit": 0,
            "cx_api_miss": 0,
            "validation_errors": 0,
            "tag_added": 0,
            "tag_removed": 0,
        }

        uncovered_assets_in_use: list[Asset] = []

        # ------------------------------------------------------------------
        # Batch API calls
        # ------------------------------------------------------------------
        for batch_start in range(0, len(all_serials), COVERAGE_BATCH_SIZE):
            batch = all_serials[batch_start: batch_start + COVERAGE_BATCH_SIZE]
            batch_num = batch_start // COVERAGE_BATCH_SIZE + 1
            records = _fetch_coverage_batch(batch, support_headers, self)

            # Optionally log the raw API response
            if log_api_response:
                if records:
                    vlog(
                        f"[API_RESPONSE] Batch {batch_num} ({len(batch)} serials):\n"
                        + json.dumps(records, indent=2, default=str)
                    )
                else:
                    vlog(
                        f"[API_RESPONSE] Batch {batch_num}  "
                        "empty or error response (no records returned)."
                    )

            if not records:
                stats["api_errors"] += 1
                self.log_warning(
                    f"Batch {batch_num}: no records returned for {len(batch)} serials."
                )
                continue

            # Index API results by normalised serial number
            api_by_serial: dict[str, dict] = {
                (rec.get("sr_no") or "").strip().upper(): rec
                for rec in records
                if (rec.get("sr_no") or "").strip()
            }

            # Build a CX lookup map for serials that are covered but have no contract number
            cx_lookup_map: dict[str, Optional[dict]] = {}
            if cx_customer_id and cx_headers:
                serials_needing_cx: list[str] = []
                for _sn in batch:
                    _rec = api_by_serial.get(_sn)
                    if not _rec:
                        continue
                    _covered = (_rec.get("is_covered") or "").upper() == "YES"
                    _cn = (_rec.get("service_contract_number") or "").strip()
                    if _covered and not _cn:
                        serials_needing_cx.append(_sn)
                if serials_needing_cx:
                    vlog(
                        f"[CX_BATCH] Looking up {len(serials_needing_cx)} covered serial(s) with missing contract details via CX Cloud"
                    )
                    cx_lookup_map = _fetch_cx_coverage_batch(
                        serials_needing_cx, cx_customer_id, cx_headers, self
                    )

            for sn in batch:
                rec = api_by_serial.get(sn)
                assets_for_sn = serial_to_assets.get(sn, [])

                #  Serial not returned by the API at all
                if rec is None:
                    vlog(f"[NO_DATA] serial={sn}  not in API response")
                    stats["uncovered_api"] += len(assets_for_sn)
                    for a in assets_for_sn:
                        if a.status == "used":
                            uncovered_assets_in_use.append(a)
                        if data.get("update_support_status"):
                            if _update_support_state(
                                a, is_covered=False,
                                do_commit=do_commit, script=self, vlog=vlog,
                            ):
                                stats["support_state_updated"] += 1
                    continue

                #  Parse API record
                is_covered = (rec.get("is_covered") or "").upper() == "YES"
                contract_number = (rec.get("service_contract_number") or "").strip()
                service_level = (rec.get("service_line_descr") or "Unknown").strip()
                coverage_end = _parse_date(rec.get("covered_product_line_end_date") or "")
                warranty_end = _parse_date(rec.get("warranty_end_date") or "")
                warranty_type_raw = (rec.get("warranty_type") or "").strip()

                #  Not covered by contract
                if not is_covered:
                    vlog(f"[UNCOVERED] serial={sn} warranty_end={warranty_end} warranty_type={warranty_type_raw or '(none)'}")
                    stats["uncovered_api"] += len(assets_for_sn)
                    today_date = date.today()
                    for a in assets_for_sn:
                        # Update warranty fields before checking coverage state
                        if _update_warranty_fields(a, warranty_end, warranty_type_raw, cisco_manufacturer, do_commit, self):
                            stats["warranty_updated"] += 1
                        # Only flag as "in use with no coverage" if warranty doesn't cover it
                        has_active_warranty = (
                            a.warranty_end is not None
                            and a.warranty_end >= today_date
                            and (a.warranty_start is None or a.warranty_start <= today_date)
                        )
                        if a.status == "used" and not has_active_warranty:
                            uncovered_assets_in_use.append(a)
                        if data.get("update_support_status"):
                            if _update_support_state(
                                a, is_covered=False,
                                do_commit=do_commit, script=self, vlog=vlog,
                            ):
                                stats["support_state_updated"] += 1
                    continue

                #  Covered but no contract number — try CX Cloud API as a fallback
                if not contract_number:
                    cx_rec = cx_lookup_map.get(sn)

                    if cx_rec:
                        #  CX Cloud returned contract details — use them
                        contract_number = (cx_rec.get("contractNumber") or "").strip()
                        service_level = (cx_rec.get("serviceLevel") or "Unknown").strip()
                        cx_coverage_end = _parse_date(cx_rec.get("coverageEndDate") or "")
                        if cx_coverage_end:
                            coverage_end = cx_coverage_end
                        vlog(
                            f"[CX_API_HIT] serial={sn} — CX Cloud returned "
                            f"contract={contract_number} svc='{service_level}' "
                            f"end={coverage_end}"
                        )
                        stats["cx_api_hit"] += len(assets_for_sn)
                        # Fall through to the normal "covered with contract" path below
                    else:
                        #  No CX data either — tag for review and move on
                        if cx_customer_id and cx_headers:
                            vlog(
                                f"[CX_API_MISS] serial={sn} — CX Cloud returned "
                                "no contract details either"
                            )
                        else:
                            vlog(
                                f"[COVERED_NO_CONTRACT] serial={sn} — "
                                "covered but no contract number returned "
                                "(CX lookup disabled)"
                            )
                        stats["cx_api_miss"] += len(assets_for_sn)
                        stats["covered_api"] += len(assets_for_sn)
                        for a in assets_for_sn:
                            if _update_warranty_fields(a, warranty_end, warranty_type_raw, cisco_manufacturer, do_commit, self):
                                stats["warranty_updated"] += 1
                            if data.get("update_support_status"):
                                if _update_support_state(
                                    a, is_covered=True,
                                    do_commit=do_commit, script=self, vlog=vlog,
                                ):
                                    stats["support_state_updated"] += 1
                            # Tag the asset for review unless it already has the tag
                            already_tagged = (
                                review_tag is not None
                                and a.tags.filter(pk=review_tag.pk).exists()
                            )
                            if not already_tagged:
                                if do_commit and review_tag is not None:
                                    a.tags.add(review_tag)
                                vlog(
                                    f"{'[DRY RUN] Would add' if not do_commit else 'Added'} "
                                    f"tag '{CISCO_NO_CONTRACT_TAG_NAME}' to asset={a.pk} '{a}'"
                                )
                                stats["tag_added"] += 1
                        continue

                #  Covered with a contract number
                stats["covered_api"] += len(assets_for_sn)
                contract_type = _resolve_contract_type(contract_number, ea_ids)

                if do_commit:
                    contract = _get_or_create_contract(
                        contract_number, contract_type, vendor, coverage_end, self
                    )
                    sku = _get_or_create_sku(service_level, contract_type, cisco_manufacturer)
                else:
                    # Dry-run stubs  log intent without DB writes
                    contract = Contract(
                        contract_id=contract_number,
                        contract_type=contract_type,
                        vendor=vendor,
                        status="active",
                        start_date=date.today() - timedelta(days=1),
                        end_date=coverage_end or date.today(),
                    )
                    sku = ContractSKU(
                        sku=service_level.upper().replace(" ", "_")[:64],
                        manufacturer=cisco_manufacturer,
                        contract_type=contract_type,
                        service_level=service_level,
                    )

                for asset in assets_for_sn:
                    if _update_warranty_fields(asset, warranty_end, warranty_type_raw, cisco_manufacturer, do_commit, self):
                        stats["warranty_updated"] += 1

                    if data.get("update_support_status"):
                        if _update_support_state(
                            asset, is_covered=True,
                            do_commit=do_commit, script=self, vlog=vlog,
                        ):
                            stats["support_state_updated"] += 1

                    # If this asset was previously tagged as not-on-account but now
                    # has a contract number, remove the tag — it's been resolved.
                    if (
                        review_tag is not None
                        and asset.tags.filter(pk=review_tag.pk).exists()
                    ):
                        if do_commit:
                            asset.tags.remove(review_tag)
                        vlog(
                            f"{'[DRY RUN] Would remove' if not do_commit else 'Removed'} "
                            f"tag '{CISCO_NO_CONTRACT_TAG_NAME}' from asset={asset.pk} '{asset}' "
                            f"(contract {contract_number} now returned)"
                        )
                        stats["tag_removed"] += 1

                    if do_commit:
                        created, reason = _create_assignment_if_missing(
                            asset, contract, sku, coverage_end, do_commit, self
                        )
                    else:
                        existing = ContractAssignment.objects.filter(
                            asset=asset,
                            contract__contract_id=contract_number,
                        ).exists()
                        created = not existing
                        reason = "would_create" if not existing else "already_exists"

                    if created:
                        stats["assignment_created"] += 1
                    else:
                        stats["assignment_skipped"] += 1

                    if reason.startswith("validation_error"):
                        stats["validation_errors"] += 1
                        self.log_warning(f"asset={asset.pk} '{asset}': {reason}")

                    vlog(
                        f"[{'DRY_RUN' if not do_commit else 'LIVE'}] "
                        f"serial={sn} asset={asset.pk} '{asset}' "
                        f"contract={contract_number} type={contract_type} "
                        f"svc='{service_level}' end={coverage_end} "
                        f" {reason}"
                    )

        # ------------------------------------------------------------------
        # Report uncovered assets in active use
        # ------------------------------------------------------------------
        if uncovered_assets_in_use:
            self.log_warning(
                f"\n{'='*60}\n"
                f"UNCOVERED ASSETS IN ACTIVE USE ({len(uncovered_assets_in_use)})\n"
                f"These devices have status='used' but Cisco reports NO active coverage.\n"
                f"{'='*60}"
            )
            for asset in uncovered_assets_in_use:
                device_info = ""
                if asset.device_id:
                    device_info = f" | device={asset.device}"
                elif asset.device_type_id:
                    device_info = f" | type={asset.device_type}"
                self.log_warning(
                    f"  UNCOVERED  serial={asset.serial}  "
                    f"asset={asset.pk} '{asset}'{device_info}"
                )

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        self.log_info(
            f"\n{'='*60}\n"
            f"SYNC COMPLETE {'(DRY RUN  no changes written)' if not do_commit else ''}\n"
            f"  Cisco assets checked   : {len(all_assets)}\n"
            f"  Covered (API)          : {stats['covered_api']}\n"
            f"  Uncovered (API)        : {stats['uncovered_api']}\n"
            f"  Assignments created    : {stats['assignment_created']}\n"
            f"  Assignments skipped    : {stats['assignment_skipped']}\n"
            f"  Warranty fields updated: {stats['warranty_updated']}\n"
            f"  Support states updated : {stats['support_state_updated']}\n"
            f"  Validation errors      : {stats['validation_errors']}\n"
            f"  API batch errors       : {stats['api_errors']}\n"
            f"  CX API hits (secondary)  : {stats['cx_api_hit']}\n"
            f"  CX API misses (no data)  : {stats['cx_api_miss']}\n"
            f"  Uncovered + in-use     : {len(uncovered_assets_in_use)}\n"
            f"  Tags added (no-acct)   : {stats['tag_added']}\n"
            f"  Tags removed (resolved): {stats['tag_removed']}\n"
            f"{'='*60}"
        )

        if (verbose or log_api_response) and logged >= log_limit:
            self.log_info(
                f"Verbose log limit reached ({log_limit}). "
                "Increase 'Verbose Log Limit' to see more."
            )
