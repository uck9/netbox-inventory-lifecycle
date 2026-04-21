import csv
import io
from datetime import date
from itertools import groupby
from operator import attrgetter

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_tables2 import RequestConfig

from netbox.views.generic import (
    ObjectDeleteView,
    ObjectEditView,
    ObjectListView,
    ObjectView,
    BulkDeleteView,
)
from utilities.views import ViewTab, register_model_view

from ..choices import ProgramCoverageStatusChoices, ProgramEligibilityChoices
from ..filtersets import AssetProgramCoverageFilterSet, VendorProgramFilterSet
from ..forms.models import AssetProgramCoverageForm, VendorProgramForm
from ..forms.filters import AssetProgramCoverageFilterForm
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
    'VendorProgramEAReportView',
    'AssetProgramCoverageListView',
    'AssetProgramCoverageView',
    'AssetProgramCoverageEditView',
    'AssetProgramCoverageDeleteView',
    'AssetProgramCoverageActivateView',
    'AssetProgramCoverageBulkDeleteView',
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

    def get_extra_context(self, request, instance):
        coverages = AssetProgramCoverage.objects.filter(program=instance)
        active_count = coverages.filter(
            status=ProgramCoverageStatusChoices.ACTIVE,
            effective_end__isnull=True,
        ).count()
        excluded_eligible_count = coverages.filter(
            status=ProgramCoverageStatusChoices.EXCLUDED,
            eligibility=ProgramEligibilityChoices.ELIGIBLE,
        ).count()
        excluded_ineligible_count = coverages.filter(
            status=ProgramCoverageStatusChoices.EXCLUDED,
            eligibility=ProgramEligibilityChoices.INELIGIBLE,
        ).count()
        terminated_count = coverages.filter(
            status=ProgramCoverageStatusChoices.TERMINATED,
        ).count()
        return {
            "active_count": active_count,
            "excluded_eligible_count": excluded_eligible_count,
            "excluded_ineligible_count": excluded_ineligible_count,
            "terminated_count": terminated_count,
        }


class VendorProgramEditView(ObjectEditView):
    queryset = VendorProgram.objects.all()
    form = VendorProgramForm


class VendorProgramDeleteView(ObjectDeleteView):
    queryset = VendorProgram.objects.all()

#
# AssetProgramCoverage
#

class AssetProgramCoverageListView(ObjectListView):
    queryset = (
        AssetProgramCoverage.objects
        .select_related(
            "asset",
            "program",
            # uncomment if these are used in the table:
            # "asset__device",
            # "asset__site",
        )
    )
    table = AssetProgramCoverageTable
    filterset = AssetProgramCoverageFilterSet
    form = AssetProgramCoverageForm
    filterset_form = AssetProgramCoverageFilterForm
    #template_name = "netbox_inventory/assetprogramcoverage_list.html"


class AssetProgramCoverageView(ObjectView):
    queryset = AssetProgramCoverage.objects.select_related("asset", "program")


class AssetProgramCoverageEditView(ObjectEditView):
    queryset = AssetProgramCoverage.objects.all()
    form = AssetProgramCoverageForm


class AssetProgramCoverageDeleteView(ObjectDeleteView):
    queryset = AssetProgramCoverage.objects.all()


@register_model_view(AssetProgramCoverage, 'bulk_delete', path='delete', detail=False)
class AssetProgramCoverageBulkDeleteView(BulkDeleteView):
    queryset = AssetProgramCoverage.objects.all()
    filterset = AssetProgramCoverageFilterSet
    table = AssetProgramCoverageTable



@register_model_view(AssetProgramCoverage, name="activate", path="activate")
class AssetProgramCoverageActivateView(ObjectView):
    """
    NetBox-native action: /<coverage_pk>/activate/
    Uses a form to create/update ContractAssignment (canonical), then flips coverage ACTIVE.
    """
    EA = "support-ea"

    def dispatch(self, request, pk):
        coverage = get_object_or_404(AssetProgramCoverage.objects.select_related("asset", "program"), pk=pk)

        # EA-only gate
        if getattr(coverage.program, "contract_type", None) != self.EA:
            raise PermissionDenied("Activation is only available for EA contracts.")

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

        return render(request, "netbox_inventory/asset/program_coverage_activate.html", {
            "object": coverage,
            "form": form,
        })

    def _activate(self, coverage, cleaned):
        # --- Policy checks ---
        if coverage.eligibility == ProgramEligibilityChoices.INELIGIBLE:
            raise ValidationError(_("This record is INELIGIBLE and cannot be activated."))

        program = coverage.program
        if getattr(program, "contract_type", None) != self.EA:
            raise ValidationError(_("Activation is only available for EA contracts."))
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
        coverage.activated_via = assignment

        # Guardrail: ACTIVE implies ELIGIBLE
        coverage.eligibility = ProgramEligibilityChoices.ELIGIBLE

        if not coverage.effective_start:
            coverage.effective_start = start_date
        coverage.effective_end = None
        coverage.full_clean()
        coverage.save()


