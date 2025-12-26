from dcim.api.views import DeviceViewSet, InventoryItemViewSet, ModuleViewSet
from netbox.api.viewsets import NetBoxModelViewSet
from utilities.query import count_related

from .. import filtersets, models
from .serializers import *

__all__ = (
    'AssetViewSet',
    'AuditFlowPageAssignmentViewSet',
    'AuditFlowPageViewSet',
    'AuditFlowViewSet',
    'AuditTrailSourceViewSet',
    'AuditTrailViewSet',
    'ContractVendorViewSet',
    'ContractSKUViewSet',
    'ContractAssignmentViewSet',
    'ContractViewSet',
    'HardwareLifecycleViewSet',
    'OrderViewSet',
    'DeviceAssetViewSet',
    'InventoryItemAssetViewSet',
    'InventoryItemGroupViewSet',
    'InventoryItemTypeViewSet',
    'ModuleAssetViewSet',
    'PurchaseViewSet',
    'SupplierViewSet',
)

#
# Assets
#


class InventoryItemGroupViewSet(NetBoxModelViewSet):
    queryset = models.InventoryItemGroup.objects.add_related_count(
        models.InventoryItemGroup.objects.all(),
        models.Asset,
        'inventoryitem_type__inventoryitem_group',
        'asset_count',
        cumulative=True,
    ).prefetch_related('tags')
    serializer_class = InventoryItemGroupSerializer
    filterset_class = filtersets.InventoryItemGroupFilterSet


class InventoryItemTypeViewSet(NetBoxModelViewSet):
    queryset = models.InventoryItemType.objects.prefetch_related('tags').annotate(
        asset_count=count_related(models.Asset, 'inventoryitem_type')
    )
    serializer_class = InventoryItemTypeSerializer
    filterset_class = filtersets.InventoryItemTypeFilterSet


class AssetViewSet(NetBoxModelViewSet):
    queryset = models.Asset.objects.prefetch_related(
        'device_type',
        'device',
        'module_type',
        'module',
        'rack_type',
        'rack',
        'storage_location',
        'order',
        'purchase__supplier',
        'tags',
    )
    serializer_class = AssetSerializer
    filterset_class = filtersets.AssetFilterSet


class DeviceAssetViewSet(DeviceViewSet):
    """
    Adds option to filter on asset assignemnet
    """

    filterset_class = filtersets.DeviceAssetFilterSet


class ModuleAssetViewSet(ModuleViewSet):
    """
    Adds option to filter on asset assignemnet
    """

    filterset_class = filtersets.ModuleAssetFilterSet


class InventoryItemAssetViewSet(InventoryItemViewSet):
    """
    Adds option to filter on asset assignemnet
    """

    filterset_class = filtersets.InventoryItemAssetFilterSet

#
# Contracts
#


class ContractVendorViewSet(NetBoxModelViewSet):
    queryset = models.ContractVendor.objects.all()
    serializer_class = ContractVendorSerializer
    filterset_class = filtersets.ContractVendorFilterSet


class ContractSKUViewSet(NetBoxModelViewSet):
    queryset = models.ContractSKU.objects.all()
    serializer_class = ContractSKUSerializer
    filterset_class = filtersets.ContractSKUFilterSet


class ContractAssignmentViewSet(NetBoxModelViewSet):
    queryset = models.ContractAssignment.objects.all()
    serializer_class = ContractAssignmentSerializer
    filterset_class = filtersets.ContractAssignmentFilterSet


class ContractViewSet(NetBoxModelViewSet):
    queryset = models.Contract.objects.prefetch_related('tags').annotate(
        asset_count=count_related(models.Asset, 'contract')
    )
    serializer_class = ContractSerializer
    filterset_class = filtersets.ContractFilterSet


#
# Hardware Lifecycle
#

class HardwareLifecycleViewSet(NetBoxModelViewSet):
    queryset = models.HardwareLifecycle.objects.all()
    serializer_class = HardwareLifecycleSerializer
    filterset_class = filtersets.HardwareLifecycleFilterSet


#
# Purchases
#


class SupplierViewSet(NetBoxModelViewSet):
    queryset = models.Supplier.objects.prefetch_related('tags').annotate(
        asset_count=count_related(models.Asset, 'purchase__supplier'),
        purchase_count=count_related(models.Purchase, 'supplier'),
        order_count=count_related(models.Order, 'purchase__supplier'),
    )
    serializer_class = SupplierSerializer
    filterset_class = filtersets.SupplierFilterSet


class PurchaseViewSet(NetBoxModelViewSet):
    queryset = models.Purchase.objects.prefetch_related('tags').annotate(
        asset_count=count_related(models.Asset, 'purchase'),
        order_count=count_related(models.Order, 'purchase'),
    )
    serializer_class = PurchaseSerializer
    filterset_class = filtersets.PurchaseFilterSet


class OrderViewSet(NetBoxModelViewSet):
    queryset = models.Order.objects.prefetch_related('tags').annotate(
        asset_count=count_related(models.Asset, 'order')
    )
    serializer_class = OrderSerializer
    filterset_class = filtersets.OrderFilterSet


#
# Audit
#


class AuditFlowPageViewSet(NetBoxModelViewSet):
    queryset = models.AuditFlowPage.objects.prefetch_related('object_type', 'tags')
    serializer_class = AuditFlowPageSerializer


class AuditFlowViewSet(NetBoxModelViewSet):
    queryset = models.AuditFlow.objects.prefetch_related('object_type', 'pages', 'tags')
    serializer_class = AuditFlowSerializer


class AuditFlowPageAssignmentViewSet(NetBoxModelViewSet):
    queryset = models.AuditFlowPageAssignment.objects.prefetch_related('flow', 'page')
    serializer_class = AuditFlowPageAssignmentSerializer


class AuditTrailSourceViewSet(NetBoxModelViewSet):
    queryset = models.AuditTrailSource.objects.prefetch_related('tags')
    serializer_class = AuditTrailSourceSerializer


class AuditTrailViewSet(NetBoxModelViewSet):
    queryset = models.AuditTrail.objects.prefetch_related('object')
    serializer_class = AuditTrailSerializer
