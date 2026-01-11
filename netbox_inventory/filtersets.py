from functools import reduce

import django_filters
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils.translation import gettext as _

from core.models import ObjectType
from dcim.filtersets import DeviceFilterSet, InventoryItemFilterSet, ModuleFilterSet
from dcim.models import (
    Device,
    DeviceRole,
    DeviceType,
    InventoryItem,
    InventoryItemRole,
    Location,
    Manufacturer,
    Module,
    ModuleType,
    Rack,
    RackRole,
    RackType,
    Site,
)
from netbox.filtersets import NetBoxModelFilterSet
from tenancy.filtersets import ContactModelFilterSet
from tenancy.models import Contact, ContactGroup, Tenant
from utilities import filters
from utilities.filters import ContentTypeFilter, TreeNodeMultipleChoiceFilter

from .choices import (
    AssetStatusChoices,
    ContractStatusChoices,
    ContractTypeChoices,
    HardwareKindChoices,
    ProgramCoverageStatusChoices,
    PurchaseStatusChoices,
)
from .models import *
from .utils import get_asset_custom_fields_search_filters, query_located

__all__ = (
    'AssetFilterSet',
    'AuditFlowFilterSet',
    'AuditFlowPageFilterSet',
    'AuditTrailFilterSet',
    'AuditTrailSourceFilterSet',
    'ContractVendorFilterSet',
    'ContractSKUFilterSet',
    'ContractFilterSet',
    'DeviceAssetFilterSet',
    'HardwareLifecycleFilterSet',
    'InventoryItemAssetFilterSet',
    'InventoryItemGroupFilterSet',
    'InventoryItemTypeFilterSet',
    'ModuleAssetFilterSet',
    'OrderFilterSet',
    'PurchaseFilterSet',
    'SupplierFilterSet',
    'VendorProgramFilterSet',
    'AssetProgramCoverageFilterSet',
    'LicenseSKUFilterSet',
)


#
# Assets
#


class InventoryItemGroupFilterSet(NetBoxModelFilterSet):
    parent_id = django_filters.ModelMultipleChoiceFilter(
        queryset=InventoryItemGroup.objects.all(),
        label='Parent group (ID)',
    )
    ancestor_id = filters.TreeNodeMultipleChoiceFilter(
        queryset=InventoryItemGroup.objects.all(),
        field_name='parent',
        lookup_expr='in',
        label='Inventory item group (ID)',
    )

    class Meta:
        model = InventoryItemGroup
        fields = (
            'id',
            'name',
            'description',
        )

    def search(self, queryset, name, value):
        query = Q(Q(name__icontains=value) | Q(description__icontains=value))
        return queryset.filter(query)


class InventoryItemTypeFilterSet(NetBoxModelFilterSet):
    manufacturer_id = django_filters.ModelMultipleChoiceFilter(
        field_name='manufacturer',
        queryset=Manufacturer.objects.all(),
        label='Manufacturer (ID)',
    )
    manufacturer = django_filters.ModelMultipleChoiceFilter(
        field_name='manufacturer__slug',
        queryset=Manufacturer.objects.all(),
        label='Manufacturer (slug)',
    )
    inventoryitem_group_id = filters.TreeNodeMultipleChoiceFilter(
        field_name='inventoryitem_group',
        queryset=InventoryItemGroup.objects.all(),
        lookup_expr='in',
        label='Inventory item group (ID)',
    )

    class Meta:
        model = InventoryItemType
        fields = (
            'id',
            'manufacturer_id',
            'manufacturer',
            'model',
            'slug',
            'description',
            'part_number',
            'inventoryitem_group_id',
        )

    def search(self, queryset, name, value):
        query = Q(
            Q(model__icontains=value)
            | Q(part_number__icontains=value)
            | Q(description__icontains=value)
        )
        return queryset.filter(query)


