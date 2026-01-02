from rest_framework import serializers

from netbox.api.serializers import NetBoxModelSerializer

from netbox_inventory.models.programs import AssetProgramCoverage, VendorProgram

__all__ = (
    'VendorProgramSerializer',
    'AssetProgramCoverageSerializer',
)

class VendorProgramSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_inventory-api:vendorprogram-detail"
    )

    class Meta:
        model = VendorProgram
        fields = (
            "id",
            "url",
            "display",
            "name",
            "slug",
            "manufacturer",
            "description",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )


class AssetProgramCoverageSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name="plugins-api:netbox_inventory-api:assetprogramcoverage-detail"
    )

    class Meta:
        model = AssetProgramCoverage
        fields = (
            "id",
            "url",
            "display",
            "asset",
            "program",
            "status",
            "eligibility",
            "effective_start",
            "effective_end",
            "decision_reason",
            "notes",
            "evidence_url",
            "source",
            "last_synced",
            "tags",
            "custom_fields",
            "created",
            "last_updated",
        )

    def validate(self, attrs):
        """Enforce that program manufacturer matches the asset's manufacturer."""
        attrs = super().validate(attrs)

        asset = attrs.get('asset') or getattr(self.instance, 'asset', None)
        program = attrs.get('program') or getattr(self.instance, 'program', None)

        program_mfr = getattr(program, 'manufacturer', None) if program else None
        asset_mfr = None
        asset_device = getattr(asset, 'device', None) if asset else None
        if asset_device is not None:
            device_type = getattr(asset_device, 'device_type', None)
            if device_type is not None:
                asset_mfr = getattr(device_type, 'manufacturer', None)

        if program_mfr and asset_mfr and program_mfr.pk != asset_mfr.pk:
            raise serializers.ValidationError({
                'program': f"Program manufacturer does not match this asset's manufacturer: ({asset_mfr})."
            })

        # For ACTIVE coverage, require determinable manufacturer when program has one
        status = attrs.get('status') or getattr(self.instance, 'status', None)
        if status == 'active' and program_mfr and asset_mfr is None:
            raise serializers.ValidationError({
                'asset': 'Cannot determine asset manufacturer (asset not linked to a device/device type).'
            })

        return attrs
