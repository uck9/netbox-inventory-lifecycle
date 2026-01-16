from datetime import date

from django.db import models
from django.forms import ValidationError


from netbox.models import NestedGroupModel
from netbox.models.features import ImageAttachmentsMixin

from ..choices import AssetStatusChoices, AssetAllocationStatusChoices, AssetDisposalReasonhoices, HardwareKindChoices
from ..managers import AssetManager
from ..utils import (
    asset_clear_old_hw,
    asset_set_new_hw,
    get_plugin_setting,
    get_prechange_field,
    get_status_for,
)
from .mixins import NamedModel


class InventoryItemGroup(NestedGroupModel, NamedModel):
    """
    Inventory Item Groups are groups of simmilar InventoryItemTypes.
    This allows you to, for example, have one Group for all your 10G-LR SFP
    pluggables, from different manufacturers/with different part numbers.
    Inventory Item Groups can be nested.
    """

    slug = None  # remove field that is defined on NestedGroupModel

    class Meta:
        ordering = ['name']
        constraints = (
            models.UniqueConstraint(
                fields=('parent', 'name'), name='%(app_label)s_%(class)s_parent_name'
            ),
            models.UniqueConstraint(
                fields=('name',),
                name='%(app_label)s_%(class)s_name',
                condition=models.Q(parent__isnull=True),
                violation_error_message='A top-level group with this name already exists.',
            ),
        )


class InventoryItemType(NamedModel, ImageAttachmentsMixin):
    """
    Inventory Item Type is a model (make, part number) of an Inventory Item. In
    that it is simmilar to Device Type or Module Type.
    """

    name = None  # remove field that is defined on PrimaryModel

    manufacturer = models.ForeignKey(
        to='dcim.Manufacturer',
        on_delete=models.PROTECT,
        related_name='inventoryitem_types',
    )
    model = models.CharField(
        max_length=100,
    )
    slug = models.SlugField(
        max_length=100,
    )
    part_number = models.CharField(
        max_length=50,
        blank=True,
        help_text='Discrete part number (optional)',
        verbose_name='Part Number',
    )
    inventoryitem_group = models.ForeignKey(
        to='netbox_inventory.InventoryItemGroup',
        on_delete=models.SET_NULL,
        related_name='inventoryitem_types',
        blank=True,
        null=True,
        verbose_name='Inventory Item Group',
    )

    clone_fields = [
        'manufacturer',
    ]

    class Meta:
        ordering = ['manufacturer', 'model']
        unique_together = [
            ['manufacturer', 'model'],
            ['manufacturer', 'slug'],
        ]

    def __str__(self):
        return self.model


