from django.db.models import Count

from netbox.views import generic
from utilities.views import register_model_view

from .. import filtersets, forms, models, tables

__all__ = (
    # CiscoSmartAccount
    'CiscoSmartAccountListView',
    'CiscoSmartAccountView',
    'CiscoSmartAccountEditView',
    'CiscoSmartAccountDeleteView',
    'CiscoSmartAccountBulkDeleteView',
    # VirtualAccount
    'VirtualAccountListView',
    'VirtualAccountView',
    'VirtualAccountEditView',
    'VirtualAccountDeleteView',
    'VirtualAccountBulkDeleteView',
    # LicenseOrder
    'LicenseOrderListView',
    'LicenseOrderView',
    'LicenseOrderEditView',
    'LicenseOrderDeleteView',
    'LicenseOrderBulkDeleteView',
    # LicenseOrderLineItem
    'LicenseOrderLineItemListView',
    'LicenseOrderLineItemView',
    'LicenseOrderLineItemEditView',
    'LicenseOrderLineItemDeleteView',
    'LicenseOrderLineItemBulkDeleteView',
    # LicenseLineItemAllocation
    'LicenseLineItemAllocationListView',
    'LicenseLineItemAllocationView',
    'LicenseLineItemAllocationEditView',
    'LicenseLineItemAllocationDeleteView',
    'LicenseLineItemAllocationBulkDeleteView',
)


# ---------------------------------------------------------------------------
# CiscoSmartAccount
# ---------------------------------------------------------------------------

@register_model_view(models.CiscoSmartAccount, 'list', path='', detail=False)
class CiscoSmartAccountListView(generic.ObjectListView):
    queryset = models.CiscoSmartAccount.objects.annotate(
        virtual_account_count=Count('virtual_accounts', distinct=True)
    )
    filterset = filtersets.CiscoSmartAccountFilterSet
    filterset_form = forms.CiscoSmartAccountFilterForm
    table = tables.CiscoSmartAccountTable


@register_model_view(models.CiscoSmartAccount)
class CiscoSmartAccountView(generic.ObjectView):
    queryset = models.CiscoSmartAccount.objects.all()

    def get_extra_context(self, request, instance):
        va_table = tables.VirtualAccountTable(
            models.VirtualAccount.objects.filter(smart_account=instance).select_related('site', 'tenant')
        )
        va_table.configure(request)
        return {
            'virtual_accounts_table': va_table,
            'virtual_account_count': instance.virtual_accounts.count(),
        }


@register_model_view(models.CiscoSmartAccount, 'add', detail=False)
@register_model_view(models.CiscoSmartAccount, 'edit')
class CiscoSmartAccountEditView(generic.ObjectEditView):
    queryset = models.CiscoSmartAccount.objects.all()
    form = forms.CiscoSmartAccountForm


@register_model_view(models.CiscoSmartAccount, 'delete')
class CiscoSmartAccountDeleteView(generic.ObjectDeleteView):
    queryset = models.CiscoSmartAccount.objects.all()


@register_model_view(models.CiscoSmartAccount, 'bulk_delete', detail=False)
class CiscoSmartAccountBulkDeleteView(generic.BulkDeleteView):
    queryset = models.CiscoSmartAccount.objects.all()
    filterset = filtersets.CiscoSmartAccountFilterSet
    table = tables.CiscoSmartAccountTable


# ---------------------------------------------------------------------------
# VirtualAccount
# ---------------------------------------------------------------------------

@register_model_view(models.VirtualAccount, 'list', path='', detail=False)
class VirtualAccountListView(generic.ObjectListView):
    queryset = models.VirtualAccount.objects.select_related('smart_account', 'site', 'tenant')
    filterset = filtersets.VirtualAccountFilterSet
    filterset_form = forms.VirtualAccountFilterForm
    table = tables.VirtualAccountTable


@register_model_view(models.VirtualAccount)
class VirtualAccountView(generic.ObjectView):
    queryset = models.VirtualAccount.objects.select_related('smart_account', 'site', 'tenant')

    def get_extra_context(self, request, instance):
        allocations = (
            models.LicenseLineItemAllocation.objects
            .filter(virtual_account=instance)
            .select_related('line_item', 'line_item__license_order')
        )
        allocations_table = tables.LicenseLineItemAllocationTable(allocations)
        allocations_table.configure(request)
        return {
            'allocations_table': allocations_table,
            'allocation_count': allocations.count(),
        }


@register_model_view(models.VirtualAccount, 'add', detail=False)
@register_model_view(models.VirtualAccount, 'edit')
class VirtualAccountEditView(generic.ObjectEditView):
    queryset = models.VirtualAccount.objects.all()
    form = forms.VirtualAccountForm


@register_model_view(models.VirtualAccount, 'delete')
class VirtualAccountDeleteView(generic.ObjectDeleteView):
    queryset = models.VirtualAccount.objects.all()


@register_model_view(models.VirtualAccount, 'bulk_delete', detail=False)
class VirtualAccountBulkDeleteView(generic.BulkDeleteView):
    queryset = models.VirtualAccount.objects.all()
    filterset = filtersets.VirtualAccountFilterSet
    table = tables.VirtualAccountTable


# ---------------------------------------------------------------------------
# LicenseOrder
# ---------------------------------------------------------------------------

