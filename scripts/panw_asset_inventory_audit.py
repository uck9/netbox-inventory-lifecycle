"""
PANW Asset Inventory Audit — NetBox Script

Takes a Palo Alto Support Portal "Devices" CSV export (Serial Number, Model
Name, Device Name, ... — one row per license/feature entitlement, so most
devices span many rows) and checks that every unique device of the selected
type(s) exists as a netbox_inventory Asset, matched by serial number
(case-insensitive, trimmed). One-directional only: this does NOT check for
NetBox assets that are missing from the CSV.

Device type classification (from the Model Name column)
----------------------------------------------------------
  hardware   Model Name starts with "PAN-PA-" but NOT "PAN-PA-VM"
             (e.g. PAN-PA-440, PAN-PA-3420, PAN-PA-445) — physical firewall
             appliances. This is the default (and typically most useful)
             scope, since VM/Panorama serials are less commonly tracked as
             discrete hardware assets.
  vm         Model Name starts with "PAN-PA-VM" (e.g. PAN-PA-VM-300,
             PAN-PA-VM-300-CLOUD) — VM-series virtual appliances.
  panorama   Model Name starts with "PAN-PRA" (e.g. PAN-PRA-1000-CP,
             PAN-PRA-25-E60) — Panorama management appliances/licenses.

Rows whose Model Name doesn't match any of the three prefixes above are
excluded from the audit (and reported once, under Verbose Logging).

CSV input
---------
Paste the export directly, or upload the .csv file instead. Required
columns (case-insensitive): "Serial Number", "Model Name". "Device Name" is
read only for readability in the report — it is not required and is not
used for matching.

Script parameters
------------------
  device_types   which categories of device to audit (default: hardware only)
  csv_text       paste CSV data (either this or csv_file required)
  csv_file       upload a .csv file instead of pasting
  verbose        also log devices that WERE found, and unrecognized models
"""
from __future__ import annotations

import csv
import io
from typing import Optional

from django.db import transaction

from extras.scripts import BooleanVar, FileVar, MultiChoiceVar, Script, TextVar

from netbox_inventory.models import Asset

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_HEADERS = ("serial number", "model name")

DEVICE_TYPE_CHOICES = (
    ("hardware", "PAN-PA hardware appliances (e.g. PAN-PA-440)"),
    ("vm", "PAN-PA-VM virtual appliances (e.g. PAN-PA-VM-300)"),
    ("panorama", "PAN-PRA Panorama appliances (e.g. PAN-PRA-1000-CP)"),
)

CATEGORY_LABELS = dict(DEVICE_TYPE_CHOICES)


def _categorize_model(model_name: str) -> Optional[str]:
    """
    Classify a Model Name into one of "hardware" / "vm" / "panorama", or
    None if unrecognized. Order matters: PAN-PA-VM must be checked before
    the bare PAN-PA prefix, since it's a more specific match of the same
    prefix.
    """
    m = (model_name or "").strip().upper()
    if not m:
        return None
    if m.startswith("PAN-PRA"):
        return "panorama"
    if m.startswith("PAN-PA-VM"):
        return "vm"
    if m.startswith("PAN-PA"):
        return "hardware"
    return None


