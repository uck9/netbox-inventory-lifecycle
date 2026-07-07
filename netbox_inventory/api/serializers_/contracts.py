from rest_framework import serializers  # type: ignore

from dcim.api.serializers_.manufacturers import ManufacturerSerializer  # type: ignore
from netbox.api.fields import ChoiceField  # type: ignore
from netbox.api.serializers import NetBoxModelSerializer  # type: ignore
from tenancy.api.serializers import ContactSerializer  # type: ignore  # noqa: F401

from netbox_inventory.api.serializers_.assets import AssetSerializer
from netbox_inventory.choices import ContractTypeChoices
from netbox_inventory.models.assets import Asset
from netbox_inventory.models.contracts import *

__all__ = (
    'ContractVendorSerializer',
    'ContractSKUSerializer',
    'ContractSerializer',
    'ContractAssignmentSerializer',
)

class ContractVendorSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='plugins-api:netbox_inventory-api:contractvendor-detail')
    manufacturer = ManufacturerSerializer(nested=True, required=False, allow_null=True)

    class Meta:
        model = ContractVendor
        fields = ('url', 'id', 'display', 'name', 'manufacturer', 'description', 'comments', 'tags', 'custom_fields', )
        brief_fields = ('url', 'id', 'display', 'name', 'manufacturer', )

class ContractSKUSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='plugins-api:netbox_inventory-api:contractsku-detail')
    manufacturer = ManufacturerSerializer(nested=True)

    class Meta:
        model = ContractSKU
        fields = ('url', 'id', 'display', 'manufacturer', 'sku', 'contract_type', 'service_level', 'description', 'comments', 'tags', 'custom_fields')
        brief_fields = ('url', 'id', 'display', 'manufacturer', 'sku', )

class ContractSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_inventory-api:contract-detail'
    )
    vendor = ContractVendorSerializer(nested=True)
    contract_type = ChoiceField(choices=ContractTypeChoices)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    renewal_date = serializers.DateField(required=False)
    asset_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Contract
        fields = (
            'id',
            'url',
            'display',
            'vendor',
            'contract_id',
            'contract_type',
            'status',
            'start_date',
            'end_date',
            'renewal_date',
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
            'contract_id',
            'vendor',
            'contract_type',
            'status',
            'start_date',
            'end_date',
        )

class ContractAssignmentSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='plugins-api:netbox_inventory-api:contractassignment-detail')
    # Read-only nested representations. These are read_only (rather than also
    # accepting writes) so they don't collide with the dedicated _id fields
    # below, which are the only supported way to set these relations. Writing
    # through the nested `asset` field crashes (AssetSerializer.to_internal_value
    # assumes it always receives a dict, which isn't true when nested=True short-
    # circuits to return the resolved model instance directly).
    contract = ContractSerializer(nested=True, read_only=True)
    sku = ContractSKUSerializer(nested=True, read_only=True, allow_null=True)
    asset = AssetSerializer(nested=True, read_only=True)
    # Write: accept PKs directly (use _id suffix — DRF resolves source automatically)
    contract_id = serializers.PrimaryKeyRelatedField(
        source='contract',
        queryset=Contract.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    sku_id = serializers.PrimaryKeyRelatedField(
        source='sku',
        queryset=ContractSKU.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    asset_id = serializers.PrimaryKeyRelatedField(
        source='asset',
        queryset=Asset.objects.all(),
        write_only=True,
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    renewal_date = serializers.DateField(required=False)

    class Meta:
        model = ContractAssignment
        fields = (
            'url', 'id', 'display',
            'contract_id', 'sku_id', 'asset_id',
            'contract', 'sku', 'asset',
            'start_date', 'end_date',
            'renewal_date', 'tags', 'description', 'comments', 'custom_fields',
        )

        brief_fields = ('url', 'id', 'display', 'contract', 'sku', 'asset', 'start_date', 'end_date')
