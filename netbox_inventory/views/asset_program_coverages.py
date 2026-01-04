from __future__ import annotations

from django.urls import reverse

from netbox.views.generic import ObjectListView

from ..models import AssetProgramCoverage
from ..filtersets import AssetProgramCoverageFilterSet
from ..tables import AssetProgramCoverageTable


class AssetProgramCoverageTabbedListView(ObjectListView):
    queryset = AssetProgramCoverage.objects.all().select_related("asset", "program")
    table = AssetProgramCoverageTable
    filterset = AssetProgramCoverageFilterSet
    template_name = "netbox_inventory/assetprogramcoverage_list.html"

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
        qs = super().get_queryset(request)
        scope = self._get_scope(request)
        status_value = self.SCOPE_TO_STATUS[scope]
        if status_value:
            qs = qs.filter(status=status_value)
        return qs

    def get_extra_context(self, request, **kwargs):
        scope = self._get_scope(request)
        show_filters = self._get_show_filters(request)

        # Preserve all filters across tabs, but normalize scope/show_filters
        params = request.GET.copy()
        params.pop("scope", None)
        params.pop("show_filters", None)
        params.pop("status", None) 
        preserved = params.urlencode()

        base_url = reverse("plugins:netbox_inventory:assetprogramcoverage_tabbed")

        def build_url(new_scope: str, *, open_filters: bool = False) -> str:
            # Keep other filters, but remove scope/status/show_filters so tabs control those
            params = request.GET.copy()
            params.pop("scope", None)
            params.pop("status", None)
            params.pop("show_filters", None)

            # Force scope into the URL every time
            params["scope"] = new_scope

            if open_filters:
                params["show_filters"] = "1"

            qs = params.urlencode()
            return f"{base_url}?{qs}" if qs else base_url


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
        }
