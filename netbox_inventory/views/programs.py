from datetime import date

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_tables2 import RequestConfig

from netbox.views.generic import (
    ObjectDeleteView,
    ObjectEditView,
    ObjectListView,
    ObjectView,
)
from utilities.views import register_model_view

from ..choices import ProgramCoverageStatusChoices, ProgramEligibilityChoices
from ..filtersets import AssetProgramCoverageFilterSet, VendorProgramFilterSet
from ..forms.models import AssetProgramCoverageForm, VendorProgramForm
from ..forms.programs import ActivateCoverageForm
from ..models import AssetProgramCoverage, ContractAssignment
from ..models.programs import (
    AssetProgramCoverage,
    VendorProgram,
    _get_asset_manufacturer,
)
from ..tables.programs import (
    AssetProgramCoverageForAssetTable,
    AssetProgramCoverageTable,
    VendorProgramTable,
)

try:
    from ..models import Asset
except Exception:  # pragma: no cover
    from ..models.assets import Asset

__all__ = (
    'VendorProgramListView',
    'VendorProgramView',
    'VendorProgramEditView',
    'VendorProgramDeleteView',
    'AssetProgramCoverageListView',
    'AssetProgramCoverageView',
    'AssetProgramCoverageEditView',
    'AssetProgramCoverageDeleteView',
    'AssetProgramCoverageTabView',
    'AssetProgramCoverageActivateView',
)


#
# VendorProgram
#

class VendorProgramListView(ObjectListView):
    queryset = VendorProgram.objects.all()
    table = VendorProgramTable
    filterset = VendorProgramFilterSet


class VendorProgramView(ObjectView):
    queryset = VendorProgram.objects.all()


class VendorProgramEditView(ObjectEditView):
    queryset = VendorProgram.objects.all()
    form = VendorProgramForm


class VendorProgramDeleteView(ObjectDeleteView):
    queryset = VendorProgram.objects.all()

#
# AssetProgramCoverage
#

class AssetProgramCoverageListView(ObjectListView):
    queryset = AssetProgramCoverage.objects.select_related("asset", "program")
    table = AssetProgramCoverageTable
    filterset = AssetProgramCoverageFilterSet


class AssetProgramCoverageView(ObjectView):
    queryset = AssetProgramCoverage.objects.select_related("asset", "program")


class AssetProgramCoverageEditView(ObjectEditView):
    queryset = AssetProgramCoverage.objects.all()
    form = AssetProgramCoverageForm


class AssetProgramCoverageDeleteView(ObjectDeleteView):
    queryset = AssetProgramCoverage.objects.all()


@register_model_view(Asset, name="program_coverage")
class AssetProgramCoverageTabView(ObjectView):
    """Render Program Coverage as a NetBox-native tab on the Asset detail view."""
    queryset = Asset.objects.all()
    template_name = "netbox_inventory/asset/program_coverage.html"

    def get_extra_context(self, request, instance):
        qs = (
            AssetProgramCoverage.objects.filter(asset=instance)
            .select_related("program")
            .order_by("program__name", "-effective_start", "-created")
        )
        table = AssetProgramCoverageForAssetTable(qs)
        RequestConfig(request, paginate={"per_page": 50}).configure(table)
        return {
            "table": table,
            "add_url": reverse("plugins:netbox_inventory:assetprogramcoverage_add") + f"?asset={instance.pk}",
        }


@register_model_view(AssetProgramCoverage, name="activate", path="activate")
class AssetProgramCoverageActivateView(ObjectView):
    """
    NetBox-native action: /<coverage_pk>/activate/
    Uses a form to create/update ContractAssignment (canonical), then flips coverage ACTIVE.
    """

    def dispatch(self, request, pk):
        coverage = get_object_or_404(AssetProgramCoverage.objects.select_related("asset", "program"), pk=pk)

        if request.method == "POST":
            form = ActivateCoverageForm(request.POST, coverage=coverage)
            if form.is_valid():
                try:
                    self._activate(coverage, form.cleaned_data)
                except ValidationError as e:
                    form.add_error(None, e)
                else:
                    messages.success(request, _("Coverage activated and contract assignment created/updated."))
                    return redirect(coverage.asset.get_absolute_url() + "?tab=program_coverage")
        else:
            form = ActivateCoverageForm(coverage=coverage, initial={"start_date": date.today()})

        return render(request, "netbox_inventory/assetprogramcoverage/activate.html", {
            "object": coverage,
            "form": form,
        })

    def _activate(self, coverage, cleaned):
        # --- Policy checks ---
        if coverage.eligibility == ProgramEligibilityChoices.INELIGIBLE:
            raise ValidationError(_("This record is INELIGIBLE and cannot be activated."))

        program = coverage.program
        program_mfr = getattr(program, "manufacturer", None)
        program_contract_type = getattr(program, "contract_type", None)

        # Manufacturer must be determinable + match (for activation)
        asset_mfr = _get_asset_manufacturer(coverage.asset)
        if program_mfr and asset_mfr is None:
            raise ValidationError(_("Cannot determine asset manufacturer (asset missing device_type/manufacturer)."))
        if program_mfr and asset_mfr and program_mfr.pk != asset_mfr.pk:
            raise ValidationError(_("Program manufacturer does not match asset manufacturer."))

        contract = cleaned["contract"]
        sku = cleaned["sku"]
        start_date = cleaned["start_date"] or date.today()
        end_date = cleaned["end_date"]

        # Enforce contract type matches program
        if program_contract_type and contract.contract_type != program_contract_type:
            raise ValidationError(_("Selected contract type does not match the program's contract type."))

        # Enforce SKU manufacturer matches program
        if program_mfr and sku.manufacturer_id != program_mfr.id:
            raise ValidationError(_("Selected SKU manufacturer does not match the program manufacturer."))

        # If you added sku.contract_type, enforce SKU type matches contract type
        if hasattr(sku, "contract_type") and program_contract_type and sku.contract_type != program_contract_type:
            raise ValidationError(_("Selected SKU type does not match contract/program type."))

        # --- Canonical: create/update ContractAssignment ---
        # You want ONE "current" assignment per asset + contract_type (or per asset+sku).
        # Given your model enforces overlap on asset+sku, simplest is:
        # - end any active assignment of same asset+sku
        # - create a new one
        #
        # If you want "one active assignment per asset+program", add program FK on assignment and key off that.

        # End any existing active assignment for same asset+sku if overlapping
        # (optional; your clean() will already block overlaps)
        assignment = ContractAssignment(
            asset=coverage.asset,
            contract=contract,
            sku=sku,
            start_date=start_date,
            end_date=end_date,
        )
        assignment.full_clean()
        assignment.save()

        # --- Flip coverage status ---
        coverage.status = ProgramCoverageStatusChoices.ACTIVE
        if not coverage.effective_start:
            coverage.effective_start = start_date
        coverage.effective_end = None
        coverage.full_clean()
        coverage.save()
