from django import forms
from django.utils.translation import gettext_lazy as _

from core.models import ObjectType
from dcim.models import (  # pyright: ignore[reportMissingImports]
    DeviceType,
    Location,
    Manufacturer,
    ModuleType,
    RackType,
    Site,
)
from extras.models import CustomField
from netbox.forms import NetBoxModelForm
from tenancy.models import Contact, ContactGroup, Tenant
from utilities.forms.fields import (
    CommentField,
    ContentTypeChoiceField,
    DynamicModelChoiceField,
    JSONField,
    SlugField,
)
from utilities.forms.rendering import FieldSet, TabbedGroups
from utilities.forms.widgets import DatePicker

from ..constants import AUDITFLOW_OBJECT_TYPE_CHOICES
from ..models import *
from ..utils import get_tags_and_edit_protected_asset_fields
from netbox_inventory.choices import HardwareKindChoices

__all__ = (
    'AssetForm',
    'AuditFlowForm',
    'AuditFlowPageAssignmentForm',
    'AuditFlowPageForm',
    'AuditTrailSourceForm',
    'ContractForm',
    'ContractSKUForm',
    'ContractVendorForm',
    'ContractAssignmentForm',
    'OrderForm',
    'InventoryItemGroupForm',
    'InventoryItemTypeForm',
    'PurchaseForm',
    'SupplierForm',
    'HardwareLifecycleForm',
    'VendorProgramForm',
    'AssetProgramCoverageForm',
    'LicenseSKUForm',
)


#
# Assets
#


class InventoryItemGroupForm(NetBoxModelForm):
    parent = DynamicModelChoiceField(
        queryset=InventoryItemGroup.objects.all(),
        required=False,
        label='Parent',
    )
    comments = CommentField()

    fieldsets = (
        FieldSet(
            'name',
            'parent',
            'description',
            'tags',
            name='Inventory Item Group',
        ),
    )

    class Meta:
        model = InventoryItemGroup
        fields = (
            'name',
            'parent',
            'description',
            'tags',
            'comments',
        )


class InventoryItemTypeForm(NetBoxModelForm):
    slug = SlugField(slug_source='model')
    inventoryitem_group = DynamicModelChoiceField(
        queryset=InventoryItemGroup.objects.all(),
        required=False,
        label='Inventory item group',
    )
    comments = CommentField()

    fieldsets = (
        FieldSet(
            'manufacturer',
            'model',
            'slug',
            'description',
            'part_number',
            'inventoryitem_group',
            'tags',
            name='Inventory Item Type',
        ),
    )

    class Meta:
        model = InventoryItemType
        fields = (
            'manufacturer',
            'model',
            'slug',
            'description',
            'part_number',
            'inventoryitem_group',
            'tags',
            'comments',
        )


