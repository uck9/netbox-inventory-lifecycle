"""
Cisco EA Asset Inventory Audit — NetBox Script

Takes a Cisco Enterprise Agreement / Support Portal device export CSV (Product
Number, Device identifier, Instance number, Item type, ..., SO/MSO number —
one row per coverage/entitlement line item) and audits every row of the
selected Item type(s) (default: "P" / Parent — the physical hardware line)
against netbox_inventory Assets.

One-directional only: this does NOT check for NetBox assets that are missing
from the CSV.

For every in-scope CSV row with a serial number ("Device identifier"), the
matching Asset (by serial, case-insensitive/trimmed) is checked for:

  1. Existence           Asset with this serial exists in NetBox at all.
  2. Product ID          part_number of whichever hardware-type FK is set on
                          the asset (device_type, module_type, or
                          inventoryitem_type — e.g. a Nexus supervisor module
                          tracked via module_type) vs CSV "Product Number".
                          Several known-OK differences are tolerated and NOT
                          reported as a mismatch, since license/feature-set
                          is tracked via the attached AssetLicense, not the
                          device_type PID:
                            - a trailing "-A" / "-E" / "-S" suffix on either
                              side (e.g. Catalyst "-S" = IP Base license)
                            - a Cisco ONE bundled-SKU "C1-" prefix on the CSV
                              side where NetBox tracks the plain hardware PID
                              instead (e.g. CSV "C1-WSC3850-24XS-S" vs
                              device_type "WS-C3850-24XS-S"; or CSV
                              "C1-C2960X-48TD-L" vs device_type
                              "WS-C2960X-48TD-L")
                            - an ISR-style mid-string license/feature-bundle
                              code inserted before the trailing "/xxx" image
                              suffix (e.g. CSV "ISR4331-VSEC/K9" or
                              "ISR4331-AXV/K9" vs device_type "ISR4331/K9"),
                              matched generically by shape, not a hardcoded
                              list of codes
                            - a trailing "=" spare/orderable-part marker on
                              the CSV side (e.g. CSV "N9K-SUP-A+=" vs
                              module_type "N9K-SUP-A+")
                          Only a genuine PID mismatch beyond these is flagged.
  3. Vendor Instance ID  asset.vendor_instance_id vs CSV "Instance number".
  4. Order               asset.order.name vs CSV "SO/MSO number".
  5. ISR permanent        For CSV rows whose Product Number carries an
     license (optional)   ISR-style mid-string license code (see #2 above,
                          e.g. "VSEC" in "ISR4331-VSEC/K9"), checks that code
                          appears in the SKU of asset.base_license_sku (the
                          perpetual/base entitlement tied to the hardware).
                          A single letter is only treated as a license code
                          when it's "V" (the Voice/UC bundle, e.g. "ISR4331-
                          V/K9") — other single letters are left alone since
                          they can denote a hardware chassis variant instead
                          of a license (e.g. "ISR4451-X/K9"). Rows without a
                          recognized code aren't checked. Controlled by the
                          "Check ISR License SKU" parameter.

CSV rows of the selected item type(s) with no "Device identifier" (e.g.
cluster-level licenses with no physical serial) cannot be serial-matched and
are reported separately rather than silently skipped.

Chassis components — power supplies (Product Number containing "PWR") and
stacking kits ("STACK-KIT") — are excluded from the audit by default —
Cisco marks them as Parent items, but they aren't tracked as individual
assets here. Disable via the "Exclude Chassis Components" parameter.

CSV input
---------
Paste the export directly, or upload the .csv file instead. Required columns
(matched case-insensitively, by substring so minor header wording changes
don't break the script): "Product Number", "Device identifier",
"Instance number", an "Item type" column, and "SO/MSO number".

Script parameters
------------------
  item_types                comma-separated Item type code(s) to audit (default: "P")
  csv_text                  paste CSV data (either this or csv_file required)
  csv_file                  upload a .csv file instead
  exclude_chassis_components  skip Product Numbers containing "PWR" or
                             "STACK-KIT" (default: True)
  check_isr_license         for ISR-style PIDs, check the mid-string license code
                             against asset.base_license_sku (default: True)
  verbose                 also log fully-matching assets, tolerated PID diffs,
                           and excluded power supplies
"""
from __future__ import annotations

