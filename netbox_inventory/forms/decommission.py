from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, Location, Site

from netbox.forms import NetBoxModelForm
from utilities.forms.fields import DynamicModelChoiceField
from utilities.forms.rendering import FieldSet

from ..models import Asset
from ..utils import prepare_asset_for_storage

__all__ = ('AssetDeviceDecommissionForm',)


class AssetDeviceDecommissionForm(NetBoxModelForm):
    """
    Guided step for decommissioning a device: unassigns the currently
    assigned asset and moves it back into storage, so the device can then
    safely be deleted. Does not touch disposal fields - disposal is a
    separate, later workflow performed directly on the Asset.
    """

    storage_site = DynamicModelChoiceField(
        queryset=Site.objects.all(),
        required=False,
        help_text='Site where the asset will be stored once unassigned',
    )
    storage_location = DynamicModelChoiceField(
        queryset=Location.objects.all(),
        required=True,
        query_params={
            'site_id': '$storage_site',
        },
        help_text='Storage location to set on the asset once it is unassigned from this device',
    )

    fieldsets = (
        FieldSet('storage_site', 'storage_location', name=_('Return Asset to Storage')),
    )

    class Meta:
        model = Device
        fields = (
            'storage_site',
            'storage_location',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # remove tags field, this form does not edit the device itself
        self.fields.pop('tags', None)

        # Remove Custom Fields from form
        for cf_name in self.custom_fields.keys():
            self.fields.pop(cf_name, None)
        self.custom_fields = {}
        self.custom_fields_groups = {}

        try:
            self.asset = self.instance.assigned_asset
        except Asset.DoesNotExist:
            self.asset = None

        # default storage_site to the asset's current install site, if known
        if self.asset and not self.is_bound:
            install_site = getattr(self.instance, 'site', None)
            if install_site:
                self.initial['storage_site'] = install_site

    def clean(self):
        cleaned_data = super().clean()
        if self.errors:
            return cleaned_data

        if not self.asset:
            raise ValidationError(
                'No asset is currently assigned to this device. Nothing to decommission.'
            )

        storage_location = cleaned_data.get('storage_location')
        try:
            prepare_asset_for_storage(self.asset, storage_location)
        except ValidationError as e:
            # surface asset validation errors (e.g. missing storage_location)
            # against the storage_location field where sensible
            if hasattr(e, 'message_dict') and 'storage_location' in e.message_dict:
                raise ValidationError(
                    {'storage_location': e.message_dict['storage_location']}
                )
            raise ValidationError(e.messages)

        return cleaned_data

    def save(self, commit=True):
        if self.errors:
            raise ValueError(
                "The %s could not be %s because the data didn't validate."
                % (
                    self.instance._meta.object_name,
                    'created' if self.instance._state.adding else 'changed',
                )
            )
        if commit:
            self.asset.save(clear_old_hw=True)
        return self.instance
