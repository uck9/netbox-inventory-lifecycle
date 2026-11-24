from datetime import date, timedelta

from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel
from netbox.plugins import get_plugin_config

from ..choices import SORValidationStatusChoices, SystemOfRecordChoices

__all__ = (
    'AssetSystemOfRecord',
)


class AssetSystemOfRecord(NetBoxModel):
    """
    An asset's identity in an external system of record (e.g. Cisco IQ, CMDB),
    plus the outcome of the most recent validation against it. One record per
    system per asset; an SOR ID can only belong to one asset within a system.

    Maintained by API integrations only — no add/edit/delete views exist in
    the UI. Separate from Asset.vendor_instance_id, which is unrelated.
    """
    asset = models.ForeignKey(
        to='netbox_inventory.Asset',
        on_delete=models.CASCADE,
        related_name='sor_records',
        verbose_name=_('Asset'),
    )
    system = models.CharField(
        max_length=50,
        choices=SystemOfRecordChoices,
        verbose_name=_('System'),
    )
    record_id = models.CharField(
        max_length=200,
        verbose_name=_('SOR ID'),
        help_text=_("The asset's identifier in the system of record."),
    )
    validation_status = models.CharField(
        max_length=30,
        choices=SORValidationStatusChoices,
        default=SORValidationStatusChoices.PENDING,
        verbose_name=_('Validation Status'),
    )
    last_validated = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Last Validated'),
    )

    prerequisite_models = (
        'netbox_inventory.Asset',
    )

    class Meta:
        ordering = ('asset', 'system')
        verbose_name = _('System of Record')
        verbose_name_plural = _('System of Record Records')
        constraints = (
            models.UniqueConstraint(
                fields=['asset', 'system'],
                name='%(app_label)s_%(class)s_unique_asset_system',
                violation_error_message=_('This asset already has a record for this system.'),
            ),
            models.UniqueConstraint(
                fields=['system', 'record_id'],
                name='%(app_label)s_%(class)s_unique_system_record_id',
                violation_error_message=_('This SOR ID is already assigned to another asset in this system.'),
            ),
        )

    def __str__(self):
        return f'{self.get_system_display()}: {self.record_id}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:assetsystemofrecord', args=[self.pk])

    def get_system_color(self):
        return SystemOfRecordChoices.colors.get(self.system)

    def get_validation_status_color(self):
        return SORValidationStatusChoices.colors.get(self.validation_status)

    @staticmethod
    def stale_cutoff() -> date:
        """Records last validated before this date are stale."""
        return date.today() - timedelta(days=get_plugin_config('netbox_inventory', 'sor_stale_days'))

    @property
    def is_stale(self) -> bool:
        """Never validated, or not validated within sor_stale_days."""
        return self.last_validated is None or self.last_validated < self.stale_cutoff()
