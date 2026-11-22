from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from utilities.forms.rendering import FieldSet

from .reassign import AssetDeviceReassignForm

__all__ = ('AssetDeviceReplacementForm',)


class AssetDeviceReplacementForm(AssetDeviceReassignForm):
    """
    Guided "hardware replacement" workflow for a device: walks through
    returning the currently assigned asset to storage (step 1) and assigning
    a replacement asset in its place (step 2), in a single submission.

    This is the same underlying mechanics as AssetDeviceReassignForm, but:
      * requires an asset to currently be assigned (there must be something
        to replace)
      * requires a replacement asset to be selected (assigned_asset is not
        optional here, unlike the generic reassign form which also permits
        plain unassignment)
      * presents the two steps with wizard-style framing
    """

    fieldsets = (
        FieldSet(
            'asset_status',
            'old_asset_storage_site',
            'old_asset_storage_location',
            name=_('Step 1: Return Current Asset to Storage'),
        ),
        FieldSet(
            'storage_site', 'storage_location', 'assigned_asset',
            name=_('Step 2: Assign Replacement Asset'),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['assigned_asset'].required = True
        self.fields['assigned_asset'].help_text = (
            'Replacement asset to assign to this device'
        )

    def clean(self, *args, **kwargs):
        cleaned_data = super().clean(*args, **kwargs)
        if self.errors:
            return cleaned_data
        if not self.old_asset:
            raise ValidationError(
                'This device has no asset currently assigned, so there is '
                'nothing to replace. Use "Edit Assignment" to assign an '
                'asset to it instead.'
            )
        if not self.new_asset:
            raise ValidationError(
                {'assigned_asset': 'A replacement asset is required.'}
            )
        return cleaned_data
