from django import forms
from django.utils.translation import gettext_lazy as _

from dcim.models import DeviceType, Location, Manufacturer, ModuleType, RackType, Site
from extras.choices import *
from extras.models import *
from netbox.forms import NetBoxModelBulkEditForm,  PrimaryModelBulkEditForm
from netbox.forms.mixins import ChangelogMessageMixin
from tenancy.models import Contact, ContactGroup, Tenant
from utilities.forms import BulkEditForm, add_blank_choice
from utilities.forms.fields import (
    CommentField,
    DynamicModelChoiceField,
)
from utilities.forms.rendering import FieldSet
from utilities.forms.widgets import BulkEditNullBooleanSelect, DatePicker

from ..choices import (
    AssetAllocationStatusChoices,
    AssetDisposalReasonhoices,
    AssetStatusChoices,
    AssetSupportReasonChoices,
    AssetSupportStateChoices,
    ContractStatusChoices,
    ContractTypeChoices,
    PurchaseStatusChoices,
)
from ..models import *
from ..models.hardware import SupportBasisChoices

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
    allocation_status = forms.ChoiceField(
        choices=add_blank_choice(AssetAllocationStatusChoices),
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
    vendor_instance_id = forms.CharField(
        label='Vendor Instance ID',
        required=False,
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
    installed_site_override = DynamicModelChoiceField(
        queryset=Site.objects.all(),
        help_text=Asset._meta.get_field('installed_site_override').help_text,
        required=False,
    )
    support_state = forms.ChoiceField(
        choices=add_blank_choice(AssetSupportStateChoices),
        required=False,
        initial='',
    )
    support_reason = forms.ChoiceField(
        choices=add_blank_choice(AssetSupportReasonChoices),
        required=False,
        initial='',
    )
    support_validated_at = forms.DateField(
        label='Support Validated At',
        required=False,
        widget=DatePicker(),
    )
    disposal_date = forms.DateField(
        label='Disposal Date',
        required=False,
        widget=DatePicker(),
    )
    disposal_reason = forms.ChoiceField(
        choices=add_blank_choice(AssetDisposalReasonhoices),
        required=False,
        initial='',
    )
    disposal_reference = forms.CharField(
        label='Disposal Reference',
        required=False,
    )

    model = Asset
    fieldsets = (
        FieldSet(
            'name',
            'status',
            'allocation_status',
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
            'vendor_instance_id',
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
            'support_state',
            'support_reason',
            'support_validated_at',
            name='Support State',
        ),
        FieldSet(
            'disposal_date',
            'disposal_reason',
            'disposal_reference',
            name='Disposal',
        ),
        FieldSet(
            'tenant',
            'contact_group',
            'contact',
            name='Assigned to',
        ),
        FieldSet(
            'storage_location',
            'installed_site_override',
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
        'vendor_instance_id',
        'storage_location',
        'installed_site_override',
        'support_reason',
        'support_validated_at',
        'disposal_date',
        'disposal_reason',
        'disposal_reference',
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
    manufacturer = DynamicModelChoiceField(
        queryset=Manufacturer.objects.all(),
        required=False,
        label=_('Manufacturer'),
    )
    contract_type = forms.ChoiceField(
        choices=add_blank_choice(ContractTypeChoices),
        required=False,
        initial='',
        label=_('Contract Type'),
    )
    service_level = forms.CharField(
        label=_('Service Level'),
        max_length=64,
        required=False,
    )
    description = forms.CharField(
        label=_('Description'),
        max_length=200,
        required=False,
    )
    comments = CommentField()

    model = ContractSKU
    fieldsets = (
        FieldSet('manufacturer', 'contract_type', 'service_level', 'description'),
    )
    nullable_fields = ('service_level', 'description')


class ContractBulkEditForm(NetBoxModelBulkEditForm):
    vendor = DynamicModelChoiceField(
        queryset=ContractVendor.objects.all(),
        required=False,
        label=_('Vendor'),
        selector=True,
    )
    contract_type = forms.ChoiceField(
        choices=add_blank_choice(ContractTypeChoices),
        required=False,
        initial='',
        label=_('Contract Type'),
    )
    status = forms.ChoiceField(
        choices=add_blank_choice(ContractStatusChoices),
        required=False,
        initial='',
    )
    start_date = forms.DateField(
        label=_('Start Date'),
        required=False,
        widget=DatePicker(),
    )
    renewal_date = forms.DateField(
        label=_('Renewal Date'),
        required=False,
        widget=DatePicker(),
    )
    end_date = forms.DateField(
        label=_('End Date'),
        required=False,
        widget=DatePicker(),
    )
    description = forms.CharField(
        label=_('Description'),
        max_length=200,
        required=False,
    )
    comments = CommentField()

    model = Contract
    fieldsets = (
        FieldSet('vendor', 'contract_type', 'status', 'description', name='Contract'),
        FieldSet('start_date', 'renewal_date', 'end_date', name='Dates'),
    )
    nullable_fields = ('description', 'start_date', 'renewal_date', 'end_date')


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
    end_date = forms.DateField(
        label=_('End date'),
        required=False,
        widget=DatePicker(),
    )
    comments = CommentField()

    model = ContractAssignment
    fieldsets = (
        FieldSet('contract', 'sku', 'description', 'end_date', ),
    )
    nullable_fields = ('contract', 'sku', 'description', 'end_date', )

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
    announcement_date = forms.DateField(
        label=_('Announcement Date'),
        required=False,
        widget=DatePicker(),
    )
    end_of_sale = forms.DateField(
        label=_('End of Sale'),
        required=False,
        widget=DatePicker(),
    )
    end_of_maintenance = forms.DateField(
        label=_('End of Maintenance'),
        required=False,
        widget=DatePicker(),
    )
    end_of_security = forms.DateField(
        label=_('End of Security'),
        required=False,
        widget=DatePicker(),
    )
    last_contract_attach = forms.DateField(
        label=_('Last Contract Attach'),
        required=False,
        widget=DatePicker(),
    )
    last_contract_renewal = forms.DateField(
        label=_('Last Contract Renewal'),
        required=False,
        widget=DatePicker(),
    )
    end_of_support = forms.DateField(
        label=_('End of Support'),
        required=False,
        widget=DatePicker(),
    )
    support_basis = forms.ChoiceField(
        choices=add_blank_choice(SupportBasisChoices),
        required=False,
        initial='',
        label=_('Support Basis'),
    )
    notice_url = forms.URLField(
        label=_('Notice URL'),
        required=False,
    )
    description = forms.CharField(
        label=_('Description'), max_length=200, required=False
    )
    comments = CommentField()

    model = HardwareLifecycle
    fieldsets = (
        FieldSet(
            'announcement_date',
            'end_of_sale',
            'end_of_maintenance',
            'end_of_security',
            'last_contract_attach',
            'last_contract_renewal',
            'end_of_support',
            'support_basis',
            name=_('Dates'),
        ),
        FieldSet(
            'notice_url',
            'description',
            name=_('Information'),
        ),
    )
    nullable_fields = (
        'announcement_date',
        'end_of_sale',
        'end_of_maintenance',
        'end_of_security',
        'last_contract_attach',
        'last_contract_renewal',
        'end_of_support',
        'notice_url',
        'description',
    )
