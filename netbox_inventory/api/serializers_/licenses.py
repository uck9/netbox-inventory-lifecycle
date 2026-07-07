from rest_framework import serializers

from dcim.api.serializers import ManufacturerSerializer
from netbox.api.serializers import NetBoxModelSerializer

from netbox_inventory.models import AssetLicense, LicenseSKU, Order, Subscription
from netbox_inventory.models.assets import Asset

__all__ = (
    'LicenseSKUSerializer',
    'SubscriptionSerializer',
    'AssetLicenseSerializer',
)


class LicenseSKUSerializer(NetBoxModelSerializer):
    manufacturer = ManufacturerSerializer(nested=True)

    class Meta:
        model = LicenseSKU
        fields = (
            "id", "url", "display", "manufacturer",
            "sku", "name", "license_kind", "description", "renewal_budget_per_unit",
            "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = (
            "id", "url", "display", "manufacturer", "sku", "name",
        )


def _serialize_order(order, context):
    """Lightweight order representation (avoids importing OrderSerializer which causes circular refs)."""
    if order is None:
        return None
    return {
        "id": order.pk,
        "url": context["request"].build_absolute_uri(
            f"/api/plugins/inventory/orders/{order.pk}/"
        ) if "request" in context else None,
        "display": str(order),
        "name": order.name,
    }


class SubscriptionSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_inventory-api:subscription-detail'
    )
    manufacturer = ManufacturerSerializer(nested=True)
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
            "description",
            "order", "order_id",
            "license_count",
            "comments",
            "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = (
            "id", "url", "display", "manufacturer", "subscription_id", "description",
        )

    def get_order(self, obj):
        return _serialize_order(obj.order, self.context)


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
    # Read-only nested representations. These are read_only (rather than also
    # accepting writes) so they don't collide with the dedicated _id fields
    # below, which are the only supported way to set these relations.
    asset = _NestedAssetSerializer(nested=True, read_only=True)
    subscription = SubscriptionSerializer(nested=True, read_only=True, allow_null=True)
    sku = LicenseSKUSerializer(nested=True, read_only=True)
    # Lightweight order representation (avoids importing OrderSerializer which causes circular refs)
    order = serializers.SerializerMethodField(read_only=True)
    # Write: accept PKs directly (use _id suffix — DRF resolves source automatically)
    asset_id = serializers.PrimaryKeyRelatedField(
        source='asset',
        queryset=Asset.objects.all(),
        write_only=True,
    )
    subscription_id = serializers.PrimaryKeyRelatedField(
        source='subscription',
        queryset=Subscription.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    order_id = serializers.PrimaryKeyRelatedField(
        source='order',
        queryset=Order.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    sku_id = serializers.PrimaryKeyRelatedField(
        source='sku',
        queryset=LicenseSKU.objects.all(),
        write_only=True,
    )
    # Computed read-only fields
    status = serializers.CharField(source='status_label', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = AssetLicense
        fields = (
            "id", "url", "display",
            # write-only FK fields
            "asset_id", "subscription_id", "order_id", "sku_id",
            # read nested representations
            "asset", "subscription", "order", "sku",
            # dates & quantities
            "start_date", "end_date", "quantity", "license_key",
            # computed
            "status", "is_active", "is_expired", "days_until_expiry",
            # misc
            "notes", "comments",
            "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = (
            "id", "url", "display",
            "subscription", "sku",
            "start_date", "end_date", "status",
        )

    def get_order(self, obj):
        return _serialize_order(obj.order, self.context)
