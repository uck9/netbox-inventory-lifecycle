from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from dcim.models import DeviceType
from extras.models import CustomField
from extras.scripts import Script, BooleanVar, IntegerVar

from netbox_inventory.models import Asset, VendorProgram, AssetProgramCoverage, HardwareLifecycle
from netbox_inventory.choices import (
    ProgramCoverageStatusChoices,
    ProgramEligibilityChoices,
    ProgramCoverageSourceChoices,
)

CISCO_NAME = "Cisco"
PROGRAM_SLUG = "cisco-enterprise-agreement"

EXPECTED_DEVICETYPE_CFS = {
    "ea_eligible": "boolean",
    "ea_exclusion_reason": "text",
}


@dataclass(frozen=True)
class Eval:
    eligibility: str
    reason: str
    eos: Optional[timezone.datetime]  # actually a date


def assert_required_custom_fields(script: Script) -> None:
    """
    NetBox 4.5: CustomField uses object_types M2M to ContentType.
    Fail fast if required DeviceType custom fields are missing or wrong type.
    """
    missing = []
    wrong_type = []

    for name, expected_type in EXPECTED_DEVICETYPE_CFS.items():
        cf = CustomField.objects.filter(
            name=name,
            object_types__app_label="dcim",
            object_types__model="devicetype",
        ).first()

        if not cf:
            missing.append(name)
            continue

        if cf.type != expected_type:
            wrong_type.append((name, cf.type, expected_type))

    if missing:
        script.log_failure(
            "Missing required DeviceType Custom Fields: "
            f"{', '.join(missing)}. "
            "Create them under Admin → Custom Fields before running this job."
        )
        raise RuntimeError("Required DeviceType custom fields not configured.")

    if wrong_type:
        details = "; ".join([f"{n} is '{got}' expected '{exp}'" for (n, got, exp) in wrong_type])
        script.log_failure("DeviceType Custom Field type mismatch: " + details)
        raise RuntimeError("Required DeviceType custom fields have incorrect types.")


def _devicetype_cf(dt: DeviceType) -> dict:
    return getattr(dt, "custom_field_data", None) or {}


def _get_dt_lifecycle(dt: DeviceType) -> Optional[HardwareLifecycle]:
    """
    HardwareLifecycle is a Generic FK. For device types, assigned_object is DeviceType.
    """
    ct = ContentType.objects.get_for_model(DeviceType)
    return HardwareLifecycle.objects.filter(
        assigned_object_type=ct,
        assigned_object_id=dt.id,
    ).first()


def evaluate_asset(asset: Asset) -> Eval:
    """
    Policy:
      - Ledger includes all Cisco Assets that have device_type set (i.e. "device assets").
      - DeviceType CF ea_eligible=False -> INELIGIBLE w/ exclusion reason.
      - If no HardwareLifecycle record -> assume supported -> ELIGIBLE.
      - Else use end_of_support: <= today -> INELIGIBLE; > today -> ELIGIBLE.
    """
    today = timezone.localdate()

    if not asset.device_type_id:
        return Eval(
            eligibility=ProgramEligibilityChoices.UNKNOWN,
            reason="No DeviceType on Asset (cannot evaluate)",
            eos=None,
        )

    dt = asset.device_type
    cf = _devicetype_cf(dt)

    if not bool(cf.get("ea_eligible", False)):
        reason = (cf.get("ea_exclusion_reason") or "").strip() or "DeviceType excluded from EA"
        return Eval(
            eligibility=ProgramEligibilityChoices.INELIGIBLE,
            reason=f"DeviceType excluded: {reason}",
            eos=None,
        )

    lifecycle = _get_dt_lifecycle(dt)
    if not lifecycle:
        return Eval(
            eligibility=ProgramEligibilityChoices.ELIGIBLE,
            reason="No HardwareLifecycle record (assumed supported)",
            eos=None,
        )

    eos = lifecycle.end_of_support
    if not eos:
        return Eval(
            eligibility=ProgramEligibilityChoices.ELIGIBLE,
            reason="HardwareLifecycle missing end_of_support (assumed supported)",
            eos=None,
        )

    if eos <= today:
        return Eval(
            eligibility=ProgramEligibilityChoices.INELIGIBLE,
            reason=f"Past End of Support (EOS: {eos})",
            eos=eos,
        )

    return Eval(
        eligibility=ProgramEligibilityChoices.ELIGIBLE,
        reason=f"Supported until {eos}",
        eos=eos,
    )