import csv
import io
import re
from typing import Optional

from django.db import transaction

from extras.scripts import BooleanVar, FileVar, Script, StringVar, TextVar

from netbox_inventory.models import Asset

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Logical column -> substring(s) used to locate the real header (case-insensitive).
# Substring matching (rather than an exact match) tolerates minor wording
# differences in Cisco's export headers across report versions.
REQUIRED_COLUMNS: dict[str, str] = {
    "product_number": "product number",
    "serial": "device identifier",
    "instance_number": "instance number",
    "item_type": "item type",
    "so_mso_number": "so/mso number",
}

# Trailing suffixes on a Product ID that designate a software feature-set /
# license level (e.g. Catalyst "-S" = IP Base, "-E" = IP Services; AP/router
# "-A" = advantage). License type is tracked via the attached AssetLicense,
# not the device_type PID, so a mismatch that is *only* one of these
# suffixes is not a real PID problem.
LICENSE_TYPE_SUFFIXES = ("-A", "-E", "-S")

# Cisco ONE bundled-SKU prefix. Cisco sometimes exports the hardware line
# under a "C1-" + PID (e.g. "C1-WSC3850-24XS-S", "C1-C2960X-48TD-L") where
# the underlying physical hardware is tracked in NetBox under its plain,
# usually "WS-" prefixed, PID (e.g. "WS-C3850-24XS-S", "WS-C2960X-48TD-L").
CISCO_ONE_PREFIX = "C1-"

# A hyphenated, all-letters license/feature-bundle code inserted directly
# before the trailing "/xxx" image suffix on ISR-style PIDs, e.g.
# "ISR4331-VSEC/K9" or "ISR4331-AXV/K9" vs the bare "ISR4331/K9" device_type
# PID. Matched generically by shape (letters-only segment before the final
# "/") rather than a hardcoded list of codes, since Cisco has many of these
# (VSEC, AXV, SEC, UC, ...) and adds more over time. A bare single letter is
# only matched when it's "V" (the Voice/UC bundle, e.g. "ISR4331-V/K9") —
# other single letters are deliberately NOT matched generically, since they
# can denote a hardware chassis variant rather than a license, e.g.
# "ISR4451-X/K9" ("X" = chassis variant, not a license code).
ISR_LICENSE_INFIX_RE = re.compile(r"^(.+)-(V|[A-Z]{2,})(/.+)$")

# Trailing "=" marks a Cisco PID as the spare/orderable-replacement part
# number for the same underlying hardware, e.g. "N9K-SUP-A+=" vs the plain
# "N9K-SUP-A+" tracked on the device_type/module_type.
SPARE_PART_SUFFIX = "="

# Substrings (case-insensitive) that mark a CSV row as a chassis component —
# a power supply or stacking kit. Cisco marks these as Parent items too, but
# they aren't tracked as individual assets here, so they're excluded from
# the audit by default.
CHASSIS_COMPONENT_MARKERS = ("PWR", "STACK-KIT")

DEFAULT_ITEM_TYPES = "P"


