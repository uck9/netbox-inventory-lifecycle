from netbox.views.generic import ObjectListView, ObjectEditView, ObjectDeleteView, ObjectView, ObjectChildrenView, \
    BulkImportView, BulkDeleteView, BulkEditView
from utilities.views import ViewTab, register_model_view, GetRelatedModelsMixin
from django.db.models import Count
from .. import filtersets, forms, models, tables




__all__ = (
    # Vendor
    'ContractVendorListView',
    'ContractVendorView',
    'ContractVendorEditView',
    'ContractVendorBulkEditView',
    'ContractVendorDeleteView',
    'ContractVendorBulkDeleteView',

    # ContractSKU
    'ContractSKUListView',
    'ContractSKUView',
    'ContractSKUEditView',
    'ContractSKUBulkEditView',
    'ContractSKUDeleteView',
    'ContractSKUBulkDeleteView',

    # Contract
    'ContractListView',
    'ContractView',
    'ContractEditView',
    'ContractBulkEditView',
    'ContractDeleteView',
    'ContractBulkDeleteView',
    'ContractAssignmentsView',

    # ContractAssignment
    'ContractAssignmentListView',
    'ContractAssignmentView',
    'ContractAssignmentEditView',
    'ContractAssignmentDeleteView',
    'ContractAssignmentBulkEditView',
    'ContractAssignmentBulkDeleteView',
)


@register_model_view(models.ContractVendor, 'list', path='', detail=False)
class ContractVendorListView(ObjectListView):
    queryset = models.ContractVendor.objects.all()
    table = tables.ContractVendorTable
    filterset = filtersets.ContractVendorFilterSet
    filterset_form = forms.ContractVendorFilterForm


@register_model_view(models.ContractVendor)
class ContractVendorView(GetRelatedModelsMixin, ObjectView):
    queryset = models.ContractVendor.objects.all()

    def get_extra_context(self, request, instance):
        assignments = models.ContractAssignment.objects.filter(
            contract__vendor=instance
        )
        return {
            'related_models': self.get_related_models(
                request, instance, extra=[(assignments, 'contract_id')]
            ),
        }


@register_model_view(models.ContractVendor, 'edit')
@register_model_view(models.ContractVendor, 'add', detail=False)
class ContractVendorEditView(ObjectEditView):
    queryset = models.ContractVendor.objects.all()
    form = forms.ContractVendorForm


@register_model_view(models.ContractVendor, 'bulk_edit')
class ContractVendorBulkEditView(BulkEditView):
    queryset = models.ContractVendor.objects.all()
    filterset = filtersets.ContractVendorFilterSet
    table = tables.ContractVendorTable
    form = forms.ContractVendorBulkEditForm


@register_model_view(models.Contract, 'bulk_import', path='import', detail=False)
class ContractBulkImportView(BulkImportView):
    queryset = models.Contract.objects.all()
    model_form = forms.ContractImportForm
    template_name = 'netbox_inventory/contract_bulk_import.html'


@register_model_view(models.ContractVendor, 'delete')
class ContractVendorDeleteView(ObjectDeleteView):
    queryset = models.ContractVendor.objects.all()


@register_model_view(models.ContractVendor, 'bulk_delete')
class ContractVendorBulkDeleteView(BulkDeleteView):
    queryset = models.ContractVendor.objects.all()
    filterset = filtersets.ContractVendorFilterSet
    table = tables.ContractVendorTable


#
# Contract SKUs
#

@register_model_view(models.ContractSKU, 'list', path='', detail=False)
class ContractSKUListView(ObjectListView):
    queryset = models.ContractSKU.objects.all()
    table = tables.ContractSKUTable
    filterset = filtersets.ContractSKUFilterSet
    filterset_form = forms.ContractSKUFilterForm


@register_model_view(models.ContractSKU)
class ContractSKUView(GetRelatedModelsMixin, ObjectView):
    queryset = models.ContractSKU.objects.all()

    def get_extra_context(self, request, instance):
        return {
            'related_models': self.get_related_models(
                request, instance
            ),
        }


@register_model_view(models.ContractSKU, 'add', detail=False)
@register_model_view(models.ContractSKU, 'edit')
class ContractSKUEditView(ObjectEditView):
    queryset = models.ContractSKU.objects.all()
    form = forms.ContractSKUForm


@register_model_view(models.ContractSKU, 'bulk_edit', detail=False)
class ContractSKUBulkEditView(BulkEditView):
    queryset = models.ContractSKU.objects.all()
    filterset = filtersets.ContractSKUFilterSet
    table = tables.ContractSKUTable
    form = forms.ContractSKUBulkEditForm


