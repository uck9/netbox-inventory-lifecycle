from netbox.search import SearchIndex

from .models import (
    Asset,
    AssetLicense,
    AuditTrailSource,
    Contract,
    ContractSKU,
    ContractVendor,
    InventoryItemGroup,
    InventoryItemType,
    LicenseBundle,
    LicenseSKU,
    Order,
    Purchase,
    Subscription,
    Supplier,
)

#
# Assets
#


class InventoryItemGroupIndex(SearchIndex):
    model = InventoryItemGroup
    fields = (
        ('name', 100),
        ('description', 500),
        ('comments', 5000),
    )


class InventoryItemTypeIndex(SearchIndex):
    model = InventoryItemType
    fields = (
        ('model', 100),
        ('part_number', 100),
        ('description', 500),
        ('comments', 5000),
    )


class AssetIndex(SearchIndex):
    model = Asset
    fields = (
        ('name', 100),
        ('asset_tag', 50),
        ('serial', 60),
        ('description', 500),
        ('comments', 5000),
    )
    display_attrs = ('name', 'asset_tag', 'status')


#
# Purchases
#


class SupplierIndex(SearchIndex):
    model = Supplier
    fields = (
        ('name', 100),
        ('description', 500),
        ('comments', 5000),
    )


class PurchaseIndex(SearchIndex):
    model = Purchase
    fields = (
        ('name', 100),
        ('description', 500),
        ('supplier_reference', 200),
        ('purchase_requisition', 200),
        ('purchase_order', 200),
        ('comments', 5000),
    )


class OrderIndex(SearchIndex):
    model = Order
    fields = (
        ('name', 100),
        ('description', 500),
        ('comments', 5000),
    )


#
# Licenses
#


class LicenseSKUIndex(SearchIndex):
    model = LicenseSKU
    fields = (
        ('sku', 100),
        ('name', 100),
        ('description', 500),
    )


class SubscriptionIndex(SearchIndex):
    model = Subscription
    fields = (
        ('subscription_id', 100),
        ('description', 500),
        ('comments', 5000),
    )


class LicenseBundleIndex(SearchIndex):
    model = LicenseBundle
    fields = (
        ('notes', 200),
        ('comments', 5000),
    )


class AssetLicenseIndex(SearchIndex):
    model = AssetLicense
    fields = (
        ('license_key', 100),
        ('notes', 200),
        ('comments', 5000),
    )


#
# Contracts
#


class ContractVendorIndex(SearchIndex):
    model = ContractVendor
    fields = (
        ('name', 100),
    )


class ContractSKUIndex(SearchIndex):
    model = ContractSKU
    fields = (
        ('sku', 100),
        ('contract_type', 200),
        ('service_level', 200),
        ('description', 500),
        ('notes', 5000),
    )


class ContractIndex(SearchIndex):
    model = Contract
    fields = (
        ('contract_id', 100),
        ('contract_type', 200),
        ('description', 500),
        ('notes', 5000),
    )


#
# Audit
#


class AuditTrailSourceIndex(SearchIndex):
    model = AuditTrailSource
    fields = (
        ('name', 100),
        ('slug', 110),
        ('description', 500),
        ('comments', 5000),
    )


indexes = [
    InventoryItemGroupIndex,
    InventoryItemTypeIndex,
    AssetIndex,
    SupplierIndex,
    PurchaseIndex,
    OrderIndex,
    LicenseSKUIndex,
    SubscriptionIndex,
    LicenseBundleIndex,
    AssetLicenseIndex,
    ContractVendorIndex,
    ContractSKUIndex,
    ContractIndex,
    AuditTrailSourceIndex,
]