class AssetFilterSet(NetBoxModelFilterSet):
    status = django_filters.MultipleChoiceFilter(
        choices=AssetStatusChoices,
    )
    kind = filters.MultiValueCharFilter(
        method='filter_kind',
        label='Type of hardware',
    )
    manufacturer_id = filters.MultiValueCharFilter(
        method='filter_manufacturer',
        label='Manufacturer (ID)',
    )
    manufacturer_name = filters.MultiValueCharFilter(
        method='filter_manufacturer',
        label='Manufacturer (name)',
    )
    device = filters.MultiValueCharFilter(
        field_name='device__name',
        lookup_expr='iexact',
        label='Device (name)',
    )
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device',
        queryset=Device.objects.all(),
        label='Device (ID)',
    )
    device_type_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device_type',
        queryset=DeviceType.objects.all(),
        label='Device type (ID)',
    )
    device_type = filters.MultiValueCharFilter(
        field_name='device_type__slug',
        lookup_expr='iexact',
        label='Device type (slug)',
    )
    device_type_model = filters.MultiValueCharFilter(
        field_name='device_type__model',
        lookup_expr='icontains',
        label='Device type (model)',
    )
    device_role_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__role',
        queryset=DeviceRole.objects.all(),
        label='Device role (ID)',
    )
    device_role = filters.MultiValueCharFilter(
        field_name='device__role__slug',
        lookup_expr='iexact',
        label='Device role (slug)',
    )
    module_id = django_filters.ModelMultipleChoiceFilter(
        field_name='module',
        queryset=Module.objects.all(),
        label='Module (ID)',
    )
    module_type_id = django_filters.ModelMultipleChoiceFilter(
        field_name='module_type',
        queryset=ModuleType.objects.all(),
        label='Module type (ID)',
    )
    module_type_model = filters.MultiValueCharFilter(
        field_name='module_type__model',
        lookup_expr='icontains',
        label='Module type (model)',
    )
    inventoryitem = filters.MultiValueCharFilter(
        field_name='inventoryitem__name',
        lookup_expr='iexact',
        label='Inventory item (name)',
    )
    inventoryitem_id = django_filters.ModelMultipleChoiceFilter(
        field_name='inventoryitem',
        queryset=InventoryItem.objects.all(),
        label='Inventory item (ID)',
    )
    inventoryitem_type_id = django_filters.ModelMultipleChoiceFilter(
        field_name='inventoryitem_type',
        queryset=InventoryItemType.objects.all(),
        label='Inventory item type (ID)',
    )
    inventoryitem_type = filters.MultiValueCharFilter(
        field_name='inventoryitem_type__slug',
        lookup_expr='iexact',
        label='Inventory item type (slug)',
    )
    inventoryitem_type_model = filters.MultiValueCharFilter(
        field_name='inventoryitem_type__model',
        lookup_expr='icontains',
        label='Inventory item type (model)',
    )
    inventoryitem_group_id = filters.TreeNodeMultipleChoiceFilter(
        field_name='inventoryitem_type__inventoryitem_group',
        queryset=InventoryItemGroup.objects.all(),
        lookup_expr='in',
        label='Inventory item group (ID)',
    )
    inventoryitem_group_name = filters.MultiValueCharFilter(
        field_name='inventoryitem_type__inventoryitem_group__name',
        lookup_expr='icontains',
        label='Inventory item group (name)',
    )
    inventoryitem_role_id = django_filters.ModelMultipleChoiceFilter(
        field_name='inventoryitem__role',
        queryset=InventoryItemRole.objects.all(),
        label='Inventory item role (ID)',
    )
    inventoryitem_role = filters.MultiValueCharFilter(
        field_name='inventoryitem__role__slug',
        lookup_expr='iexact',
        label='Inventory item role (slug)',
    )
    rack = filters.MultiValueCharFilter(
        field_name='rack__name',
        lookup_expr='iexact',
        label='Rack (name)',
    )
    rack_id = django_filters.ModelMultipleChoiceFilter(
        field_name='rack',
        queryset=Rack.objects.all(),
        label='Rack (ID)',
    )
    rack_type_id = django_filters.ModelMultipleChoiceFilter(
        field_name='rack_type',
        queryset=RackType.objects.all(),
        label='Rack type (ID)',
    )
    rack_type = filters.MultiValueCharFilter(
        field_name='rack_type__slug',
        lookup_expr='iexact',
        label='Rack type (slug)',
    )
    rack_type_model = filters.MultiValueCharFilter(
        field_name='rack_type__model',
        lookup_expr='icontains',
        label='Rack type (model)',
    )
    rack_role_id = django_filters.ModelMultipleChoiceFilter(
        field_name='rack__role',
        queryset=RackRole.objects.all(),
        label='Rack role (ID)',
    )
    rack_role = filters.MultiValueCharFilter(
        field_name='rack__role__slug',
        lookup_expr='iexact',
        label='Rack role (slug)',
    )
    is_assigned = django_filters.BooleanFilter(
        method='filter_is_assigned',
        label='Is assigned to hardware',
    )
    tenant_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Tenant.objects.all(),
        field_name='tenant',
        label='Tenant (ID)',
    )
    tenant = django_filters.ModelMultipleChoiceFilter(
        queryset=Tenant.objects.all(),
        field_name='tenant__slug',
        to_field_name='slug',
        label='Tenant (slug)',
    )
    tenant_name = filters.MultiValueCharFilter(
        field_name='tenant__name',
        lookup_expr='icontains',
        label='Tenant (name)',
    )
    contact_group_id = django_filters.ModelMultipleChoiceFilter(
        queryset=ContactGroup.objects.all(),
        field_name='contact__groups',
        label='Contact Group (ID)',
    )
    contact_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Contact.objects.all(),
        field_name='contact',
        label='Contact (ID)',
    )
    owner_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Tenant.objects.all(),
        field_name='owner',
        label='Owner (ID)',
    )
    owner = django_filters.ModelMultipleChoiceFilter(
        queryset=Tenant.objects.all(),
        field_name='owner__slug',
        to_field_name='slug',
        label='Owner (slug)',
    )
    owner_name = filters.MultiValueCharFilter(
        field_name='owner__name',
        lookup_expr='icontains',
        label='Owner (name)',
    )
    order_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Order.objects.all(),
        field_name='order',
        label='Order (ID)',
    )
    order = django_filters.CharFilter(
        field_name='order__name',
        lookup_expr='iexact',
        label='Order (name)',
    )
    purchase_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Purchase.objects.all(),
        field_name='purchase',
        label='Purchase (ID)',
    )
    purchase = django_filters.CharFilter(
        field_name='purchase__name',
        lookup_expr='iexact',
        label='Purchase (name)',
    )
    supplier_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Supplier.objects.all(),
        field_name='purchase__supplier',
        label='Supplier (ID)',
    )
    supplier = django_filters.CharFilter(
        field_name='purchase__supplier__name',
        lookup_expr='iexact',
        label='Supplier (name)',
    )
    vendor_ship_date = django_filters.DateFromToRangeFilter()
    warranty_start = django_filters.DateFromToRangeFilter()
    warranty_end = django_filters.DateFromToRangeFilter()
    purchase_date = django_filters.DateFromToRangeFilter(
        field_name='purchase__date',
    )
    storage_site_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Site.objects.all(),
        field_name='storage_location__site',
        label='Storage site (ID)',
    )
    storage_location_id = TreeNodeMultipleChoiceFilter(
        queryset=Location.objects.all(),
        field_name='storage_location',
        lookup_expr='in',
        label='Storage location (ID)',
    )
    installed_site_slug = filters.MultiValueCharFilter(
        method='filter_installed_site_slug',
        label='Installed site (slug)',
    )
    installed_site_id = filters.MultiValueCharFilter(
        method='filter_installed',
        field_name='site',
        label='Installed site (ID)',
    )
    installed_location_id = filters.MultiValueCharFilter(
        method='filter_installed',
        field_name='location',
        label='Installed location (ID)',
    )
    installed_rack_id = filters.MultiValueCharFilter(
        method='filter_installed',
        field_name='rack',
        label='Installed rack (ID)',
    )
    installed_device_id = filters.MultiValueCharFilter(
        method='filter_installed_device',
        field_name='id',
        label='Installed device (ID)',
    )
    installed_device_name = filters.MultiValueCharFilter(
        method='filter_installed_device',
        field_name='name',
        label='Installed device (name)',
    )
    located_site_id = filters.MultiValueCharFilter(
        method='filter_located',
        field_name='site',
        label='Located site (ID)',
    )
    located_location_id = filters.MultiValueCharFilter(
        method='filter_located',
        field_name='location',
        label='Located location (ID)',
    )
    tenant_any_id = filters.MultiValueCharFilter(
        method='filter_tenant_any',
        field_name='id',
        label='Any tenant (slug)',
    )
    tenant_any = filters.MultiValueCharFilter(
        method='filter_tenant_any',
        field_name='slug',
        label='Any tenant (slug)',
    )

    class Meta:
        model = Asset
        fields = ('id', 'name', 'serial', 'asset_tag', 'description')

    def search(self, queryset, name, value):
        query = (
            Q(id__contains=value)
            | Q(serial__icontains=value)
            | Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(asset_tag__icontains=value)
            | Q(device_type__model__icontains=value)
            | Q(module_type__model__icontains=value)
            | Q(inventoryitem_type__model__icontains=value)
            | Q(rack_type__model__icontains=value)
            | Q(device__name__icontains=value)
            | Q(inventoryitem__name__icontains=value)
            | Q(rack__name__icontains=value)
            | Q(order__name__icontains=value)
            | Q(purchase__name__icontains=value)
            | Q(purchase__supplier__name__icontains=value)
            | Q(tenant__name__icontains=value)
            | Q(owner__name__icontains=value)
        )
        custom_field_filters = get_asset_custom_fields_search_filters()
        for custom_field_filter in custom_field_filters:
            query |= Q(**{custom_field_filter: value})

        return queryset.filter(query)

    def filter_kind(self, queryset, name, value):
        query = None
        for kind in HardwareKindChoices.values():
            if kind in value:
                q = Q(**{f'{kind}_type__isnull': False})
                if query:
                    query = query | q
                else:
                    query = q
        if query:
            return queryset.filter(query)
        else:
            return queryset

    def filter_manufacturer(self, queryset, name, value):
        if name == 'manufacturer_id':
            return queryset.filter(
                Q(device_type__manufacturer__in=value)
                | Q(module_type__manufacturer__in=value)
                | Q(inventoryitem_type__manufacturer__in=value)
            )
        elif name == 'manufacturer_name':
            # OR for every passed value and for all hardware types
            q = Q()
            for v in value:
                q |= Q(device_type__manufacturer__name__icontains=v)
                q |= Q(module_type__manufacturer__name__icontains=v)
                q |= Q(inventoryitem_type__manufacturer__name__icontains=v)
            return queryset.filter(q)

    def filter_is_assigned(self, queryset, name, value):
        if value:
            # is assigned to any hardware
            return queryset.filter(
                Q(device__isnull=False)
                | Q(module__isnull=False)
                | Q(inventoryitem__isnull=False)
            )
        else:
            # is not assigned to hardware kind
            return queryset.filter(
                Q(device__isnull=True)
                & Q(module__isnull=True)
                & Q(inventoryitem__isnull=True)
            )

    def filter_installed(self, queryset, name, value):
        return query_located(queryset, name, value, assets_shown='installed')

    def filter_installed_site_slug(self, queryset, name, value):
        return query_located(queryset, 'site__slug', value, assets_shown='installed')

    def filter_installed_device(self, queryset, name, value):
        return query_located(queryset, name, value, assets_shown='installed')

    def filter_located(self, queryset, name, value):
        return query_located(queryset, name, value)

    def filter_tenant_any(self, queryset, name, value):
        # filter OR for owner and tenant fields
        if name == 'slug':
            q_list = (
                Q(tenant__slug__iexact=n) | Q(owner__slug__iexact=n) for n in value
            )
        elif name == 'id':
            q_list = (Q(tenant__pk=n) | Q(owner__pk=n) for n in value)
        q_list = reduce(lambda a, b: a | b, q_list)
        return queryset.filter(q_list)