@register_model_view(models.ContractSKU, 'delete')
class ContractSKUDeleteView(ObjectDeleteView):
    queryset = models.ContractSKU.objects.all()
    filterset = filtersets.ContractSKUFilterSet
    table = tables.ContractSKUTable


@register_model_view(models.ContractSKU, 'bulk_delete')
class ContractSKUBulkDeleteView(BulkDeleteView):
    queryset = models.ContractSKU.objects.all()
    filterset = filtersets.ContractSKUFilterSet
    table = tables.ContractSKUTable


#
# Contracts
#

@register_model_view(models.Contract, name='list', detail=False)
class ContractListView(ObjectListView):
    queryset = models.Contract.objects.annotate(
        asset_count=Count('assignments__asset', distinct=True),
    )
    table = tables.ContractTable
    filterset = filtersets.ContractFilterSet
    filterset_form = forms.ContractFilterForm
    actions = {
        'add': {'add'},
        'export': {'view'},
        'edit': {'change'},
        'delete': {'delete'},
        'bulk_edit': {'change'},
        'bulk_delete': {'delete'},
    }


@register_model_view(models.Contract)
class ContractView(ObjectView):
    queryset = models.Contract.objects.all()


@register_model_view(models.Contract, name='assignments')
class ContractAssignmentsView(ObjectChildrenView):
    template_name = 'netbox_inventory/contract/assignments.html'
    queryset = models.Contract.objects.all()
    child_model = models.ContractAssignment
    table = tables.ContractAssignmentTable
    filterset = filtersets.ContractAssignmentFilterSet
    actions = {
        'add': {'add'},
        'edit': {'change'},
        'delete': {'delete'},
        'bulk_edit': {'change'},
        'bulk_delete': {'delete'},
    }
    tab = ViewTab(
        label='Assignments',
        badge=lambda obj: models.ContractAssignment.objects.filter(contract=obj).count(),
    )

    def get_children(self, request, parent):
        return self.child_model.objects.filter(contract=parent)


@register_model_view(models.Contract, 'add', detail=False)
@register_model_view(models.Contract, 'edit')
class ContractEditView(ObjectEditView):
    queryset = models.Contract.objects.all()
    form = forms.ContractForm


@register_model_view(models.Contract, 'bulk_edit', detail=False)
class ContractBulkEditView(BulkEditView):
    queryset = models.Contract.objects.all()
    filterset = filtersets.ContractFilterSet
    table = tables.ContractTable
    form = forms.ContractBulkEditForm


@register_model_view(models.Contract, 'delete')
class ContractDeleteView(ObjectDeleteView):
    queryset = models.Contract.objects.all()


@register_model_view(models.Contract, 'bulk_delete')
class ContractBulkDeleteView(BulkDeleteView):
    queryset = models.Contract.objects.all()
    filterset = filtersets.ContractFilterSet
    table = tables.ContractTable


#
# Contract Assignments
#

@register_model_view(models.ContractAssignment, name='list')
class ContractAssignmentListView(ObjectListView):
    queryset = models.ContractAssignment.objects.all()
    table = tables.ContractAssignmentTable
    filterset = filtersets.ContractAssignmentFilterSet
    filterset_form = forms.ContractAssignmentFilterForm
    actions = {
        'add': {'add'},
        'export': {'view'},
        'edit': {'change'},
        'delete': {'delete'},
        'bulk_edit': {'change'},
        'bulk_delete': {'delete'},
    }


@register_model_view(models.ContractAssignment)
class ContractAssignmentView(ObjectView):
    queryset = models.ContractAssignment.objects.all()


@register_model_view(models.ContractAssignment, 'add', detail=False)
@register_model_view(models.ContractAssignment, 'edit')
class ContractAssignmentEditView(ObjectEditView):
    template_name = 'netbox_inventory/contractassignment_edit.html'
    queryset = models.ContractAssignment.objects.all()
    form = forms.ContractAssignmentForm


@register_model_view(models.ContractAssignment, 'bulk_edit', detail=False)
class ContractAssignmentBulkEditView(BulkEditView):
    queryset = models.ContractAssignment.objects.all()
    filterset = filtersets.ContractAssignmentFilterSet
    table = tables.ContractAssignmentTable
    form = forms.ContractAssignmentBulkEditForm


@register_model_view(models.ContractAssignment, 'delete')
class ContractAssignmentDeleteView(ObjectDeleteView):
    queryset = models.ContractAssignment.objects.all()


@register_model_view(models.ContractAssignment, 'bulk_delete')
class ContractAssignmentBulkDeleteView(BulkDeleteView):
    queryset = models.ContractAssignment.objects.all()
    filterset = filtersets.ContractAssignmentFilterSet
    table = tables.ContractAssignmentTable
