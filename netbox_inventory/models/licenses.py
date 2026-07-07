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
    'LicenseBundle',
    'AssetLicense',
)

class LicenseKindChoices(models.TextChoices):
    PERPETUAL = "perpetual", _("Perpetual")
    SUBSCRIPTION = "subscription", _("Subscription")
    BUNDLE = "bundle", _("Bundle")


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
    renewal_budget_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Renewal Budget (per unit)"),
        help_text=_(
            'Estimated/list renewal cost per unit (seat) per term, used for budget reporting. '
            'Multiply by an AssetLicense quantity to estimate total renewal cost for that assignment.'
        ),
    )
    is_enterprise_wide = models.BooleanField(
        default=False,
        verbose_name=_("Enterprise-Wide"),
        help_text=_(
            'This SKU represents a single shared/enterprise-wide entitlement rather than a '
            'per-device purchase, even though it may be assigned to many assets individually '
            '(e.g. a vendor-side logging/telemetry service reported against every device). '
            'Device-scoped reports should surface this SKU once, not once per asset.'
        ),
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


class LicenseBundle(NetBoxModel):
    """
    Groups several separately-tracked AssetLicense feature entries on one asset
    under the single commercial SKU that was actually purchased.

    Some vendors (e.g. Palo Alto) sell one bundle SKU per device, but their
    licensing API reports the purchase back as N separate per-feature license
    entitlements (Threat Prevention, URL Filtering, WildFire, ...) — each with
    its own vendor part number, none of which reflects what was actually paid.
    A LicenseBundle is the priced "parent": create it once (pointing at a
    LicenseSKU with license_kind=BUNDLE and the real renewal_budget_per_unit),
    then set AssetLicense.bundle on the relevant already-synced feature rows so
    reporting can roll up budget at the bundle level instead of pricing (or
    double-counting) each feature SKU individually.

    Which feature SKUs belong to which bundle varies by purchase/order — there
    is no fixed, reusable mapping — so this is a per-asset, manually-curated
    grouping rather than a static relationship on LicenseSKU itself.
    """
    asset = models.ForeignKey(
        to='netbox_inventory.Asset',
        on_delete=models.CASCADE,
        related_name='license_bundles',
        verbose_name=_('Asset'),
    )
    sku = models.ForeignKey(
        to='netbox_inventory.LicenseSKU',
        on_delete=models.PROTECT,
        related_name='bundles',
        verbose_name=_('Bundle SKU'),
        help_text=_('The commercial SKU actually purchased (LicenseSKU with license_kind=Bundle).'),
    )
    order = models.ForeignKey(
        to='netbox_inventory.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='license_bundles',
        verbose_name=_('Order'),
        help_text=_('Purchase order this bundle was bought under (optional).'),
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Start Date'),
        help_text=_('Date this bundle term begins. Leave blank if not yet known.'),
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('End Date'),
        help_text=_('Date this bundle term ends. Leave blank for open-ended/perpetual.'),
    )
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name=_('Quantity'),
        help_text=_('Number of bundle units purchased (usually 1 per device).'),
    )
    notes = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Notes'),
    )
    comments = models.TextField(
        blank=True,
        verbose_name=_('Comments'),
    )

    clone_fields = ('asset', 'sku', 'order', 'start_date', 'end_date', 'quantity')
    prerequisite_models = (
        'netbox_inventory.Asset',
        'netbox_inventory.LicenseSKU',
    )

    class Meta:
        ordering = ('asset', 'sku', 'start_date')
        verbose_name = _('License Bundle')
        verbose_name_plural = _('License Bundles')
        constraints = (
            models.UniqueConstraint(
                fields=['asset', 'sku', 'start_date'],
                name='%(app_label)s_%(class)s_unique_asset_sku_start',
                violation_error_message=_(
                    'A license bundle record already exists for this asset, SKU, and start date.'
                ),
            ),
        )

    def __str__(self):
        expires = self.end_date.isoformat() if self.end_date else 'ongoing'
        return f'{self.asset} – {self.sku.sku} bundle (expires {expires})'

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:licensebundle', args=[self.pk])

    # ------------------------------------------------------------------
    # Computed properties (mirror AssetLicense's — same "unknown start
    # means already active" convention)
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        today = date.today()
        if self.start_date and self.start_date > today:
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
        if not self.start_date:
            return False
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

    def clean(self):
        super().clean()

        if self.sku_id and self.sku.license_kind != LicenseKindChoices.BUNDLE:
            raise ValidationError({
                'sku': _('License bundles must reference a SKU with License Type = Bundle.'),
            })

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
                        f'Bundle SKU manufacturer ({self.sku.manufacturer}) does not match '
                        f'asset manufacturer ({asset_manufacturer}).'
                    )
                })

        if self.order_id and self.sku_id:
            if self.order.manufacturer != self.sku.manufacturer:
                raise ValidationError({
                    'order': _(
                        f'Order manufacturer ({self.order.manufacturer}) does not match '
                        f'bundle SKU manufacturer ({self.sku.manufacturer}).'
                    )
                })

        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({
                'end_date': _('End date must be on or after start date.'),
            })

        if self.asset_id and self.sku_id and not self.start_date:
            duplicates = LicenseBundle.objects.filter(
                asset_id=self.asset_id, sku_id=self.sku_id, start_date__isnull=True,
            ).exclude(pk=self.pk)
            if duplicates.exists():
                raise ValidationError({
                    'start_date': _(
                        'Another license bundle record for this asset and SKU already has no '
                        'start date set. Fill in a start date to disambiguate, or edit the existing record.'
                    ),
                })