class HasAssetFilterMixin(NetBoxModelFilterSet):
    has_asset_assigned = django_filters.BooleanFilter(
        method='_has_asset_assigned',
        label='Has an asset assigned',
    )

    def _has_asset_assigned(self, queryset, name, value):
        params = Q(assigned_asset__isnull=False)
        if value:
            return queryset.filter(params)
        return queryset.exclude(params)


class DeviceAssetFilterSet(HasAssetFilterMixin, DeviceFilterSet):
    pass


class ModuleAssetFilterSet(HasAssetFilterMixin, ModuleFilterSet):
    pass


class InventoryItemAssetFilterSet(HasAssetFilterMixin, InventoryItemFilterSet):
    pass


#
# Contracts
#

class ContractVendorFilterSet(NetBoxModelFilterSet):

    class Meta:
        model = ContractVendor
        fields = ('id', 'q', 'name', )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = (
            Q(name__icontains=value)
        )
        return queryset.filter(qs_filter).distinct()


class ContractSKUFilterSet(NetBoxModelFilterSet):
    manufacturer_id = django_filters.ModelMultipleChoiceFilter(
        field_name='manufacturer',
        queryset=Manufacturer.objects.all(),
        label=_('Manufacturer (ID)'),
    )
    manufacturer = django_filters.ModelMultipleChoiceFilter(
        field_name='manufacturer__slug',
        queryset=Manufacturer.objects.all(),
        to_field_name='slug',
        label=_('Manufacturer (slug)'),
    )

    class Meta:
        model = ContractSKU
        fields = ('id', 'q', 'sku', )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = (
            Q(sku__icontains=value) |
            Q(manufacturer__name__icontains=value)
        )
        return queryset.filter(qs_filter).distinct()


