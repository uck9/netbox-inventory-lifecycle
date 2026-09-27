"""
Cisco License Central Asset Audit — NetBox Script

Takes a Cisco License Central device inventory export CSV (one row per
device/host — Device Name, Product Number, up to five "Device Identifier N
Name"/"Device Identifier N Value" pairs, Instance Number, Customer Site ID,
Warranty Type, Sales Order, Ship Date, ...) and validates every row against
the matching netbox_inventory Asset, by serial number.

One-directional and asset-centric only: this does NOT report CSV rows that
don't match any NetBox asset (e.g. software-only entries, MAC-address/host-id
rows, or hardware not yet tracked here) as a finding — it only validates
assets that already exist in NetBox against what License Central reports for
them. A short summary count of unmatched CSV rows with a serial is still
logged (in verbose mode, the rows themselves are listed too) purely so you
can sanity-check the totals.

Matching
--------
Serial number is read from the CSV's "Device Identifier 1 Value" column
(matched case-insensitively/trimmed against Asset.serial). This is the
column License Central puts the device serial number in for the vast
majority of rows; where it instead holds a MAC address / host ID / UUID for
a software-only or virtual entry, that row simply won't match any hardware
Asset and is silently skipped (see above).

For every CSV row whose serial matches a NetBox Asset, the following fields
are checked:

  1. Instance Number      CSV "Instance Number" vs Asset.vendor_instance_id.
  2. Customer Site ID     CSV "Customer Site ID" vs the vendor_site_id of the
                          asset's Installed-At Location (Asset.installed_at),
                          scoped to the Cisco InstalledAtLocation catalog.
                          Fixing this links to an existing InstalledAtLocation
                          for Cisco with that vendor_site_id if one exists; if
                          not, it creates one from the CSV's own Customer
                          Name/Address/City/State/Province/County/Country/
                          Zip columns (see "Installed-At Location fields"
                          below) and links to that instead.
  3. Warranty Type        CSV "Warranty Type" (a Cisco warranty SKU code,
                          e.g. "WARR-LTD-LIFE-HW") vs the sku of
                          Asset.warranty_type. Unlike Customer Site ID, when
                          fixing this field a WarrantyType catalog row IS
                          created (manufacturer=Cisco, sku=name=the CSV code)
                          if one doesn't already exist for that SKU.
  4. Sales Order          CSV "Sales Order" vs Asset.order.name. Fixing this
                          is one-directional and narrow: it only ever
                          *assigns* an Order to an asset that currently has
                          none, by looking up an existing Order (scoped to
                          Cisco) whose name matches the CSV value — it never
                          creates a new Order, and it never touches an asset
                          that already has a *different* Order set (that's
                          always reported as a mismatch and left alone,
                          fix or no fix), since the order an asset is
                          assigned to is authoritative data from our own
                          purchasing records, not something License Central
                          should overwrite.
  5. Ship Date            CSV "Ship Date" (format "DD-Mon-YY", e.g.
                          "12-May-20") vs Asset.vendor_ship_date.

CSV rows with no value in one of these columns simply aren't checked for
that field (nothing to compare against) — this is not reported as a finding.

Installed-At Location fields
-----------------------------
InstalledAtLocation only has one field for state/region and none for county,
so creating one from the CSV folds those columns in as follows:
  vendor_site_id  <- Customer Site ID
  customer_name   <- Customer Name
  address         <- Customer Address, with ", <County> County" appended
                     when Customer County is present (used for US addresses;
                     there's nowhere else on the model to put it)
  city            <- Customer City
  state           <- Customer State, falling back to Customer Province when
                     State is blank (License Central uses State for AU/US
                     addresses and Province for others)
  country         <- Customer Country
  postcode        <- Customer Zip/Postal Code
A location already existing in NetBox for that Customer Site ID is always
linked as-is — its fields are never overwritten from the CSV, only a brand
new one is populated this way.

Fixing
------
Each of the five fields has its own "Fix ..." checkbox parameter, all
defaulting to OFF. With all boxes unchecked (the default), the script only
reports what doesn't match; nothing is written. Checking a box makes the
script correct that field's value on the Asset wherever License Central and
NetBox disagree (including filling in a value where the Asset field was
empty, and — for Customer Site ID — creating a new Installed-At Location
when no matching one exists yet). Fix Sales Order is narrower than the
others: it only fills in an Order on an asset that has none, and only when
an existing Order with that name already exists in NetBox (see "Sales Order"
above) — it never creates an Order, and never overwrites an asset's existing
(mismatched) Order. As with any NetBox script, nothing is actually persisted
to the database unless "Commit changes" is also checked when running the
script — with a fix box checked but commit off, the script logs what it
*would* fix (and what it *would* create) without writing anything, same as a
normal report-only run.

CSV input
---------
Paste the export directly, or upload the .csv file instead. Required
columns (matched case-insensitively — first by an exact header match, then
by substring, so minor header wording changes don't break the script):
"Device Identifier 1 Value", "Instance Number", "Customer Site ID",
"Warranty Type", "Sales Order", "Ship Date". The Customer Name/Address/City/
State/Province/County/Country/Zip columns used to create a new Installed-At
Location are optional — if any are missing from the CSV, that field is just
left blank on any newly created location.

Script parameters
------------------
  csv_text                  paste CSV data (either this or csv_file required)
  csv_file                  upload a .csv file instead
  fix_instance_number       correct Asset.vendor_instance_id from the CSV
  fix_customer_site_id      link Asset.installed_at to the matching Cisco
                             Installed-At Location for the CSV's Customer
                             Site ID (only when one already exists)
  fix_warranty_type         correct Asset.warranty_type from the CSV,
                             creating the WarrantyType catalog row if needed
  fix_missing_sales_order   assign Asset.order from the CSV's Sales Order,
                             but only when the asset currently has no order
                             and a matching Order already exists in NetBox
  fix_ship_date             correct Asset.vendor_ship_date from the CSV
  verbose                   also log fully-matching assets and unmatched
                             CSV rows
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from django.db import transaction

from dcim.models import Manufacturer
from extras.scripts import BooleanVar, FileVar, Script, TextVar

from netbox_inventory.models import Asset, InstalledAtLocation, Order, WarrantyType

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CISCO_MANUFACTURER_NAME = "Cisco"

# Logical column -> substring (case-insensitive) used to locate the real
# header. Resolution tries an exact match against the (lowercased) header
# first, then falls back to substring matching, so close-but-not-identical
# header wording across export versions doesn't break the script while still
# avoiding collisions like "Instance Number" vs "Parent Instance Number".
REQUIRED_COLUMNS: dict[str, str] = {
    "serial": "device identifier 1 value",
    "instance_number": "instance number",
    "customer_site_id": "customer site id",
    "warranty_type": "warranty type",
    "sales_order": "sales order",
    "ship_date": "ship date",
}

# Optional columns used only to populate a new InstalledAtLocation when
# fixing Customer Site ID and no matching one already exists. Missing from
# the CSV, that field is simply left blank on the created location.
ADDRESS_COLUMNS: dict[str, str] = {
    "customer_name": "customer name",
    "customer_address": "customer address",
    "customer_city": "customer city",
    "customer_state": "customer state",
    "customer_province": "customer province",
    "customer_county": "customer county",
    "customer_country": "customer country",
    "customer_postcode": "customer zip/postal code",
}

# Cisco License Central renders dates like "12-May-20".
SHIP_DATE_FORMAT = "%d-%b-%y"


def _parse_ship_date(raw: str):
    """
    Parse a License Central "Ship Date" value (e.g. "12-May-20") into a date,
    or None if blank/unparseable.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, SHIP_DATE_FORMAT).date()
    except ValueError:
        return None


