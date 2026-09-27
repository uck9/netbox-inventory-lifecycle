"""
Associate Assets to Devices by Serial Number — NetBox Script

Finds Devices with no associated Asset (dcim.Device.assigned_asset is null)
and, for each, looks for an unassigned Asset with a matching device_type and
serial number. When exactly one match is found, the asset is associated to
the device (asset.device = device).

This is a cleanup/reconciliation script for cases where Assets and Devices
were created independently (e.g. imported separately, or an Asset row was
added after the Device already existed) and never linked.

Matching rules
--------------
  - Device.device_type must equal Asset.device_type
  - Device.serial must equal Asset.serial (case-insensitive, trimmed)
  - Only Assets with kind='device' are considered (device_type set, and not
    already assigned to another device — asset.device_id is null)
  - Devices that already have an assigned_asset are skipped entirely
  - Devices with a blank serial are skipped (nothing to match on)
  - If more than one unassigned Asset matches the same (device_type, serial)
    pair, the match is skipped and reported — this indicates a data quality
    issue (duplicate serials) that needs manual review rather than a script
    guessing which one is correct.

Filters
-------
Scope can be narrowed by device, device_type, and/or site (all optional,
combinable). Filters apply to the candidate Device queryset.

Script parameters
------------------
  dry_run             preview associations without writing to the database
                       (default True — this script defaults to dry-run since
                       it mutates existing Assets in bulk)
  device_filter        limit to specific devices
  device_type_filter    limit to specific device types
  site_filter          limit to devices in selected sites
  verbose              per-device log lines for non-matches too
"""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from dcim.models import Device, DeviceType, Site
from extras.scripts import BooleanVar, MultiObjectVar, Script

from netbox_inventory.models import Asset

# ---------------------------------------------------------------------------
# Main Script
# ---------------------------------------------------------------------------


