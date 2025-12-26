from datetime import date

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse

from dcim.models import Device, DeviceType, Module, ModuleType
from netbox.models import PrimaryModel
from utilities.choices import ChoiceSet

from netbox_inventory.constants import HARDWARE_LIFECYCLE_MODELS

__all__ = (
    'HardwareLifecycle',
)


class SupportBasisChoices(ChoiceSet):
    key = 'HardwareLifecycle.support_basis'
    DEFAULT_KEY = 'support'

    CHOICES = [
        (DEFAULT_KEY, 'End of Support'),
        ('security', 'End of Security'),
    ]

MIGRATION_CALC_MONTH = settings.PLUGINS_CONFIG["netbox_inventory"].get("hw_migration_calc_month", 6)


class HardwareLifecycle(PrimaryModel):
    assigned_object_type = models.ForeignKey(
        to=ContentType,
        limit_choices_to=HARDWARE_LIFECYCLE_MODELS,
        on_delete=models.PROTECT,
        related_name='+',
        blank=True,
        null=True
    )
    assigned_object_id = models.PositiveBigIntegerField(
        blank=True,
        null=True
    )
    assigned_object = GenericForeignKey(
        ct_field='assigned_object_type',
        fk_field='assigned_object_id'
    )

    end_of_sale = models.DateField(blank=True, null=True)
    end_of_maintenance = models.DateField(blank=True, null=True)
    end_of_security = models.DateField(blank=True, null=True)
    last_contract_attach = models.DateField(blank=True, null=True)
    last_contract_renewal = models.DateField(blank=True, null=True)
    end_of_support = models.DateField(blank=True, null=True)
    notice_url = models.URLField(blank=True)
    support_basis = models.CharField(
        max_length=16,
        choices=SupportBasisChoices,
        default=SupportBasisChoices.DEFAULT_KEY,
    )

    class Meta:
        ordering = ['assigned_object_type']
        constraints = (
            models.UniqueConstraint(
                'assigned_object_type', 'assigned_object_id',
                name='%(app_label)s_%(class)s_unique_object',
                violation_error_message="Objects must be unique."
            ),
        )

    @property
    def name(self):
        return self


    def __str__(self):
        if not self.assigned_object:
            return f'{self.pk}'
        elif isinstance(self.assigned_object, ModuleType):
            return f'Module Type: {self.assigned_object.model}'
        return f'Device Type: {self.assigned_object.model}'


    @property
    def is_supported(self):
        """
        Return False only if the selected support basis date exists and has passed.

        If no relevant lifecycle date is set, assume the hardware is supported.
        """
        today = date.today()

        # Decide which lifecycle date to evaluate
        if self.support_basis == SupportBasisChoices.DEFAULT_KEY:  # 'support'
            end_date = self.end_of_support
        else:  # 'security'
            end_date = self.end_of_security

        # No published date => still supported
        if not end_date:
            return True

        return today < end_date


    @property
    def assigned_object_count(self):
        if isinstance(self.assigned_object, DeviceType):
            return Device.objects.filter(device_type=self.assigned_object).count()
        return Module.objects.filter(module_type=self.assigned_object).count()


    def _support_basis_date(self):
        """
        Return the lifecycle date used for support calculations
        based on the configured support_basis.
        """
        if self.support_basis == SupportBasisChoices.DEFAULT_KEY:  # 'support'
            return self.end_of_support
        return self.end_of_security


    @property
    def days_to_vendor_eos(self):
        """
        Return the number of days until the vendor-defined end date
        based on support_basis.

        Returns None if no relevant vendor date is set.
        """
        today = date.today()
        end_date = self._support_basis_date()

        if not end_date:
            return None

        return (end_date - today).days


    @property
    def calc_replacement_year(self):
        """
        Calculate the replacement year based on the selected support basis date.

        Returns None if no relevant vendor date is set.
        """
        end_date = self._support_basis_date()

        if not end_date:
            return None

        if end_date.month <= MIGRATION_CALC_MONTH:
            replace_date = end_date - relativedelta(years=1)
        else:
            replace_date = end_date

        return replace_date.year


    @property
    def calc_budget_year(self):
        """
        Calculate the budget year based on the selected support basis date.

        Returns None if no relevant vendor date is set.
        """
        end_date = self._support_basis_date()

        if not end_date:
            return None

        if end_date.month <= MIGRATION_CALC_MONTH:
            budget_date = end_date - relativedelta(years=2)
        else:
            budget_date = end_date - relativedelta(years=1)

        return budget_date.year


    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:hardwarelifecycle', args=[self.pk])