def _pid_variants(pid: str) -> set[str]:
    """
    Return the set of PID forms that should be treated as equivalent to `pid`
    for comparison purposes: the PID itself, plus tolerated variants for a
    trailing license/feature-set suffix (-A / -E / -S), a Cisco ONE "C1-"
    bundle prefix, an ISR-style mid-string license infix before "/xxx", and
    a trailing "=" spare/orderable-part marker. Transformations are applied
    to a fixed point so they can stack (e.g. a C1- prefix uncovering a
    further -S suffix). Two PIDs are considered a match if their variant
    sets intersect.
    """
    p = pid.strip().upper()
    if not p:
        return set()

    variants = {p}
    changed = True
    while changed:
        changed = False
        for base in list(variants):
            candidates: set[str] = set()

            for suffix in LICENSE_TYPE_SUFFIXES:
                if base.endswith(suffix) and len(base) > len(suffix):
                    candidates.add(base[: -len(suffix)])

            if base.startswith(CISCO_ONE_PREFIX):
                remainder = base[len(CISCO_ONE_PREFIX):]
                candidates.add(remainder)
                if remainder.startswith("WS") and not remainder.startswith("WS-"):
                    # e.g. "WSC3850-24XS-S" -> "WS-C3850-24XS-S"
                    candidates.add("WS-" + remainder[2:])
                elif not remainder.startswith("WS-"):
                    # e.g. "C2960X-48TD-L" -> "WS-C2960X-48TD-L"
                    candidates.add("WS-" + remainder)

            m = ISR_LICENSE_INFIX_RE.match(base)
            if m:
                candidates.add(m.group(1) + m.group(3))

            if base.endswith(SPARE_PART_SUFFIX) and len(base) > len(SPARE_PART_SUFFIX):
                candidates.add(base[: -len(SPARE_PART_SUFFIX)])

            for c in candidates:
                if c not in variants:
                    variants.add(c)
                    changed = True

    return variants


def _asset_pid_field(asset: Asset) -> tuple[Optional[str], Optional[str]]:
    """
    Return (type_label, part_number) for whichever PID-bearing hardware-type
    FK is set on the asset — device_type, module_type, or inventoryitem_type,
    in that order (an Asset has exactly one of these set). rack_type has no
    part_number field, so it's not a PID source. (None, None) if none of the
    three PID-bearing types is set.
    """
    if asset.device_type_id is not None:
        return "device_type", asset.device_type.part_number
    if asset.module_type_id is not None:
        return "module_type", asset.module_type.part_number
    if asset.inventoryitem_type_id is not None:
        return "inventoryitem_type", asset.inventoryitem_type.part_number
    return None, None


def _resolve_required_headers(fieldnames: list[str], script: Script) -> Optional[dict[str, str]]:
    """
    Locate each REQUIRED_COLUMNS entry within the CSV's actual (lowercased)
    header row by substring match. Returns a dict of logical name -> actual
    lowercased header text, or None (with an error logged) if any required
    column can't be found.
    """
    lowered = [(h or "").strip().lower() for h in fieldnames if h]
    resolved: dict[str, str] = {}
    missing: list[str] = []

    for logical_name, needle in REQUIRED_COLUMNS.items():
        match = next((h for h in lowered if needle in h), None)
        if match is None:
            missing.append(needle)
        else:
            resolved[logical_name] = match

    if missing:
        script.log_failure(
            "CSV is missing required column(s) (matched by substring): "
            + ", ".join(f'"{m}"' for m in missing)
        )
        return None

    return resolved


