from dcim.models import Device
from netbox.views import generic

from ..forms.decommission import *

__all__ = ('AssetDeviceDecommissionView',)


class AssetDeviceDecommissionView(generic.ObjectEditView):
    """
    Guided workflow step for decommissioning a device: unassigns the
    currently assigned asset and moves it back into storage. Does not delete
    the device itself - once the asset is unassigned the user can delete the
    device normally. Does not touch disposal - that remains a separate,
    later workflow performed directly on the Asset.
    """

    queryset = Device.objects.all()
    template_name = 'netbox_inventory/asset_decommission.html'
    form = AssetDeviceDecommissionForm
