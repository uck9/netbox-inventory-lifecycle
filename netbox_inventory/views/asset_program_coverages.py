from __future__ import annotations

from django.db.models import Count
from django.urls import reverse

from netbox.views.generic import ObjectListView

from ..filtersets import AssetProgramCoverageFilterSet
from ..models import AssetProgramCoverage
from ..tables import AssetProgramCoverageTable


class AssetProgramCoverageTabbedListView(ObjectListView):
    queryset = AssetProgramCoverage.objects.all().select_related("asset", "program")
    table = AssetProgramCoverageTable
    filterset = AssetProgramCoverageFilterSet
    template_name = "netbox_inventory/assetprogramcoverage_tabbed_list.html"

    # Update these to match your actual status values
    SCOPE_TO_STATUS = {
        "all": None,
        "planned": "planned",
        "active": "active",
        "excluded": "excluded",
        "terminated": "terminated",
    }

    def _get_scope(self, request) -> str:
        # Primary: explicit scope param from our tabs
        scope = (request.GET.get("scope") or "").lower().strip()
        if scope in self.SCOPE_TO_STATUS:
            return scope

        # Fallback: user filtered by status directly, map it to a scope
        status = (request.GET.get("status") or "").lower().strip()
        reverse_map = {
            v: k for k, v in self.SCOPE_TO_STATUS.items() if v  # planned/active/...
        }
        if status in reverse_map:
            return reverse_map[status]

        return "all"


    def _get_show_filters(self, request) -> bool:
        return str(request.GET.get("show_filters", "")).lower() in ("1", "true", "yes", "on")


    def get_queryset(self, request):
        """
        Return the list queryset for the page (this drives what rows show in the table).
        NetBox passes `request` into get_queryset() in this view type.
        """
        scope = self._get_scope(request)
        status_value = self.SCOPE_TO_STATUS.get(scope)

        # Start from a fresh base queryset (avoids scope bleed / NetBox internal munging)
        qs = (
            AssetProgramCoverage.objects.all()
            .select_related("asset", "program")
        )

        # Apply scope filter to the LIST results
        if status_value:
            qs = qs.filter(status=status_value)

        return qs


    def get_extra_context(self, request, **kwargs):
        scope = self._get_scope(request)
        show_filters = self._get_show_filters(request)

        base_url = reverse("plugins:netbox_inventory:assetprogramcoverage_tabbed")

        def build_url(new_scope: str, *, open_filters: bool = False) -> str:
            p = request.GET.copy()
            p.pop("scope", None)
            p.pop("status", None)
            p.pop("show_filters", None)

            # always include scope so hover/click reflects it
            p["scope"] = new_scope
            if open_filters:
                p["show_filters"] = "1"

            qs = p.urlencode()
            return f"{base_url}?{qs}" if qs else base_url

        # ---------- COUNTS ----------
        # Strip tab-driving params so counts reflect *global* filters only
        filter_params = request.GET.copy()
        filter_params.pop("scope", None)
        filter_params.pop("status", None)
        filter_params.pop("show_filters", None)

        # IMPORTANT: fresh base queryset (not self.queryset)
        base_qs = (
            AssetProgramCoverage.objects.all()
            .select_related("asset", "program")
        )

        # Apply your filterset to this unscoped base
        fs = self.filterset(filter_params, queryset=base_qs, request=request)
        counted_qs = fs.qs

        rows = list(counted_qs.values("status").annotate(c=Count("id")))
        by_status = {r["status"]: int(r["c"]) for r in rows}

        def count_for(status_value):
            # status_value might be None for "all"
            return int(by_status.get(status_value, 0) or 0)

        tab_counts = {
            "all": int(counted_qs.count()),
            "planned": count_for(self.SCOPE_TO_STATUS["planned"]),
            "active": count_for(self.SCOPE_TO_STATUS["active"]),
            "excluded": count_for(self.SCOPE_TO_STATUS["excluded"]),
            "terminated": count_for(self.SCOPE_TO_STATUS["terminated"]),
        }

        return {
            "active_scope": scope,
            "show_filters": show_filters,
            "tab_urls": {
                "all": build_url("all"),
                "planned": build_url("planned"),
                "active": build_url("active"),
                "excluded": build_url("excluded"),
                "terminated": build_url("terminated"),
                "filters": build_url(scope, open_filters=True),
            },
            "tab_counts": tab_counts,

            # extra debug so you can see what the DB actually holds
            "debug_by_status": by_status,
            "debug_counted_total": int(counted_qs.count()),
            "debug_filter_params": filter_params.urlencode(),
        }