def _read_csv_rows(data: dict, script: Script) -> Optional[tuple[list[dict], dict[str, str]]]:
    """
    Return (parsed CSV rows with normalised/lowercased header keys, resolved
    required-header map), or None (with an error already logged) if the
    input is missing or invalid.
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

    rows = []
    for row in reader:
        normalized = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items() if k}
        rows.append(normalized)
    return rows, resolved


# ---------------------------------------------------------------------------
# Main Script
# ---------------------------------------------------------------------------


class AuditCiscoAssetInventory(Script):
    class Meta:
        name = "Inventory: Audit Cisco EA Devices Against Assets"
        description = (
            "Checks a Cisco EA/Support Portal device export against NetBox — for every "
            "row of the selected Item type(s) (default: Parent), validates the Asset "
            "exists by serial, and that device_type PID, Vendor Instance ID, and Order "
            "match what Cisco reports. CSV -> NetBox direction only."
        )

    item_types = StringVar(
        default=DEFAULT_ITEM_TYPES,
        required=False,
        label="Item Type(s) to Audit",
        description=(
            'Comma-separated Item type code(s) from the CSV\'s "Item type" column '
            '(e.g. "P" for Parent hardware lines). Default: P.'
        ),
    )

    csv_text = TextVar(
        required=False,
        label="CSV Data",
        description="Paste the Cisco EA / Support Portal device export CSV here.",
    )

    csv_file = FileVar(
        required=False,
        label="CSV File",
        description="Alternative to pasting CSV Data above — upload the .csv file instead.",
    )

    exclude_chassis_components = BooleanVar(
        default=True,
        label="Exclude Chassis Components",
        description=(
            'Skip CSV rows whose Product Number contains "PWR" (power supplies) or '
            '"STACK-KIT" (stacking kits). Cisco marks these as Parent items too, but '
            "they aren't tracked as individual assets here."
        ),
    )

    check_isr_license = BooleanVar(
        default=True,
        label="Check ISR License SKU",
        description=(
            "For CSV rows whose Product Number has an ISR-style mid-string license "
            'code before the trailing "/xxx" (e.g. "VSEC" in "ISR4331-VSEC/K9"), check '
            "that code appears in the SKU of the asset's permanent license "
            "(Asset.base_license_sku). Rows without such a code aren't checked."
        ),
    )

    verbose = BooleanVar(
        default=False,
        label="Verbose Logging",
        description=(
            "Also log assets that fully matched, PID differences that were "
            "tolerated (license suffix / C1- prefix / ISR license infix), and excluded "
            "power supplies."
        ),
    )

    # -----------------------------------------------------------------------

    @transaction.atomic
    def run(self, data, commit):
        verbose = bool(data.get("verbose", False))

        selected_item_types = {
            t.strip().upper()
            for t in (data.get("item_types") or DEFAULT_ITEM_TYPES).split(",")
            if t.strip()
        }
        if not selected_item_types:
            self.log_failure("No item types selected — nothing to audit.")
            return
        self.log_info(f"Auditing Item type(s): {', '.join(sorted(selected_item_types))}")

        check_isr_license = bool(data.get("check_isr_license", True))
        if check_isr_license:
            self.log_info(
                "Checking ISR-style PIDs' license code against asset.base_license_sku."
            )

        exclude_chassis_components = bool(data.get("exclude_chassis_components", True))
        if exclude_chassis_components:
            self.log_info(
                "Excluding Product Numbers containing "
                + " or ".join(f'"{m}"' for m in CHASSIS_COMPONENT_MARKERS)
                + " (chassis components)."
            )

        parsed = _read_csv_rows(data, self)
        if parsed is None:
            return
        rows, headers = parsed
        if not rows:
            self.log_info("CSV contained no data rows.")
            return
        self.log_info(f"Parsed {len(rows)} row(s) from CSV.")

        # ------------------------------------------------------------------
        # Reduce to in-scope rows, split by whether a serial is present.
        # First-seen row wins per serial (defensive — production exports seen
        # so far have exactly one Parent row per serial, but don't assume it).
        # ------------------------------------------------------------------
        in_scope_with_serial: dict[str, dict] = {}
        no_serial_rows: list[dict] = []
        excluded_chassis_components: list[dict] = []
        duplicate_serial_count = 0
        in_scope_total = 0

        for row in rows:
            item_type = row.get(headers["item_type"], "").strip().upper()
            if item_type not in selected_item_types:
                continue

            csv_product_number = row.get(headers["product_number"], "").upper()
            if exclude_chassis_components and any(
                marker in csv_product_number for marker in CHASSIS_COMPONENT_MARKERS
            ):
                excluded_chassis_components.append(row)
                continue

            in_scope_total += 1

            serial = row.get(headers["serial"], "").strip()
            if not serial:
                no_serial_rows.append(row)
                continue

            key = serial.upper()
            if key in in_scope_with_serial:
                duplicate_serial_count += 1
                continue
            in_scope_with_serial[key] = row

        self.log_info(
            f"{in_scope_total} row(s) match selected item type(s) and are not excluded "
            f"chassis components; {len(in_scope_with_serial)} with a serial (device identifier), "
            f"{len(no_serial_rows)} without."
        )
        if excluded_chassis_components:
            self.log_info(
                f"{len(excluded_chassis_components)} chassis component row(s) excluded "
                + "(Product Number contains "
                + " or ".join(f'"{m}"' for m in CHASSIS_COMPONENT_MARKERS)
                + ")."
            )
        if duplicate_serial_count:
            self.log_warning(
                f"{duplicate_serial_count} additional in-scope row(s) shared a serial "
                "already seen — only the first row per serial was audited."
            )
        if not in_scope_with_serial and not no_serial_rows:
            self.log_info("Nothing in scope to audit.")
            return

        # ------------------------------------------------------------------
        # Look up matching Assets (case-insensitive serial match), pulling
        # device_type + order in the same query.
        # ------------------------------------------------------------------
        assets_by_serial: dict[str, Asset] = {}
        for asset in (
            Asset.objects
            .select_related("device_type", "module_type", "inventoryitem_type", "order", "base_license_sku")
            .exclude(serial__isnull=True)
            .exclude(serial__exact="")
        ):
            key = asset.serial.strip().upper()
            # First match wins; NetBox doesn't enforce serial uniqueness.
            assets_by_serial.setdefault(key, asset)

        # ------------------------------------------------------------------
        # Audit each in-scope, serialed CSV row against its Asset.
        # ------------------------------------------------------------------
        missing: list[tuple[str, dict]] = []
        pid_mismatch: list[tuple[str, dict, Asset]] = []
        pid_no_type: list[tuple[str, dict, Asset]] = []
        pid_no_part_number: list[tuple[str, dict, Asset]] = []
        pid_tolerated: list[tuple[str, dict, Asset]] = []  # informational only (-A/-E, C1-WS)
        instance_missing: list[tuple[str, dict, Asset]] = []
        instance_mismatch: list[tuple[str, dict, Asset]] = []
        order_missing: list[tuple[str, dict, Asset]] = []
        order_mismatch: list[tuple[str, dict, Asset]] = []
        isr_license_missing: list[tuple[str, dict, Asset, str]] = []
        isr_license_mismatch: list[tuple[str, dict, Asset, str, str]] = []
        fully_clean: list[tuple[str, dict, Asset]] = []

        for serial_key, row in sorted(in_scope_with_serial.items()):
            asset = assets_by_serial.get(serial_key)
            if asset is None:
                missing.append((serial_key, row))
                continue

            row_is_clean = True

            # --- PID check --------------------------------------------------
            csv_pid = row.get(headers["product_number"], "").strip().upper()
            pid_type_label, pid_raw = _asset_pid_field(asset)
            if pid_type_label is None:
                pid_no_type.append((serial_key, row, asset))
                row_is_clean = False
            else:
                asset_pid = (pid_raw or "").strip().upper()
                if not asset_pid:
                    pid_no_part_number.append((serial_key, row, asset))
                    row_is_clean = False
                elif csv_pid == asset_pid:
                    pass  # exact match
                elif _pid_variants(csv_pid) & _pid_variants(asset_pid):
                    pid_tolerated.append((serial_key, row, asset))
                    # Not a failure — informational only, doesn't mark row unclean.
                else:
                    pid_mismatch.append((serial_key, row, asset))
                    row_is_clean = False

            # --- Vendor Instance ID (Instance number) check ------------------
            csv_instance = row.get(headers["instance_number"], "").strip()
            asset_instance = (asset.vendor_instance_id or "").strip()
            if not asset_instance:
                instance_missing.append((serial_key, row, asset))
                row_is_clean = False
            elif asset_instance != csv_instance:
                instance_mismatch.append((serial_key, row, asset))
                row_is_clean = False

            # --- Order (SO/MSO number) check --------------------------------
            csv_so_mso = row.get(headers["so_mso_number"], "").strip()
            if asset.order_id is None:
                order_missing.append((serial_key, row, asset))
                row_is_clean = False
            elif (asset.order.name or "").strip() != csv_so_mso:
                order_mismatch.append((serial_key, row, asset))
                row_is_clean = False

            # --- ISR permanent license check (optional) ----------------------
            if check_isr_license:
                m = ISR_LICENSE_INFIX_RE.match(csv_pid)
                if m:
                    license_code = m.group(2)
                    if asset.base_license_sku_id is None:
                        isr_license_missing.append((serial_key, row, asset, license_code))
                        row_is_clean = False
                    else:
                        base_sku = (asset.base_license_sku.sku or "").strip().upper()
                        if license_code not in base_sku:
                            isr_license_mismatch.append(
                                (serial_key, row, asset, license_code, base_sku)
                            )
                            row_is_clean = False

            if row_is_clean:
                fully_clean.append((serial_key, row, asset))

        # ------------------------------------------------------------------
        # Report
        # ------------------------------------------------------------------
        def pn(row: dict) -> str:
            return row.get(headers["product_number"], "")

        def fmt_asset(asset: Asset) -> str:
            return f"asset={asset.pk} '{asset}'"

        def fmt_pid(asset: Asset) -> str:
            type_label, pid = _asset_pid_field(asset)
            if type_label is None:
                return "(no device_type/module_type/inventoryitem_type)"
            return f"{type_label}_pid={pid or '(none)'}"

        if no_serial_rows:
            self.log_warning(
                f"NO SERIAL PROVIDED BY CISCO — cannot audit ({len(no_serial_rows)}):"
            )
            for row in no_serial_rows:
                self.log_warning(
                    f"  product={pn(row)}  "
                    f"instance={row.get(headers['instance_number'], '')}  "
                    f"so_mso={row.get(headers['so_mso_number'], '')}"
                )

        if missing:
            self.log_warning(f"MISSING FROM NETBOX ({len(missing)}):")
            for serial_key, row in missing:
                self.log_warning(
                    f"  serial={row.get(headers['serial'], '')}  product={pn(row)}  "
                    f"instance={row.get(headers['instance_number'], '')}  "
                    f"so_mso={row.get(headers['so_mso_number'], '')}"
                )

        if pid_mismatch:
            self.log_warning(f"PID MISMATCH ({len(pid_mismatch)}):")
            for serial_key, row, asset in pid_mismatch:
                self.log_warning(
                    f"  serial={row.get(headers['serial'], '')}  {fmt_asset(asset)}  "
                    f"csv_pid={pn(row)}  {fmt_pid(asset)}"
                )

        if pid_no_type:
            self.log_warning(
                f"ASSET HAS NO DEVICE/MODULE/INVENTORYITEM TYPE ({len(pid_no_type)}):"
            )
            for serial_key, row, asset in pid_no_type:
                self.log_warning(
                    f"  serial={row.get(headers['serial'], '')}  {fmt_asset(asset)}  "
                    f"csv_pid={pn(row)}"
                )

        if pid_no_part_number:
            self.log_warning(
                f"ASSET'S TYPE HAS NO PART NUMBER SET ({len(pid_no_part_number)}):"
            )
            for serial_key, row, asset in pid_no_part_number:
                type_label, _ = _asset_pid_field(asset)
                type_obj = getattr(asset, type_label) if type_label else None
                self.log_warning(
                    f"  serial={row.get(headers['serial'], '')}  {fmt_asset(asset)}  "
                    f"{type_label}={type_obj}  csv_pid={pn(row)}"
                )

        if instance_missing:
            self.log_warning(
                f"VENDOR INSTANCE ID MISSING ON ASSET ({len(instance_missing)}):"
            )
            for serial_key, row, asset in instance_missing:
                self.log_warning(
                    f"  serial={row.get(headers['serial'], '')}  {fmt_asset(asset)}  "
                    f"csv_instance={row.get(headers['instance_number'], '')}"
                )

        if instance_mismatch:
            self.log_warning(f"VENDOR INSTANCE ID MISMATCH ({len(instance_mismatch)}):")
            for serial_key, row, asset in instance_mismatch:
                self.log_warning(
                    f"  serial={row.get(headers['serial'], '')}  {fmt_asset(asset)}  "
                    f"asset_instance={asset.vendor_instance_id}  "
                    f"csv_instance={row.get(headers['instance_number'], '')}"
                )

        if order_missing:
            self.log_warning(f"ORDER MISSING ON ASSET ({len(order_missing)}):")
            for serial_key, row, asset in order_missing:
                self.log_warning(
                    f"  serial={row.get(headers['serial'], '')}  {fmt_asset(asset)}  "
                    f"csv_so_mso={row.get(headers['so_mso_number'], '')}"
                )

        if order_mismatch:
            self.log_warning(f"ORDER MISMATCH ({len(order_mismatch)}):")
            for serial_key, row, asset in order_mismatch:
                self.log_warning(
                    f"  serial={row.get(headers['serial'], '')}  {fmt_asset(asset)}  "
                    f"asset_order={asset.order.name}  "
                    f"csv_so_mso={row.get(headers['so_mso_number'], '')}"
                )

        if isr_license_missing:
            self.log_warning(
                f"ISR PERMANENT LICENSE MISSING ON ASSET ({len(isr_license_missing)}):"
            )
            for serial_key, row, asset, license_code in isr_license_missing:
                self.log_warning(
                    f"  serial={row.get(headers['serial'], '')}  {fmt_asset(asset)}  "
                    f"csv_pid={pn(row)}  csv_license_code={license_code}  "
                    f"asset.base_license_sku=(none)"
                )

        if isr_license_mismatch:
            self.log_warning(f"ISR PERMANENT LICENSE MISMATCH ({len(isr_license_mismatch)}):")
            for serial_key, row, asset, license_code, base_sku in isr_license_mismatch:
                self.log_warning(
                    f"  serial={row.get(headers['serial'], '')}  {fmt_asset(asset)}  "
                    f"csv_pid={pn(row)}  csv_license_code={license_code}  "
                    f"asset.base_license_sku={base_sku}"
                )

        if verbose and pid_tolerated:
            self.log_info(
                f"PID differs only by a tolerated pattern (license suffix, C1- prefix, "
                f"or ISR license infix) — not flagged ({len(pid_tolerated)}):"
            )
            for serial_key, row, asset in pid_tolerated:
                self.log_info(
                    f"  serial={row.get(headers['serial'], '')}  {fmt_asset(asset)}  "
                    f"csv_pid={pn(row)}  {fmt_pid(asset)}"
                )

        if verbose and fully_clean:
            self.log_info(f"FULLY MATCHED ({len(fully_clean)}):")
            for serial_key, row, asset in fully_clean:
                self.log_info(
                    f"  serial={row.get(headers['serial'], '')}  {fmt_asset(asset)}"
                )

        if verbose and excluded_chassis_components:
            self.log_info(f"EXCLUDED — CHASSIS COMPONENTS ({len(excluded_chassis_components)}):")
            for row in excluded_chassis_components:
                self.log_info(
                    f"  serial={row.get(headers['serial'], '')}  product={pn(row)}"
                )

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        checked = len(in_scope_with_serial)
        summary_lines = [f"\n{'='*60}", "AUDIT COMPLETE", f"{'='*60}"]
        summary_lines.append(f"  In-scope rows (item type match)      : {in_scope_total}")
        summary_lines.append(f"  Excluded — chassis components         : {len(excluded_chassis_components)}")
        summary_lines.append(f"  Checked against NetBox (had serial)  : {checked}")
        summary_lines.append(f"  No serial in CSV (not audited)       : {len(no_serial_rows)}")
        summary_lines.append(f"  Missing from NetBox                  : {len(missing)}")
        summary_lines.append(f"  PID mismatch                         : {len(pid_mismatch)}")
        summary_lines.append(f"  PID tolerated diff (OK)               : {len(pid_tolerated)}")
        summary_lines.append(f"  Asset has no device/module/item type  : {len(pid_no_type)}")
        summary_lines.append(f"  Asset's type has no part number       : {len(pid_no_part_number)}")
        summary_lines.append(f"  Vendor Instance ID missing on asset  : {len(instance_missing)}")
        summary_lines.append(f"  Vendor Instance ID mismatch          : {len(instance_mismatch)}")
        summary_lines.append(f"  Order missing on asset               : {len(order_missing)}")
        summary_lines.append(f"  Order mismatch                       : {len(order_mismatch)}")
        summary_lines.append(f"  ISR permanent license missing         : {len(isr_license_missing)}")
        summary_lines.append(f"  ISR permanent license mismatch        : {len(isr_license_mismatch)}")
        summary_lines.append(f"  Fully matched                        : {len(fully_clean)}")
        summary_lines.append("=" * 60)
        self.log_info("\n".join(summary_lines))
