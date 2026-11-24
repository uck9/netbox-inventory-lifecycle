from rest_framework import serializers

from netbox.api.fields import ChoiceField
from netbox.api.serializers import NetBoxModelSerializer

from netbox_inventory.choices import SORValidationStatusChoices, SystemOfRecordChoices
from netbox_inventory.models import AssetSystemOfRecord

from .licenses import _NestedAssetSerializer

__all__ = (
    'AssetSystemOfRecordSerializer',
    'NestedAssetSystemOfRecordSerializer',
)


class AssetSystemOfRecordSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_inventory-api:assetsystemofrecord-detail'
    )
    asset = _NestedAssetSerializer(nested=True)
    system = ChoiceField(choices=SystemOfRecordChoices)
    validation_status = ChoiceField(choices=SORValidationStatusChoices, required=False)
    is_stale = serializers.BooleanField(read_only=True)

    class Meta:
        model = AssetSystemOfRecord
        fields = (
            'id', 'url', 'display',
            'asset',
            'system', 'record_id', 'validation_status', 'last_validated', 'is_stale',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = (
            'id', 'url', 'display', 'system', 'record_id', 'validation_status',
        )


class NestedAssetSystemOfRecordSerializer(serializers.ModelSerializer):
    """Read-only per-asset summary embedded in AssetSerializer."""
    system = ChoiceField(choices=SystemOfRecordChoices, read_only=True)
    validation_status = ChoiceField(choices=SORValidationStatusChoices, read_only=True)
    is_stale = serializers.BooleanField(read_only=True)

    class Meta:
        model = AssetSystemOfRecord
        fields = ('id', 'system', 'record_id', 'validation_status', 'last_validated', 'is_stale')
        read_only_fields = fields
