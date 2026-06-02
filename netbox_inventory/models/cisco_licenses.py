from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from dcim.models import Site
from netbox.models import NetBoxModel
from tenancy.models import Tenant

from ..choices import LicenseDataSourceChoices, LicenseOrderSourceChoices, LicenseTypeChoices

__all__ = (
    'CiscoSmartAccount',
    'VirtualAccount',
    'LicenseOrder',
    'LicenseOrderLineItem',
    'LicenseLineItemAllocation',
)


class CiscoSmartAccount(NetBoxModel):
    name = models.CharField(
        max_length=200,
        verbose_name=_('Name'),
        help_text=_('e.g. WOODSIDE ENERGY LTD'),
    )
    domain = models.CharField(
        max_length=200,
        unique=True,
        verbose_name=_('Domain'),
        help_text=_('e.g. woodside.com'),
    )
    comments = models.TextField(blank=True, verbose_name=_('Comments'))

    clone_fields = ('name',)

    class Meta:
        ordering = ('name',)
        verbose_name = _('Cisco Smart Account')
        verbose_name_plural = _('Cisco Smart Accounts')

    def __str__(self):
        return f'{self.name} ({self.domain})'

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:ciscosmartaccount', args=[self.pk])


class VirtualAccount(NetBoxModel):
    smart_account = models.ForeignKey(
        to='netbox_inventory.CiscoSmartAccount',
        on_delete=models.PROTECT,
        related_name='virtual_accounts',
        verbose_name=_('Smart Account'),
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_('Name'),
        help_text=_('e.g. AusOps - IT - MB2'),
    )
    site = models.ForeignKey(
        to=Site,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='virtual_accounts',
        verbose_name=_('Site'),
    )
    tenant = models.ForeignKey(
        to=Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='virtual_accounts',
        verbose_name=_('Tenant'),
        help_text=_('e.g. IT or OT tenant for this site'),
    )
    va_token = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Registration Token'),
        help_text=_('Token used for device registration against this Virtual Account.'),
    )
    va_token_expiry = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Token Expiry'),
    )
    comments = models.TextField(blank=True, verbose_name=_('Comments'))

    clone_fields = ('smart_account', 'site', 'tenant')
    prerequisite_models = ('netbox_inventory.CiscoSmartAccount',)

    class Meta:
        ordering = ('smart_account', 'name')
        verbose_name = _('Virtual Account')
        verbose_name_plural = _('Virtual Accounts')
        constraints = (
            models.UniqueConstraint(
                fields=['smart_account', 'name'],
                name='%(app_label)s_%(class)s_unique_smart_account_name',
                violation_error_message=_('Virtual Account name must be unique within a Smart Account.'),
            ),
        )

    def __str__(self):
        return f'{self.smart_account.domain} / {self.name}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:virtualaccount', args=[self.pk])


class LicenseOrder(NetBoxModel):
    cisco_order_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Cisco Order Number'),
        help_text=_('Cisco-assigned order identifier. May be absent for EA portal-generated orders.'),
    )
    subscription_id = models.CharField(
        max_length=128,
        blank=True,
        verbose_name=_('Subscription ID'),
        help_text=_('Vendor subscription or EA identifier. Always present for EA orders.'),
    )
    source = models.CharField(
        max_length=20,
        choices=LicenseOrderSourceChoices,
        default=LicenseOrderSourceChoices.STANDARD,
        verbose_name=_('Source'),
    )
    purchase = models.ForeignKey(
        to='netbox_inventory.Purchase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='license_orders',
        verbose_name=_('Purchase'),
        help_text=_('Purchase this license order was raised against. Optional for EA-generated orders.'),
    )
    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Synced'),
        help_text=_('Set by the reconcile script on each API sync.'),
    )
    notes = models.TextField(blank=True, verbose_name=_('Notes'))
    comments = models.TextField(blank=True, verbose_name=_('Comments'))

    clone_fields = ('source', 'purchase')
    prerequisite_models = ('netbox_inventory.Purchase',)

    class Meta:
        ordering = ('cisco_order_number', 'subscription_id')
        verbose_name = _('License Order')
        verbose_name_plural = _('License Orders')

    def __str__(self):
        if self.cisco_order_number:
            return self.cisco_order_number
        if self.subscription_id:
            return f'Sub: {self.subscription_id}'
        return f'License Order #{self.pk}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:licenseorder', args=[self.pk])


