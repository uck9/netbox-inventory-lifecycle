from rest_framework import serializers
from dcim.api.serializers_.manufacturers import ManufacturerSerializer
from netbox.api.fields import ChoiceField
from netbox.api.serializers import NetBoxModelSerializer
from tenancy.api.serializers import ContactSerializer

from netbox_inventory.models.contracts import *
from netbox_inventory.api.serializers_.assets import AssetSerializer

from netbox_inventory.choices import ContractTypeChoices, ContractStatusChoices

__all__ = (
    'ContractVendorSerializer',
    'ContractSKUSerializer',
    'ContractSerializer',
    'ContractAssignmentSerializer',
)

class ContractVendorSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='plugins-api:netbox_inventory-api:contractvendor-detail')

    class Meta:
        model = ContractVendor
        fields = ('url', 'id', 'display', 'name', 'description', 'comments', 'tags', 'custom_fields', )
        brief_fields = ('url', 'id', 'display', 'name', )

class ContractSKUSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='plugins-api:netbox_inventory-api:contractsku-detail')
    manufacturer = ManufacturerSerializer(nested=True)

    class Meta:
        model = ContractSKU
        fields = ('url', 'id', 'display', 'manufacturer', 'sku', 'service_level','description', 'comments', 'tags', 'custom_fields' )
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
    contract = ContractSerializer(nested=True)
    sku = ContractSKUSerializer(nested=True, required=False, allow_null=True)
    asset = AssetSerializer(nested=True, required=False, allow_null=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    renewal_date = serializers.DateField(required=False)

    class Meta:
        model = ContractAssignment
        fields = (
            'url', 'id', 'display', 'contract', 'sku', 'asset', 'start_date', 'end_date', 
            'renewal_date', 'tags', 'description', 'comments', 'custom_fields',
        )

        brief_fields = ('url', 'id', 'display', 'contract', 'sku', 'asset', 'start_date', 'end_date')