import logging

from datetime import date as _date
from django.utils import timezone

from django.db.models.signals import post_save, pre_delete, pre_save, post_delete, post_save
from django.dispatch import receiver

from dcim.models import Device, InventoryItem, Module, Rack
from utilities.exceptions import AbortRequest

from .choices import (
    AssetSupportStateChoices,
    ProgramCoverageStatusChoices,
    ProgramEligibilityChoices,
    AssetSupportReasonChoices,
    AssetSupportSourceChoices,
)
from .models import Asset, Order, ContractAssignment, AssetProgramCoverage
from .services.asset_support_state import apply_computed_support
from .utils import get_plugin_setting, get_status_for, is_equal_none

logger = logging.getLogger('netbox.netbox_inventory.signals')


@receiver(pre_save, sender=Device)
@receiver(pre_save, sender=Module)
@receiver(pre_save, sender=InventoryItem)
@receiver(pre_save, sender=Rack)
def prevent_update_serial_asset_tag(instance, **kwargs):
    """
    When a hardware (Device, Module, InventoryItem, Rack) has an Asset assigned and
    user changes serial or asset_tag on hardware, prevent that change
    and inform that change must be made on Asset instance instead.

    Only enforces if `sync_hardware_serial_asset_tag` setting is true.
    """
    try:
        # will raise RelatedObjectDoesNotExist if not set
        asset = instance.assigned_asset
    except Asset.DoesNotExist:
        return
    if not get_plugin_setting('sync_hardware_serial_asset_tag'):
        # don't enforce if sync not enabled
        return
    if instance.pk and (
        not is_equal_none(asset.serial, instance.serial)
        or not is_equal_none(asset.asset_tag, instance.asset_tag)
    ):
        raise AbortRequest(
            f'Cannot change {asset.kind} serial and asset tag if asset is assigned. Please update via inventory > asset instead.'
        )


@receiver(pre_delete, sender=Device)
@receiver(pre_delete, sender=Module)
@receiver(pre_delete, sender=InventoryItem)
@receiver(pre_delete, sender=Rack)
def free_assigned_asset(instance, **kwargs):
    """
    If a hardware (Device, Module, InventoryItem, Rack) has an Asset assigned and
    that hardware is deleted, update Asset.status to stored_status.

    Netbox handles deletion in a DB transaction, so if deletion failes for any
    reason, this status change will also be reverted.
    """
    stored_status = get_status_for('stored')
    if not stored_status:
        return
    try:
        # will raise RelatedObjectDoesNotExist if not set
        asset = instance.assigned_asset
    except Asset.DoesNotExist:
        return
    asset.snapshot()
    asset.status = stored_status
    # also unassign that item from asset
    setattr(asset, asset.kind, None)
    asset.full_clean()
    asset.save(clear_old_hw=False)
    logger.info(f'Asset marked as stored {asset}')


@receiver(post_save, sender=Order)
def handle_order_purchase_change(instance, created, **kwargs):
    """
    Update child Assets if Order Purchase has changed.
    """
    if not created:
        Asset.objects.filter(order=instance).update(purchase=instance.purchase)

def _has_current_matching_assignment(coverage: AssetProgramCoverage) -> bool:
    """
    Does this asset currently have a contract assignment that satisfies ACTIVE rules
    for this coverage's program?
    """
    program = coverage.program
    today = _date.today()

    qs = ContractAssignment.objects.filter(
        asset=coverage.asset,
        contract__contract_type=program.contract_type,
    ).select_related("contract", "sku")

    if program.manufacturer_id:
        qs = qs.filter(sku__manufacturer_id=program.manufacturer_id)

    return any(
        a.effective_start_date and a.effective_start_date <= today <= (a.effective_end_date or _date.max)
        for a in qs
    )


