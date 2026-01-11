from django.db import models
from django.utils.translation import gettext_lazy as _

from dcim.models import Manufacturer
from netbox.models import NetBoxModel

__all__ = (
    'LicenseSKU',
    'LicenseKindChoices',
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
