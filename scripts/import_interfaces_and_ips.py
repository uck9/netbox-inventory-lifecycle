"""
Import Interfaces & IP Addresses — NetBox Script

Bulk-creates Interfaces and IP Addresses from a pasted (or uploaded) CSV, for
associating IPs to devices that were imported without them and need their
management/primary IPs set up.

CSV format
----------
Required columns:
  device            Exact device name. Must resolve to exactly one existing
                     Device — ambiguous or unmatched names fail the row.
  interface_name    Name of the interface to create (e.g. "GigabitEthernet0/1").
  interface_type    A valid NetBox interface type slug (e.g. "1000base-t",
                     "10gbase-x-sfpp", "virtual"). See Device Type > Interfaces
                     in NetBox, or dcim.choices.InterfaceTypeChoices, for the
                     full list of valid values.
  ip_address_cidr   IP address WITH mask, e.g. "10.0.0.1/24" or "2001:db8::1/64".

Optional columns:
  vrf               VRF name. If given, must match exactly one existing VRF.
                     Leave blank for the global (no-VRF) table.
  dns_name          Set directly on the IP address record.
  tags              Existing tag SLUGS, separated by "|" (pipe). Chosen over
                     comma since commas are the CSV field delimiter and pipe
                     is not a valid character in a NetBox tag slug. Unknown
                     slugs are skipped with a warning — tags are never
                     auto-created here (they'd get an arbitrary color/no
                     real definition).
  primary_ip        true/false (also accepts yes/no, 1/0). If true, this IP
                     is set as the device's primary IPv4 or IPv6 address
                     (based on the address family). If more than one row for
                     the same device + address family requests primary_ip,
                     only the first is honored; later ones are created
                     normally but the primary flag is ignored and reported.

Example CSV:
  device,interface_name,interface_type,ip_address_cidr,vrf,dns_name,tags,primary_ip
  sw01,Vlan1,virtual,10.10.1.5/24,,sw01.example.com,mgmt|core,true
  sw01,GigabitEthernet0/1,1000base-t,10.10.2.1/30,CUSTOMER-A,,wan,false

Row-handling rules
-------------------
  - If an interface with the same name already exists on the device, the
    row is SKIPPED and reported as a conflict (not touched, not reused) —
    resolve those manually.
  - If a matching IP address (same address + VRF) already exists:
      - unassigned                -> attached to the new interface
      - already on this interface -> no-op (idempotent re-run)
      - assigned elsewhere        -> row SKIPPED and reported as a conflict
  - All lookups (device, vrf, tags) are validated before anything is
    written; a bad row is skipped individually and does not block the rest
    of the CSV.

Script parameters
------------------
  dry_run          preview without writing to the database (default True —
                    this script creates/modifies records in bulk)
  csv_text         paste CSV data directly (either this or csv_file required)
  csv_file         upload a .csv file instead of pasting
  verbose          log every row considered, including skips (can be noisy)
"""
from __future__ import annotations

import csv
import io
import ipaddress
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from utilities.exceptions import AbortRequest

from dcim.choices import InterfaceTypeChoices
from dcim.models import Device, Interface
from extras.models import Tag
from extras.scripts import BooleanVar, FileVar, Script, TextVar
from ipam.models import VRF, IPAddress, Prefix

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_HEADERS = ("device", "interface_name", "interface_type", "ip_address_cidr")
OPTIONAL_HEADERS = ("vrf", "dns_name", "tags", "primary_ip")
TAG_DELIMITER = "|"
TRUE_VALUES = {"true", "yes", "y", "1"}
FALSE_VALUES = {"false", "no", "n", "0", ""}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_bool(value: str, script: Script, row_num: int, field: str) -> Optional[bool]:
    v = (value or "").strip().lower()
    if v in TRUE_VALUES:
        return True
    if v in FALSE_VALUES:
        return False
    script.log_warning(f"Row {row_num}: unrecognized value '{value}' for {field} — treating as false.")
    return False


def _check_prefix_mask_mismatch(
    ip_iface: "ipaddress._BaseAddress",
    vrf: Optional[VRF],
    row_num: int,
    script: Script,
) -> bool:
    """
    Look up the most specific existing Prefix (same VRF) that contains this
    IP's host address. If one exists and its mask length differs from the
    mask supplied in the CSV, log a warning for manual review. This is
    advisory only — the IP is still created with the mask as supplied.
    Returns True if a mismatch was found/logged.
    """
    host_bits = 32 if ip_iface.version == 4 else 128
    best_prefix = (
        Prefix.objects
        .filter(vrf=vrf, prefix__net_contains_or_equals=f"{ip_iface.ip}/{host_bits}")
        .order_by("-prefix__net_mask_length")
        .first()
    )
    if best_prefix is None:
        return False

    supplied_mask = ip_iface.network.prefixlen
    existing_mask = best_prefix.prefix.prefixlen
    if supplied_mask == existing_mask:
        return False

    vrf_note = f" in VRF '{vrf}'" if vrf else " in the global table"
    script.log_warning(
        f"Row {row_num}: MASK MISMATCH — IP '{ip_iface.ip}' supplied as /{supplied_mask} "
        f"falls within existing prefix {best_prefix.prefix}{vrf_note} (/{existing_mask}). "
        "The IP will still be created with the mask as supplied — please review."
    )
    return True


