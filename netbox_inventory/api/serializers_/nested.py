from rest_framework import serializers

from netbox.api.serializers import WritableNestedSerializer

from netbox_inventory.models import Contract, InventoryItemGroup

__all__ = ('NestedContractSerializer', 'NestedInventoryItemGroupSerializer')


class NestedContractSerializer(WritableNestedSerializer):
    class Meta:
        model = Contract
        fields = ('id', 'url', 'display', 'contract_id')


class NestedInventoryItemGroupSerializer(WritableNestedSerializer):
    _depth = serializers.IntegerField(source='level', read_only=True)

    class Meta:
        model = InventoryItemGroup
        fields = ('id', 'url', 'display', 'name', 'description', '_depth')
