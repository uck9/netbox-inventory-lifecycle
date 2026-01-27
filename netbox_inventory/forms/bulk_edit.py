from django import forms
from django.utils.translation import gettext_lazy as _

from dcim.models import DeviceType, Location, Manufacturer, ModuleType, RackType
from extras.choices import *
from extras.models import *
from netbox.forms import NetBoxModelBulkEditForm,  PrimaryModelBulkEditForm
from netbox.forms.mixins import ChangelogMessageMixin
from tenancy.models import Contact, ContactGroup, Tenant
from utilities.forms import BulkEditForm, add_blank_choice
from utilities.forms.fields import DynamicModelChoiceField
from utilities.forms.rendering import FieldSet
from utilities.forms.widgets import BulkEditNullBooleanSelect, DatePicker

from ..choices import AssetStatusChoices, PurchaseStatusChoices
from ..models import *

__all__ = (
    'AssetBulkEditForm',
    'AuditFlowBulkEditForm',
    'AuditFlowPageBulkEditForm',
    'AuditFlowPageAssignmentBulkEditForm',
    'AuditTrailSourceBulkEditForm',
    'ContractVendorBulkEditForm',
    'ContractSKUBulkEditForm',
    'ContractBulkEditForm',
    'ContractAssignmentBulkEditForm',
    'HardwareLifecycleBulkEditForm',
    'OrderBulkEditForm',
    'InventoryItemGroupBulkEditForm',
    'PurchaseBulkEditForm',
    'SupplierBulkEditForm',
    'InventoryItemTypeBulkEditForm',
)

#
# Assets
#


class InventoryItemGroupBulkEditForm(PrimaryModelBulkEditForm):
    parent = DynamicModelChoiceField(
        queryset=InventoryItemGroup.objects.all(),
        required=False,
    )

    model = InventoryItemGroup
    fieldsets = (
        FieldSet(
            'parent',
            'description',
        ),
    )
    nullable_fields = (
        'parent',
        'description',
    )


class InventoryItemTypeBulkEditForm(PrimaryModelBulkEditForm):
    manufacturer = DynamicModelChoiceField(
        queryset=Manufacturer.objects.all(),
        required=False,
        label='Manufacturer',
    )
    inventoryitem_group = DynamicModelChoiceField(
        queryset=InventoryItemGroup.objects.all(),
        required=False,
        label='Inventory Item Group',
    )

    model = InventoryItemType
    fieldsets = (
        FieldSet(
            'manufacturer',
            'inventoryitem_group',
            'description',
            name='Inventory Item Type',
        ),
    )
    nullable_fields = (
        'inventoryitem_group',
        'description',
        'comments',
    )


class AssetBulkEditForm(PrimaryModelBulkEditForm):
    name = forms.CharField(
        required=False,
    )
    status = forms.ChoiceField(
        choices=add_blank_choice(AssetStatusChoices),
        required=False,
        initial='',
    )
    device_type = DynamicModelChoiceField(
        queryset=DeviceType.objects.all(),
        required=False,
        label='Device type',
    )
    # FIXME figure out how to only show set null checkbox
    device = forms.CharField(
        disabled=True,
        required=False,
    )
    module_type = DynamicModelChoiceField(
        queryset=ModuleType.objects.all(),
        required=False,
        label='Module type',
    )
    # FIXME figure out how to only show set null checkbox
    module = forms.CharField(
        disabled=True,
        required=False,
    )
    rack_type = DynamicModelChoiceField(
        queryset=RackType.objects.all(),
        required=False,
        label='Rack type',
    )
    # FIXME figure out how to only show set null checkbox
    rack = forms.CharField(
        disabled=True,
        required=False,
    )
    owning_tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        help_text=Asset._meta.get_field('owning_tenant').help_text,
        required=not Asset._meta.get_field('owning_tenant').blank,
    )
    purchase = DynamicModelChoiceField(
        queryset=Purchase.objects.all(),
        help_text=Asset._meta.get_field('purchase').help_text,
        required=not Asset._meta.get_field('purchase').blank,
    )
    order = DynamicModelChoiceField(
        queryset=Order.objects.all(),
        help_text=Asset._meta.get_field('order').help_text,
        required=not Asset._meta.get_field('order').blank,
    )
    base_license_sku = DynamicModelChoiceField(
        queryset=LicenseSKU.objects.filter(license_kind=LicenseKindChoices.PERPETUAL),
        help_text=Asset._meta.get_field('base_license_sku').help_text,
        required=not Asset._meta.get_field('base_license_sku').blank,
    )
    vendor_ship_date = forms.DateField(
        label='Vendor Ship Date',
        required=False,
        widget=DatePicker(),
    )
    warranty_start = forms.DateField(
        label='Warranty start',
        required=False,
        widget=DatePicker(),
    )
    warranty_end = forms.DateField(
        label='Warranty end',
        required=False,
        widget=DatePicker(),
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        help_text=Asset._meta.get_field('tenant').help_text,
        required=not Asset._meta.get_field('tenant').blank,
    )
    contact_group = DynamicModelChoiceField(
        queryset=ContactGroup.objects.all(),
        required=False,
        null_option='None',
        label='Contact Group',
        help_text='Filter contacts by group',
    )
    contact = DynamicModelChoiceField(
        queryset=Contact.objects.all(),
        help_text=Asset._meta.get_field('contact').help_text,
        required=not Asset._meta.get_field('contact').blank,
        query_params={
            'group_id': '$contact_group',
        },
    )
    storage_location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        help_text=Asset._meta.get_field('storage_location').help_text,
        required=False,
    )

    model = Asset
    fieldsets = (
        FieldSet(
            'name',
            'status',
            'description',
            name='General',
        ),
        FieldSet(
            'device_type',
            'device',
            'module_type',
            'module',
            'rack_type',
            'rack',
            name='Hardware',
        ),
        FieldSet(
            'owning_tenant',
            'purchase',
            'order',
            'base_license_sku',
            'vendor_ship_date',
            'warranty_start',
            'warranty_end',
            name='Purchase',
        ),
        FieldSet(
            'vendor_ship_date',
            'warranty_start',
            'warranty_end',
            name='Key Hardware Dates',
        ),
        FieldSet(
            'tenant',
            'contact_group',
            'contact',
            name='Assigned to',
        ),
        FieldSet(
            'storage_location',
            name='Location',
        ),
    )
    nullable_fields = (
        'name',
        'description',
        'device',
        'module',
        'rack',
        'owning_tenant',
        'purchase',
        'order',
        'tenant',
        'contact',
        'warranty_start',
        'warranty_end',
        'storage_location',
    )


