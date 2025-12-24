from netbox.views import generic
from utilities.query import count_related
from utilities.views import register_model_view

from .. import filtersets, forms, models, tables

__all__ = (
    'OrderView',
    'OrderListView',
    'OrderEditView',
    'OrderDeleteView',
    'OrderBulkImportView',
    'OrderBulkEditView',
    'OrderBulkDeleteView',
)


@register_model_view(models.Order)
class OrderView(generic.ObjectView):
    queryset = models.Order.objects.all()

    def get_extra_context(self, request, instance):
        return {
            'asset_count': models.Asset.objects.filter(order=instance).count(),
        }


@register_model_view(models.Order, 'list', path='', detail=False)
class OrderListView(generic.ObjectListView):
    queryset = models.Order.objects.annotate(
        asset_count=count_related(models.Asset, 'order'),
    )
    table = tables.OrderTable
    filterset = filtersets.OrderFilterSet
    filterset_form = forms.OrderFilterForm


@register_model_view(models.Order, 'edit')
@register_model_view(models.Order, 'add', detail=False)
class OrderEditView(generic.ObjectEditView):
    queryset = models.Order.objects.all()
    form = forms.OrderForm


@register_model_view(models.Order, 'delete')
class OrderDeleteView(generic.ObjectDeleteView):
    queryset = models.Order.objects.all()


@register_model_view(models.Order, 'bulk_import', path='import', detail=False)
class OrderBulkImportView(generic.BulkImportView):
    queryset = models.Order.objects.all()
    model_form = forms.OrderImportForm


@register_model_view(models.Order, 'bulk_edit', path='edit', detail=False)
class OrderBulkEditView(generic.BulkEditView):
    queryset = models.Order.objects.all()
    filterset = filtersets.OrderFilterSet
    table = tables.OrderTable
    form = forms.OrderBulkEditForm


@register_model_view(models.Order, 'bulk_delete', path='delete', detail=False)
class OrderBulkDeleteView(generic.BulkDeleteView):
    queryset = models.Order.objects.all()
    filterset = filtersets.OrderFilterSet
    table = tables.OrderTable
