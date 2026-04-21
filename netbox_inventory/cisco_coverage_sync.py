"""
Cisco Coverage Sync — NetBox Script

Queries the Cisco Support API Coverage Summary endpoint for every Cisco asset
that has a serial number, then creates/updates ContractAssignment records so
that NetBox reflects the current coverage state.

How it fits the data model
--------------------------
  ContractVendor  ← "Cisco Systems" (created if missing)
  ContractSKU     ← keyed on Cisco service_line_descr (e.g. "Solution Support")
  Contract        ← keyed on service_contract_number from the API
  ContractAssignment ← per-asset link; auto-sets VendorProgram via clean()
  AssetProgramCoverage ← activated by signal when ContractAssignment is saved
  Asset.support_state  ← flipped to COVERED by signal

EA program linkage
------------------
If a contract is typed as "support-ea" (either by matching the ea_contract_ids
parameter or because it already exists in NetBox as that type), ContractAssignment
.clean() will auto-resolve the VendorProgram (e.g. "Cisco Enterprise Agreement"),
and the post_save signal will flip AssetProgramCoverage to ACTIVE.

Prerequisites
-------------
  PLUGINS_CONFIG["netbox_inventory"]["cisco_support_api_client_id"]
  PLUGINS_CONFIG["netbox_inventory"]["cisco_support_api_client_secret"]

Script parameters (all optional)
---------------------------------
  dry_run           — do not write to DB (default True)
  ea_contract_ids   — comma-separated contract numbers to treat as EA
  skip_covered      — skip assets that already have an active ContractAssignment
  verbose           — per-asset log lines
  log_limit         — max verbose log lines
"""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Optional

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from dcim.models import Manufacturer
from extras.scripts import BooleanVar, IntegerVar, Script, StringVar