class ContractFilterSet(NetBoxModelFilterSet):
    vendor_id = django_filters.ModelMultipleChoiceFilter(
        field_name='vendor',
        queryset=ContractVendor.objects.all(),
        label=_('Vendor (ID)'),
    )
    vendor = django_filters.ModelMultipleChoiceFilter(
        field_name='vendor__name',
        queryset=ContractVendor.objects.all(),
        to_field_name='name',
        label=_('Vendor (Name)'),
    )
    contract_type = django_filters.MultipleChoiceFilter(
        choices=ContractTypeChoices,
    )
    status = django_filters.MultipleChoiceFilter(
        choices=ContractStatusChoices,
    )
    start_date = django_filters.DateFromToRangeFilter()
    end_date = django_filters.DateFromToRangeFilter()
    renewal_date = django_filters.DateFromToRangeFilter()
    is_active = django_filters.BooleanFilter(
        method='filter_is_active',
        label='Is currently active',
    )
    is_expired = django_filters.BooleanFilter(
        method='filter_is_expired',
        label='Is expired',
    )
    needs_renewal = django_filters.BooleanFilter(
        method='filter_needs_renewal',
        label='Needs renewal',
    )

    class Meta:
        model = Contract
        fields = (
            'id',
            'contract_id',
            'vendor',
            'contract_type',
            'status',
            'start_date',
            'end_date',
            'renewal_date',
            'description',
        )

    def search(self, queryset, name, value):
        query = Q(
            Q(name__icontains=value)
            | Q(contract_id__icontains=value)
            | Q(description__icontains=value)
            | Q(vendor__name__icontains=value)
        )
        return queryset.filter(query)

    def filter_is_active(self, queryset, name, value):
        from datetime import date
        today = date.today()
        if value:
            return queryset.filter(start_date__lte=today, end_date__gte=today)
        else:
            return queryset.exclude(start_date__lte=today, end_date__gte=today)

    def filter_is_expired(self, queryset, name, value):
        from datetime import date
        today = date.today()
        if value:
            return queryset.filter(end_date__lt=today)
        else:
            return queryset.exclude(end_date__lt=today)

    def filter_needs_renewal(self, queryset, name, value):
        from datetime import date
        today = date.today()
        if value:
            return queryset.filter(renewal_date__lte=today).exclude(renewal_date__isnull=True)
        else:
            return queryset.exclude(renewal_date__lte=today).filter(renewal_date__isnull=False)


