from datetime import date

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models

# from django.db.models import Q
from django.db.models.functions import Lower
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import PrimaryModel

from netbox_inventory.choices import (
    AssetStatusChoices,
    ContractStatusChoices,
    ContractTypeChoices,
)

# from netbox_inventory.models.programs import VendorProgram

__all__ = (
    'ContractVendor',
    'ContractSKU',
    'Contract',
    'ContractAssignment',
)

class ContractVendor(PrimaryModel):
    name = models.CharField(max_length=100)

    clone_fields = ()
    prerequisite_models = ()

    class Meta:
        ordering = ['name']
        constraints = (
            models.UniqueConstraint(
                Lower('name'),
                name='%(app_label)s_%(class)s_unique_name',
                violation_error_message="Contract Vendor must be unique."
            ),
        )

    def __str__(self):
        return f'{self.name}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:contractvendor', args=[self.pk])

class ContractSKU(PrimaryModel):
    """
    A single support SKU.
    This is the atomic unit of coverage that can be assigned to assets.
    """
    manufacturer = models.ForeignKey(
        to='dcim.Manufacturer',
        on_delete=models.CASCADE,
        related_name='contract_skus',
    )
    sku = models.CharField(
        max_length=64,
        unique=True,
        verbose_name=_('SKU'),
        help_text=_('Vendor SKU identifier (e.g. L-AC-OPT-5Y-SUP)'),
    )
    contract_type = models.CharField(
        max_length=16,
        choices=ContractTypeChoices,
        verbose_name=_("Contract Type"),
        help_text=_("Which contract type this SKU is valid for (EA, ALC, etc.)"),
    )
    service_level = models.CharField(
        max_length=64,
        blank=True,
        verbose_name=_('Service Level'),
        help_text=_('e.g. TAC 24x7, NBD, DNA Advantage, etc.'),
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Description'),
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
    )

    clone_fields = (
        'manufacturer',
        'sku',
        'description',
        'service_level',
        'notes',
    )

    prerequisite_models = (
        'dcim.Manufacturer',
    )

    class Meta:
        ordering = ['sku']
        verbose_name = _('Contract SKU')
        verbose_name_plural = _('Contract SKUs')

    def __str__(self):
        if self.description:
            return f'{self.sku} ({self.description})'
        return self.sku

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:contractsku', args=[self.pk])


