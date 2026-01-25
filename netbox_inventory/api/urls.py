from netbox.api.routers import NetBoxRouter

from . import views

app_name = 'netbox_inventory'

router = NetBoxRouter()
router.APIRootView = views.NetboxInventoryRootView

# Assets
router.register('assets', views.AssetViewSet)
router.register('inventory-item-types', views.InventoryItemTypeViewSet)
router.register('inventory-item-groups', views.InventoryItemGroupViewSet)
router.register('dcim/devices', views.DeviceAssetViewSet)
router.register('dcim/modules', views.ModuleAssetViewSet)
router.register('dcim/inventory-items', views.InventoryItemAssetViewSet)


# HardwareLifecycle
router.register('hardwarelifecycle', views.HardwareLifecycleViewSet)

# Contracts
router.register('contracts', views.ContractViewSet)
router.register('contract-assignments', views.ContractAssignmentViewSet)
router.register('contract-vendors', views.ContractVendorViewSet)
router.register('contract-skus', views.ContractSKUViewSet)


# Orders
router.register('suppliers', views.SupplierViewSet)
router.register('purchases', views.PurchaseViewSet)
router.register('orders', views.OrderViewSet)


# Audit
router.register('audit-flows', views.AuditFlowViewSet)
router.register('audit-flowpages', views.AuditFlowPageViewSet)
router.register('audit-flowpage-assignments', views.AuditFlowPageAssignmentViewSet)
router.register('audit-trail-sources', views.AuditTrailSourceViewSet)
router.register('audit-trails', views.AuditTrailViewSet)

# Programs
router.register('vendor-programs', views.VendorProgramViewSet)
router.register('asset-program-coverages', views.AssetProgramCoverageViewSet)

router.register("license-skus", views.LicenseSKUViewSet)

urlpatterns = router.urls