class SyncCiscoAssetsToEALedger(Script):
    class Meta:
        name = "EA Ledger: Sync Cisco assets into Cisco Enterprise Agreement"
        description = (
            "Ensures every Cisco device_type-based Asset has a current AssetProgramCoverage row "
            "in the Cisco EA program ledger. Eligibility computed from DeviceType CF ea_eligible "
            "and HardwareLifecycle end_of_support. Adds verbose per-asset logging when enabled."
        )

    dry_run = BooleanVar(
        default=True,
        description="If enabled, no database changes are written.",
    )

    update_existing = BooleanVar(
        default=True,
        description="If enabled, recompute eligibility/status/reason for existing current rows too.",
    )

    verbose = BooleanVar(
        default=False,
        description="Log per-asset computed EA configuration (can be noisy).",
    )

    log_limit = IntegerVar(
        default=200,
        description="Max number of per-asset log lines when verbose is enabled.",
    )

    @transaction.atomic
    def run(self, data, commit):
        # Fail fast if required DeviceType CFs aren't configured correctly
        assert_required_custom_fields(self)

        do_commit = bool(commit) and (not data["dry_run"])
        now = timezone.now()
        today = timezone.localdate()

        verbose = bool(data.get("verbose", False))
        log_limit = int(data.get("log_limit", 200))
        logged = 0

        def vlog(msg: str) -> None:
            nonlocal logged
            if not verbose or logged >= log_limit:
                return
            self.log_info(msg)
            logged += 1

        try:
            program = VendorProgram.objects.get(slug=PROGRAM_SLUG)
        except VendorProgram.DoesNotExist:
            self.log_failure(f"VendorProgram slug='{PROGRAM_SLUG}' not found.")
            return

        qs = (
            Asset.objects
            .select_related("device_type__manufacturer")
            .filter(device_type__manufacturer__name__iexact=CISCO_NAME)
        )

        total = qs.count()
        self.log_info(f"Ledger syncing {total} Cisco assets into '{PROGRAM_SLUG}'...")
        if verbose:
            self.log_info(f"Verbose logging enabled (limit={log_limit}).")

        created = updated = unchanged = failed = 0

        for asset in qs.iterator(chunk_size=500):
            coverage, was_created = AssetProgramCoverage.objects.get_or_create(
                program=program,
                asset=asset,
                effective_end__isnull=True,  # matches your partial unique constraint for "current"
                defaults={
                    "status": ProgramCoverageStatusChoices.PLANNED,
                    "eligibility": ProgramEligibilityChoices.UNKNOWN,
                    "source": ProgramCoverageSourceChoices.SYNC,
                    "last_synced": now,
                },
            )

            orig_status = coverage.status
            orig_elig = coverage.eligibility
            orig_reason = coverage.decision_reason
            orig_end = coverage.effective_end

            if was_created:
                created += 1

            if (not was_created) and (not data["update_existing"]):
                action = "SKIP"
                vlog(
                    f"[{action}] asset={asset.pk} '{asset}' "
                    f"elig={orig_elig} status={orig_status} end={orig_end} "
                    f"{'(DRY RUN)' if not do_commit else ''}"
                )
                unchanged += 1
                continue

            r = evaluate_asset(asset)
            changed = False

            # Eligibility
            if coverage.eligibility != r.eligibility:
                coverage.eligibility = r.eligibility
                changed = True

            # Decision reason (100 chars max)
            desired_reason = (r.reason or "")[:100]
            if coverage.decision_reason != desired_reason:
                coverage.decision_reason = desired_reason
                changed = True

            # Source + sync time
            if coverage.source != ProgramCoverageSourceChoices.SYNC:
                coverage.source = ProgramCoverageSourceChoices.SYNC
                changed = True

            coverage.last_synced = now

            # Status enforcement (safe)
            if r.eligibility == ProgramEligibilityChoices.INELIGIBLE:
                if coverage.status == ProgramCoverageStatusChoices.ACTIVE:
                    coverage.status = ProgramCoverageStatusChoices.TERMINATED
                    coverage.effective_end = coverage.effective_end or r.eos or today
                    changed = True
                else:
                    # NOTE: This assumes your guardrails allow EXCLUDED + INELIGIBLE.
                    if coverage.status not in (
                        ProgramCoverageStatusChoices.EXCLUDED,
                        ProgramCoverageStatusChoices.TERMINATED,
                    ):
                        coverage.status = ProgramCoverageStatusChoices.EXCLUDED
                        changed = True

            action = "CREATE" if was_created else ("UPDATE" if changed else "NOCHANGE")
            eos_txt = str(r.eos) if r.eos else "-"
            vlog(
                f"[{action}] asset={asset.pk} '{asset}' "
                f"elig: {orig_elig}->{coverage.eligibility} "
                f"status: {orig_status}->{coverage.status} "
                f"end: {orig_end}->{coverage.effective_end} "
                f"eos={eos_txt} "
                f"reason='{coverage.decision_reason}' "
                f"{'(DRY RUN)' if not do_commit else ''}"
            )

            if not changed:
                unchanged += 1
                continue

            # Validate + save
            try:
                coverage.full_clean()
            except ValidationError as e:
                failed += 1
                self.log_failure(
                    f"{asset}: validation failed: {e}. "
                    f"(computed elig={coverage.eligibility}, status={coverage.status}, eos={eos_txt})"
                )
                # revert in-memory changes for safety (not strictly required, but keeps logs sane)
                coverage.status = orig_status
                coverage.eligibility = orig_elig
                coverage.decision_reason = orig_reason
                coverage.effective_end = orig_end
                continue

            if do_commit:
                coverage.save()

            updated += 1

        self.log_info(
            f"Done. created={created}, updated={updated}, unchanged={unchanged}, failed={failed}, "
            f"commit={'yes' if do_commit else 'no (dry run)'}"
        )

        if verbose and logged >= log_limit:
            self.log_info(f"Verbose log limit reached ({log_limit}). Increase log_limit to see more.")
