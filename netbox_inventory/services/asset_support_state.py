from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db.models import Q
from django.utils import timezone

from ..choices import AssetSupportStateChoices, AssetSupportReasonChoices, AssetSupportSourceChoices
from ..models import ContractAssignment


@dataclass(frozen=True)
class SupportResult:
    state: str
    reason: str | None


def _is_active_assignment(a: ContractAssignment, today: date) -> bool:
    # Null dates treated as open-ended
    if a.start_date and a.start_date > today:
        return False
    if a.end_date and a.end_date < today:
        return False
    return True


def compute_asset_support(asset) -> SupportResult:
    """
    Vendor-agnostic:
    - If any active ContractAssignment exists => COVERED (reason None)
    - Else if asset currently marked EXCLUDED => keep EXCLUDED (reason must exist)
    - Else => UNCOVERED with best-effort reason (CONTRACT_MISSING by default)
    """
    today = timezone.now().date()

    # Pull only assignments for this asset. If you support multiple hardware relations,
    # keep this logic here.
    qs = (
        ContractAssignment.objects
        .filter(asset=asset)
        .only("id", "start_date", "end_date", "contract_id", "sku_id", "program_id")
    )

    # Determine if any is active "now"
    has_active = any(_is_active_assignment(a, today) for a in qs)

    if has_active:
        return SupportResult(state=AssetSupportStateChoices.COVERED, reason=None)

    # If the asset is explicitly excluded, keep it excluded (reason enforced by validation)
    if asset.support_state == AssetSupportStateChoices.EXCLUDED:
        return SupportResult(state=AssetSupportStateChoices.EXCLUDED, reason=asset.support_reason)

    # Otherwise uncovered
    return SupportResult(state=AssetSupportStateChoices.UNCOVERED, reason=AssetSupportReasonChoices.CONTRACT_MISSING)


def apply_computed_support(asset, *, save: bool = True) -> bool:
    """
    Applies computed support values to an asset.
    Returns True if changes were made.
    """
    result = compute_asset_support(asset)
    changed = (
        asset.support_state != result.state
        or (asset.support_reason or None) != (result.reason or None)
        or asset.support_source != AssetSupportSourceChoices.COMPUTED
    )

    if not changed:
        # still update validated_at? I’d keep it stable unless changed.
        return False

    asset.support_state = result.state
    asset.support_reason = result.reason
    asset.support_source = AssetSupportSourceChoices.COMPUTED
    asset.touch_support_validated()

    if save:
        asset.full_clean()
        asset.save()

    return True
