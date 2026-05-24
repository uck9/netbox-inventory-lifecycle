from rest_framework import serializers

from dcim.api.serializers import ManufacturerSerializer
from netbox.api.serializers import NetBoxModelSerializer

from netbox_inventory.models import (
    AssetLicense,
    LicenseSKU,
    Order,
    SmartAccount,
    Subscription,
    VirtualAccount,
)
from netbox_inventory.models.assets import Asset

__all__ = (
    'LicenseSKUSerializer',
    'SmartAccountSerializer',
    'VirtualAccountSerializer',
    'SubscriptionSerializer',
    'AssetLicenseSerializer',
)


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


class SmartAccountSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_inventory-api:smartaccount-detail'
    )
    manufacturer = ManufacturerSerializer(nested=True)
    virtual_account_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = SmartAccount
        fields = (
            "id", "url", "display",
            "manufacturer",
            "account_domain",
            "description",
            "virtual_account_count",
            "comments",
            "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = (
            "id", "url", "display", "manufacturer", "account_domain",
        )


class VirtualAccountSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_inventory-api:virtualaccount-detail'
    )
    smart_account = SmartAccountSerializer(nested=True)
    smart_account_id = serializers.PrimaryKeyRelatedField(
        source='smart_account',
        queryset=SmartAccount.objects.all(),
        write_only=True,
    )
    subscription_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = VirtualAccount
        fields = (
            "id", "url", "display",
            "smart_account", "smart_account_id",
            "name",
            "description",
            "subscription_count",
            "comments",
            "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = (
            "id", "url", "display", "smart_account", "name",
        )


class SubscriptionSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_inventory-api:subscription-detail'
    )
    manufacturer = ManufacturerSerializer(nested=True)
    virtual_account = VirtualAccountSerializer(nested=True, read_only=True)
    virtual_account_id = serializers.PrimaryKeyRelatedField(
        source='virtual_account',
        queryset=VirtualAccount.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    order = serializers.SerializerMethodField(read_only=True)
    order_id = serializers.PrimaryKeyRelatedField(
        source='order',
        queryset=Order.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    license_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Subscription
        fields = (
            "id", "url", "display",
            "manufacturer",
            "subscription_id",
            "subscription_type",
            "virtual_account", "virtual_account_id",
            "order", "order_id",
            "quantity",
            "start_date",
            "end_date",
            "description",
            "license_count",
            "comments",
            "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = (
            "id", "url", "display", "manufacturer", "subscription_id",
            "subscription_type", "description",
        )

    def get_order(self, obj):
        if obj.order_id is None:
            return None
        return {
            "id": obj.order.pk,
            "url": self.context["request"].build_absolute_uri(
                f"/api/plugins/inventory/orders/{obj.order.pk}/"
            ) if "request" in self.context else None,
            "display": str(obj.order),
            "name": obj.order.name,
        }


class _NestedAssetSerializer(NetBoxModelSerializer):
    """Minimal nested asset representation — avoids circular import with AssetSerializer."""

    class Meta:
        model = Asset
        fields = ('id', 'url', 'display', 'name', 'asset_tag', 'serial')
        brief_fields = ('id', 'url', 'display', 'name')


class AssetLicenseSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_inventory-api:assetlicense-detail'
    )
    asset = _NestedAssetSerializer(nested=True)
    subscription = SubscriptionSerializer(nested=True)
    sku = LicenseSKUSerializer(nested=True)
    asset_id = serializers.PrimaryKeyRelatedField(
        source='asset',
        queryset=Asset.objects.all(),
        write_only=True,
    )
    subscription_id = serializers.PrimaryKeyRelatedField(
        source='subscription',
        queryset=Subscription.objects.all(),
        write_only=True,
    )
    sku_id = serializers.PrimaryKeyRelatedField(
        source='sku',
        queryset=LicenseSKU.objects.all(),
        write_only=True,
    )
    status = serializers.CharField(source='status_label', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = AssetLicense
        fields = (
            "id", "url", "display",
            "asset_id", "subscription_id", "sku_id",
            "asset", "subscription", "sku",
            "license_source",
            "start_date", "end_date", "quantity",
            "status", "is_active", "is_expired", "days_until_expiry",
            "notes", "comments",
            "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = (
            "id", "url", "display",
            "subscription", "sku",
            "start_date", "end_date", "status",
        )
