from django import forms
from django.utils.translation import gettext_lazy as _

from ..models import Contract, ContractSKU


class ActivateCoverageForm(forms.Form):
    contract = forms.ModelChoiceField(
        queryset=Contract.objects.none(),
        label=_("Contract"),
        help_text=_("Select the contract to activate coverage under."),
    )
    sku = forms.ModelChoiceField(
        queryset=ContractSKU.objects.none(),
        label=_("SKU"),
        help_text=_("Select the support SKU (service level is derived from SKU)."),
    )
    start_date = forms.DateField(
        required=False,
        label=_("Start date"),
        help_text=_("Defaults to today if blank."),
    )
    end_date = forms.DateField(
        required=False,
        label=_("End date"),
        help_text=_("Leave blank for open-ended / until contract ends."),
    )

    def __init__(self, *args, coverage=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.coverage = coverage

        # Hard filter contract + sku choices to prevent wrong picks
        if coverage is None:
            return

        program = coverage.program
        contract_type = getattr(program, "contract_type", None)
        manufacturer = getattr(program, "manufacturer", None)

        # Contracts filtered by contract_type (EA vs ALC)
        if contract_type:
            self.fields["contract"].queryset = Contract.objects.filter(contract_type=contract_type)
        else:
            self.fields["contract"].queryset = Contract.objects.all()

        # SKUs filtered by manufacturer + contract_type (if you add sku.contract_type)
        sku_qs = ContractSKU.objects.all()
        if manufacturer:
            sku_qs = sku_qs.filter(manufacturer=manufacturer)

        # If you added sku.contract_type, enforce correct SKU type too
        if hasattr(ContractSKU, "contract_type") and contract_type:
            sku_qs = sku_qs.filter(contract_type=contract_type)

        self.fields["sku"].queryset = sku_qs