class ContractAssignmentFilterSet(NetBoxModelFilterSet):
    contract_id = django_filters.ModelMultipleChoiceFilter(
        field_name='contract',
        queryset=Contract.objects.all(),
        label=_('Contract'),
    )
    contract = django_filters.ModelMultipleChoiceFilter(
        field_name='contract__contract_id',
        queryset=Contract.objects.all(),
        to_field_name='contract_id',
        label=_('Contract'),
    )
    sku_id = django_filters.ModelMultipleChoiceFilter(
        field_name='sku',
        queryset=ContractSKU.objects.all(),
        label=_('SKU'),
    )
    sku = django_filters.ModelMultipleChoiceFilter(
        field_name='sku__sku',
        queryset=ContractSKU.objects.all(),
        to_field_name='sku',
        label=_('SKU'),
    )
    asset_id = django_filters.ModelMultipleChoiceFilter(
        field_name='asset',
        queryset=Asset.objects.all(),
        label=_('Asset (ID)'),
    )
    asset = django_filters.ModelMultipleChoiceFilter(
        field_name='asset__name',
        queryset=Asset.objects.all(),
        to_field_name='name',
        label=_('Asset (name)'),
    )
    asset_status = django_filters.ModelMultipleChoiceFilter(
        field_name='asset__status',
        queryset=Asset.objects.all(),
        to_field_name='status',
        label=_('Asset Status'),
    )

    class Meta:
        model = ContractAssignment
        fields = ('id', 'q', 'end_date')


    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = (
            Q(contract__contract_id__icontains=value) |
            Q(contract__vendor__name__icontains=value) |
            Q(sku__sku__icontains=value) |
            Q(asset__name__icontains=value)
        )
        return queryset.filter(qs_filter).distinct()