def _find_header(lowered: list[str], needle: str) -> Optional[str]:
    """
    Locate a single header within the CSV's actual (lowercased) header row:
    first by an exact match, then by substring, so minor header wording
    changes don't break the script while a needle that's also a substring of
    another column's header (e.g. "instance number" also being a substring
    of "parent instance number") still resolves correctly regardless of
    column order.
    """
    match = next((h for h in lowered if h == needle), None)
    if match is None:
        match = next((h for h in lowered if needle in h), None)
    return match


def _resolve_required_headers(fieldnames: list[str], script: Script) -> Optional[dict[str, str]]:
    """
    Resolve every REQUIRED_COLUMNS entry to an actual header. Returns a dict
    of logical name -> actual lowercased header text, or None (with an error
    logged) if any required column can't be found.
    """
    lowered = [(h or "").strip().lower() for h in fieldnames if h]
    resolved: dict[str, str] = {}
    missing: list[str] = []

    for logical_name, needle in REQUIRED_COLUMNS.items():
        match = _find_header(lowered, needle)
        if match is None:
            missing.append(needle)
        else:
            resolved[logical_name] = match

    if missing:
        script.log_failure(
            "CSV is missing required column(s) (matched by exact/substring name): "
            + ", ".join(f'"{m}"' for m in missing)
        )
        return None

    return resolved


def _resolve_optional_headers(fieldnames: list[str], columns: dict[str, str]) -> dict[str, Optional[str]]:
    """
    Resolve each entry in `columns` to an actual header, same matching rules
    as _resolve_required_headers, but missing columns just map to None
    instead of failing the script.
    """
    lowered = [(h or "").strip().lower() for h in fieldnames if h]
    return {logical_name: _find_header(lowered, needle) for logical_name, needle in columns.items()}