class AssetLicense(NetBoxModel):
    """
    Assignment of a specific LicenseSKU to an Asset for a defined time period,
    linked to either a Subscription (recurring/entitlement-ID licensing, e.g.
    Cisco EA) or directly to an Order (one-off/qty-based licensing bought
    under a PO with no entitlement ID, e.g. traditional Cisco licenses).
    Multiple AssetLicense records per asset are supported (concurrent or
    sequential, one per SKU).

    Validation enforces that the asset and license SKU share the same manufacturer,
    and that any linked subscription/order also match that manufacturer.
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
        null=True,
        blank=True,
        help_text=_('Subscription/entitlement this license is enrolled under (if any).'),
    )
    order = models.ForeignKey(
        to='netbox_inventory.Order',
        on_delete=models.PROTECT,
        related_name='asset_licenses',
        verbose_name=_('Order'),
        null=True,
        blank=True,
        help_text=_(
            'Purchase order this license was bought under, for licenses with no '
            'subscription/entitlement ID (e.g. a quantity of Cisco licenses bought '
            'under a hardware or standalone order).'
        ),
    )
    sku = models.ForeignKey(
        to='netbox_inventory.LicenseSKU',
        on_delete=models.PROTECT,
        related_name='asset_licenses',
        verbose_name=_('License SKU'),
        help_text=_('The specific license product being assigned.'),
    )
    bundle = models.ForeignKey(
        to='netbox_inventory.LicenseBundle',
        on_delete=models.SET_NULL,
        related_name='asset_licenses',
        verbose_name=_('Bundle'),
        null=True,
        blank=True,
        help_text=_(
            'If this feature license was part of a purchased bundle SKU (e.g. one Palo Alto '
            'device SKU that the vendor reports back as several separate feature licenses), '
            'link the bundle here so renewal budget is tracked on the bundle, not this SKU.'
        ),
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Start Date'),
        help_text=_(
            'Date this license term begins. Leave blank if not yet known (e.g. awaiting '
            'manual calculation) — treated as already active until an end date says otherwise.'
        ),
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
    license_key = models.CharField(
        max_length=128,
        blank=True,
        verbose_name=_('License Key'),
        help_text=_(
            'Vendor-issued unique activation/license key, where one exists (e.g. Palo Alto). '
            'Leave blank for quantity-based licensing with no per-asset key (e.g. Cisco).'
        ),
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

    clone_fields = ('subscription', 'order', 'sku', 'bundle', 'start_date', 'end_date', 'quantity')
    prerequisite_models = (
        'netbox_inventory.Asset',
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
        start = self.start_date.isoformat() if self.start_date else 'unknown start'
        end = self.end_date.isoformat() if self.end_date else 'ongoing'
        return f'{self.asset} – {self.sku.sku} ({start} → {end})'

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:assetlicense', args=[self.pk])

    # ------------------------------------------------------------------
    # Computed properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        today = date.today()
        # An unknown start date is treated as already active (we're tracking
        # a license that exists today, just haven't back-filled when it began).
        if self.start_date and self.start_date > today:
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
        if not self.start_date:
            return False
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

        # Subscription manufacturer must also match, when a subscription is set.
        if self.subscription_id and self.sku_id:
            if self.subscription.manufacturer != self.sku.manufacturer:
                raise ValidationError({
                    'subscription': _(
                        f'Subscription manufacturer ({self.subscription.manufacturer}) does not match '
                        f'license SKU manufacturer ({self.sku.manufacturer}).'
                    )
                })

        # Order manufacturer must also match, when an order is set directly (no subscription).
        if self.order_id and self.sku_id:
            if self.order.manufacturer != self.sku.manufacturer:
                raise ValidationError({
                    'order': _(
                        f'Order manufacturer ({self.order.manufacturer}) does not match '
                        f'license SKU manufacturer ({self.sku.manufacturer}).'
                    )
                })

        # A bundle groups feature licenses on one specific asset — it must be
        # the same asset, and its bundle SKU must share the feature SKU's manufacturer.
        if self.bundle_id:
            if self.asset_id and self.bundle.asset_id != self.asset_id:
                raise ValidationError({
                    'bundle': _('This bundle belongs to a different asset.'),
                })
            if self.sku_id and self.bundle.sku.manufacturer != self.sku.manufacturer:
                raise ValidationError({
                    'bundle': _(
                        f'Bundle SKU manufacturer ({self.bundle.sku.manufacturer}) does not match '
                        f'license SKU manufacturer ({self.sku.manufacturer}).'
                    )
                })

        # Date sanity.
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({
                'end_date': _('End date must be on or after start date.'),
            })

        # The (asset, sku, start_date) DB constraint can't catch duplicates when
        # start_date is NULL (NULL != NULL), so guard against it here instead.
        if self.asset_id and self.sku_id and not self.start_date:
            duplicates = AssetLicense.objects.filter(
                asset_id=self.asset_id, sku_id=self.sku_id, start_date__isnull=True,
            ).exclude(pk=self.pk)
            if duplicates.exists():
                raise ValidationError({
                    'start_date': _(
                        'Another asset license record for this asset and SKU already has no '
                        'start date set. Fill in a start date to disambiguate, or edit the existing record.'
                    ),
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