#
# Purchases
#


class SupplierFilterSet(NetBoxModelFilterSet, ContactModelFilterSet):
    class Meta:
        model = Supplier
        fields = (
            'id',
            'name',
            'slug',
            'description',
        )

    def search(self, queryset, name, value):
        query = Q(
            Q(name__icontains=value)
            | Q(slug__icontains=value)
            | Q(description__icontains=value)
        )
        return queryset.filter(query)


class PurchaseFilterSet(NetBoxModelFilterSet):
    supplier_id = django_filters.ModelMultipleChoiceFilter(
        field_name='supplier',
        queryset=Supplier.objects.all(),
        label='Supplier (ID)',
    )
    status = django_filters.MultipleChoiceFilter(
        choices=PurchaseStatusChoices,
    )
    date = django_filters.DateFromToRangeFilter()

    class Meta:
        model = Purchase
        fields = ('id', 'supplier', 'name', 'date', 'description')

    def search(self, queryset, name, value):
        query = Q(
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(supplier__name__icontains=value)
        )
        return queryset.filter(query)


class OrderFilterSet(NetBoxModelFilterSet):
    purchase_id = django_filters.ModelMultipleChoiceFilter(
        field_name='purchase',
        queryset=Purchase.objects.all(),
        label='Purchase (ID)',
    )
    supplier_id = django_filters.ModelMultipleChoiceFilter(
        field_name='purchase__supplier',
        queryset=Supplier.objects.all(),
        label='Supplier (ID)',
    )
    manufacturer_id = django_filters.ModelMultipleChoiceFilter(
        queryset=Manufacturer.objects.all(),
        field_name='manufacturer',
        label='Manufacturer (ID)',
    )

    class Meta:
        model =Order
        fields = (
            'id',
            'name',
            'manufacturer',
            'description',
            'purchase',
        )

    def search(self, queryset, name, value):
        query = Q(
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(purchase__name__icontains=value)
            | Q(purchase__supplier__name__icontains=value)
            | Q(manufacturer__name__icontains=value)
        )
        return queryset.filter(query)