class Asset(NamedModel, ImageAttachmentsMixin):
    """
    An Asset represents a piece of hardware we want to keep track of. It has a
    make (model, part number) that is one of: Device Type, Module Type,
    InventoryItem Type or Rack Type.

    Asset must have a serial number, can have an asset tag (inventory number). It
    must have one of DeviceType, ModuleType, InventoryItemType, RackType. It can have
    a storage location (instance of Location). There are also fields to keep track of
    purchase and warranty info.

    An asset that is in use, can be assigned to a Device, Module, InventoryItem or
    Rack.
    """

    objects = AssetManager()

    #
    # fields that identify asset
    #
    name = models.CharField(
        help_text='Can be used to quickly identify a particular asset',
        max_length=128,
        blank=True,
        null=False,
        default='',
    )
    asset_tag = models.CharField(
        help_text='Identifier assigned by owner',
        max_length=50,
        blank=True,
        null=True,
        default=None,
        verbose_name='Asset Tag',
    )
    serial = models.CharField(
        help_text='Identifier assigned by manufacturer',
        max_length=60,
        verbose_name='Serial Number',
        blank=True,
        null=True,
        default=None,
    )

    #
    # status fields
    #
    status = models.CharField(
        max_length=30,
        choices=AssetStatusChoices,
        help_text='Asset physicallifecycle status',
        verbose_name='Physical Status',
    )
    allocation_status = models.CharField(
        max_length=30,
        choices=AssetAllocationStatusChoices,
        help_text='Asset logical allocation status',
        verbose_name='Allocation Status',
        default=None,
        null=True,
        blank=True,
    )

    #
    # hardware type fields
    #
    device_type = models.ForeignKey(
        to='dcim.DeviceType',
        on_delete=models.PROTECT,
        related_name='assets',
        blank=True,
        null=True,
        verbose_name='Device Type',
    )
    module_type = models.ForeignKey(
        to='dcim.ModuleType',
        on_delete=models.PROTECT,
        related_name='assets',
        blank=True,
        null=True,
        verbose_name='Module Type',
    )
    inventoryitem_type = models.ForeignKey(
        to='netbox_inventory.InventoryItemType',
        on_delete=models.PROTECT,
        related_name='+',
        blank=True,
        null=True,
        verbose_name='Inventory Item Type',
    )
    rack_type = models.ForeignKey(
        to='dcim.RackType',
        on_delete=models.PROTECT,
        related_name='assets',
        blank=True,
        null=True,
        verbose_name='Rack Type',
    )

    #
    # used fields
    #
    device = models.OneToOneField(
        to='dcim.Device',
        on_delete=models.SET_NULL,
        related_name='assigned_asset',
        blank=True,
        null=True,
    )
    module = models.OneToOneField(
        to='dcim.Module',
        on_delete=models.SET_NULL,
        related_name='assigned_asset',
        blank=True,
        null=True,
    )
    inventoryitem = models.OneToOneField(
        to='dcim.InventoryItem',
        on_delete=models.SET_NULL,
        related_name='assigned_asset',
        blank=True,
        null=True,
        verbose_name='Inventory Item',
    )
    rack = models.OneToOneField(
        to='dcim.Rack',
        on_delete=models.SET_NULL,
        related_name='assigned_asset',
        blank=True,
        null=True,
    )
    tenant = models.ForeignKey(
        help_text='Tenant using this asset',
        to='tenancy.Tenant',
        on_delete=models.PROTECT,
        related_name='+',
        blank=True,
        null=True,
    )
    contact = models.ForeignKey(
        help_text='Contact using this asset',
        to='tenancy.Contact',
        on_delete=models.PROTECT,
        related_name='+',
        blank=True,
        null=True,
    )
    storage_location = models.ForeignKey(
        help_text='Where is this asset stored when not in use',
        to='dcim.Location',
        on_delete=models.PROTECT,
        related_name='assets',
        blank=True,
        null=True,
        verbose_name='Storage Location',
    )
    installed_site_override = models.ForeignKey(
        to='dcim.Site',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="assets_with_installed_site_override",
        help_text=(
            "Manual site for deployed assets when no installed device exists. "
            "Ignored if asset is assigned to a device."
        ),
    )
    #
    # purchase info
    #
    owner = models.ForeignKey(
        help_text='Who owns this asset',
        to='tenancy.Tenant',
        on_delete=models.PROTECT,
        related_name='+',
        blank=True,
        null=True,
    )
    order = models.ForeignKey(
        help_text='Order this asset was part of',
        to='netbox_inventory.Order',
        on_delete=models.PROTECT,
        related_name='assets',
        blank=True,
        null=True,
    )
    purchase = models.ForeignKey(
        help_text='Purchase through which this asset was procured.',
        to='netbox_inventory.Purchase',
        on_delete=models.PROTECT,
        related_name='assets',
        blank=True,
        null=True,
    )
    contract = models.ManyToManyField(
        help_text='Contracts associated with this asset',
        to='netbox_inventory.Contract',
        related_name='assets',
        blank=True,
        verbose_name='Contracts',
    )
    vendor_ship_date = models.DateField(
        help_text='Date when vendor shipped this asset',
        blank=True,
        null=True,
        verbose_name='Vendor Ship Date',
    )
    warranty_start = models.DateField(
        help_text='First date warranty for this asset is valid',
        blank=True,
        null=True,
        verbose_name='Warranty Start',
    )
    warranty_end = models.DateField(
        help_text='Last date warranty for this asset is valid',
        blank=True,
        null=True,
        verbose_name='Warranty End',
    )
    base_license_sku = models.ForeignKey(
        to="netbox_inventory.LicenseSKU",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assets_as_base',
        verbose_name='Base license SKU',
        help_text='Perpetual/base entitlement tied to the hardware.',
    )
    vendor_instance_id = models.CharField(
        help_text='A vendor-assigned unique identifier for the physical device instance, distinct from serial number.',
        max_length=100,
        verbose_name='Vendor Instance ID',
        blank=True,
        null=True,
        default=None,
    )

    #
    # Disposal Info
    #
    disposal_date = models.DateField(
        help_text='Date this asset was disposed',
        blank=True,
        null=True,
        verbose_name='Disposal Date',
    )
    disposal_reason = models.CharField(
        max_length=30,
        choices=AssetDisposalReasonhoices,
        help_text='Asset disposal reason',
        blank=True,
        null=True,
    )
    disposal_reference = models.CharField(
        help_text='Disposal reference number or notes',
        max_length=100,
        verbose_name='Disposal Reference',
        blank=True,
        null=True,
        default=None,
    )

    clone_fields = [
        'name',
        'asset_tag',
        'status',
        'device_type',
        'module_type',
        'inventoryitem_type',
        'owner',
        'purchase',
        'order',
        'contract',
        'warranty_start',
        'warranty_end',
        'tenant',
        'contact',
        'storage_location',
        'comments',
    ]

    @property
    def kind(self):
        if self.device_type_id:
            return 'device'
        elif self.module_type_id:
            return 'module'
        elif self.inventoryitem_type_id:
            return 'inventoryitem'
        elif self.rack_type_id:
            return 'rack'
        assert False, f'Invalid hardware kind detected for asset {self.pk}'

    def get_kind_display(self):
        return dict(HardwareKindChoices)[self.kind]

    @property
    def hardware_type(self):
        return (
            self.device_type
            or self.module_type
            or self.inventoryitem_type
            or self.rack_type
            or None
        )

    @property
    def hardware(self):
        return self.device or self.module or self.inventoryitem or self.rack or None

    @property
    def storage_site(self):
        if self.storage_location:
            return self.storage_location.site

    @property
    def installed_site(self):
        """
        Effective installed site for this asset.

        Precedence:
        1) installed_device.site (device/module/inventoryitem's device site)
        2) installed_site_override (manual, e.g. OT assets)
        3) rack.site (if the asset itself is a rack)
        """
        device = self.installed_device
        if device and device.site:
            return device.site

        if self.installed_site_override:
            return self.installed_site_override

        if self.rack and self.rack.site:
            return self.rack.site

        return None

    @property
    def installed_location(self):
        device = self.installed_device
        if device:
            return device.location
        if self.rack:
            return self.rack.location

    @property
    def installed_rack(self):
        device = self.installed_device
        if device:
            return device.rack
        if self.rack:
            return self.rack

    @property
    def installed_device(self):
        if self.kind == 'rack':
            return None
        elif self.kind == 'device':
            return self.device
        elif self.hardware:
            return self.hardware.device
        else:
            return None

    @property
    def current_site(self):
        installed = self.installed_site
        if installed:
            return installed
        return self.storage_site

    @property
    def current_location(self):
        installed = self.installed_location
        # we can have an installed site but no installed location
        # so return None in that case
        if installed or self.installed_site:
            return installed
        return self.storage_location

    @property
    def warranty_remaining(self):
        """
        How many days are left in warranty period.
        Returns negative duration if warranty expired
        Return None if warranty_end not defined
        """
        if self.warranty_end:
            return self.warranty_end - date.today()
        return None

    @property
    def warranty_elapsed(self):
        """
        How many days have passed in warranty period.
        Returns negative duration if period has not started yet
        Return None if warranty_start not defined
        """
        if self.warranty_start:
            return date.today() - self.warranty_start
        return None

    @property
    def warranty_total(self):
        if self.warranty_end and self.warranty_start:
            return self.warranty_end - self.warranty_start
        return None

    @property
    def warranty_progress(self):
        """
        Percentage of warranty elapsed
        Returns > 100 if warranty has expired, < 0 if not started yet and None
        if warranty_start or warranty_end not set.
        """
        if not self.warranty_start or not self.warranty_end:
            return None
        return int(100 * (self.warranty_elapsed / self.warranty_total))

    def clean(self):
        self.clean_order()
        self.clean_warranty_dates()
        self.validate_hardware_types()
        self.validate_hardware()
        self.update_status()
        self.update_allocation_status()
        self.validate_storage_location_required()
        self.clean_storage_fields()
        self.clean_installed_site_override()
        return super().clean()

    def save(self, clear_old_hw=True, *args, **kwargs):
        self.update_allocation_status()
        self.update_hardware_used(clear_old_hw)
        return super().save(*args, **kwargs)

    def validate_hardware_types(self):
        """
        Ensure only one device/module_type/inventoryitem_type/rack_type is set at a time.
        """
        if (
            sum(
                map(
                    bool,
                    [
                        self.device_type,
                        self.module_type,
                        self.inventoryitem_type,
                        self.rack_type,
                    ],
                )
            )
            > 1
        ):
            raise ValidationError(
                'Only one of device type, module type inventory item type and rack type can be set for the same asset.'
            )
        if (
            not self.device_type
            and not self.module_type
            and not self.inventoryitem_type
            and not self.rack_type
        ):
            raise ValidationError(
                'One of device type, module type, inventory item type or rack type must be set.'
            )

    def validate_hardware(self):
        """
        Ensure only one device/module is set at a time and it matches device/module_type.
        """
        kind = self.kind
        _type = getattr(self, kind + '_type')
        hw = getattr(self, kind)
        hw_others = dict(HardwareKindChoices).keys() - [kind]

        # e.g.: self.device_type and self.device.device_type must match
        # InventoryItem does not have FK to InventoryItemType
        if kind != 'inventoryitem':
            if not getattr(self, '_in_reassign', False):
                # but don't check if we are reassigning asset to another device
                if hw and _type != getattr(hw, kind + '_type'):
                    raise ValidationError(
                        {
                            kind: f'{kind} type of {kind} does not match {kind} type of asset'
                        }
                    )
        # ensure only one hardware is set and that it is correct kind
        # e.g. if self.device_type is set, we cannot have self.module or self.inventoryitem set
        for hw_other in hw_others:
            if getattr(self, hw_other):
                raise ValidationError(
                    f'Cannot set {hw_other} for asset that is a {kind}'
                )

    def update_status(self):
        """
        If asset was assigned or unassigned to a particular device, module, inventoryitem, rack
        update asset.status. Depending on plugin configuration.
        """
        old_hw = get_prechange_field(self, self.kind)
        new_hw = getattr(self, self.kind)
        old_status = get_prechange_field(self, 'status')
        stored_status = get_status_for('stored')
        used_status = get_status_for('used')
        if old_status != self.status:
            # status has also been changed manually, don't change it automatically
            return
        if used_status and new_hw and not old_hw:
            self.status = used_status
        elif stored_status and not new_hw and old_hw:
            self.status = stored_status

    def update_allocation_status(self):
        """
        Enforce allocation_status rules:

        - If the asset is assigned to a *device* and physical status is 'used',
        allocation_status must be 'consumed'.
        - If no device is assigned, do not force allocation_status.
        But if the record still has the default UNALLOCATED and status is 'used',
        clear it to NULL so manual "used but not deployed" is clean.
        """
        USED = "used"
        CONSUMED = "consumed"

        # If assigned to a device and used -> consumed (hard rule)
        if self.device_id and self.status == USED:
            self.allocation_status = CONSUMED
            return

        # If no device, allow allocation_status to remain NULL.
        # Also normalize: if status is used and allocation_status is the default UNALLOCATED, clear it.
        if not self.device_id and self.status == USED:
            if self.allocation_status == AssetAllocationStatusChoices.UNALLOCATED:
                self.allocation_status = None

    def update_hardware_used(self, clear_old_hw=True):
        """
        If assigning as device, module, inventoryitem or rack set serial and
        asset_tag on it. Also remove them if unasigning.
        """
        if not get_plugin_setting('sync_hardware_serial_asset_tag'):
            return None
        old_hw = get_prechange_field(self, self.kind)
        new_hw = getattr(self, self.kind)
        if old_hw:
            old_hw.snapshot()
        if new_hw:
            new_hw.snapshot()
        old_serial = get_prechange_field(self, 'serial')
        old_asset_tag = get_prechange_field(self, 'asset_tag')
        if not new_hw and old_hw and clear_old_hw:
            # unassigned existing asset, nothing asssigned now
            asset_clear_old_hw(old_hw)
        elif new_hw and old_hw != new_hw:
            # assigned something new
            if old_hw and clear_old_hw:
                # but first clear previous hw data
                asset_clear_old_hw(old_hw)
            asset_set_new_hw(asset=self, hw=new_hw)
        elif self.serial != old_serial or self.asset_tag != old_asset_tag:
            # just changed asset's serial or asset_tag, update assigned hw
            if new_hw:
                asset_set_new_hw(asset=self, hw=new_hw)

    def clean_order(self):
        if self.order and self.order.purchase != self.purchase:
            raise ValidationError(
                f'Assigned order must belong to selected purchase ({self.purchase}).'
            )

    def clean_warranty_dates(self):
        if (
            self.warranty_start
            and self.warranty_end
            and self.warranty_end <= self.warranty_start
        ):
            raise ValidationError(
                {'warranty_end': 'Warranty end date must be after warranty start date.'}
            )

    def clean_installed_site_override(self):
        """
        Keep installed_site_override meaningful and non-conflicting.

        - If a device is associated (directly or indirectly), override is ignored -> clear it.
        - If not in deployed state (used+allocated), override is meaningless -> clear it.
        """
        deployed_without_device = (
            self.status == 'used'
            and self.allocation_status == 'allocated'
            and self.installed_device is None
        )

        # If any installed device exists, device.site is authoritative
        if self.installed_device is not None and self.installed_site_override_id is not None:
            self.installed_site_override = None
            return

        # Only keep override in the specific OT scenario we care about
        if not deployed_without_device and self.installed_site_override_id is not None:
            self.installed_site_override = None
            return

        # Optional HARD enforcement (uncomment if you want to block saving)
        # if deployed_without_device and self.installed_site_override_id is None:
        #     raise ValidationError({
        #         'installed_site_override': "Required when Status is 'used' and Allocation Status is 'allocated' and no device is assigned."
        #     })

    def clean_storage_fields(self):
        """
        Storage fields are only meaningful when status == stored.
        Clear them otherwise to avoid conflicting state.
        """
        if self.status != 'stored':
            # storage_site is derived from storage_location, so only clear storage_location
            if self.storage_location_id is not None:
                self.storage_location = None


    def validate_storage_location_required(self):
        if self.status == 'stored' and self.storage_location_id is None:
            raise ValidationError({
                'storage_location': "Storage Location is required when Status is 'stored'."
            })

    def get_status_color(self):
        return AssetStatusChoices.colors.get(self.status)

    def get_allocation_status_color(self):
        return AssetAllocationStatusChoices.colors.get(self.allocation_status)

    def __str__(self):
        parts = [
            self.asset_tag,
            self.hardware_type,
            self.serial,
        ]

        # Keep only truthy values (None, "", etc. are dropped)
        label = " - ".join(str(p) for p in parts if p)

        # Absolute fallback so __str__ never returns empty
        return label or f'{self.hardware_type} (id:{self.id})'

    class Meta:
        ordering = (
            'device_type',
            'module_type',
            'inventoryitem_type',
            'rack_type',
            'serial',
        )
        constraints = (
            models.UniqueConstraint(
                fields=('device_type', 'serial'),
                name='unique_device_type_serial',
            ),
            models.UniqueConstraint(
                fields=('module_type', 'serial'),
                name='unique_module_type_serial',
            ),
            models.UniqueConstraint(
                fields=('inventoryitem_type', 'serial'),
                name='unique_inventoryitem_type_serial',
            ),
            models.UniqueConstraint(
                fields=('rack_type', 'serial'),
                name='unique_rack_type_serial',
            ),
            models.UniqueConstraint(
                fields=('owner', 'asset_tag'),
                name='unique_owner_asset_tag',
            ),
            models.UniqueConstraint(
                'asset_tag',
                condition=models.Q(owner__isnull=True),
                name='unique_asset_tag',
                violation_error_message='Asset with this Asset Tag and no Owner already exists.',
            ),
        )