class Contract(PrimaryModel):
    """
    A Vendor contract.
    """
    contract_id = models.CharField(
        max_length=64,
        unique=True,
        verbose_name=_('Contract ID'),
        help_text=_('Contract number / identifier.'),
    )
    contract_type = models.CharField(
        max_length=16,
        choices=ContractTypeChoices,
        verbose_name=_('Contract Type'),
    )
    vendor = models.ForeignKey(
        to='netbox_inventory.ContractVendor',
        on_delete=models.SET_NULL,
        related_name='contracts',
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=30,
        choices=ContractStatusChoices,
        help_text='Current status of the contract',
    )
    description = models.CharField(
        max_length=128,
        verbose_name=_('Description'),
        help_text=_('Friendly name for this contract (e.g. "Global Network EA 2025–2028").'),
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date when the contract starts',
        verbose_name=_('Start Date'),
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text='Date when the contract ends',
        verbose_name=_('End Date'),
    )
    renewal_date = models.DateField(
        blank=True,
        null=True,
        help_text='Date when the contract is up for renewal',
        verbose_name='Renewal Date',
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
    )

    prerequisite_models = (
        'netbox_inventory.ContractVendor',
    )

    clone_fields = (
        'contract_id',
        'contract_type',
        'description',
        'vendor',
        'status',
        'start_date',
        'end_date',
        'notes',
    )

    class Meta:
        ordering = ['contract_id']
        verbose_name = _('Contract')
        verbose_name_plural = _('Contracts')
        constraints = (
            models.UniqueConstraint(
                'vendor', Lower('contract_id'),
                name='%(app_label)s_%(class)s_unique_vendor_contract_id',
                violation_error_message="Contract must be unique per vendor."
            ),
        )

    def __str__(self):
        return f'{self.contract_id}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_inventory:contract', args=[self.pk])

    @property
    def is_active(self):
        """Check if the contract is currently active based on dates."""
        from datetime import date
        today = date.today()
        return self.start_date <= today <= self.end_date

    @property
    def days_until_expiry(self):
        """Calculate days until contract expires."""
        from datetime import date
        today = date.today()
        if self.end_date > today:
            return (self.end_date - today).days
        return 0

    @property
    def is_expired(self):
        """Check if the contract has expired."""
        from datetime import date
        return self.end_date < date.today()

    @property
    def needs_renewal(self):
        """Check if the contract needs renewal based on renewal date."""
        if not self.renewal_date:
            return False
        from datetime import date
        return date.today() >= self.renewal_date

    @property
    def remaining_time_display(self):
        """Get a user-friendly display of remaining contract time."""
        if self.is_expired:
            from django.utils.timesince import timesince
            return f"Expired {timesince(self.end_date)} ago"
        elif self.days_until_expiry <= 0:
            return "Expires today"
        elif self.days_until_expiry == 1:
            return "1 day remaining"
        else:
            return f"{self.days_until_expiry} days remaining"

    @property
    def remaining_time_class(self):
        """Get the CSS class for the remaining time badge."""
        if self.is_expired or self.days_until_expiry <= 0:
            return "bg-danger"
        elif self.days_until_expiry <= 7:
            return "bg-danger"
        elif self.days_until_expiry <= 30:
            return "bg-warning"
        elif self.days_until_expiry <= 90:
            return "bg-info"
        else:
            return "bg-success"

    @property
    def remaining_time_icon(self):
        """Get the icon for the remaining time badge."""
        if self.is_expired or self.days_until_expiry <= 0:
            return "mdi-alert-circle"
        elif self.days_until_expiry <= 30:
            return "mdi-alert"
        elif self.days_until_expiry <= 90:
            return "mdi-information"
        else:
            return "mdi-check-circle"

    @property
    def contract_duration_days(self):
        """Get the total duration of the contract in days."""
        if not self.start_date or not self.end_date:
            return None
        return (self.end_date - self.start_date).days

    @property
    def days_elapsed(self):
        """Get the number of days elapsed since contract start."""
        if not self.start_date:
            return None
        from datetime import date
        today = date.today()
        if today < self.start_date:
            return 0  # Contract hasn't started yet
        return (today - self.start_date).days

    @property
    def progress_percentage(self):
        """Get the contract progress as a percentage (0-100)."""
        if not self.contract_duration_days or self.contract_duration_days <= 0:
            return 0
        if self.is_expired:
            return 100
        if self.days_elapsed is None or self.days_elapsed < 0:
            return 0
        return min(100, (self.days_elapsed / self.contract_duration_days) * 100)

    def update_status_based_on_dates(self):
        """
        Update contract status based on current date and contract dates.
        Returns True if status was changed, False otherwise.
        """
        from datetime import date
        today = date.today()
        original_status = self.status

        # Only auto-update if current status allows it
        # Don't override manually set statuses like 'cancelled' or 'renewed'
        if self.status in ['draft', 'active', 'expired', '']:
            if self.end_date < today:
                # Contract has expired
                self.status = 'expired'
            elif self.start_date <= today <= self.end_date:
                # Contract is currently active
                if self.status != 'active':
                    self.status = 'active'
            elif self.start_date > today:
                # Contract hasn't started yet
                if self.status not in ['draft']:
                    self.status = 'draft'

        return self.status != original_status

@receiver(pre_save, sender=Contract)
def auto_update_contract_status(sender, instance, **kwargs):
    """
    Automatically update contract status based on dates when saving.
    """
    instance.update_status_based_on_dates()