def _reconcile_coverages_for_asset(asset_id: int) -> None:
    coverages = (
        AssetProgramCoverage.objects
        .filter(asset_id=asset_id, status=ProgramCoverageStatusChoices.ACTIVE)
        .select_related("program", "asset")
    )

    today = _date.today()

    for coverage in coverages:
        if _has_current_matching_assignment(coverage):
            continue

        # Downgrade: ACTIVE -> PLANNED + UNKNOWN
        coverage.status = ProgramCoverageStatusChoices.PLANNED
        coverage.eligibility = ProgramEligibilityChoices.UNKNOWN

        # Optional: close out effective period
        if coverage.effective_start and not coverage.effective_end:
            coverage.effective_end = today

        # Avoid recursion issues: save only changed fields
        coverage.save(update_fields=["status", "eligibility", "effective_end"])

def _reconcile_all_for_asset(asset_id: int) -> None:
    _reconcile_coverages_for_asset(asset_id)
    _reconcile_asset_support(asset_id)

def _assignment_is_active(a: ContractAssignment, today: _date) -> bool:
    if a.start_date and a.start_date > today:
        return False
    if a.end_date and a.end_date < today:
        return False
    return True


def _has_any_active_assignment(asset_id: int) -> bool:
    today = timezone.now().date()

    qs = (
        ContractAssignment.objects
        .filter(asset_id=asset_id)
        .only("id", "start_date", "end_date")
    )
    for a in qs:
        if _assignment_is_active(a, today):
            return True
    return False


def _reconcile_asset_support(asset_id: int) -> None:
    """
    Vendor-agnostic support state:
    - If any active assignment exists => COVERED
    - Else => UNCOVERED (unless EXCLUDED is sticky)
    """
    asset = (
        Asset.objects
        .filter(id=asset_id)
        .only("id", "support_state", "support_reason", "support_source", "support_validated_at")
        .first()
    )
    if not asset:
        return

    today = timezone.now().date()
    has_active = _has_any_active_assignment(asset_id)

    # Policy choice: EXCLUDED is sticky (recommended)
    if asset.support_state == AssetSupportStateChoices.EXCLUDED:
        # Still stamp validation/source as computed if you want
        # (or leave source as manual if you want exclusions to remain manual)
        # I’d keep the exclusion "owner intent" as manual if set that way.
        changed_fields = []
        if asset.support_validated_at != today:
            asset.support_validated_at = today
            changed_fields.append("support_validated_at")
        if asset.support_source != AssetSupportSourceChoices.COMPUTED:
            asset.support_source = AssetSupportSourceChoices.COMPUTED
            changed_fields.append("support_source")
        if changed_fields:
            asset.full_clean()
            asset.save(update_fields=changed_fields)
        return

    # Compute new state/reason
    if has_active:
        new_state = AssetSupportStateChoices.COVERED
        new_reason = None
    else:
        new_state = AssetSupportStateChoices.UNCOVERED
        # If reason already set (e.g. coverage_pending), keep it; else default
        new_reason = asset.support_reason or AssetSupportReasonChoices.CONTRACT_MISSING

    changed_fields = []

    if asset.support_state != new_state:
        asset.support_state = new_state
        changed_fields.append("support_state")

    # Normalize blank to None
    if (asset.support_reason or None) != (new_reason or None):
        asset.support_reason = new_reason
        changed_fields.append("support_reason")

    if asset.support_source != AssetSupportSourceChoices.COMPUTED:
        asset.support_source = AssetSupportSourceChoices.COMPUTED
        changed_fields.append("support_source")

    if asset.support_validated_at != today:
        asset.support_validated_at = today
        changed_fields.append("support_validated_at")

    if changed_fields:
        asset.full_clean()
        asset.save(update_fields=changed_fields)


@receiver(post_delete, sender=ContractAssignment)
def contract_assignment_deleted(sender, instance, **kwargs):
    if instance.asset_id:
        _reconcile_all_for_asset(instance.asset_id)


@receiver(post_save, sender=ContractAssignment)
def contract_assignment_saved(sender, instance, **kwargs):
    if instance.asset_id:
        _reconcile_all_for_asset(instance.asset_id)