class AssetForm(NetBoxModelForm):
    manufacturer = DynamicModelChoiceField(
        queryset=Manufacturer.objects.all(),
        required=False,
        initial_params={
            'device_types': '$device_type',
            'module_types': '$module_type',
            'inventoryitem_types': '$inventoryitem_type',
            'rack_types': '$rack_type',
        },
    )
    device_type = DynamicModelChoiceField(
        queryset=DeviceType.objects.all(),
        required=False,
        query_params={
            'manufacturer_id': '$manufacturer',
        },
    )
    module_type = DynamicModelChoiceField(
        queryset=ModuleType.objects.all(),
        required=False,
        query_params={
            'manufacturer_id': '$manufacturer',
        },
    )
    inventoryitem_type = DynamicModelChoiceField(
        queryset=InventoryItemType.objects.all(),
        required=False,
        query_params={
            'manufacturer_id': '$manufacturer',
        },
        label='Inventory item type',
    )
    rack_type = DynamicModelChoiceField(
        queryset=RackType.objects.all(),
        required=False,
        query_params={
            'manufacturer_id': '$manufacturer',
        },
    )
    owner = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        help_text=Asset._meta.get_field('owner').help_text,
        required=not Asset._meta.get_field('owner').blank,
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
        query_params={'purchase_id': '$purchase'},
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
        initial_params={
            'contact': '$contact',
        },
    )
    contact = DynamicModelChoiceField(
        queryset=Contact.objects.all(),
        help_text=Asset._meta.get_field('contact').help_text,
        required=not Asset._meta.get_field('contact').blank,
        query_params={
            'group_id': '$contact_group',
        },
    )
    storage_site = DynamicModelChoiceField(
        queryset=Site.objects.all(),
        required=False,
        initial_params={
            'locations': '$storage_location',
        },
    )
    storage_location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        help_text=Asset._meta.get_field('storage_location').help_text,
        required=False,
        query_params={
            'site_id': '$storage_site',
        },
    )
    base_license_sku = DynamicModelChoiceField(
        queryset=LicenseSKU.objects.filter(license_kind=LicenseKindChoices.PERPETUAL),
        required=False,
        query_params={
            # Filter by manufacturer field on the Asset form if you have it:
            "manufacturer_id": "$manufacturer",
        },
    )
    comments = CommentField()

    fieldsets = (
        FieldSet('name', 'asset_tag', 'description', 'tags', 'status', name='General'),
        FieldSet(
            'serial',
            'vendor_instance_id',
            'manufacturer',
            'device_type',
            'module_type',
            'inventoryitem_type',
            'rack_type',
            name='Hardware',
        ),
        FieldSet(
            'owner',
            'purchase',
            'order',
            'base_license_sku',
            name='Purchase',
        ),
        FieldSet(
            'vendor_ship_date',
            'warranty_start',
            'warranty_end',
            name='Key Hardware Dates',
        ),
        FieldSet('tenant', 'contact_group', 'contact', name='Assigned to'),
        FieldSet('storage_site', 'storage_location', name='Location'),
    )

    class Meta:
        model = Asset
        fields = (
            'name',
            'asset_tag',
            'serial',
            'vendor_instance_id',
            'status',
            'allocation_status',
            'manufacturer',
            'device_type',
            'module_type',
            'inventoryitem_type',
            'rack_type',
            'storage_location',
            'owner',
            'purchase',
            'order',
            'base_license_sku',
            'vendor_ship_date',
            'warranty_start',
            'warranty_end',
            'tenant',
            'contact_group',
            'contact',
            'tags',
            'description',
            'comments',
            'storage_site',
            'installed_site_override',
        )
        widgets = {
            'vendor_ship_date': DatePicker(),
            'warranty_start': DatePicker(),
            'warranty_end': DatePicker(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._disable_fields_by_tags()

        # Only apply the cf_ filter if the custom field exists on dcim.Location
        has_storage_cf = CustomField.objects.filter(
            name="asset_storage_location",
            object_types__app_label="dcim",
            object_types__model="location",
        ).exists()

        if not has_storage_cf:
            return

        field = self.fields["storage_location"]
        widget = field.widget

        # Prefer the widget helper if available (NetBox uses this internally)
        if hasattr(widget, "add_query_param"):
            widget.add_query_param("cf_asset_storage_location", "true")
        else:
            # Fallbacks across widget variants
            if hasattr(widget, "static_params"):
                widget.static_params["cf_asset_storage_location"] = "true"
            else:
                widget.attrs["data-query-param-cf_asset_storage_location"] = "true"

        # Used for picking the default active tab for hardware type selection
        self.no_hardware_type = True
        if self.instance:
            if (
                self.instance.device_type
                or self.instance.module_type
                or self.instance.inventoryitem_type
                or self.instance.rack_type
            ):
                self.no_hardware_type = False

        # if assigned to device/module/... we can't change device_type/...
        if (
            self.instance.device
            or self.instance.module
            or self.instance.inventoryitem
            or self.instance.rack
        ):
            self.fields['manufacturer'].disabled = True
            for kind in HardwareKindChoices.values():
                self.fields[f'{kind}_type'].disabled = True


    def _disable_fields_by_tags(self):
        """
        We need to disable fields that are not editable based on the tags that are assigned to the asset.
        """
        if not self.instance.pk:
            # If we are creating a new asset we can't disable fields
            return

        # Disable fields that should not be edited
        tags = self.instance.tags.all().values_list('slug', flat=True)
        tags_and_disabled_fields = get_tags_and_edit_protected_asset_fields()

        for tag in tags:
            if tag not in tags_and_disabled_fields:
                continue

            for field in tags_and_disabled_fields[tag]:
                if field in self.fields:
                    self.fields[field].disabled = True

    def clean(self):
        super().clean()

        # ----------------------------
        # Storage logic
        # ----------------------------
        status = self.cleaned_data.get("status")
        if status != "stored":
            self.cleaned_data["storage_location"] = None

        # ----------------------------
        # Infer purchase
        # ----------------------------
        order = self.cleaned_data.get("order")
        purchase = self.cleaned_data.get("purchase")

        if order and not purchase:
            self.cleaned_data["purchase"] = order.purchase

        # ----------------------------
        # Installed Site logic
        # ----------------------------
        status = self.cleaned_data.get("status")
        storage_location = self.cleaned_data.get("storage_location")

        # Enforce: stored => must have storage location
        if status == "stored" and not storage_location:
            self.add_error("storage_location", "Storage Location is required when Status is 'stored'.")

        # Clear storage fields unless stored (keeps data consistent)
        if status != "stored":
            self.cleaned_data["storage_location"] = None

        allocation = self.cleaned_data.get("allocation_status")
        device = self.cleaned_data.get("installed_device")
        site_override = self.cleaned_data.get("installed_site_override")

        is_deployed_without_device = (
            status == "used"
            and allocation == "allocated"
            and device is None
        )

        # Device always wins — clear manual site if device exists
        if device and site_override:
            self.cleaned_data["installed_site_override"] = None

        # Warn if OT-style deployed asset has no site info
        if is_deployed_without_device and site_override is None:
            self.add_error(
                "installed_site_override",
                "Required when Status is 'used', Allocation is 'allocated', and no device is assigned."
            )

        # If the asset is not in a state where the override is meaningful, clear it
        if not is_deployed_without_device:
            self.cleaned_data["installed_site_override"] = None

        return self.cleaned_data

#
# Contract
#


class ContractVendorForm(NetBoxModelForm):

    class Meta:
        model = ContractVendor
        fields = ('name', 'description', 'comments', 'tags', )


class ContractSKUForm(NetBoxModelForm):
    manufacturer = DynamicModelChoiceField(
        queryset=Manufacturer.objects.all(),
        selector=False,
    )

    class Meta:
        model = ContractSKU
        fields = ('manufacturer', 'sku', 'contract_type', 'description', 'comments', 'tags', )

class ContractForm(NetBoxModelForm):
    vendor = DynamicModelChoiceField(
        queryset=ContractVendor.objects.all(),
        selector=True,
    )

    class Meta:
        model = Contract
        fields = ('vendor', 'contract_id', 'description', 'contract_type', 'status',
            'start_date', 'renewal_date', 'end_date', 'comments', 'tags', )
        widgets = {
            'start_date': DatePicker(),
            'renewal_date': DatePicker(),
            'end_date': DatePicker(),
        }


class ContractAssignmentForm(NetBoxModelForm):
    contract = DynamicModelChoiceField(
        queryset=Contract.objects.all(),
        required=False,
        selector=True,
    )
    sku = DynamicModelChoiceField(
        queryset=ContractSKU.objects.all(),
        required=False,
        selector=True,
        label=_('SKU'),
    )
    asset = DynamicModelChoiceField(
        queryset=Asset.objects.all(),
        required=False,
        selector=True,
        label=_('Asset'),
    )

    class Meta:
        model = ContractAssignment
        fields = ('contract', 'sku', 'asset', 'end_date', 'description', 'comments', 'tags', )
        widgets = {
            'end_date': DatePicker(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


#
# Purchases
#


class SupplierForm(NetBoxModelForm):
    slug = SlugField(slug_source='name')
    comments = CommentField()

    fieldsets = (FieldSet('name', 'slug', 'description', 'tags', name='Supplier'),)

    class Meta:
        model = Supplier
        fields = (
            'name',
            'slug',
            'description',
            'comments',
            'tags',
        )


class PurchaseForm(NetBoxModelForm):
    comments = CommentField()

    fieldsets = (
        FieldSet(
            'supplier', 'name', 'purchase_requisition', 'purchase_order', 'internal_reference', 'supplier_reference', 'status', 'date', 'description', 'tags', name='Purchase'
        ),
    )

    class Meta:
        model = Purchase
        fields = (
            'supplier',
            'name',
            'purchase_requisition',
            'purchase_order',
            'internal_reference',
            'supplier_reference',
            'status',
            'date',
            'description',
            'comments',
            'tags',
        )
        widgets = {
            'date': DatePicker(),
        }


class OrderForm(NetBoxModelForm):
    name = forms.CharField(
        label="Order ID",
        help_text="Manufacturer-specific order identifier",
        required=True,
    )
    comments = CommentField()

    fieldsets = (
        FieldSet(
            'purchase',
            'manufacturer',
            'name',
            'description',
            'tags',
            name='Order',
        ),
    )

    class Meta:
        model = Order
        fields = (
            'purchase',
            'manufacturer',
            'name',
            'description',
            'comments',
            'tags',
        )
        widgets = {
            'date': DatePicker(),
        }


#
# Audit
#


class BaseFlowForm(NetBoxModelForm):
    """
    Internal base form class for audit flow models.
    """

    object_type = ContentTypeChoiceField(
        queryset=ObjectType.objects.public(),
    )
    object_filter = JSONField(
        required=False,
        help_text=_(
            'Enter object filter in <a href="https://json.org/">JSON</a> format, '
            'mapping attributes to values.'
        ),
    )
    comments = CommentField()

    fieldsets = (
        FieldSet(
            'name',
            'description',
            'tags',
        ),
        FieldSet(
            'object_type',
            'object_filter',
            name=_('Assignment'),
        ),
    )

    class Meta:
        fields = (
            'name',
            'description',
            'tags',
            'object_type',
            'object_filter',
            'comments',
        )


class AuditFlowPageForm(BaseFlowForm):
    class Meta(BaseFlowForm.Meta):
        model = AuditFlowPage


class AuditFlowForm(BaseFlowForm):
    # Restrict inherited object_type to those object types that represent physical
    # locations.
    object_type = ContentTypeChoiceField(
        queryset=ObjectType.objects.public(),
        limit_choices_to=AUDITFLOW_OBJECT_TYPE_CHOICES,
    )

    fieldsets = (
        FieldSet(
            'name',
            'description',
            'tags',
            'enabled',
        ),
        FieldSet(
            'object_type',
            'object_filter',
            name=_('Assignment'),
        ),
    )

    class Meta(BaseFlowForm.Meta):
        model = AuditFlow
        fields = BaseFlowForm.Meta.fields + ('enabled',)


class AuditFlowPageAssignmentForm(NetBoxModelForm):
    fieldsets = (
        FieldSet(
            'flow',
            'page',
            'weight',
        ),
    )

    class Meta:
        model = AuditFlowPageAssignment
        fields = (
            'flow',
            'page',
            'weight',
        )


class AuditTrailSourceForm(NetBoxModelForm):
    slug = SlugField()
    comments = CommentField()

    fieldsets = (
        FieldSet(
            'name',
            'slug',
            'description',
            'tags',
        ),
    )

    class Meta:
        model = AuditTrailSource
        fields = (
            'name',
            'slug',
            'description',
            'comments',
            'tags',
        )


class HardwareLifecycleForm(NetBoxModelForm):
    device_type = DynamicModelChoiceField(
        queryset=DeviceType.objects.all(),
        required=False,
        selector=True,
        label=_('Device Type'),
    )
    module_type = DynamicModelChoiceField(
        queryset=ModuleType.objects.all(),
        required=False,
        selector=True,
        label=_('Module Type'),
    )

    fieldsets = (
        FieldSet(
            TabbedGroups(
                FieldSet('device_type', name=_('Device Type')),
                FieldSet('module_type', name=_('Module Type')),
            ),
        ),
        FieldSet(
            'last_contract_attach',
            'last_contract_renewal',
            'end_of_sale',
            'end_of_maintenance',
            'end_of_security',
            'end_of_support',
            'support_basis',
            name=_('Dates'),
        ),
        FieldSet('notice_url', 'description', name=_('Information')),
        FieldSet('tags', name=_('Tags')),
    )

    class Meta:
        model = HardwareLifecycle
        fields = (
            'last_contract_attach',
            'last_contract_renewal',
            'end_of_sale',
            'end_of_maintenance',
            'end_of_security',
            'end_of_support',
            'notice_url',
            'support_basis',
            'description',
            'comments',
            'tags',
        )
        widgets = {
            'last_contract_attach': DatePicker(),
            'last_contract_renewal': DatePicker(),
            'end_of_sale': DatePicker(),
            'end_of_maintenance': DatePicker(),
            'end_of_security': DatePicker(),
            'end_of_support': DatePicker(),
        }

    def __init__(self, *args, **kwargs):
        # Initialize helper selectors
        instance = kwargs.get('instance')
        initial = kwargs.get('initial', {}).copy()
        if instance:
            if type(instance.assigned_object) is DeviceType:
                initial['device_type'] = instance.assigned_object
            elif type(instance.assigned_object) is ModuleType:
                initial['module_type'] = instance.assigned_object
        kwargs['initial'] = initial

        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()

        # Handle object assignment
        selected_objects = [
            field
            for field in ('device_type', 'module_type')
            if self.cleaned_data[field]
        ]

        if len(selected_objects) > 1:
            raise forms.ValidationError(
                {
                    selected_objects[
                        1
                    ]: "You can only have a lifecycle for a device or module type"
                }
            )
        elif selected_objects:
            self.instance.assigned_object = self.cleaned_data[selected_objects[0]]
        else:
            self.instance.assigned_object = None


class VendorProgramForm(NetBoxModelForm):
    slug = SlugField(slug_source='name')
    comments = CommentField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If an asset is selected/known, constrain program choices to matching manufacturer
        asset = self.initial.get('asset') or getattr(self.instance, 'asset', None)
        if asset is None and 'asset' in self.data:
            try:
                asset = AssetProgramCoverage._meta.get_field('asset').remote_field.model.objects.get(pk=self.data.get('asset'))
            except Exception:
                asset = None

        asset_mfr = None
        asset_device = getattr(asset, 'device', None) if asset else None
        if asset_device is not None:
            device_type = getattr(asset_device, 'device_type', None)
            if device_type is not None:
                asset_mfr = getattr(device_type, 'manufacturer', None)

        if asset_mfr is not None:
            self.fields['program'].queryset = VendorProgram.objects.filter(manufacturer=asset_mfr).order_by('name')

    class Meta:
        model = VendorProgram
        fields = (
            "name",
            "slug",
            "manufacturer",
            'contract_type',
            "description",
            "tags",
            "comments",
        )


class AssetProgramCoverageForm(NetBoxModelForm):
    comments = CommentField()
    program = DynamicModelChoiceField(
        queryset=VendorProgram.objects.all(),
        required=True,
    )
    asset = DynamicModelChoiceField(
        queryset=Asset.objects.all(),
        required=True,
        query_params={
            # This will call the Asset API with ?program_id=<selected_program_id>
            "program_id": "$program",
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # If an asset is selected/known, constrain program choices to matching manufacturer
        asset = self.initial.get('asset') or getattr(self.instance, 'asset', None)
        if asset is None and 'asset' in self.data:
            try:
                asset = AssetProgramCoverage._meta.get_field('asset').remote_field.model.objects.get(pk=self.data.get('asset'))
            except Exception:
                asset = None

        asset_mfr = None
        asset_device = getattr(asset, 'device', None) if asset else None
        if asset_device is not None:
            device_type = getattr(asset_device, 'device_type', None)
            if device_type is not None:
                asset_mfr = getattr(device_type, 'manufacturer', None)

        if asset_mfr is not None:
            self.fields['program'].queryset = VendorProgram.objects.filter(manufacturer=asset_mfr).order_by('name')

    class Meta:
        model = AssetProgramCoverage
        fields = (
            "program",
            "asset",
            "status",
            "eligibility",
            "effective_start",
            "effective_end",
            "decision_reason",
            "evidence_url",
            "source",
            "last_synced",
            "tags",
            "comments",
            "notes",
        )
        widgets = {
            'effective_start': DatePicker(),
            'effective_end': DatePicker(),
        }


class LicenseSKUForm(NetBoxModelForm):
    manufacturer = DynamicModelChoiceField(
        queryset=Manufacturer.objects.all()
    )

    class Meta:
        model = LicenseSKU
        fields = (
            "manufacturer",
            "sku",
            "name",
            "license_kind",
            "description",
            "tags",
        )