#
# Audit
#


class BaseFlowFilterSet(NetBoxModelFilterSet):
    """
    Internal base filterset class for audit flow models.
    """

    object_type_id = django_filters.ModelMultipleChoiceFilter(
        queryset=ObjectType.objects.public(),
    )
    object_type = ContentTypeFilter()

    class Meta:
        fields = (
            'id',
            'name',
            'description',
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )


class AuditFlowPageFilterSet(BaseFlowFilterSet):
    assigned_flow_id = django_filters.ModelMultipleChoiceFilter(
        queryset=AuditFlow.objects.all(),
        field_name='assigned_flows',
        label=_('Assigned Audit Flow (ID)'),
    )

    class Meta(BaseFlowFilterSet.Meta):
        model = AuditFlowPage
        fields = BaseFlowFilterSet.Meta.fields + ('assigned_flow_id',)


class AuditFlowFilterSet(BaseFlowFilterSet):
    page_id = django_filters.ModelMultipleChoiceFilter(
        queryset=AuditFlowPage.objects.all(),
        field_name='pages',
        label=_('Audit Flow Page (ID)'),
    )

    class Meta(BaseFlowFilterSet.Meta):
        model = AuditFlow
        fields = BaseFlowFilterSet.Meta.fields + (
            'enabled',
            'page_id',
        )


class AuditTrailSourceFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = AuditTrailSource
        fields = (
            'id',
            'name',
            'slug',
            'description',
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(slug__icontains=value)
            | Q(description__icontains=value)
        )


class AuditTrailFilterSet(NetBoxModelFilterSet):
    # Disable inherited filters for nonexistent fields.
    tag = None
    tag_id = None

    object_type = ContentTypeFilter()
    source_id = django_filters.ModelMultipleChoiceFilter(
        queryset=AuditTrailSource.objects.all(),
        label='Source (ID)',
    )
    source = django_filters.ModelMultipleChoiceFilter(
        field_name='source__slug',
        queryset=AuditTrailSource.objects.all(),
        to_field_name='slug',
        label=_('Source (slug)'),
    )

    class Meta:
        model = AuditTrail
        fields = (
            'id',
            'object_type_id',
            'object_id',
        )