def _read_csv_rows(
    data: dict, script: Script
) -> Optional[tuple[list[dict], dict[str, str], dict[str, Optional[str]]]]:
    """
    Return (parsed CSV rows with normalised/lowercased header keys, resolved
    required-header map, resolved optional address-header map), or None
    (with an error already logged) if the input is missing or invalid.
    """
    csv_file = data.get("csv_file")
    csv_text = (data.get("csv_text") or "").strip()

    if csv_file:
        raw = csv_file.read()
        text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    elif csv_text:
        text = csv_text
    else:
        script.log_failure("No CSV input provided — paste CSV data or upload a CSV file.")
        return None

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        script.log_failure("CSV has no header row.")
        return None

    resolved = _resolve_required_headers(reader.fieldnames, script)
    if resolved is None:
        return None
    address_headers = _resolve_optional_headers(reader.fieldnames, ADDRESS_COLUMNS)

    rows = []
    for row in reader:
        normalized = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items() if k}
        rows.append(normalized)
    return rows, resolved, address_headers


def _get_or_create_warranty_type(
    sku: str,
    cisco_manufacturer: Manufacturer,
    do_commit: bool,
    cache: dict[str, WarrantyType],
    script: Script,
) -> WarrantyType:
    """
    Resolve a Cisco warranty SKU code (e.g. "WARR-LTD-LIFE-HW") to a
    WarrantyType catalog row, creating one if it doesn't exist yet. When
    do_commit is False, returns an existing row if there is one, otherwise
    an unsaved in-memory WarrantyType — this lets a fix-preview run report
    what it would do without actually creating catalog rows that would then
    need to be rolled back. Cached per script run so repeated SKUs across
    rows only hit the DB once.
    """
    if sku in cache:
        return cache[sku]

    if not do_commit:
        warranty_type = WarrantyType.objects.filter(sku=sku).first() or WarrantyType(
            sku=sku, name=sku, manufacturer=cisco_manufacturer,
        )
        cache[sku] = warranty_type
        return warranty_type

    warranty_type, created = WarrantyType.objects.get_or_create(
        sku=sku,
        defaults={"name": sku, "manufacturer": cisco_manufacturer},
    )
    if created:
        script.log_success(f"Created warranty type: {sku}")
    cache[sku] = warranty_type
    return warranty_type


def _build_installed_at_defaults(row: dict, address_headers: dict[str, Optional[str]]) -> dict:
    """
    Map License Central's customer/address columns onto InstalledAtLocation's
    field set. The model has a single "state" field, so Customer Province
    fills it in when Customer State is blank (License Central uses State for
    AU/US-style addresses and Province for others); it has no county field,
    so Customer County (used for US addresses) is appended to the street
    address instead of being dropped on the floor.
    """

    def get(logical_name: str) -> str:
        header = address_headers.get(logical_name)
        return row.get(header, "").strip() if header else ""

    address = get("customer_address")
    county = get("customer_county")
    if county:
        address = f"{address}, {county} County" if address else f"{county} County"

    return {
        "customer_name": get("customer_name"),
        "address": address,
        "city": get("customer_city"),
        "state": get("customer_state") or get("customer_province"),
        "country": get("customer_country"),
        "postcode": get("customer_postcode"),
    }


def _get_or_create_installed_at_location(
    vendor_site_id: str,
    cisco_manufacturer: Manufacturer,
    defaults: dict,
    do_commit: bool,
    cache: dict[str, tuple[str, InstalledAtLocation]],
    script: Script,
) -> tuple[str, InstalledAtLocation]:
    """
    Resolve a Cisco Customer Site ID to an InstalledAtLocation, creating one
    from the CSV's address columns (see _build_installed_at_defaults) if it
    doesn't exist yet. Returns (outcome, location) where outcome is
    "existing" or "created". When do_commit is False, a location that would
    be created is returned as an unsaved in-memory instance instead of
    actually being written, mirroring _get_or_create_warranty_type's
    fix-preview behavior. Cached per script run so repeated site IDs across
    rows only hit the DB once and aren't created twice.
    """
    if vendor_site_id in cache:
        return cache[vendor_site_id]

    location = InstalledAtLocation.objects.filter(
        manufacturer=cisco_manufacturer, vendor_site_id=vendor_site_id,
    ).first()
    if location is not None:
        result = ("existing", location)
        cache[vendor_site_id] = result
        return result

    if not do_commit:
        location = InstalledAtLocation(
            manufacturer=cisco_manufacturer, vendor_site_id=vendor_site_id, **defaults,
        )
    else:
        location = InstalledAtLocation.objects.create(
            manufacturer=cisco_manufacturer, vendor_site_id=vendor_site_id, **defaults,
        )
        script.log_success(
            f"Created Installed-At Location: {vendor_site_id}"
            + (f" ({defaults['customer_name']})" if defaults.get("customer_name") else "")
        )

    result = ("created", location)
    cache[vendor_site_id] = result
    return result


# ---------------------------------------------------------------------------
# Main Script
# ---------------------------------------------------------------------------


