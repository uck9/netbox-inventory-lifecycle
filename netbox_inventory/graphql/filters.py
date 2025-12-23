import strawberry_django

from netbox.graphql.filter_mixins import BaseFilterMixin

from netbox_inventory import models

__all__ = (
    'AssetFilter',
    'SupplierFilter'
    'OrderFilter',
    'PurchaseFilter',
    'InventoryItemTypeFilter',
    'InventoryItemGroupFilter',
)


@strawberry_django.filter(models.Asset, lookups=True)
class AssetFilter(BaseFilterMixin):
    pass


@strawberry_django.filter(models.Supplier, lookups=True)
class SupplierFilter(BaseFilterMixin):
    pass


@strawberry_django.filter(models.Purchase, lookups=True)
class PurchaseFilter(BaseFilterMixin):
    pass


@strawberry_django.filter(models.Order, lookups=True)
class OrderFilter(BaseFilterMixin):
    pass


@strawberry_django.filter(models.InventoryItemType, lookups=True)
class InventoryItemTypeFilter(BaseFilterMixin):
    pass


@strawberry_django.filter(models.InventoryItemGroup, lookups=True)
class InventoryItemGroupFilter(BaseFilterMixin):
    pass
