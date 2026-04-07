from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from dcim.models import Manufacturer
from netbox.models import NetBoxModel

__all__ = (
    'LicenseSKU',
    'LicenseKindChoices',
    'Subscription',
    'AssetLicense',
)

class LicenseKindChoices(models.TextChoices):
    PERPETUAL = "perpetual", _("Perpetual")
    SUBSCRIPTION = "subscription", _("Subscription")


class LicenseSKU(NetBoxModel):
    """
    Canonical list of license SKUs (base + subscription).
    V1 scope: enough metadata to filter in forms and report cleanly.
    """
    manufacturer = models.ForeignKey(
        to=Manufacturer,
        on_delete=models.PROTECT,
        related_name="license_skus",
    )
    sku = models.CharField(
        max_length=64,
        unique=True,
        verbose_name=_("SKU"),
        help_text=_("Vendor SKU or product code (unique)."),
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_("Name"),
    )
    license_kind = models.CharField(
        max_length=16,
        choices=LicenseKindChoices.choices,
        default=LicenseKindChoices.SUBSCRIPTION,
        verbose_name=_("License Type"),
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Description"),
    )

    class Meta:
        ordering = ("manufacturer", "sku")
        verbose_name = _("License SKU")
        verbose_name_plural = _("License SKUs")

    def __str__(self):
        return f"{self.sku} ({self.name})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:licensesku', args=[self.pk])


class Subscription(NetBoxModel):
    """
    A vendor subscription entitlement container (e.g. a Cisco EA subscription ID,
    or a legacy order-linked subscription ID).  Many AssetLicense records can point
    to a single Subscription — that is the Cisco EA pattern.
    """
    manufacturer = models.ForeignKey(
        to=Manufacturer,
        on_delete=models.PROTECT,
        related_name='subscriptions',
        verbose_name=_('Manufacturer'),
    )
    subscription_id = models.CharField(
        max_length=128,
        verbose_name=_('Subscription ID'),
        help_text=_('Vendor-assigned subscription or entitlement identifier.'),
    )
    order = models.ForeignKey(
        to='netbox_inventory.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscriptions',
        verbose_name=_('Order'),
        help_text=_('Purchase order this subscription was created under (optional).'),
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Human-readable label, e.g. "Global Cisco EA 2024".'),
    )
    comments = models.TextField(
        blank=True,
        verbose_name=_('Comments'),
    )

    clone_fields = ('manufacturer', 'order', 'description')
    prerequisite_models = ('dcim.Manufacturer',)

    class Meta:
        ordering = ('manufacturer', 'subscription_id')
        verbose_name = _('Subscription')
        verbose_name_plural = _('Subscriptions')
        constraints = (
            models.UniqueConstraint(
                fields=['manufacturer', 'subscription_id'],
                name='%(app_label)s_%(class)s_unique_manufacturer_subscription_id',
                violation_error_message=_('Subscription ID must be unique per manufacturer.'),
            ),
        )

    def __str__(self):
        return f'{self.subscription_id} ({self.manufacturer})'

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:subscription', args=[self.pk])


class AssetLicense(NetBoxModel):
    """
    Assignment of a specific LicenseSKU to an Asset under a Subscription,
    for a defined time period.  Multiple AssetLicense records per asset are
    supported (concurrent or sequential).

    Validation enforces that the asset and license SKU share the same manufacturer.
    """
    asset = models.ForeignKey(
        to='netbox_inventory.Asset',
        on_delete=models.CASCADE,
        related_name='asset_licenses',
        verbose_name=_('Asset'),
    )
    subscription = models.ForeignKey(
        to='netbox_inventory.Subscription',
        on_delete=models.PROTECT,
        related_name='asset_licenses',
        verbose_name=_('Subscription'),
    )
    sku = models.ForeignKey(
        to='netbox_inventory.LicenseSKU',
        on_delete=models.PROTECT,
        related_name='asset_licenses',
        verbose_name=_('License SKU'),
        help_text=_('The specific license product being assigned.'),
    )
    start_date = models.DateField(
        verbose_name=_('Start Date'),
        help_text=_('Date this license term begins.'),
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('End Date'),
        help_text=_('Date this license term ends. Leave blank for open-ended/perpetual.'),
    )
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name=_('Quantity'),
        help_text=_('Number of license seats/units (usually 1).'),
    )
    notes = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('e.g. "renewed from prior sub", "EA uplift"'),
    )
    comments = models.TextField(
        blank=True,
        verbose_name=_('Comments'),
    )

    clone_fields = ('subscription', 'sku', 'start_date', 'end_date', 'quantity')
    prerequisite_models = (
        'netbox_inventory.Asset',
        'netbox_inventory.Subscription',
        'netbox_inventory.LicenseSKU',
    )

    class Meta:
        ordering = ('asset', 'sku', 'start_date')
        verbose_name = _('Asset License')
        verbose_name_plural = _('Asset Licenses')
        constraints = (
            models.UniqueConstraint(
                fields=['asset', 'sku', 'start_date'],
                name='%(app_label)s_%(class)s_unique_asset_sku_start',
                violation_error_message=_(
                    'An asset license record already exists for this asset, SKU, and start date.'
                ),
            ),
        )

    def __str__(self):
        end = self.end_date.isoformat() if self.end_date else 'ongoing'
        return f'{self.asset} – {self.sku.sku} ({self.start_date} → {end})'

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:assetlicense', args=[self.pk])

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        today = date.today()
        if self.start_date > today:
            return False
        if self.end_date and self.end_date < today:
            return False
        return True

    @property
    def is_expired(self) -> bool:
        if not self.end_date:
            return False
        return self.end_date < date.today()

    @property
    def is_pending(self) -> bool:
        return self.start_date > date.today()

    @property
    def status_label(self) -> str:
        if self.is_pending:
            return 'pending'
        if self.is_expired:
            return 'expired'
        return 'active'

    @property
    def days_until_expiry(self):
        if not self.end_date:
            return None
        delta = (self.end_date - date.today()).days
        return max(delta, 0)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self):
        super().clean()

        # Manufacturer cross-check: asset vendor must match license SKU vendor.
        if self.asset_id and self.sku_id:
            asset_manufacturer = _get_asset_manufacturer(self.asset)
            if asset_manufacturer is None:
                raise ValidationError(
                    _('Cannot determine asset manufacturer. '
                      'Ensure the asset has a device type, module type, or inventory item type with a manufacturer.')
                )
            if asset_manufacturer != self.sku.manufacturer:
                raise ValidationError({
                    'sku': _(
                        f'License SKU manufacturer ({self.sku.manufacturer}) does not match '
                        f'asset manufacturer ({asset_manufacturer}).'
                    )
                })

        # Subscription manufacturer must also match.
        if self.subscription_id and self.sku_id:
            if self.subscription.manufacturer != self.sku.manufacturer:
                raise ValidationError({
                    'subscription': _(
                        f'Subscription manufacturer ({self.subscription.manufacturer}) does not match '
                        f'license SKU manufacturer ({self.sku.manufacturer}).'
                    )
                })

        # Date sanity.
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({
                'end_date': _('End date must be on or after start date.'),
            })


def _get_asset_manufacturer(asset):
    """Return the Manufacturer for an asset, or None if undetermined."""
    if asset.device_type_id:
        return asset.device_type.manufacturer
    if asset.module_type_id:
        return asset.module_type.manufacturer
    if asset.inventoryitem_type_id:
        return asset.inventoryitem_type.manufacturer
    if asset.rack_type_id:
        return asset.rack_type.manufacturer
    return None