class AuditCiscoLicenseCentralAssets(Script):
    class Meta:
        name = "Inventory: Audit Cisco License Central Assets"
        description = (
            "Checks a Cisco License Central device export against NetBox — for every "
            "CSV row whose serial (Device Identifier 1 Value) matches an Asset, validates "
            "Instance Number, Customer Site ID, Warranty Type, Sales Order, and Ship Date. "
            "Optional per-field checkboxes (all off by default) correct mismatches in NetBox."
        )

    csv_text = TextVar(
        required=False,
        label="CSV Data",
        description="Paste the Cisco License Central device inventory export CSV here.",
    )

    csv_file = FileVar(
        required=False,
        label="CSV File",
        description="Alternative to pasting CSV Data above — upload the .csv file instead.",
    )

    fix_instance_number = BooleanVar(
        default=False,
        label="Fix Instance Number",
        description=(
            "Correct Asset.vendor_instance_id from the CSV's Instance Number wherever "
            "they differ (including filling it in where currently blank)."
        ),
    )

    fix_customer_site_id = BooleanVar(
        default=False,
        label="Fix Customer Site ID",
        description=(
            "Link the asset to the Cisco Installed-At Location matching the CSV's "
            "Customer Site ID, wherever it differs from the asset's current one. If no "
            "Installed-At Location exists yet for that Site ID, creates one from the "
            "CSV's Customer Name/Address/City/State/Province/County/Country/Zip columns."
        ),
    )

    fix_warranty_type = BooleanVar(
        default=False,
        label="Fix Warranty Type",
        description=(
            "Correct Asset.warranty_type from the CSV's Warranty Type code wherever they "
            "differ. Creates the Warranty Type catalog entry (manufacturer=Cisco) if the "
            "code doesn't already exist in NetBox."
        ),
    )

    fix_missing_sales_order = BooleanVar(
        default=False,
        label="Fix Missing Sales Order",
        description=(
            "When an asset has no Order set, assign it the existing Order (scoped to Cisco) "
            "whose name matches the CSV's Sales Order — only when exactly one such Order "
            "already exists in NetBox; a Sales Order with no matching Order is just reported, "
            "never created. Never touches an asset that already has a different Order set — "
            "that's always reported as a mismatch, never overwritten."
        ),
    )

    fix_ship_date = BooleanVar(
        default=False,
        label="Fix Ship Date",
        description=(
            "Correct Asset.vendor_ship_date from the CSV's Ship Date wherever they differ."
        ),
    )

    verbose = BooleanVar(
        default=False,
        label="Verbose Logging",
        description=(
            "Also log assets that fully matched and CSV rows with a serial that didn't "
            "match any asset in NetBox."
        ),
    )

    # -----------------------------------------------------------------------

    @transaction.atomic
    def run(self, data, commit):
        do_commit = bool(commit)
        verbose = bool(data.get("verbose", False))
        fix_instance_number = bool(data.get("fix_instance_number", False))
        fix_customer_site_id = bool(data.get("fix_customer_site_id", False))
        fix_warranty_type = bool(data.get("fix_warranty_type", False))
        fix_missing_sales_order = bool(data.get("fix_missing_sales_order", False))
        fix_ship_date = bool(data.get("fix_ship_date", False))

        any_fix_enabled = (
            fix_instance_number
            or fix_customer_site_id
            or fix_warranty_type
            or fix_missing_sales_order
            or fix_ship_date
        )
        if any_fix_enabled:
            self.log_info(
                "Fix mode: "
                + ", ".join(
                    label
                    for label, enabled in (
                        ("Instance Number", fix_instance_number),
                        ("Customer Site ID", fix_customer_site_id),
                        ("Warranty Type", fix_warranty_type),
                        ("Missing Sales Order", fix_missing_sales_order),
                        ("Ship Date", fix_ship_date),
                    )
                    if enabled
                )
                + (
                    " — changes WILL be written."
                    if do_commit
                    else " — 'Commit changes' is off, so nothing will actually be written; "
                    "logged as a preview of what would change."
                )
            )
        else:
            self.log_info("Report-only run — no fix checkboxes enabled, nothing will be written.")

        try:
            cisco_manufacturer = Manufacturer.objects.get(name__iexact=CISCO_MANUFACTURER_NAME)
        except Manufacturer.DoesNotExist:
            self.log_failure(
                f'Manufacturer "{CISCO_MANUFACTURER_NAME}" not found in NetBox. '
                "Create it first under Devices > Manufacturers."
            )
            return

        parsed = _read_csv_rows(data, self)
        if parsed is None:
            return
        rows, headers, address_headers = parsed
        if not rows:
            self.log_info("CSV contained no data rows.")
            return
        self.log_info(f"Parsed {len(rows)} row(s) from CSV.")

        if fix_customer_site_id:
            missing_address_columns = [
                ADDRESS_COLUMNS[logical_name]
                for logical_name, header in address_headers.items()
                if header is None
            ]
            if missing_address_columns:
                self.log_warning(
                    "Customer Site ID fix is on, but the CSV is missing column(s) "
                    + ", ".join(f'"{m}"' for m in missing_address_columns)
                    + " — those fields will be left blank on any newly created "
                    "Installed-At Location."
                )

        # ------------------------------------------------------------------
        # Reduce to rows with a serial. First-seen row wins per serial.
        # ------------------------------------------------------------------
        rows_with_serial: dict[str, dict] = {}
        no_serial_count = 0
        duplicate_serial_count = 0

        for row in rows:
            serial = row.get(headers["serial"], "").strip()
            if not serial:
                no_serial_count += 1
                continue
            key = serial.upper()
            if key in rows_with_serial:
                duplicate_serial_count += 1
                continue
            rows_with_serial[key] = row

        self.log_info(
            f"{len(rows_with_serial)} row(s) with a serial (Device Identifier 1 Value); "
            f"{no_serial_count} row(s) without one (not checkable, skipped)."
        )
        if duplicate_serial_count:
            self.log_warning(
                f"{duplicate_serial_count} additional row(s) shared a serial already seen — "
                "only the first row per serial was audited."
            )
        if not rows_with_serial:
            self.log_info("Nothing in scope to audit.")
            return

        # ------------------------------------------------------------------
        # Look up matching Assets (case-insensitive serial match).
        # ------------------------------------------------------------------
        assets_by_serial: dict[str, Asset] = {}
        for asset in (
            Asset.objects
            .select_related("warranty_type", "installed_at", "order")
            .exclude(serial__isnull=True)
            .exclude(serial__exact="")
        ):
            key = asset.serial.strip().upper()
            # First match wins; NetBox doesn't enforce serial uniqueness.
            assets_by_serial.setdefault(key, asset)

        # ------------------------------------------------------------------
        # Audit each matched (serial, row, asset).
        # ------------------------------------------------------------------
        unmatched_rows: list[tuple[str, dict]] = []

        instance_missing: list[tuple[str, dict, Asset]] = []
        instance_mismatch: list[tuple[str, dict, Asset]] = []
        instance_fixed: list[tuple[str, dict, Asset, Optional[str], str]] = []

        site_missing: list[tuple[str, dict, Asset, str]] = []
        site_mismatch: list[tuple[str, dict, Asset, Optional[str], str]] = []
        site_linked: list[tuple[str, dict, Asset, Optional[str], str]] = []
        site_created: list[tuple[str, dict, Asset, Optional[str], str]] = []

        warranty_missing: list[tuple[str, dict, Asset, str]] = []
        warranty_mismatch: list[tuple[str, dict, Asset, Optional[str], str]] = []
        warranty_fixed: list[tuple[str, dict, Asset, Optional[str], str]] = []

        ship_date_missing: list[tuple[str, dict, Asset, str]] = []
        ship_date_mismatch: list[tuple[str, dict, Asset, str]] = []
        ship_date_unparseable: list[tuple[str, dict, Asset, str]] = []
        ship_date_fixed: list[tuple[str, dict, Asset, Optional[str], str]] = []

        order_missing: list[tuple[str, dict, Asset, str]] = []
        order_no_match: list[tuple[str, dict, Asset, str]] = []
        order_ambiguous: list[tuple[str, dict, Asset, str, int]] = []
        order_fixed: list[tuple[str, dict, Asset, str]] = []
        order_mismatch: list[tuple[str, dict, Asset, str, str]] = []

        fully_clean: list[tuple[str, dict, Asset]] = []

        installed_at_cache: dict[str, tuple[str, InstalledAtLocation]] = {}
        warranty_type_cache: dict[str, WarrantyType] = {}
        order_lookup_cache: dict[str, list[Order]] = {}

        for serial_key, row in sorted(rows_with_serial.items()):
            asset = assets_by_serial.get(serial_key)
            if asset is None:
                unmatched_rows.append((serial_key, row))
                continue

            row_is_clean = True
            update_fields: list[str] = []

            # --- Instance Number --------------------------------------------
            csv_instance = row.get(headers["instance_number"], "").strip()
            if csv_instance:
                current_instance = (asset.vendor_instance_id or "").strip()
                if current_instance != csv_instance:
                    row_is_clean = False
                    if fix_instance_number:
                        old = current_instance or None
                        asset.vendor_instance_id = csv_instance
                        update_fields.append("vendor_instance_id")
                        instance_fixed.append((serial_key, row, asset, old, csv_instance))
                    elif not current_instance:
                        instance_missing.append((serial_key, row, asset))
                    else:
                        instance_mismatch.append((serial_key, row, asset))

            # --- Customer Site ID (Installed-At Location) --------------------
            csv_site_id = row.get(headers["customer_site_id"], "").strip()
            if csv_site_id:
                current_site_id = (
                    asset.installed_at.vendor_site_id if asset.installed_at_id else None
                )
                if current_site_id != csv_site_id:
                    row_is_clean = False
                    if fix_customer_site_id:
                        defaults = _build_installed_at_defaults(row, address_headers)
                        outcome, location = _get_or_create_installed_at_location(
                            csv_site_id, cisco_manufacturer, defaults, do_commit, installed_at_cache, self,
                        )
                        asset.installed_at = location
                        update_fields.append("installed_at")
                        if outcome == "created":
                            site_created.append((serial_key, row, asset, current_site_id, csv_site_id))
                        else:
                            site_linked.append((serial_key, row, asset, current_site_id, csv_site_id))
                    elif current_site_id is None:
                        site_missing.append((serial_key, row, asset, csv_site_id))
                    else:
                        site_mismatch.append((serial_key, row, asset, current_site_id, csv_site_id))

            # --- Warranty Type -------------------------------------------------
            csv_warranty_sku = row.get(headers["warranty_type"], "").strip()
            if csv_warranty_sku:
                current_sku = asset.warranty_type.sku if asset.warranty_type_id else None
                if current_sku != csv_warranty_sku:
                    row_is_clean = False
                    if fix_warranty_type:
                        warranty_type = _get_or_create_warranty_type(
                            csv_warranty_sku, cisco_manufacturer, do_commit, warranty_type_cache, self,
                        )
                        asset.warranty_type = warranty_type
                        update_fields.append("warranty_type")
                        warranty_fixed.append((serial_key, row, asset, current_sku, csv_warranty_sku))
                    elif current_sku is None:
                        warranty_missing.append((serial_key, row, asset, csv_warranty_sku))
                    else:
                        warranty_mismatch.append((serial_key, row, asset, current_sku, csv_warranty_sku))

            # --- Ship Date -------------------------------------------------------
            csv_ship_date_raw = row.get(headers["ship_date"], "").strip()
            if csv_ship_date_raw:
                parsed_ship_date = _parse_ship_date(csv_ship_date_raw)
                if parsed_ship_date is None:
                    row_is_clean = False
                    ship_date_unparseable.append((serial_key, row, asset, csv_ship_date_raw))
                elif asset.vendor_ship_date != parsed_ship_date:
                    row_is_clean = False
                    if fix_ship_date:
                        old = asset.vendor_ship_date
                        asset.vendor_ship_date = parsed_ship_date
                        update_fields.append("vendor_ship_date")
                        ship_date_fixed.append((serial_key, row, asset, old, parsed_ship_date))
                    elif asset.vendor_ship_date is None:
                        ship_date_missing.append((serial_key, row, asset, csv_ship_date_raw))
                    else:
                        ship_date_mismatch.append((serial_key, row, asset, csv_ship_date_raw))

            # --- Sales Order (only ever fills in a missing order; never overwrites) --
            csv_sales_order = row.get(headers["sales_order"], "").strip()
            if csv_sales_order:
                current_order = asset.order.name if asset.order_id else None
                if current_order is not None and current_order != csv_sales_order:
                    # Asset already has a (different) order — always report, never touch.
                    row_is_clean = False
                    order_mismatch.append((serial_key, row, asset, current_order, csv_sales_order))
                elif current_order is None:
                    row_is_clean = False
                    if fix_missing_sales_order:
                        if csv_sales_order not in order_lookup_cache:
                            order_lookup_cache[csv_sales_order] = list(
                                Order.objects.filter(
                                    manufacturer=cisco_manufacturer, name=csv_sales_order,
                                )
                            )
                        matches = order_lookup_cache[csv_sales_order]
                        if len(matches) == 1:
                            asset.order = matches[0]
                            update_fields.append("order")
                            order_fixed.append((serial_key, row, asset, csv_sales_order))
                        elif len(matches) == 0:
                            order_no_match.append((serial_key, row, asset, csv_sales_order))
                        else:
                            order_ambiguous.append(
                                (serial_key, row, asset, csv_sales_order, len(matches))
                            )
                    else:
                        order_missing.append((serial_key, row, asset, csv_sales_order))

            # --- Persist ------------------------------------------------------------
            if update_fields and do_commit:
                asset.save(update_fields=update_fields)

            if row_is_clean:
                fully_clean.append((serial_key, row, asset))

        # ------------------------------------------------------------------
        # Report
        # ------------------------------------------------------------------
        def fmt_asset(asset: Asset) -> str:
            return f"asset={asset.pk} '{asset}'"

        committed_note = "" if do_commit else " (not committed — 'Commit changes' is off)"

        if instance_missing:
            self.log_warning(f"INSTANCE NUMBER MISSING ON ASSET ({len(instance_missing)}):")
            for serial_key, row, asset in instance_missing:
                self.log_warning(
                    f"  serial={serial_key}  {fmt_asset(asset)}  "
                    f"csv_instance={row.get(headers['instance_number'], '')}"
                )

        if instance_mismatch:
            self.log_warning(f"INSTANCE NUMBER MISMATCH ({len(instance_mismatch)}):")
            for serial_key, row, asset in instance_mismatch:
                self.log_warning(
                    f"  serial={serial_key}  {fmt_asset(asset)}  "
                    f"asset_instance={asset.vendor_instance_id}  "
                    f"csv_instance={row.get(headers['instance_number'], '')}"
                )

        if instance_fixed:
            self.log_success(f"INSTANCE NUMBER FIXED{committed_note} ({len(instance_fixed)}):")
            for serial_key, row, asset, old, new in instance_fixed:
                self.log_success(f"  serial={serial_key}  {fmt_asset(asset)}  {old!r} -> {new!r}")

        if site_missing:
            self.log_warning(f"CUSTOMER SITE ID MISSING ON ASSET ({len(site_missing)}):")
            for serial_key, row, asset, csv_site_id in site_missing:
                self.log_warning(f"  serial={serial_key}  {fmt_asset(asset)}  csv_site_id={csv_site_id}")

        if site_mismatch:
            self.log_warning(f"CUSTOMER SITE ID MISMATCH ({len(site_mismatch)}):")
            for serial_key, row, asset, current, csv_site_id in site_mismatch:
                self.log_warning(
                    f"  serial={serial_key}  {fmt_asset(asset)}  "
                    f"asset_site_id={current}  csv_site_id={csv_site_id}"
                )

        if site_linked:
            self.log_success(
                f"CUSTOMER SITE ID FIXED — linked to existing Installed-At Location"
                f"{committed_note} ({len(site_linked)}):"
            )
            for serial_key, row, asset, old, new in site_linked:
                self.log_success(f"  serial={serial_key}  {fmt_asset(asset)}  {old!r} -> {new!r}")

        if site_created:
            self.log_success(
                f"CUSTOMER SITE ID FIXED — new Installed-At Location created from CSV address "
                f"columns{committed_note} ({len(site_created)}); verify the address details:"
            )
            for serial_key, row, asset, old, new in site_created:
                self.log_success(f"  serial={serial_key}  {fmt_asset(asset)}  {old!r} -> {new!r}")

        if warranty_missing:
            self.log_warning(f"WARRANTY TYPE MISSING ON ASSET ({len(warranty_missing)}):")
            for serial_key, row, asset, csv_sku in warranty_missing:
                self.log_warning(f"  serial={serial_key}  {fmt_asset(asset)}  csv_warranty_type={csv_sku}")

        if warranty_mismatch:
            self.log_warning(f"WARRANTY TYPE MISMATCH ({len(warranty_mismatch)}):")
            for serial_key, row, asset, current, csv_sku in warranty_mismatch:
                self.log_warning(
                    f"  serial={serial_key}  {fmt_asset(asset)}  "
                    f"asset_warranty_type={current}  csv_warranty_type={csv_sku}"
                )

        if warranty_fixed:
            self.log_success(f"WARRANTY TYPE FIXED{committed_note} ({len(warranty_fixed)}):")
            for serial_key, row, asset, old, new in warranty_fixed:
                self.log_success(f"  serial={serial_key}  {fmt_asset(asset)}  {old!r} -> {new!r}")

        if ship_date_missing:
            self.log_warning(f"SHIP DATE MISSING ON ASSET ({len(ship_date_missing)}):")
            for serial_key, row, asset, csv_raw in ship_date_missing:
                self.log_warning(f"  serial={serial_key}  {fmt_asset(asset)}  csv_ship_date={csv_raw}")

        if ship_date_mismatch:
            self.log_warning(f"SHIP DATE MISMATCH ({len(ship_date_mismatch)}):")
            for serial_key, row, asset, csv_raw in ship_date_mismatch:
                self.log_warning(
                    f"  serial={serial_key}  {fmt_asset(asset)}  "
                    f"asset_ship_date={asset.vendor_ship_date}  csv_ship_date={csv_raw}"
                )

        if ship_date_unparseable:
            self.log_warning(
                f"SHIP DATE UNPARSEABLE (expected format DD-Mon-YY, e.g. '12-May-20') "
                f"({len(ship_date_unparseable)}):"
            )
            for serial_key, row, asset, csv_raw in ship_date_unparseable:
                self.log_warning(f"  serial={serial_key}  {fmt_asset(asset)}  csv_ship_date={csv_raw!r}")

        if ship_date_fixed:
            self.log_success(f"SHIP DATE FIXED{committed_note} ({len(ship_date_fixed)}):")
            for serial_key, row, asset, old, new in ship_date_fixed:
                self.log_success(f"  serial={serial_key}  {fmt_asset(asset)}  {old} -> {new}")

        if order_missing:
            self.log_warning(
                f"SALES ORDER MISSING ON ASSET — enable 'Fix Missing Sales Order' to link it "
                f"if a matching Order exists ({len(order_missing)}):"
            )
            for serial_key, row, asset, csv_so in order_missing:
                self.log_warning(f"  serial={serial_key}  {fmt_asset(asset)}  csv_sales_order={csv_so}")

        if order_no_match:
            self.log_warning(
                f"SALES ORDER MISSING ON ASSET — no matching Order exists in NetBox to link "
                f"(not created automatically) ({len(order_no_match)}):"
            )
            for serial_key, row, asset, csv_so in order_no_match:
                self.log_warning(f"  serial={serial_key}  {fmt_asset(asset)}  csv_sales_order={csv_so}")

        if order_ambiguous:
            self.log_warning(
                f"SALES ORDER MISSING ON ASSET — multiple Cisco Orders share that name in "
                f"NetBox, skipped as ambiguous ({len(order_ambiguous)}):"
            )
            for serial_key, row, asset, csv_so, count in order_ambiguous:
                self.log_warning(
                    f"  serial={serial_key}  {fmt_asset(asset)}  "
                    f"csv_sales_order={csv_so}  matching_orders={count}"
                )

        if order_fixed:
            self.log_success(f"SALES ORDER FIXED{committed_note} ({len(order_fixed)}):")
            for serial_key, row, asset, csv_so in order_fixed:
                self.log_success(f"  serial={serial_key}  {fmt_asset(asset)}  order set to {csv_so!r}")

        if order_mismatch:
            self.log_warning(
                f"SALES ORDER MISMATCH — asset already has a different order, never overwritten "
                f"({len(order_mismatch)}):"
            )
            for serial_key, row, asset, current, csv_so in order_mismatch:
                self.log_warning(
                    f"  serial={serial_key}  {fmt_asset(asset)}  "
                    f"asset_order={current}  csv_sales_order={csv_so}"
                )

        if verbose and fully_clean:
            self.log_info(f"FULLY MATCHED ({len(fully_clean)}):")
            for serial_key, row, asset in fully_clean:
                self.log_info(f"  serial={serial_key}  {fmt_asset(asset)}")

        if verbose and unmatched_rows:
            self.log_info(
                f"CSV row(s) with a serial that did not match any asset in NetBox "
                f"({len(unmatched_rows)}):"
            )
            for serial_key, row in unmatched_rows:
                self.log_info(
                    f"  serial={serial_key}  device_name={row.get('device name', '')}  "
                    f"product_number={row.get('product number', '')}"
                )

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        checked = len(rows_with_serial) - len(unmatched_rows)
        summary_lines = [f"\n{'='*60}", "AUDIT COMPLETE", f"{'='*60}"]
        summary_lines.append(f"  CSV rows with a serial                : {len(rows_with_serial)}")
        summary_lines.append(f"  Matched to a NetBox asset             : {checked}")
        summary_lines.append(f"  Not matched to any NetBox asset       : {len(unmatched_rows)}")
        summary_lines.append(f"  Instance Number missing               : {len(instance_missing)}")
        summary_lines.append(f"  Instance Number mismatch              : {len(instance_mismatch)}")
        summary_lines.append(f"  Instance Number fixed                 : {len(instance_fixed)}")
        summary_lines.append(f"  Customer Site ID missing              : {len(site_missing)}")
        summary_lines.append(f"  Customer Site ID mismatch             : {len(site_mismatch)}")
        summary_lines.append(f"  Customer Site ID linked (existing)    : {len(site_linked)}")
        summary_lines.append(f"  Customer Site ID linked (new, created): {len(site_created)}")
        summary_lines.append(f"  Warranty Type missing                 : {len(warranty_missing)}")
        summary_lines.append(f"  Warranty Type mismatch                : {len(warranty_mismatch)}")
        summary_lines.append(f"  Warranty Type fixed                   : {len(warranty_fixed)}")
        summary_lines.append(f"  Ship Date missing                     : {len(ship_date_missing)}")
        summary_lines.append(f"  Ship Date mismatch                    : {len(ship_date_mismatch)}")
        summary_lines.append(f"  Ship Date unparseable                 : {len(ship_date_unparseable)}")
        summary_lines.append(f"  Ship Date fixed                       : {len(ship_date_fixed)}")
        summary_lines.append(f"  Sales Order missing (fix off)         : {len(order_missing)}")
        summary_lines.append(f"  Sales Order missing — no match found  : {len(order_no_match)}")
        summary_lines.append(f"  Sales Order missing — ambiguous match : {len(order_ambiguous)}")
        summary_lines.append(f"  Sales Order fixed                     : {len(order_fixed)}")
        summary_lines.append(f"  Sales Order mismatch (never fixed)    : {len(order_mismatch)}")
        summary_lines.append(f"  Fully matched                         : {len(fully_clean)}")
        summary_lines.append("=" * 60)
        self.log_info("\n".join(summary_lines))
