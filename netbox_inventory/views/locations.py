from netbox.views import generic
from utilities.query import count_related
from utilities.views import register_model_view

from .. import filtersets, forms, models, tables

__all__ = (
    'InstalledAtLocationView',
    'InstalledAtLocationListView',
    'InstalledAtLocationEditView',
    'InstalledAtLocationDeleteView',
    'InstalledAtLocationBulkImportView',
    'InstalledAtLocationBulkEditView',
    'InstalledAtLocationBulkDeleteView',
)


@register_model_view(models.InstalledAtLocation)
class InstalledAtLocationView(generic.ObjectView):
    queryset = models.InstalledAtLocation.objects.select_related('manufacturer').prefetch_related('sites')

    def get_extra_context(self, request, instance):
        return {
            'asset_count': models.Asset.objects.filter(installed_at=instance).count(),
        }


@register_model_view(models.InstalledAtLocation, 'list', path='', detail=False)
class InstalledAtLocationListView(generic.ObjectListView):
    queryset = models.InstalledAtLocation.objects.select_related(
        'manufacturer'
    ).prefetch_related('sites').annotate(
        asset_count=count_related(models.Asset, 'installed_at'),
    )
    table = tables.InstalledAtLocationTable
    filterset = filtersets.InstalledAtLocationFilterSet
    filterset_form = forms.InstalledAtLocationFilterForm


@register_model_view(models.InstalledAtLocation, 'edit')
@register_model_view(models.InstalledAtLocation, 'add', detail=False)
class InstalledAtLocationEditView(generic.ObjectEditView):
    queryset = models.InstalledAtLocation.objects.all()
    form = forms.InstalledAtLocationForm


@register_model_view(models.InstalledAtLocation, 'delete')
class InstalledAtLocationDeleteView(generic.ObjectDeleteView):
    queryset = models.InstalledAtLocation.objects.all()


@register_model_view(models.InstalledAtLocation, 'bulk_import', path='import', detail=False)
class InstalledAtLocationBulkImportView(generic.BulkImportView):
    queryset = models.InstalledAtLocation.objects.all()
    model_form = forms.InstalledAtLocationImportForm


@register_model_view(models.InstalledAtLocation, 'bulk_edit', path='edit', detail=False)
class InstalledAtLocationBulkEditView(generic.BulkEditView):
    queryset = models.InstalledAtLocation.objects.all()
    filterset = filtersets.InstalledAtLocationFilterSet
    table = tables.InstalledAtLocationTable
    form = forms.InstalledAtLocationBulkEditForm


@register_model_view(models.InstalledAtLocation, 'bulk_delete', path='delete', detail=False)
class InstalledAtLocationBulkDeleteView(generic.BulkDeleteView):
    queryset = models.InstalledAtLocation.objects.all()
    filterset = filtersets.InstalledAtLocationFilterSet
    table = tables.InstalledAtLocationTable