def _read_csv_rows(data: dict, script: Script) -> Optional[list[dict]]:
    """
    Return parsed CSV rows as dicts (normalised, stripped, lowercased header
    keys), or None (with an error already logged) if the input is missing
    or invalid.
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

    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = [h for h in REQUIRED_HEADERS if h not in headers]
    if missing:
        script.log_failure(
            f"CSV is missing required column(s): {', '.join(missing)}. "
            f"Required: {', '.join(REQUIRED_HEADERS)}."
        )
        return None

    rows = []
    for row in reader:
        normalized = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items() if k}
        rows.append(normalized)
    return rows


# ---------------------------------------------------------------------------
# Main Script
# ---------------------------------------------------------------------------


class AuditPanwAssetInventory(Script):
    class Meta:
        name = "Inventory: Audit Palo Alto Devices Against Assets"
        description = (
            "Checks a Palo Alto Support Portal device export against NetBox — reports "
            "every unique device of the selected type(s), by Model Name, whose serial "
            "number has no matching netbox_inventory Asset. CSV -> NetBox direction only."
        )

    device_types = MultiChoiceVar(
        choices=DEVICE_TYPE_CHOICES,
        default=["hardware"],
        required=False,
        label="Device Types to Audit",
        description=(
            "Which categories of device (by Model Name prefix) to check. "
            "Defaults to hardware appliances only."
        ),
    )

    csv_text = TextVar(
        required=False,
        label="CSV Data",
        description="Paste the Palo Alto Support Portal device export CSV here.",
    )

    csv_file = FileVar(
        required=False,
        label="CSV File",
        description="Alternative to pasting CSV Data above — upload the .csv file instead.",
    )

    verbose = BooleanVar(
        default=False,
        label="Verbose Logging",
        description="Also log devices that WERE found in NetBox, and any unrecognized Model Names.",
    )

    # -----------------------------------------------------------------------

    @transaction.atomic
    def run(self, data, commit):
        verbose = bool(data.get("verbose", False))

        selected_categories = set(data.get("device_types") or [])
        if not selected_categories:
            self.log_failure("No device types selected — nothing to audit.")
            return
        self.log_info(
            "Auditing categories: "
            + ", ".join(CATEGORY_LABELS[c] for c in selected_categories)
        )

        rows = _read_csv_rows(data, self)
        if rows is None:
            return
        if not rows:
            self.log_info("CSV contained no data rows.")
            return
        self.log_info(f"Parsed {len(rows)} row(s) from CSV.")

        # ------------------------------------------------------------------
        # Reduce to unique devices by serial number (first-seen model/name
        # wins — CSV rows for the same device should agree anyway).
        # ------------------------------------------------------------------
        devices: dict[str, dict] = {}
        unrecognized_models: set[str] = set()
        for row in rows:
            serial = row.get("serial number", "")
            model = row.get("model name", "")
            device_name = row.get("device name", "")
            if not serial:
                continue
            category = _categorize_model(model)
            if category is None:
                if model:
                    unrecognized_models.add(model)
                continue
            key = serial.upper()
            if key not in devices:
                devices[key] = {
                    "serial": serial,
                    "model": model,
                    "device_name": device_name,
                    "category": category,
                }

        if unrecognized_models:
            if verbose:
                self.log_warning(
                    "Unrecognized Model Name prefix(es), excluded from audit: "
                    + ", ".join(sorted(unrecognized_models))
                )
            else:
                self.log_info(
                    f"{len(unrecognized_models)} unrecognized Model Name prefix(es) "
                    "excluded from audit (enable Verbose Logging to list them)."
                )

        in_scope = [d for d in devices.values() if d["category"] in selected_categories]
        self.log_info(
            f"{len(devices)} unique device(s) found in CSV across all recognized categories; "
            f"{len(in_scope)} in the selected scope."
        )
        if not in_scope:
            self.log_info("Nothing in scope to audit.")
            return

        # ------------------------------------------------------------------
        # Look up existing Asset serials in NetBox (one query, matched
        # case-insensitively in Python since Asset.serial casing is not
        # guaranteed to match the vendor portal's).
        # ------------------------------------------------------------------
        existing_upper = {
            s.strip().upper()
            for s in Asset.objects.exclude(serial__isnull=True).exclude(serial__exact="")
            .values_list("serial", flat=True)
            if s
        }

        stats = {c: {"checked": 0, "found": 0, "missing": 0} for c in selected_categories}
        missing_by_category: dict[str, list[dict]] = {c: [] for c in selected_categories}

        for d in in_scope:
            cat = d["category"]
            stats[cat]["checked"] += 1
            if d["serial"].upper() in existing_upper:
                stats[cat]["found"] += 1
                if verbose:
                    self.log_info(
                        f"[FOUND] serial={d['serial']} model={d['model']} "
                        f"device_name={d['device_name'] or '(blank)'}"
                    )
            else:
                stats[cat]["missing"] += 1
                missing_by_category[cat].append(d)

        # ------------------------------------------------------------------
        # Report
        # ------------------------------------------------------------------
        for cat in selected_categories:
            missing = missing_by_category[cat]
            if not missing:
                continue
            self.log_warning(f"MISSING FROM NETBOX — {CATEGORY_LABELS[cat]} ({len(missing)}):")
            for d in sorted(missing, key=lambda x: x["serial"]):
                self.log_warning(
                    f"  serial={d['serial']}  model={d['model']}  "
                    f"device_name={d['device_name'] or '(blank)'}"
                )

        summary_lines = [f"\n{'='*60}", "AUDIT COMPLETE", f"{'='*60}"]
        for cat in selected_categories:
            s = stats[cat]
            summary_lines.append(
                f"  {CATEGORY_LABELS[cat]:<45}: "
                f"checked={s['checked']:<5} found={s['found']:<5} missing={s['missing']}"
            )
        summary_lines.append("=" * 5)
        self.log_info("\n".join(summary_lines))