class HardwareLifecycleFilterSet(NetBoxModelFilterSet):
    assigned_object_type_id = django_filters.ModelMultipleChoiceFilter(
        queryset=ContentType.objects.all()
    )
    device_type = django_filters.ModelMultipleChoiceFilter(
        field_name='device_type__model',
        queryset=DeviceType.objects.all(),
        to_field_name='model',
        label=_('Device Type (Model)'),
        method='filter_types',
    )
    device_type_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device_type',
        queryset=DeviceType.objects.all(),
        label=_('Device Type'),
        method='filter_types',
    )
    module_type = django_filters.ModelMultipleChoiceFilter(
        field_name='module_type__model',
        queryset=ModuleType.objects.all(),
        to_field_name='model',
        label=_('Module Type (Model)'),
        method='filter_types',
    )
    module_type_id = django_filters.ModelMultipleChoiceFilter(
        field_name='module_type',
        queryset=ModuleType.objects.all(),
        label=_('Module Type'),
        method='filter_types',
    )

    class Meta:
        model = HardwareLifecycle
        fields = (
            'id',
            'assigned_object_type_id',
            'assigned_object_id',
            'end_of_sale',
            'end_of_maintenance',
            'end_of_security',
            'end_of_support',
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        qs_filter = Q(
            Q(device_type__model__icontains=value)
            | Q(module_type__model__icontains=value)
        )
        return queryset.filter(qs_filter).distinct()

    def filter_types(self, queryset, name, value):
        if '__' in name:
            name, leftover = name.split('__', 1)  # noqa F841

        if type(value) is list:
            name = f'{name}__in'

        if not value:
            return queryset
        try:
            return queryset.filter(**{f'{name}': value})
        except ValueError:
            return queryset.none()


class VendorProgramFilterSet(NetBoxModelFilterSet):
    q = django_filters.CharFilter(method="search", label="Search")
    manufacturer_id = filters.MultiValueCharFilter(
        method='filter_manufacturer',
        label='Manufacturer (ID)',
    )

    class Meta:
        model = VendorProgram
        fields = (
            "id",
            "name",
            "slug",
            "manufacturer_id",
            "tag",
        )


class LicenseSKUFilterSet(NetBoxModelFilterSet):
    manufacturer_id = django_filters.ModelMultipleChoiceFilter(
        field_name="manufacturer",
        queryset=Manufacturer.objects.all(),
        label="Manufacturer (ID)",
    )
    q = django_filters.CharFilter(method="search", label="Search")

    class Meta:
        model = LicenseSKU
        fields = ("manufacturer_id", "license_kind", "sku")

    def search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(sku__icontains=value) | Q(name__icontains=value)
        )


class AssetProgramCoverageFilterSet(NetBoxModelFilterSet):
    """
    FilterSet for AssetProgramCoverage list view.

    Notes:
    - Adjust field names (effective_start/effective_end, status choices, etc.) to match your model.
    - "q" implements a simple search across common related fields.
    """

    q = django_filters.CharFilter(method="filter_q", label="Search")

    # Status
    status = django_filters.MultipleChoiceFilter(
        choices=AssetStatusChoices,
    )

    # Common foreign keys
    program_id = django_filters.ModelMultipleChoiceFilter(
        field_name="program",
        queryset=VendorProgram.objects.all(),
        label="Program",
    )
    asset_id = django_filters.ModelMultipleChoiceFilter(
        field_name="asset",
        queryset=Asset.objects.all(),
        label="Asset",
    )
    # If your Asset links to a Device (asset.device or asset.assigned_object), adjust accordingly
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name="asset__device",
        queryset=Device.objects.all(),
        label="Device",
    )
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name="asset__device__site",
        queryset=Site.objects.all(),
        label="Site",
    )
    tenant_id = django_filters.ModelMultipleChoiceFilter(
        field_name="asset__device__tenant",
        queryset=Tenant.objects.all(),
        label="Tenant",
    )

    # Effective dates (range)
    effective_start = django_filters.DateFromToRangeFilter(
        field_name="effective_start",
        label="Effective start (range)",
    )
    effective_end = django_filters.DateFromToRangeFilter(
        field_name="effective_end",
        label="Effective end (range)",
    )

    class Meta:
        model = AssetProgramCoverage
        fields = (
            "q",
            "program_id",
            "asset_id",
            "device_id",
            "site_id",
            "tenant_id",
            "status",
            "effective_start",
            "effective_end",
        )

    def filter_q(self, queryset, name, value):
        if not value:
            return queryset

        value = value.strip()
        return queryset.filter(
            Q(program__name__icontains=value)
            | Q(program__slug__icontains=value)
            | Q(asset__name__icontains=value)
            | Q(asset__serial__icontains=value)
            | Q(asset__device__name__icontains=value)
            | Q(asset__device__serial__icontains=value)
        )