class AssociateAssetsBySerial(Script):
    class Meta:
        name = "Inventory: Associate Assets to Devices by Serial Number"
        description = (
            "Finds devices with no linked asset and, where an unassigned asset "
            "with the same device type and serial number exists, associates it. "
            "Supports dry-run preview and filtering by device, device type, and site."
        )

    dry_run = BooleanVar(
        default=True,
        label="Dry Run",
        description="Preview associations without writing to the database.",
    )

    device_filter = MultiObjectVar(
        model=Device,
        required=False,
        label="Devices",
        description=(
            "Limit to these specific devices. "
            "Leave blank to consider all devices (subject to other active filters)."
        ),
    )

    device_type_filter = MultiObjectVar(
        model=DeviceType,
        required=False,
        label="Device Types",
        description=(
            "Limit to devices of these device types. "
            "Leave blank to consider all device types."
        ),
    )

    site_filter = MultiObjectVar(
        model=Site,
        required=False,
        label="Sites",
        description="Limit to devices in these sites. Leave blank to consider all sites.",
    )

    verbose = BooleanVar(
        default=False,
        label="Verbose Logging",
        description="Log every device considered, including non-matches (can be noisy).",
    )

    # -----------------------------------------------------------------------

    @transaction.atomic
    def run(self, data, commit):
        do_commit = bool(commit) and not data["dry_run"]
        verbose = bool(data.get("verbose", False))

        # ------------------------------------------------------------------
        # Build candidate Device queryset: no linked asset
        # ------------------------------------------------------------------
        device_qs = (
            Device.objects
            .select_related("device_type", "site")
            .filter(assigned_asset__isnull=True)
        )

        selected_devices = data.get("device_filter")
        if selected_devices:
            device_qs = device_qs.filter(pk__in=[d.pk for d in selected_devices])
            self.log_info(
                f"Device filter active — limiting to {selected_devices.count()} specific device(s)."
            )

        selected_device_types = data.get("device_type_filter")
        if selected_device_types:
            device_qs = device_qs.filter(device_type__in=selected_device_types)
            dt_names = ", ".join(dt.model for dt in selected_device_types)
            self.log_info(f"Device type filter active — limiting to: {dt_names}")

        selected_sites = data.get("site_filter")
        if selected_sites:
            device_qs = device_qs.filter(site__in=selected_sites)
            site_names = ", ".join(s.name for s in selected_sites)
            self.log_info(f"Site filter active — limiting to: {site_names}")

        devices = list(device_qs)
        self.log_info(f"Found {len(devices)} device(s) with no linked asset.")

        # Warn if specific devices were silently dropped (already have an asset,
        # or filtered out by another active filter)
        if selected_devices:
            requested_pks = {d.pk for d in selected_devices}
            returned_pks = {d.pk for d in devices}
            dropped = requested_pks - returned_pks
            if dropped:
                self.log_warning(
                    f"{len(dropped)} selected device(s) excluded — already have a "
                    "linked asset, or filtered out by another active filter."
                )

        devices_with_serial = [d for d in devices if (d.serial or "").strip()]
        skipped_no_serial = len(devices) - len(devices_with_serial)
        if skipped_no_serial:
            self.log_info(
                f"Skipping {skipped_no_serial} device(s) with no serial number "
                "(nothing to match on)."
            )

        if not devices_with_serial:
            self.log_info("Nothing to do.")
            return

        # ------------------------------------------------------------------
        # Build a (device_type_id, serial) -> [unassigned assets] map, scoped
        # to just the device types we actually need, to avoid loading every
        # unassigned asset in the database.
        # ------------------------------------------------------------------
        device_type_ids = {d.device_type_id for d in devices_with_serial}

        unassigned_assets = (
            Asset.objects
            .select_related("device_type")
            .filter(
                device_type_id__in=device_type_ids,
                device__isnull=True,
            )
            .exclude(serial__isnull=True)
            .exclude(serial__exact="")
        )

        asset_map: dict[tuple[int, str], list[Asset]] = {}
        for asset in unassigned_assets:
            key = (asset.device_type_id, asset.serial.strip().upper())
            asset_map.setdefault(key, []).append(asset)

        # ------------------------------------------------------------------
        # Match + associate
        # ------------------------------------------------------------------
        stats = {
            "matched": 0,
            "associated": 0,
            "no_match": 0,
            "ambiguous": 0,
            "validation_errors": 0,
        }

        for device in devices_with_serial:
            key = (device.device_type_id, device.serial.strip().upper())
            candidates = asset_map.get(key) or []

            if not candidates:
                stats["no_match"] += 1
                if verbose:
                    self.log_info(
                        f"[NO_MATCH] device={device.pk} '{device}' "
                        f"type={device.device_type} serial={device.serial} — "
                        "no unassigned asset with matching type + serial."
                    )
                continue

            if len(candidates) > 1:
                stats["ambiguous"] += 1
                self.log_warning(
                    f"[AMBIGUOUS] device={device.pk} '{device}' "
                    f"type={device.device_type} serial={device.serial} — "
                    f"{len(candidates)} unassigned assets match "
                    f"(asset ids: {', '.join(str(a.pk) for a in candidates)}). "
                    "Skipping — resolve the duplicate serials manually."
                )
                continue

            stats["matched"] += 1
            asset = candidates[0]

            self.log_success(
                f"{'[DRY RUN] Would associate' if not do_commit else 'Associating'} "
                f"asset={asset.pk} '{asset}' -> device={device.pk} '{device}' "
                f"(type={device.device_type}, serial={device.serial})"
            )

            if do_commit:
                asset.device = device
                try:
                    asset.full_clean()
                except ValidationError as exc:
                    stats["validation_errors"] += 1
                    self.log_failure(
                        f"asset={asset.pk} '{asset}' -> device={device.pk} '{device}': "
                        f"validation error: {exc}"
                    )
                    continue
                asset.save()

            stats["associated"] += 1
            # Remove from the map so a duplicate-serial device later in this
            # run can't be matched to an asset we've already claimed.
            asset_map[key] = []

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        self.log_info(
            f"\n{'='*60}\n"
            f"ASSOCIATION COMPLETE {'(DRY RUN — no changes written)' if not do_commit else ''}\n"
            f"  Devices checked        : {len(devices_with_serial)}\n"
            f"  Devices skipped (no serial): {skipped_no_serial}\n"
            f"  Matches found          : {stats['matched']}\n"
            f"  Associated             : {stats['associated']}\n"
            f"  No match               : {stats['no_match']}\n"
            f"  Ambiguous (skipped)    : {stats['ambiguous']}\n"
            f"  Validation errors      : {stats['validation_errors']}\n"
            f"{'='*60}"
        )