def _read_csv_rows(data: dict, script: Script) -> Optional[list[dict]]:
    """
    Return parsed CSV rows as dicts (normalised, stripped header keys), or
    None (with an error already logged) if the input is missing/invalid.
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
            f"Required: {', '.join(REQUIRED_HEADERS)}. Optional: {', '.join(OPTIONAL_HEADERS)}."
        )
        return None

    rows = []
    for row in reader:
        normalized = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items() if k}
        rows.append(normalized)
    return rows


# ---------------------------------------------------------------------------
# Row resolution — validates a single row and resolves all FK lookups.
# Returns a "plan" dict on success, or None (with an error logged) on failure.
# ---------------------------------------------------------------------------

def _resolve_row(
    row: dict,
    row_num: int,
    device_cache: dict,
    vrf_cache: dict,
    claimed_interfaces: set,
    claimed_ips: set,
    script: Script,
) -> Optional[dict]:
    device_name = row.get("device", "")
    interface_name = row.get("interface_name", "")
    interface_type = row.get("interface_type", "").strip().lower()
    cidr = row.get("ip_address_cidr", "")
    vrf_name = row.get("vrf", "")
    dns_name = row.get("dns_name", "")
    tags_raw = row.get("tags", "")
    primary_raw = row.get("primary_ip", "")

    if not device_name:
        script.log_failure(f"Row {row_num}: missing device.")
        return None
    if not interface_name:
        script.log_failure(f"Row {row_num}: missing interface_name.")
        return None

    # --- device ---
    if device_name not in device_cache:
        matches = list(Device.objects.filter(name__iexact=device_name))
        if len(matches) == 0:
            device_cache[device_name] = None
        elif len(matches) > 1:
            script.log_failure(
                f"Row {row_num}: device '{device_name}' is ambiguous "
                f"({len(matches)} devices match) — skipping."
            )
            device_cache[device_name] = None
        else:
            device_cache[device_name] = matches[0]
    device = device_cache[device_name]
    if device is None:
        if device_name in device_cache:
            script.log_failure(f"Row {row_num}: device '{device_name}' not found — skipping.")
        return None

    # --- interface_type ---
    if interface_type not in InterfaceTypeChoices.values():
        script.log_failure(
            f"Row {row_num}: invalid interface_type '{row.get('interface_type', '')}' "
            f"for device '{device_name}'. See dcim.choices.InterfaceTypeChoices for valid values."
        )
        return None

    # --- existing interface conflict check (DB + earlier rows in this same CSV) ---
    iface_key = (device.pk, interface_name.lower())
    if iface_key in claimed_interfaces or Interface.objects.filter(device=device, name=interface_name).exists():
        script.log_warning(
            f"Row {row_num}: interface '{interface_name}' already exists on device "
            f"'{device_name}' (or is created by an earlier row in this CSV) — "
            "skipping row (not modified)."
        )
        return None
    claimed_interfaces.add(iface_key)

    # --- ip_address_cidr ---
    ip_iface = None
    if cidr:
        if "/" not in cidr:
            script.log_failure(
                f"Row {row_num}: ip_address_cidr '{cidr}' is missing a mask "
                "(expected e.g. '10.0.0.1/24') — skipping."
            )
            return None
        try:
            ip_iface = ipaddress.ip_interface(cidr)
        except ValueError as exc:
            script.log_failure(f"Row {row_num}: invalid ip_address_cidr '{cidr}': {exc} — skipping.")
            return None

    # --- primary_ip ---
    primary_ip = _parse_bool(primary_raw, script, row_num, "primary_ip")
    if primary_ip and not cidr:
        script.log_failure(
            f"Row {row_num}: primary_ip=true but ip_address_cidr is blank — skipping."
        )
        return None

    # --- vrf ---
    vrf = None
    if vrf_name:
        if vrf_name not in vrf_cache:
            matches = list(VRF.objects.filter(name__iexact=vrf_name))
            if len(matches) == 0:
                vrf_cache[vrf_name] = None
            elif len(matches) > 1:
                script.log_failure(
                    f"Row {row_num}: vrf '{vrf_name}' is ambiguous "
                    f"({len(matches)} VRFs match) — skipping."
                )
                vrf_cache[vrf_name] = None
            else:
                vrf_cache[vrf_name] = matches[0]
        vrf = vrf_cache[vrf_name]
        if vrf is None:
            script.log_failure(f"Row {row_num}: vrf '{vrf_name}' not found — skipping.")
            return None

    # --- prefix mask mismatch check (advisory only, does not block the row) ---
    mask_mismatch = False
    if ip_iface:
        mask_mismatch = _check_prefix_mask_mismatch(ip_iface, vrf, row_num, script)

    # --- tags ---
    tag_objs = []
    if tags_raw:
        ipaddress_ct = ContentType.objects.get_for_model(IPAddress)
        for slug in (s.strip() for s in tags_raw.split(TAG_DELIMITER)):
            if not slug:
                continue
            tag = Tag.objects.filter(slug=slug).first()
            if not tag:
                script.log_warning(
                    f"Row {row_num}: tag slug '{slug}' not found — skipping that tag."
                )
                continue
            if tag.object_types.exists() and not tag.object_types.filter(pk=ipaddress_ct.pk).exists():
                script.log_warning(
                    f"Row {row_num}: tag '{slug}' is not enabled for IP addresses "
                    "(restricted to other object types) — skipping that tag."
                )
                continue
            tag_objs.append(tag)

    # --- existing IP conflict check (DB + earlier rows in this same CSV) ---
    existing_ip = None
    if cidr:
        ip_key = (cidr, vrf.pk if vrf else None)
        if ip_key in claimed_ips:
            script.log_warning(
                f"Row {row_num}: IP '{cidr}' is already claimed by an earlier row "
                "in this CSV — skipping row (not modified)."
            )
            return None
        existing_ip = IPAddress.objects.filter(address=cidr, vrf=vrf).first()
        if existing_ip and existing_ip.assigned_object_id is not None:
            script.log_warning(
                f"Row {row_num}: IP '{cidr}' already exists and is assigned to "
                f"{existing_ip.assigned_object} — skipping row (not modified)."
            )
            return None
        claimed_ips.add(ip_key)

    return {
        "row_num": row_num,
        "device": device,
        "interface_name": interface_name,
        "interface_type": interface_type,
        "cidr": cidr,
        "ip_version": ip_iface.version if ip_iface else None,
        "vrf": vrf,
        "dns_name": dns_name,
        "tags": tag_objs,
        "primary_ip": primary_ip,
        "existing_ip": existing_ip,
        "mask_mismatch": mask_mismatch,
    }


# ---------------------------------------------------------------------------
# Main Script
# ---------------------------------------------------------------------------


class ImportInterfacesAndIPs(Script):
    class Meta:
        name = "Inventory: Import Interfaces & IP Addresses from CSV"
        description = (
            "Bulk-creates interfaces and IP addresses on devices from a pasted or "
            "uploaded CSV, optionally setting the primary IP. See script source "
            "docstring for the full CSV format."
        )

    dry_run = BooleanVar(
        default=True,
        label="Dry Run",
        description="Preview without writing to the database.",
    )

    csv_text = TextVar(
        required=False,
        label="CSV Data",
        description=(
            "Paste CSV data here. Required columns: device, interface_name, "
            "interface_type, ip_address_cidr. Optional: vrf, dns_name, "
            "tags (pipe '|' separated slugs), primary_ip (true/false)."
        ),
    )

    csv_file = FileVar(
        required=False,
        label="CSV File",
        description="Alternative to pasting CSV Data above — upload a .csv file instead.",
    )

    verbose = BooleanVar(
        default=False,
        label="Verbose Logging",
        description="Log every row considered, including successful skips (can be noisy).",
    )

    # -----------------------------------------------------------------------

    @transaction.atomic
    def run(self, data, commit):
        do_commit = bool(commit) and not data["dry_run"]
        verbose = bool(data.get("verbose", False))

        rows = _read_csv_rows(data, self)
        if rows is None:
            return
        if not rows:
            self.log_info("CSV contained no data rows.")
            return

        self.log_info(f"Parsed {len(rows)} row(s) from CSV.")

        # ------------------------------------------------------------------
        # Resolve + validate every row up front (read-only)
        # ------------------------------------------------------------------
        device_cache: dict[str, Optional[Device]] = {}
        vrf_cache: dict[str, Optional[VRF]] = {}
        claimed_interfaces: set[tuple[int, str]] = set()
        claimed_ips: set[tuple[str, Optional[int]]] = set()
        plans = []
        for i, row in enumerate(rows):
            row_num = i + 2  # account for header row, 1-indexed
            plan = _resolve_row(
                row, row_num, device_cache, vrf_cache, claimed_interfaces, claimed_ips, self
            )
            if plan:
                plans.append(plan)

        skipped_at_validation = len(rows) - len(plans)
        mask_mismatch_count = sum(1 for p in plans if p["mask_mismatch"])

        # ------------------------------------------------------------------
        # Resolve duplicate primary_ip requests within this CSV — first one
        # for a given (device, address family) wins, others are demoted.
        # ------------------------------------------------------------------
        seen_primary: set[tuple[int, int]] = set()
        for plan in plans:
            if not plan["primary_ip"]:
                continue
            key = (plan["device"].pk, plan["ip_version"])
            if key in seen_primary:
                self.log_warning(
                    f"Row {plan['row_num']}: another row already claims primary_ip for "
                    f"device '{plan['device']}' (IPv{plan['ip_version']}) — primary flag "
                    "ignored for this row; the interface/IP are still created."
                )
                plan["primary_ip"] = False
            else:
                seen_primary.add(key)

        if not plans:
            self.log_info("Nothing to do — no rows passed validation.")
            return

        # ------------------------------------------------------------------
        # Create
        # ------------------------------------------------------------------
        stats = {
            "interfaces_created": 0,
            "ips_created": 0,
            "ips_attached_existing": 0,
            "primary_set": 0,
            "validation_errors": 0,
        }

        for plan in plans:
            device = plan["device"]
            row_num = plan["row_num"]

            interface = Interface(
                device=device,
                name=plan["interface_name"],
                type=plan["interface_type"],
            )
            try:
                interface.full_clean()
            except ValidationError as exc:
                stats["validation_errors"] += 1
                self.log_failure(f"Row {row_num}: interface validation error: {exc}")
                continue

            self.log_success(
                f"{'[DRY RUN] Would create' if not do_commit else 'Created'} "
                f"interface '{plan['interface_name']}' (type={plan['interface_type']}) "
                f"on device '{device}'."
            )
            if do_commit:
                interface.save()
            stats["interfaces_created"] += 1

            if not plan["cidr"]:
                if verbose:
                    self.log_info(f"Row {row_num}: no ip_address_cidr — interface only.")
                continue

            existing_ip = plan["existing_ip"]
            if existing_ip:
                # Unassigned IP that already exists — attach it.
                ip_obj = existing_ip
                ip_obj.assigned_object = interface
                if plan["dns_name"]:
                    ip_obj.dns_name = plan["dns_name"]
                action = "attach existing"
            else:
                ip_obj = IPAddress(
                    address=plan["cidr"],
                    vrf=plan["vrf"],
                    dns_name=plan["dns_name"],
                    status="active",
                    assigned_object=interface,
                )
                action = "create"

            if do_commit:
                try:
                    ip_obj.full_clean()
                except ValidationError as exc:
                    stats["validation_errors"] += 1
                    self.log_failure(f"Row {row_num}: IP address validation error: {exc}")
                    continue
                ip_obj.save()
                if plan["tags"]:
                    try:
                        ip_obj.tags.set(plan["tags"])
                    except (ValidationError, AbortRequest) as exc:
                        self.log_warning(
                            f"Row {row_num}: could not apply tags to IP '{plan['cidr']}': {exc}"
                        )
            else:
                if plan["tags"] and verbose:
                    tag_names = ", ".join(t.slug for t in plan["tags"])
                    self.log_info(f"Row {row_num}: would apply tags: {tag_names}")

            self.log_success(
                f"{'[DRY RUN] Would ' + action if not do_commit else action.capitalize() + 'd'} "
                f"IP '{plan['cidr']}'"
                + (f" vrf={plan['vrf']}" if plan["vrf"] else "")
                + f" -> interface '{plan['interface_name']}' on '{device}'."
            )
            if existing_ip:
                stats["ips_attached_existing"] += 1
            else:
                stats["ips_created"] += 1

            if plan["primary_ip"]:
                field = "primary_ip4" if plan["ip_version"] == 4 else "primary_ip6"
                self.log_success(
                    f"{'[DRY RUN] Would set' if not do_commit else 'Set'} "
                    f"'{plan['cidr']}' as {field} for device '{device}'."
                )
                if do_commit:
                    setattr(device, field, ip_obj)
                    device.save()
                stats["primary_set"] += 1

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        self.log_info(
            f"\n{'='*60}\n"
            f"IMPORT COMPLETE {'(DRY RUN — no changes written)' if not do_commit else ''}\n"
            f"  Rows parsed              : {len(rows)}\n"
            f"  Rows skipped (validation): {skipped_at_validation}\n"
            f"  Interfaces created       : {stats['interfaces_created']}\n"
            f"  IPs created              : {stats['ips_created']}\n"
            f"  IPs attached (existing)  : {stats['ips_attached_existing']}\n"
            f"  Primary IPs set          : {stats['primary_set']}\n"
            f"  Prefix mask mismatches   : {mask_mismatch_count} (see warnings above — review these)\n"
            f"  Validation errors        : {stats['validation_errors']}\n"
            f"{'='*60}"
        )
