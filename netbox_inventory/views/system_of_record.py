from django.template import Context

from netbox.object_actions import BulkExport
from netbox.plugins import get_plugin_config
from netbox.views import generic
from utilities.views import ViewTab, register_model_view

from .. import filtersets, forms, models, tables

__all__ = (
    'AssetSystemOfRecordListView',
    'AssetSystemOfRecordView',
    'AssetSORTabView',
)

# System of Record records are maintained via the REST API only. Only list,
# detail (plus NetBox's automatic changelog/journal tabs) and the asset tab
# are registered here — deliberately no add/edit/delete/import/bulk views.


@register_model_view(models.AssetSystemOfRecord, 'list', path='', detail=False)
class AssetSystemOfRecordListView(generic.ObjectListView):
    queryset = models.AssetSystemOfRecord.objects.select_related('asset')
    filterset = filtersets.AssetSystemOfRecordFilterSet
    filterset_form = forms.AssetSystemOfRecordFilterForm
    table = tables.AssetSystemOfRecordTable
    actions = (BulkExport,)


@register_model_view(models.AssetSystemOfRecord)
class AssetSystemOfRecordView(generic.ObjectView):
    queryset = models.AssetSystemOfRecord.objects.select_related('asset')
    actions = ()


@register_model_view(models.Asset, name='system-of-record', path='system-of-record')
class AssetSORTabView(generic.ObjectView):
    """'System of Record' tab on the Asset detail page."""
    queryset = models.Asset.objects.all()
    template_name = 'netbox_inventory/asset/system_of_record.html'

    tab = ViewTab(
        label='System of Record',
        badge=lambda asset: asset.sor_records.count(),
        hide_if_empty=True,
        permission='netbox_inventory.view_assetsystemofrecord',
        weight=520,
    )

    def get_extra_context(self, request, instance):
        qs = models.AssetSystemOfRecord.objects.restrict(request.user, 'view').filter(asset=instance)
        sor_table = tables.AssetSystemOfRecordForAssetTable(qs)
        sor_table.configure(request)
        # inc/table.html doesn't set table.context; ActionsColumn needs the
        # request to resolve permissions (see AssetLicenseTabView).
        sor_table.context = Context({'request': request})
        return {
            'sor_table': sor_table,
            'sor_stale_days': get_plugin_config('netbox_inventory', 'sor_stale_days'),
        }