#
# Contracts
#

class ContractVendorBulkEditForm(NetBoxModelBulkEditForm):
    description = forms.CharField(
        label=_('Description'),
        max_length=200,
        required=False
    )
    comments = CommentField()

    model = ContractVendor
    fieldsets = (
        FieldSet('description', ),
    )
    nullable_fields = ('description', )


class ContractSKUBulkEditForm(NetBoxModelBulkEditForm):
    description = forms.CharField(
        label=_('Description'),
        max_length=200,
        required=False
    )
    comments = CommentField()

    model = ContractSKU
    fieldsets = (
        FieldSet('description', ),
    )
    nullable_fields = ('description', )


class ContractBulkEditForm(NetBoxModelBulkEditForm):
    description = forms.CharField(
        label=_('Description'),
        max_length=200,
        required=False
    )
    comments = CommentField()

    model = Contract
    fieldsets = (
        FieldSet('description', ),
    )
    nullable_fields = ('description', )


class ContractAssignmentBulkEditForm(NetBoxModelBulkEditForm):
    contract = DynamicModelChoiceField(
        queryset=Contract.objects.all(),
        label=_('Contract'),
        required=False,
        selector=True
    )
    sku = DynamicModelChoiceField(
        queryset=ContractSKU.objects.all(),
        label=_('SKU'),
        required=False,
        selector=True
    )
    description = forms.CharField(
        label=_('Description'),
        max_length=200,
        required=False
    )
    end = forms.DateField(
        label=_('End date'),
        required=False,
        widget=DatePicker(),
    )
    comments = CommentField()

    model = ContractAssignment
    fieldsets = (
        FieldSet('contract', 'sku', 'description', 'end', ),
    )
    nullable_fields = ('contract', 'sku', 'description', 'end', )

#
# Purchases
#


class SupplierBulkEditForm(PrimaryModelBulkEditForm):

    model = Supplier
    fieldsets = (
        FieldSet(
            'description',
            name='General',
        ),
    )
    nullable_fields = ('description',)


class PurchaseBulkEditForm(PrimaryModelBulkEditForm):
    status = forms.ChoiceField(
        choices=add_blank_choice(PurchaseStatusChoices),
        required=False,
        initial='',
    )
    date = forms.DateField(
        label='Date',
        required=False,
        widget=DatePicker(),
    )
    supplier = DynamicModelChoiceField(
        queryset=Supplier.objects.all(),
        required=False,
        label='Supplier',
    )

    model = Purchase
    fieldsets = (
        FieldSet(
            'date',
            'status',
            'supplier',
            'description',
            name='General',
        ),
    )
    nullable_fields = (
        'date',
        'description',
    )


class OrderBulkEditForm(PrimaryModelBulkEditForm):
    date = forms.DateField(
        label='Date',
        required=False,
        widget=DatePicker(),
    )
    purchase = DynamicModelChoiceField(
        queryset=Purchase.objects.all(),
        required=False,
        label='Purchase',
    )

    model = Order
    fieldsets = (
        FieldSet(
            'date',
            'purchase',
            'description',
            name='General',
        ),
    )
    nullable_fields = (
        'date',
        'description',
    )


#
# Audit
#


class AuditFlowBulkEditForm(PrimaryModelBulkEditForm):
    enabled = forms.NullBooleanField(
        required=False,
        widget=BulkEditNullBooleanSelect(),
    )

    model = AuditFlow

    fieldsets = (
        FieldSet(
            'enabled',
            name=_('Attributes'),
        ),
    )


class AuditFlowPageBulkEditForm(NetBoxModelBulkEditForm):
    model = AuditFlowPage

    fieldsets = (
        FieldSet(
            'description',
            name=_('Attributes'),
        ),
    )
    nullable_fields = (
        'description',
    )


class AuditFlowPageAssignmentBulkEditForm(ChangelogMessageMixin, BulkEditForm):
    pk = forms.ModelMultipleChoiceField(
        queryset=AuditFlowPageAssignment.objects.all(),
        widget=forms.MultipleHiddenInput,
    )
    weight = forms.IntegerField(
        required=False,
    )

    fieldsets = (
        FieldSet(
            'weight',
            name=_('Attributes'),
        ),
    )


class AuditTrailSourceBulkEditForm(NetBoxModelBulkEditForm):
    model = AuditTrailSource

    fieldsets = (
        FieldSet(
            'description',
            name=_('Attributes'),
        ),
    )
    nullable_fields = (
        'description',
    )


#
# Hardware Lifecycle
#

class HardwareLifecycleBulkEditForm(NetBoxModelBulkEditForm):
    description = forms.CharField(
        label=_('Description'), max_length=200, required=False
    )
    comments = CommentField()

    model = HardwareLifecycle
    fieldsets = (
        FieldSet(
            'description',
        ),
    )
    nullable_fields = ('description',)