class LicenseOrderLineItem(NetBoxModel):
    license_order = models.ForeignKey(
        to='netbox_inventory.LicenseOrder',
        on_delete=models.CASCADE,
        related_name='line_items',
        verbose_name=_('License Order'),
    )
    po_line_item_number = models.CharField(
        max_length=100,
        verbose_name=_('PO Line Item Number'),
        help_text=_("Cisco's purchaseOrderLineItemNo."),
    )
    product_sku = models.CharField(
        max_length=100,
        verbose_name=_('Product SKU'),
        help_text=_('e.g. C9300X-DNA-24Y-A'),
    )
    product_name = models.CharField(
        max_length=200,
        verbose_name=_('Product Name'),
    )
    license_type = models.CharField(
        max_length=20,
        choices=LicenseTypeChoices,
        default=LicenseTypeChoices.TERM,
        verbose_name=_('License Type'),
    )
    quantity_ordered = models.PositiveIntegerField(
        verbose_name=_('Quantity Ordered'),
    )
    subscription_id = models.CharField(
        max_length=128,
        blank=True,
        verbose_name=_('Subscription ID'),
        help_text=_('May be set at line item level when different from the order.'),
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Start Date'),
        help_text=_('TERM licenses only.'),
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('End Date'),
        help_text=_('TERM licenses only. EA end date for EA-generated orders.'),
    )
    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Synced'),
    )
    comments = models.TextField(blank=True, verbose_name=_('Comments'))

    clone_fields = ('license_order', 'license_type', 'product_sku', 'product_name')
    prerequisite_models = ('netbox_inventory.LicenseOrder',)

    class Meta:
        ordering = ('license_order', 'po_line_item_number')
        verbose_name = _('License Order Line Item')
        verbose_name_plural = _('License Order Line Items')
        constraints = (
            models.UniqueConstraint(
                fields=['license_order', 'po_line_item_number'],
                name='%(app_label)s_%(class)s_unique_order_line_item',
                violation_error_message=_('Line item number must be unique within a license order.'),
            ),
        )

    def __str__(self):
        return f'{self.license_order} / {self.po_line_item_number} — {self.product_sku}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:licenseorderlineitem', args=[self.pk])


class LicenseLineItemAllocation(NetBoxModel):
    line_item = models.ForeignKey(
        to='netbox_inventory.LicenseOrderLineItem',
        on_delete=models.CASCADE,
        related_name='allocations',
        verbose_name=_('Line Item'),
    )
    virtual_account = models.ForeignKey(
        to='netbox_inventory.VirtualAccount',
        on_delete=models.PROTECT,
        related_name='allocations',
        verbose_name=_('Virtual Account'),
    )
    quantity = models.PositiveIntegerField(
        verbose_name=_('Quantity'),
        help_text=_('Portion of the line item quantity allocated to this Virtual Account.'),
    )
    data_source = models.CharField(
        max_length=20,
        choices=LicenseDataSourceChoices,
        default=LicenseDataSourceChoices.MANUAL,
        verbose_name=_('Data Source'),
        help_text=_('MANUAL records are editable in the UI. API_SYNC records are managed by the reconcile script.'),
    )
    synced_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Last Synced'),
    )
    comments = models.TextField(blank=True, verbose_name=_('Comments'))

    clone_fields = ('line_item', 'virtual_account', 'data_source')
    prerequisite_models = (
        'netbox_inventory.LicenseOrderLineItem',
        'netbox_inventory.VirtualAccount',
    )

    class Meta:
        ordering = ('line_item', 'virtual_account')
        verbose_name = _('License Line Item Allocation')
        verbose_name_plural = _('License Line Item Allocations')
        constraints = (
            models.UniqueConstraint(
                fields=['line_item', 'virtual_account'],
                name='%(app_label)s_%(class)s_unique_line_item_virtual_account',
                violation_error_message=_('An allocation for this line item and Virtual Account already exists.'),
            ),
        )

    def __str__(self):
        return f'{self.line_item} → {self.virtual_account} ({self.quantity})'

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:licenselineitemallocation', args=[self.pk])
