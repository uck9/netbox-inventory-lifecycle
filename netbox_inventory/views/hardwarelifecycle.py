from django.contrib.contenttypes.models import ContentType

from netbox.views.generic import (
    BulkDeleteView,
    BulkEditView,
    BulkImportView,
    ObjectDeleteView,
    ObjectEditView,
    ObjectListView,
    ObjectView,
)
from utilities.views import register_model_view

from netbox_inventory.filtersets import HardwareLifecycleFilterSet
from netbox_inventory.forms import (
    HardwareLifecycleBulkEditForm,
    HardwareLifecycleFilterForm,
    HardwareLifecycleImportForm,
)
from netbox_inventory.forms.bulk_import import resolve_lifecycle_object
from netbox_inventory.forms.models import HardwareLifecycleForm
from netbox_inventory.models import HardwareLifecycle
from netbox_inventory.tables import HardwareLifecycleTable

__all__ = (
    'HardwareLifecycleListView',
    'HardwareLifecycleView',
    'HardwareLifecycleEditView',
    'HardwareLifecycleBulkEditView',
    'HardwareLifecycleBulkImportView',
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


@register_model_view(HardwareLifecycle, 'bulk_import', detail=False)
class HardwareLifecycleBulkImportView(BulkImportView):
    queryset = HardwareLifecycle.objects.all()
    model_form = HardwareLifecycleImportForm

    def create_and_update_objects(self, form, request):
        # Rows without an id update the existing lifecycle record for their
        # device/module type (there can only be one), so EoX data can be
        # re-imported without first looking up record IDs.
        for record in form.cleaned_data['data']:
            if record.get('id'):
                continue
            obj, error = resolve_lifecycle_object(
                record.get('manufacturer'), record.get('device_type'), record.get('module_type'),
            )
            if error:
                continue  # Reported by the model form's own validation
            existing = HardwareLifecycle.objects.filter(
                assigned_object_type=ContentType.objects.get_for_model(obj),
                assigned_object_id=obj.pk,
            ).values_list('pk', flat=True).first()
            if existing:
                record['id'] = existing
        return super().create_and_update_objects(form, request)


@register_model_view(HardwareLifecycle, 'delete')
class HardwareLifecycleDeleteView(ObjectDeleteView):
    queryset = HardwareLifecycle.objects.all()


@register_model_view(HardwareLifecycle, 'bulk_delete')
class HardwareLifecycleBulkDeleteView(BulkDeleteView):
    queryset = HardwareLifecycle.objects.all()
    filterset = HardwareLifecycleFilterSet
    table = HardwareLifecycleTable
