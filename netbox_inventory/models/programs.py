from datetime import date
from datetime import date as _date

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.db.models.functions import Lower

from netbox.models import PrimaryModel

from ..choices import (
    ProgramCoverageSourceChoices,
    ProgramCoverageStatusChoices,
    ProgramEligibilityChoices,
    ContractTypeChoices,
)


def _is_assignment_active(a, today):
    start = a.effective_start_date
    end = a.effective_end_date or _date.max
    if not start:
        return False
    return start <= today <= end


def _get_asset_device_type(asset):
    # Your Asset has device_type; keep fallback for safety
    dt = getattr(asset, "device_type", None)
    if dt:
        return dt
    dev = getattr(asset, "device", None)
    if dev and getattr(dev, "device_type", None):
        return dev.device_type
    return None


def _get_asset_manufacturer(asset):
    dt = _get_asset_device_type(asset)
    return getattr(dt, "manufacturer", None) if dt else None


def _coverage_date():
    # You might prefer timezone.now().date(); date.today() is fine if consistent elsewhere
    return date.today()


class VendorProgram(PrimaryModel):
    """
    Represents a vendor/program context (e.g. Cisco EA, Palo Alto PA).
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text=_("Human-friendly program name (e.g. 'Cisco EA')."),
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text=_("Stable identifier for APIs/automation (e.g. 'cisco-ea')."),
    )
    manufacturer = models.ForeignKey(
        to='dcim.Manufacturer',
        on_delete=models.PROTECT,
        related_name='vendor_programs',
        null=True,
        blank=True,
        help_text=_('Manufacturer this program applies to (e.g. Cisco, Palo Alto Networks).'),
    )
    contract_type = models.CharField(
        max_length=16,
        choices=ContractTypeChoices,
        verbose_name=_("Contract Type"),
        help_text=_("Contract type this program represents (e.g. EA, ALC)."),
    )
    class Meta:
        ordering = ("name",)
        constraints = (
            models.UniqueConstraint(
                fields=['manufacturer', 'contract_type'],
                name='uniq_vendorprogram_manufacturer_contract_type',
                violation_error_message=_(
                    "A program already exists for this manufacturer and contract type."
                ),
            ),
            # optional: also make name unique case-insensitively per manufacturer
            models.UniqueConstraint(
                Lower('name'), 'manufacturer',
                name='uniq_vendorprogram_manufacturer_name_ci',
                violation_error_message=_(
                    "Program name must be unique per manufacturer."
                ),
            ),
        )

    def __str__(self):
        return self.name


class AssetProgramCoverage(PrimaryModel):
    """
    Tracks whether an Asset is included/excluded/terminated for a given VendorProgram,
    and whether it is eligible for future inclusion.
    """

    asset = models.ForeignKey(
        to="netbox_inventory.Asset",
        on_delete=models.CASCADE,
        related_name="program_coverages",
    )
    program = models.ForeignKey(
        to="netbox_inventory.VendorProgram",
        on_delete=models.CASCADE,
        related_name="asset_coverages",
    )
    status = models.CharField(
        max_length=20,
        choices=ProgramCoverageStatusChoices,
        default=ProgramCoverageStatusChoices.PLANNED,
    )
    eligibility = models.CharField(
        max_length=20,
        choices=ProgramEligibilityChoices,
        default=ProgramEligibilityChoices.UNKNOWN,
    )
    effective_start = models.DateField(
        null=True,
        blank=True,
        help_text=_("When this coverage/decision became effective."),
    )
    effective_end = models.DateField(
        null=True,
        blank=True,
        help_text=_("When this coverage ended (required for Terminated)."),
    )
    decision_reason = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Reason code or short reason text (e.g. 'spare', 'lab', 'never_supported')."),
    )
    notes = models.TextField(blank=True)
    evidence_url = models.URLField(
        blank=True,
        help_text=_("Link to external report/ticket backing this decision."),
    )
    source = models.CharField(
        max_length=20,
        choices=ProgramCoverageSourceChoices,
        default=ProgramCoverageSourceChoices.MANUAL,
    )
    last_synced = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("program__name", "asset__name")
        constraints = [
            # Allow only one "current" record per asset+program (effective_end is NULL)
            models.UniqueConstraint(
                fields=["asset", "program"],
                condition=Q(effective_end__isnull=True),
                name="netboxinv_asset_program_coverage_one_current",
            ),
        ]

    def get_status_color(self):
        return ProgramCoverageStatusChoices.colors.get(self.status)

    def get_eligibility_color(self):
        return ProgramEligibilityChoices.colors.get(self.eligibility)

    def get_source_color(self):
        return ProgramCoverageSourceChoices.colors.get(self.source)

    def __str__(self):
        return f"{self.asset} / {self.program}"

    def clean(self):
        super().clean()

        self._validate_date_sanity()
        self._validate_status_eligibility_guardrails()
        self._validate_manufacturer_rules()
        self._validate_terminated_requires_end_date()
        self._validate_active_requires_matching_contract()

    # -------------------------
    # Validators (small + testable)
    # -------------------------

    def _validate_date_sanity(self) -> None:
        if self.effective_start and self.effective_end and self.effective_end < self.effective_start:
            raise ValidationError({"effective_end": _("effective_end cannot be before effective_start.")})

    def _validate_status_eligibility_guardrails(self) -> None:
        status = self.status
        eligibility = self.eligibility

        # ACTIVE -> ELIGIBLE
        if status == ProgramCoverageStatusChoices.ACTIVE:
            if eligibility != ProgramEligibilityChoices.ELIGIBLE:
                raise ValidationError({"eligibility": _("ACTIVE coverage requires eligibility to be ELIGIBLE.")})
            return

        # TERMINATED -> INELIGIBLE
        if status == ProgramCoverageStatusChoices.TERMINATED:
            if eligibility != ProgramEligibilityChoices.INELIGIBLE:
                raise ValidationError({
                    "eligibility": _("TERMINATED coverage requires eligibility to be INELIGIBLE (cannot be re-added).")
                })
            return

        # PLANNED/EXCLUDED -> not INELIGIBLE (can still be UNKNOWN or ELIGIBLE)
        if status in (ProgramCoverageStatusChoices.PLANNED, ProgramCoverageStatusChoices.EXCLUDED):
            if eligibility == ProgramEligibilityChoices.INELIGIBLE:
                raise ValidationError({
                    "eligibility": _("PLANNED/EXCLUDED coverage cannot be INELIGIBLE. Use TERMINATED for permanent removal.")
                })
            return

        # If someone sets INELIGIBLE, it must be TERMINATED (hard rule per your lifecycle definition)
        if eligibility == ProgramEligibilityChoices.INELIGIBLE:
            raise ValidationError({"status": _("INELIGIBLE records must be TERMINATED.")})

    def _validate_manufacturer_rules(self) -> None:
        program_mfr = getattr(self.program, "manufacturer", None)
        asset_mfr = _get_asset_manufacturer(self.asset)

        if self.status == ProgramCoverageStatusChoices.ACTIVE and program_mfr and asset_mfr is None:
            raise ValidationError({
                "asset": _("Cannot determine asset manufacturer (no device_type/manufacturer found for this asset).")
            })

        if program_mfr and asset_mfr and program_mfr.pk != asset_mfr.pk:
            raise ValidationError({
                "program": _(
                    "Program manufacturer does not match this asset's manufacturer (%(asset_mfr)s)."
                ) % {"asset_mfr": asset_mfr},
            })

    def _validate_terminated_requires_end_date(self) -> None:
        if self.status == ProgramCoverageStatusChoices.TERMINATED and not self.effective_end:
            raise ValidationError({"effective_end": _("TERMINATED coverage should have an effective_end date.")})

    def _validate_active_requires_matching_contract(self) -> None:
        if self.status != ProgramCoverageStatusChoices.ACTIVE:
            return

        ContractAssignment = apps.get_model('netbox_inventory', 'ContractAssignment')
        today = _date.today()

        candidates = ContractAssignment.objects.filter(
            asset=self.asset,
            contract__contract_type=self.program.contract_type,
        ).select_related('contract', 'sku')

        if self.program.manufacturer_id:
            candidates = candidates.filter(sku__manufacturer_id=self.program.manufacturer_id)

        is_current = any(
            a.effective_start_date and a.effective_start_date <= today <= (a.effective_end_date or _date.max)
            for a in candidates
        )

        if not is_current:
            raise ValidationError({
                "status": _("ACTIVE coverage requires a current contract assignment matching the program.")
            })