from netbox_inventory.models import (
    Asset,
    Contract,
    ContractAssignment,
    ContractSKU,
    ContractVendor,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CISCO_MANUFACTURER_NAME = "Cisco"
CISCO_VENDOR_NAME = "Cisco Systems"

# Cisco Coverage Summary API — accepts up to 75 serial numbers per request
COVERAGE_API_URL = "https://apix.cisco.com/cs/api/v1/coverage/summary/serial_numbers/{serial_numbers}"
COVERAGE_BATCH_SIZE = 75

TOKEN_URL = "https://id.cisco.com/oauth2/default/v1/token"


# ---------------------------------------------------------------------------
# Auth helper (mirrors SyncCiscoHwEoXDates.api_logon)
# ---------------------------------------------------------------------------

def _get_auth_headers(script: Script) -> Optional[dict]:
    cfg = settings.PLUGINS_CONFIG.get("netbox_inventory", {}) or {}
    client_id = cfg.get("cisco_support_api_client_id", "")
    client_secret = cfg.get("cisco_support_api_client_secret", "")

    if not client_id or not client_secret:
        script.log_failure(
            "Cisco API credentials not configured. "
            "Set cisco_support_api_client_id / cisco_support_api_client_secret "
            "in PLUGINS_CONFIG['netbox_inventory']."
        )
        return None

    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    if r.status_code != 200:
        script.log_failure(f"Token request failed ({r.status_code}): {r.text}")
        return None

    token = r.json().get("access_token")
    if not token:
        script.log_failure(f"Token response missing access_token: {r.text}")
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
    """Call the Coverage Summary API for up to 75 serials. Returns raw records."""
    url = COVERAGE_API_URL.format(serial_numbers=",".join(serial_numbers))
    try:
        r = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as exc:
        script.log_warning(f"Coverage API request error: {exc}")
        return []

    if r.status_code != 200:
        script.log_warning(f"Coverage API error ({r.status_code}): {r.text[:300]}")
        return []

    data = r.json()
    return data.get("serial_numbers", [])


# ---------------------------------------------------------------------------
# DB helpers (idempotent get-or-create wrappers)
# ---------------------------------------------------------------------------

def _get_or_create_vendor(cisco_manufacturer: Manufacturer) -> ContractVendor:
    vendor, _ = ContractVendor.objects.get_or_create(name=CISCO_VENDOR_NAME)
    return vendor


def _resolve_contract_type(
    contract_number: str,
    ea_ids: set[str],
) -> str:
    """
    Determine contract_type for a contract_number:
    1. If it already exists in the DB, preserve its type.
    2. If the number is in the ea_ids override set → support-ea.
    3. Otherwise default to support-alc.
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
) -> Contract:
    """Get or create a Contract keyed on contract_number + vendor."""
    contract, created = Contract.objects.get_or_create(
        contract_id=contract_number,
        vendor=vendor,
        defaults={
            "contract_type": contract_type,
            "status": "active",
            "description": f"Cisco support contract {contract_number}",
            "end_date": coverage_end_date,
        },
    )
    # If it already existed but the end_date is further out, update it
    if not created and coverage_end_date:
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
    # Normalise to a stable identifier (e.g. "Solution Support" → "SOLUTION_SUPPORT")
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


def _create_assignment_if_missing(
    asset: Asset,
    contract: Contract,
    sku: ContractSKU,
    end_date: Optional[date],
    do_commit: bool,
    script: Script,
) -> tuple[bool, str]:
    """
    Create a ContractAssignment for the asset if one doesn't already cover
    the same period.  Returns (created, reason_string).
    """
    # Use contract dates as fallback
    effective_end = end_date or contract.end_date
    effective_start = contract.start_date

    # Check for an existing active assignment for this asset+sku that already
    # covers today — avoid duplicates even if end_dates differ slightly.
    today = date.today()
    existing_qs = ContractAssignment.objects.filter(
        asset=asset,
        sku=sku,
        contract=contract,
    )
    if existing_qs.exists():
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
        assignment.save()  # signals will update support_state + AssetProgramCoverage

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
            "covered assets. Uncovered assets in active use are reported. "
            "ContractAssignments for EA contracts auto-link to the Cisco EA VendorProgram."
        )

    dry_run = BooleanVar(
        default=True,
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

    skip_covered = BooleanVar(
        default=True,
        label="Skip Already-Covered Assets",
        description=(
            "Skip assets that already have at least one active ContractAssignment. "
            "Disable to re-validate all assets against the API."
        ),
    )

    verbose = BooleanVar(
        default=False,
        label="Verbose Logging",
        description="Emit per-asset log lines (can be noisy for large inventories).",
    )

    log_limit = IntegerVar(
        default=500,
        label="Verbose Log Limit",
        description="Maximum per-asset log lines when verbose is enabled.",
    )

    asset_limit = IntegerVar(
        default=0,
        required=False,
        label="Asset Limit",
        description="Process only the first N assets (0 = no limit). Useful for test runs.",
    )

    @transaction.atomic
    def run(self, data, commit):
        do_commit = bool(commit) and not data["dry_run"]
        verbose = bool(data.get("verbose", False))
        log_limit = int(data.get("log_limit", 500))
        logged = 0

        # Parse EA contract ID overrides
        raw_ea = (data.get("ea_contract_ids") or "").strip()
        ea_ids: set[str] = {s.strip() for s in raw_ea.split(",") if s.strip()}
        if ea_ids:
            self.log_info(f"Treating these contract IDs as EA: {', '.join(sorted(ea_ids))}")

        def vlog(msg: str) -> None:
            nonlocal logged
            if not verbose or logged >= log_limit:
                return
            self.log_info(msg)
            logged += 1

        # ------------------------------------------------------------------
        # Resolve Cisco manufacturer — bail if not configured
        # ------------------------------------------------------------------
        try:
            cisco_manufacturer = Manufacturer.objects.get(name__iexact=CISCO_MANUFACTURER_NAME)
        except Manufacturer.DoesNotExist:
            self.log_failure(
                f'Manufacturer "{CISCO_MANUFACTURER_NAME}" not found in NetBox. '
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
        # Build asset list: Cisco assets with a serial number
        # ------------------------------------------------------------------
        asset_qs = (
            Asset.objects
            .select_related("device_type__manufacturer", "module_type__manufacturer")
            .filter(
                device_type__manufacturer=cisco_manufacturer,
            )
            .exclude(serial__isnull=True)
            .exclude(serial__exact="")
        )

        all_assets = list(asset_qs)
        total = len(all_assets)
        self.log_info(f"Found {total} Cisco assets with serial numbers.")

        if data.get("skip_covered"):
            # Collect asset PKs that already have an active assignment
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
                f"  {len(covered_pks)} already have active coverage — skipping. "
                f"Checking {len(unchecked)} assets against the API."
            )
            all_assets = unchecked

        if not all_assets:
            self.log_info("Nothing to sync.")
            return

        # Apply optional asset limit (for test / dry runs against a small sample)
        asset_limit = int(data.get("asset_limit") or 0)
        if asset_limit > 0:
            all_assets = all_assets[:asset_limit]
            self.log_info(f"Asset limit active — processing first {len(all_assets)} asset(s).")

        # ------------------------------------------------------------------
        # Build serial → asset map (handle duplicate serials gracefully)
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

        # ------------------------------------------------------------------
        # Stats
        # ------------------------------------------------------------------
        stats = {
            "covered_api": 0,        # reported covered by Cisco API
            "uncovered_api": 0,      # reported uncovered by Cisco API
            "assignment_created": 0,
            "assignment_skipped": 0,
            "api_errors": 0,
            "validation_errors": 0,
        }

        covered_serials: set[str] = set()
        uncovered_assets_in_use: list[Asset] = []

        # ------------------------------------------------------------------
        # Batch API calls
        # ------------------------------------------------------------------
        for batch_start in range(0, len(all_serials), COVERAGE_BATCH_SIZE):
            batch = all_serials[batch_start : batch_start + COVERAGE_BATCH_SIZE]
            records = _fetch_coverage_batch(batch, headers, self)

            if not records:
                stats["api_errors"] += 1
                self.log_warning(
                    f"Batch {batch_start // COVERAGE_BATCH_SIZE + 1}: "
                    f"no records returned for {len(batch)} serials."
                )
                continue

            # Index API results by normalised serial number
            api_by_serial: dict[str, dict] = {}
            for rec in records:
                sn = (rec.get("sr_no") or "").strip().upper()
                if sn:
                    api_by_serial[sn] = rec

            for sn in batch:
                rec = api_by_serial.get(sn)
                assets_for_sn = serial_to_assets.get(sn, [])

                if rec is None:
                    # Serial not returned by API at all — treat as uncovered
                    vlog(f"[NO_DATA] serial={sn} — not in API response")
                    stats["uncovered_api"] += len(assets_for_sn)
                    for a in assets_for_sn:
                        if a.status == "used":
                            uncovered_assets_in_use.append(a)
                    continue

                is_covered = (rec.get("is_covered") or "").upper() == "YES"
                contract_number = (rec.get("service_contract_number") or "").strip()
                service_level = (rec.get("service_line_descr") or "Unknown").strip()
                coverage_end = _parse_date(rec.get("coverage_end_date") or "")
                warranty_end = _parse_date(rec.get("warranty_end_date") or "")

                if not is_covered:
                    vlog(
                        f"[UNCOVERED] serial={sn} "
                        f"warranty_end={warranty_end}"
                    )
                    stats["uncovered_api"] += len(assets_for_sn)
                    for a in assets_for_sn:
                        if a.status == "used":
                            uncovered_assets_in_use.append(a)
                    continue

                # Covered — skip if no contract number (shouldn't happen, but be safe)
                if not contract_number:
                    vlog(f"[COVERED_NO_CONTRACT] serial={sn} — covered but no contract number")
                    stats["covered_api"] += len(assets_for_sn)
                    covered_serials.add(sn)
                    continue

                covered_serials.add(sn)
                stats["covered_api"] += len(assets_for_sn)

                # Determine and look up / create contract objects
                contract_type = _resolve_contract_type(contract_number, ea_ids)

                if do_commit:
                    contract = _get_or_create_contract(
                        contract_number, contract_type, vendor, coverage_end
                    )
                    sku = _get_or_create_sku(service_level, contract_type, cisco_manufacturer)
                else:
                    # Dry-run: use stubs so we can log intent without DB writes
                    contract = Contract(
                        contract_id=contract_number,
                        contract_type=contract_type,
                        vendor=vendor,
                        status="active",
                        end_date=coverage_end,
                    )
                    sku = ContractSKU(
                        sku=service_level.upper().replace(" ", "_")[:64],
                        manufacturer=cisco_manufacturer,
                        contract_type=contract_type,
                        service_level=service_level,
                    )

                for asset in assets_for_sn:
                    if do_commit:
                        created, reason = _create_assignment_if_missing(
                            asset, contract, sku, coverage_end, do_commit, self
                        )
                    else:
                        # Dry run — just check if one already exists
                        existing = ContractAssignment.objects.filter(
                            asset=asset, contract__contract_id=contract_number
                        ).exists()
                        created, reason = (not existing), ("would_create" if not existing else "already_exists")

                    if created:
                        stats["assignment_created"] += 1
                    else:
                        stats["assignment_skipped"] += 1

                    vlog(
                        f"[{'DRY_RUN' if not do_commit else 'LIVE'}] "
                        f"serial={sn} asset={asset.pk} '{asset}' "
                        f"contract={contract_number} type={contract_type} "
                        f"svc='{service_level}' end={coverage_end} "
                        f"→ {reason}"
                    )

                    if reason.startswith("validation_error"):
                        stats["validation_errors"] += 1
                        self.log_warning(
                            f"asset={asset.pk} '{asset}': {reason}"
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
                    f"  UNCOVERED  serial={asset.serial}  asset={asset.pk} '{asset}'"
                    f"{device_info}"
                )

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        self.log_info(
            f"\n{'='*60}\n"
            f"SYNC COMPLETE {'(DRY RUN — no changes written)' if not do_commit else ''}\n"
            f"  Cisco assets checked : {len(all_assets)}\n"
            f"  Covered (API)        : {stats['covered_api']}\n"
            f"  Uncovered (API)      : {stats['uncovered_api']}\n"
            f"  Assignments created  : {stats['assignment_created']}\n"
            f"  Assignments skipped  : {stats['assignment_skipped']}\n"
            f"  Validation errors    : {stats['validation_errors']}\n"
            f"  API batch errors     : {stats['api_errors']}\n"
            f"  Uncovered + in-use   : {len(uncovered_assets_in_use)}\n"
            f"{'='*60}"
        )

        if verbose and logged >= log_limit:
            self.log_info(
                f"Verbose log limit reached ({log_limit}). "
                "Increase 'Verbose Log Limit' to see more."
            )
