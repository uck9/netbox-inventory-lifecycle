from netbox.views.generic import (
    ObjectListView,
    ObjectEditView,
    ObjectDeleteView,
    ObjectView,
    BulkEditView,
    BulkDeleteView,
)
from netbox_inventory.filtersets import HardwareLifecycleFilterSet
from netbox_inventory.forms import (
    HardwareLifecycleFilterForm,
    HardwareLifecycleBulkEditForm,
)
from netbox_inventory.forms.models import HardwareLifecycleForm
from netbox_inventory.models import HardwareLifecycle
from netbox_inventory.tables import HardwareLifecycleTable
from utilities.views import register_model_view


__all__ = (
    'HardwareLifecycleListView',
    'HardwareLifecycleView',
    'HardwareLifecycleEditView',
    'HardwareLifecycleBulkEditView',
    'HardwareLifecycleDeleteView',
    'HardwareLifecycleBulkDeleteView',
)


@register_model_view(HardwareLifecycle, name='list')
class HardwareLifecycleListView(ObjectListView):
    queryset = HardwareLifecycle.objects.all()
    table = HardwareLifecycleTable
    filterset = HardwareLifecycleFilterSet
    filterset_form = HardwareLifecycleFilterForm


@register_model_view(HardwareLifecycle)
class HardwareLifecycleView(ObjectView):
    queryset = HardwareLifecycle.objects.all()

    def get_extra_context(self, request, instance):

        return {}


@register_model_view(HardwareLifecycle, 'edit')
class HardwareLifecycleEditView(ObjectEditView):
    queryset = HardwareLifecycle.objects.all()
    form = HardwareLifecycleForm


@register_model_view(HardwareLifecycle, 'bulk_edit')
class HardwareLifecycleBulkEditView(BulkEditView):
    queryset = HardwareLifecycle.objects.all()
    filterset = HardwareLifecycleFilterSet
    table = HardwareLifecycleTable
    form = HardwareLifecycleBulkEditForm


@register_model_view(HardwareLifecycle, 'delete')
class HardwareLifecycleDeleteView(ObjectDeleteView):
    queryset = HardwareLifecycle.objects.all()


@register_model_view(HardwareLifecycle, 'bulk_delete')
class HardwareLifecycleBulkDeleteView(BulkDeleteView):
    queryset = HardwareLifecycle.objects.all()
    filterset = HardwareLifecycleFilterSet
    table = HardwareLifecycleTable