#
# EA Backcharge Report
#

@register_model_view(VendorProgram, name="ea_report", path="ea-report")
class VendorProgramEAReportView(ObjectView):
    """
    Site-based backcharge report for a VendorProgram.

    Lists all ACTIVE coverage records grouped by:
      site → device type → contract SKU / service level

    Supports ?export=csv to download a flat CSV for billing/finance.
    """
    queryset = VendorProgram.objects.all()
    template_name = "netbox_inventory/vendorprogram_ea_report.html"

    tab = ViewTab(label="EA Report", weight=600)

    def get(self, request, pk):
        program = get_object_or_404(VendorProgram, pk=pk)

        coverages = (
            AssetProgramCoverage.objects
            .filter(program=program, status=ProgramCoverageStatusChoices.ACTIVE, effective_end__isnull=True)
            .select_related(
                "asset__device_type__manufacturer",
                "asset__device__site",
                "asset__installed_site_override",
                "asset__rack__site",
                "activated_via__sku",
                "activated_via__contract",
            )
            .order_by()
        )

        # Build rows with resolved site
        rows = []
        for cov in coverages:
            asset = cov.asset
            site = asset.current_site
            device_type = asset.device_type
            sku = getattr(cov.activated_via, "sku", None) if cov.activated_via else None
            contract = getattr(cov.activated_via, "contract", None) if cov.activated_via else None
            rows.append({
                "coverage": cov,
                "asset": asset,
                "site": site,
                "site_name": site.name if site else "— No site —",
                "device_type": device_type,
                "device_type_name": str(device_type) if device_type else "Unknown",
                "sku": sku,
                "sku_name": str(sku) if sku else "—",
                "service_level": getattr(sku, "service_level", "—") if sku else "—",
                "contract": contract,
                "contract_id": getattr(contract, "contract_id", "—") if contract else "—",
                "effective_start": cov.effective_start,
            })

        if request.GET.get("export") == "csv":
            return self._csv_response(program, rows)

        # Group by site for the HTML view
        rows_sorted = sorted(rows, key=lambda r: (r["site_name"], r["device_type_name"], r["sku_name"]))
        site_groups = []
        for site_name, site_rows in groupby(rows_sorted, key=lambda r: r["site_name"]):
            site_rows = list(site_rows)
            dt_groups = []
            for dt_name, dt_rows in groupby(site_rows, key=lambda r: r["device_type_name"]):
                dt_rows = list(dt_rows)
                sku_groups = []
                for sku_name, sku_rows in groupby(dt_rows, key=lambda r: r["sku_name"]):
                    sku_rows = list(sku_rows)
                    sku_groups.append({
                        "sku_name": sku_name,
                        "service_level": sku_rows[0]["service_level"],
                        "count": len(sku_rows),
                    })
                dt_groups.append({"device_type_name": dt_name, "sku_groups": sku_groups, "count": len(dt_rows)})
            site_groups.append({"site_name": site_name, "dt_groups": dt_groups, "count": len(site_rows)})

        return render(request, self.template_name, {
            "object": program,
            "tab": self.tab,
            "site_groups": site_groups,
            "total": len(rows),
            "report_date": date.today(),
        })

    def _csv_response(self, program, rows):
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Program", "Site", "Asset Name", "Serial", "Device Type", "Manufacturer",
            "SKU", "Service Level", "Contract ID", "Effective Start",
        ])
        for r in sorted(rows, key=lambda x: (x["site_name"], x["device_type_name"])):
            asset = r["asset"]
            writer.writerow([
                str(program),
                r["site_name"],
                asset.name or "",
                getattr(asset, "serial", "") or "",
                r["device_type_name"],
                str(asset.device_type.manufacturer) if asset.device_type else "",
                r["sku_name"],
                r["service_level"],
                r["contract_id"],
                r["effective_start"] or "",
            ])

        filename = f"ea-report-{program.slug}-{date.today()}.csv"
        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