@register_model_view(models.LicenseOrder, 'list', path='', detail=False)
class LicenseOrderListView(generic.ObjectListView):
    queryset = models.LicenseOrder.objects.select_related('purchase').annotate(
        line_item_count=Count('line_items', distinct=True)
    )
    filterset = filtersets.LicenseOrderFilterSet
    filterset_form = forms.LicenseOrderFilterForm
    table = tables.LicenseOrderTable


@register_model_view(models.LicenseOrder)
class LicenseOrderView(generic.ObjectView):
    queryset = models.LicenseOrder.objects.select_related('purchase')

    def get_extra_context(self, request, instance):
        line_items = (
            models.LicenseOrderLineItem.objects
            .filter(license_order=instance)
            .prefetch_related('allocations__virtual_account')
        )
        line_items_table = tables.LicenseOrderLineItemTable(line_items)
        line_items_table.configure(request)
        return {
            'line_items_table': line_items_table,
            'line_item_count': line_items.count(),
        }


@register_model_view(models.LicenseOrder, 'add', detail=False)
@register_model_view(models.LicenseOrder, 'edit')
class LicenseOrderEditView(generic.ObjectEditView):
    queryset = models.LicenseOrder.objects.all()
    form = forms.LicenseOrderForm


@register_model_view(models.LicenseOrder, 'delete')
class LicenseOrderDeleteView(generic.ObjectDeleteView):
    queryset = models.LicenseOrder.objects.all()


@register_model_view(models.LicenseOrder, 'bulk_delete', detail=False)
class LicenseOrderBulkDeleteView(generic.BulkDeleteView):
    queryset = models.LicenseOrder.objects.all()
    filterset = filtersets.LicenseOrderFilterSet
    table = tables.LicenseOrderTable


# ---------------------------------------------------------------------------
# LicenseOrderLineItem
# ---------------------------------------------------------------------------

@register_model_view(models.LicenseOrderLineItem, 'list', path='', detail=False)
class LicenseOrderLineItemListView(generic.ObjectListView):
    queryset = models.LicenseOrderLineItem.objects.select_related('license_order')
    filterset = filtersets.LicenseOrderLineItemFilterSet
    filterset_form = forms.LicenseOrderLineItemFilterForm
    table = tables.LicenseOrderLineItemTable


@register_model_view(models.LicenseOrderLineItem)
class LicenseOrderLineItemView(generic.ObjectView):
    queryset = models.LicenseOrderLineItem.objects.select_related('license_order')

    def get_extra_context(self, request, instance):
        allocations = (
            models.LicenseLineItemAllocation.objects
            .filter(line_item=instance)
            .select_related('virtual_account', 'virtual_account__smart_account')
        )
        allocations_table = tables.LicenseLineItemAllocationTable(allocations)
        allocations_table.configure(request)
        return {
            'allocations_table': allocations_table,
            'allocation_count': allocations.count(),
        }


@register_model_view(models.LicenseOrderLineItem, 'add', detail=False)
@register_model_view(models.LicenseOrderLineItem, 'edit')
class LicenseOrderLineItemEditView(generic.ObjectEditView):
    queryset = models.LicenseOrderLineItem.objects.all()
    form = forms.LicenseOrderLineItemForm


@register_model_view(models.LicenseOrderLineItem, 'delete')
class LicenseOrderLineItemDeleteView(generic.ObjectDeleteView):
    queryset = models.LicenseOrderLineItem.objects.all()


@register_model_view(models.LicenseOrderLineItem, 'bulk_delete', detail=False)
class LicenseOrderLineItemBulkDeleteView(generic.BulkDeleteView):
    queryset = models.LicenseOrderLineItem.objects.all()
    filterset = filtersets.LicenseOrderLineItemFilterSet
    table = tables.LicenseOrderLineItemTable


# ---------------------------------------------------------------------------
# LicenseLineItemAllocation
# ---------------------------------------------------------------------------

@register_model_view(models.LicenseLineItemAllocation, 'list', path='', detail=False)
class LicenseLineItemAllocationListView(generic.ObjectListView):
    queryset = models.LicenseLineItemAllocation.objects.select_related(
        'line_item', 'line_item__license_order', 'virtual_account', 'virtual_account__smart_account'
    )
    filterset = filtersets.LicenseLineItemAllocationFilterSet
    filterset_form = forms.LicenseLineItemAllocationFilterForm
    table = tables.LicenseLineItemAllocationTable


@register_model_view(models.LicenseLineItemAllocation)
class LicenseLineItemAllocationView(generic.ObjectView):
    queryset = models.LicenseLineItemAllocation.objects.select_related(
        'line_item', 'line_item__license_order', 'virtual_account', 'virtual_account__smart_account'
    )


@register_model_view(models.LicenseLineItemAllocation, 'add', detail=False)
@register_model_view(models.LicenseLineItemAllocation, 'edit')
class LicenseLineItemAllocationEditView(generic.ObjectEditView):
    queryset = models.LicenseLineItemAllocation.objects.all()
    form = forms.LicenseLineItemAllocationForm


@register_model_view(models.LicenseLineItemAllocation, 'delete')
class LicenseLineItemAllocationDeleteView(generic.ObjectDeleteView):
    queryset = models.LicenseLineItemAllocation.objects.all()


@register_model_view(models.LicenseLineItemAllocation, 'bulk_delete', detail=False)
class LicenseLineItemAllocationBulkDeleteView(generic.BulkDeleteView):
    queryset = models.LicenseLineItemAllocation.objects.all()
    filterset = filtersets.LicenseLineItemAllocationFilterSet
    table = tables.LicenseLineItemAllocationTable
