from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from dcim.models import Device
from netbox.views import generic

from ..forms.replace import AssetDeviceReplacementForm
from ..models import Asset

__all__ = ('AssetDeviceReplacementView',)


class AssetDeviceReplacementView(generic.ObjectEditView):
    """
    Guided "hardware replacement" workflow: returns the device's currently
    assigned asset to storage and assigns a replacement asset to the device,
    in a single wizard-style form.
    """

    queryset = Device.objects.all()
    template_name = 'netbox_inventory/asset_replace.html'
    form = AssetDeviceReplacementForm

    def get(self, request, *args, **kwargs):
        obj = self.get_object(**kwargs)
        try:
            obj.assigned_asset
        except Asset.DoesNotExist:
            messages.warning(
                request,
                f'{obj} has no asset currently assigned, so there is '
                'nothing to replace. Use "Edit Assignment" to assign an '
                'asset to it instead.',
            )
            return redirect(
                reverse('plugins:netbox_inventory:asset_device_reassign', kwargs={'pk': obj.pk})
            )
        return super().get(request, *args, **kwargs)
