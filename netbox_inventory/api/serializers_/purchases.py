from rest_framework import serializers

from netbox.api.serializers import NetBoxModelSerializer
from dcim.api.serializers_.manufacturers import ManufacturerSerializer
from tenancy.api.serializers import ContactSerializer

from .nested import *
from netbox_inventory.models import Order, Purchase, Supplier


class SupplierSerializer(NetBoxModelSerializer):
    asset_count = serializers.IntegerField(read_only=True)
    purchase_count = serializers.IntegerField(read_only=True)
    order_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Supplier
        fields = (
            'id',
            'url',
            'display',
            'name',
            'slug',
            'description',
            'comments',
            'tags',
            'custom_fields',
            'created',
            'last_updated',
            'asset_count',
            'purchase_count',
            'order_count',
        )
        brief_fields = ('id', 'url', 'display', 'name', 'slug', 'description')


class PurchaseSerializer(NetBoxModelSerializer):
    supplier = SupplierSerializer(nested=True)
    asset_count = serializers.IntegerField(read_only=True)
    order_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Purchase
        fields = (
            'id',
            'url',
            'display',
            'supplier',
            'name',
            'purchase_requisition',
            'purchase_order',
            'internal_reference',
            'supplier_reference',
            'status',
            'date',
            'description',
            'comments',
            'tags',
            'custom_fields',
            'created',
            'last_updated',
            'asset_count',
            'order_count',
        )
        brief_fields = (
            'id',
            'url',
            'display',
            'supplier',
            'name',
            'purchase_requisition',
            'purchase_order',
            'internal_reference',
            'status',
            'date',
            'description',
        )


class OrderSerializer(NetBoxModelSerializer):
    purchase = PurchaseSerializer(nested=True)
    manufacturer = ManufacturerSerializer(nested=True)
    asset_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = (
            'id',
            'url',
            'display',
            'purchase',
            'name',
            'description',
            'comments',
            'manufacturer',
            'tags',
            'custom_fields',
            'created',
            'last_updated',
            'asset_count',
        )
        brief_fields = ('id', 'url', 'display', 'name', 'manufacturer', 'description')
