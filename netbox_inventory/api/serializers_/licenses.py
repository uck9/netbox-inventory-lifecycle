from rest_framework import serializers
from netbox.api.serializers import NetBoxModelSerializer
from dcim.api.serializers import ManufacturerSerializer

from netbox_inventory.models import LicenseSKU

__all__ = (
    'LicenseSKUSerializer',)

class LicenseSKUSerializer(NetBoxModelSerializer):
    manufacturer = ManufacturerSerializer(nested=True)

    class Meta:
        model = LicenseSKU
        fields = (
            "id", "url", "display", "manufacturer",
            "sku", "name", "license_kind", "description",
            "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = (
            "id", "url", "display", "manufacturer", "sku", "name",
        )