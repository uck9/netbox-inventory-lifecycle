from rest_framework import serializers

from dcim.api.serializers_.manufacturers import ManufacturerSerializer
from dcim.api.serializers_.sites import SiteSerializer
from netbox.api.serializers import PrimaryModelSerializer

from netbox_inventory.models import InstalledAtLocation


__all__ = ('InstalledAtLocationSerializer',)


class InstalledAtLocationSerializer(PrimaryModelSerializer):
    manufacturer = ManufacturerSerializer(nested=True)
    sites = SiteSerializer(nested=True, many=True, required=False)
    asset_count = serializers.IntegerField(read_only=True)
    full_address = serializers.CharField(read_only=True)

    class Meta:
        model = InstalledAtLocation
        fields = (
            'id',
            'url',
            'display',
            'manufacturer',
            'vendor_site_id',
            'address',
            'city',
            'state',
            'postcode',
            'country',
            'sites',
            'full_address',
            'description',
            'comments',
            'tags',
            'custom_fields',
            'created',
            'last_updated',
            'asset_count',
        )
        brief_fields = (
            'id',
            'url',
            'display',
            'manufacturer',
            'vendor_site_id',
            'city',
            'country',
            'full_address',
        )