class ContractAssignment(PrimaryModel):
    contract = models.ForeignKey(
        to='netbox_inventory.Contract',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='assignments',
    )
    sku = models.ForeignKey(
        to='netbox_inventory.ContractSKU',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='assignments',
    )
    program = models.ForeignKey(
        to='netbox_inventory.VendorProgram',
        on_delete=models.PROTECT,
        related_name='contract_assignments',
        null=True,
        blank=True,
    )
    asset = models.ForeignKey(
        to='netbox_inventory.Asset',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='contracts',
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Start Date'),
        help_text=_('Support coverage start date for this assignment'),
    )
    renewal_date = models.DateField(
        blank=True,
        null=True,
        help_text='Renewal date for this assignment',
        verbose_name='Renewal Date',
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('End Date'),
        help_text=_('Support coverage end date for this assignment'),
    )
    clone_fields = (
        'contract', 'sku', 'start_date', 'end_date', 'renewal_date',
    )
    prerequisite_models = (
        'netbox_inventory.Contract',
        'netbox_inventory.ContractSKU',
        'netbox_inventory.Asset',
    )

    class Meta:
        ordering = ['contract', 'asset', 'start_date']
        constraints = (
            # Prevent exact duplicates; overlap logic is in clean()
            models.UniqueConstraint(
                fields=['asset', 'sku', 'start_date', 'end_date'],
                name='uniq_contractassignment_asset_sku_period',
            ),
        )

    def __str__(self):
        if self.asset and self.contract:
            return f'{self.asset}: {self.contract.contract_id}'
        elif self.asset:
            return f'{self.asset}: (no contract)'
        elif self.contract:
            return f'(no asset): {self.contract.contract_id}'
        return f'Contract assignment #{self.pk}'

    def get_absolute_url(self):
        return reverse(
            f'plugins:{self._meta.app_label}:{self._meta.model_name}',
            args=[self.pk],
        )

    @property
    def effective_start_date(self):
        """
        Start date used for overlap checks:
        - prefer explicit start
        - fall back to contract start if available
        """
        if self.start_date:
            return self.start_date
        if self.contract and self.contract.start_date:
            return self.contract.start_date
        return None  # truly unknown

    @property
    def effective_end_date(self):
        """
        End date used for overlap checks:
        - prefer explicit end
        - fall back to contract end if available
        """
        if self.end_date:
            return self.end_date
        if self.contract and self.contract.end_date:
            return self.contract.end_date
        return None  # open-ended

    @property
    def effective_renewal_date(self):
        """
        End date used for overlap checks:
        - prefer explicit end
        - fall back to contract end if available
        """
        if self.renewal_date:
            return self.renewal_date
        if self.contract and self.contract.renewal_date:
            return self.contract.renewal_date
        return None  # truly unknown

    def get_asset_status_color(self):
        return AssetStatusChoices.colors.get(self.asset.status)

    def get_coverage_status_color(self):
        return ContractStatusChoices.colors.get(self.support_coverage_status)

    @property
    def assignment_type(self):
        return 'asset'

    @property
    def is_active(self):
        """Check if the contract assignment is currently active based on dates."""
        if not self.start_date or not self.end_date:
            return False
        from datetime import date
        today = date.today()
        return self.effective_start_date <= today <= self.effective_end_date

    @property
    def days_until_expiry(self):
        """Calculate days until contract assignment expires."""
        if not self.effective_end_date:
            return False
        from datetime import date
        today = date.today()
        if self.effective_end_date > today:
            return (self.effective_end_date - today).days
        return 0

    @property
    def is_expired(self):
        """Check if the contract assignment has expired."""
        if not self.effective_end_date:
            return False
        from datetime import date
        return self.effective_end_date < date.today()

    @property
    def needs_renewal(self):
        """Check if the contract assignment needs renewal based on renewal date."""
        if not self.effective_renewal_date:
            return False
        from datetime import date
        return date.today() >= self.effective_renewal_date

    @property
    def remaining_time_display(self):
        """Get a user-friendly display of remaining contract time."""
        if self.is_expired:
            from django.utils.timesince import timesince
            return f"Expired {timesince(self.effective_end_date)} ago"
        elif self.days_until_expiry <= 0:
            return "Expires today"
        elif self.days_until_expiry == 1:
            return "1 day remaining"
        else:
            return f"{self.days_until_expiry} days remaining"

    @property
    def remaining_time_class(self):
        """Get the CSS class for the remaining time badge."""
        if self.is_expired or self.days_until_expiry <= 0:
            return "bg-danger"
        elif self.days_until_expiry <= 7:
            return "bg-danger"
        elif self.days_until_expiry <= 30:
            return "bg-warning"
        elif self.days_until_expiry <= 90:
            return "bg-info"
        else:
            return "bg-success"

    @property
    def remaining_time_icon(self):
        """Get the icon for the remaining time badge."""
        if self.is_expired or self.days_until_expiry <= 0:
            return "mdi-alert-circle"
        elif self.days_until_expiry <= 30:
            return "mdi-alert"
        elif self.days_until_expiry <= 90:
            return "mdi-information"
        else:
            return "mdi-check-circle"

    @property
    def contract_duration_days(self):
        """Get the total duration of the contract in days."""
        if not self.effective_start_date or not self.effective_end_date:
            return None
        return (self.effective_end_date - self.effective_start_date).days

    @property
    def days_elapsed(self):
        """Get the number of days elapsed since contract start."""
        if not self.effective_start_date:
            return None
        from datetime import date
        today = date.today()
        if today < self.effective_start_date:
            return 0  # Contract hasn't started yet
        return (today - self.effective_start_date).days

    @property
    def progress_percentage(self):
        """Get the contract assignment progress as a percentage (0-100)."""
        if not self.contract_duration_days or self.contract_duration_days <= 0:
            return 0
        if self.is_expired:
            return 100
        if self.days_elapsed is None or self.days_elapsed < 0:
            return 0
        return min(100, (self.days_elapsed / self.contract_duration_days) * 100)

    def update_status_based_on_dates(self):
        """
        Update contract status based on current date and contract dates.
        Returns True if status was changed, False otherwise.
        """
        from datetime import date
        today = date.today()
        original_status = self.status

        # Only auto-update if current status allows it
        # Don't override manually set statuses like 'cancelled' or 'renewed'
        if self.status in ['draft', 'active', 'expired']:
            if self.effective_end_date < today:
                # Contract has expired
                self.status = 'expired'
            elif self.effective_start_date <= today <= self.effective_end_date:
                # Contract is currently active
                if self.status != 'active':
                    self.status = 'active'
            elif self.effective_start_date > today:
                # Contract hasn't started yet
                if self.status not in ['draft']:
                    self.status = 'draft'

        return self.status != original_status

    def clean(self):
        """
        Enforce:
        - no overlapping active periods for the same asset+sku
        - basic sanity on dates
        """
        super().clean()

        # If no device or no sku, don't bother enforcing period logic
        if not self.asset or not self.sku:
            return

        start = self.effective_start_date
        end = self.effective_end_date

        # Basic sanity: if both present, start must be <= end
        if start and end and start > end:
            raise ValidationError({
                'start': _('Start date must be before or equal to end date.'),
                'end': _('End date must be after or equal to start date.'),
            })

        # If we still don't have a start, we can't do meaningful overlap checks
        # You can tighten this to require start if you want.
        if not start:
            return

        # Normalize "open" end as max date for comparison
        this_end = end or date.max

        # Set Contract and Program if not set
        if self.contract and self.sku and not self.program:
            VendorProgram = apps.get_model('netbox_inventory', 'VendorProgram')
            self.program = VendorProgram.objects.filter(
                manufacturer=self.sku.manufacturer,
                contract_type=self.contract.contract_type,
            ).first()

        # Ensure SKU contract_type matches Contract contract_type
        if self.contract and self.sku:
            if self.contract.contract_type and self.sku.contract_type:
                if self.contract.contract_type != self.sku.contract_type:
                    raise ValidationError({
                        'sku': _(f'SKU type ({self.sku.contract_type}) does not match contract type ({self.contract.contract_type}).')
                    })

        qs = ContractAssignment.objects.filter(
            asset=self.asset,
            sku=self.sku,
        ).exclude(pk=self.pk)

        for other in qs:
            o_start = other.effective_start_date
            o_end = other.effective_end_date or date.max

            # If the other record has no start, treat it as always active
            if o_start is None:
                o_start = date.min

            # Classic interval overlap check:
            # [start, this_end] overlaps [o_start, o_end] if:
            # start <= o_end AND o_start <= this_end
            if start <= o_end and o_start <= this_end:
                raise ValidationError(
                    _('This asset and SKU already have coverage during the specified period.')
                )