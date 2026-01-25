from django.urls import include, path

from netbox.views.generic import ObjectChangeLogView
from utilities.urls import get_model_urls

from . import views
from .models import (
    AssetProgramCoverage,
    ContractAssignment,
    HardwareLifecycle,
    VendorProgram,
)

urlpatterns = [
    # InventoryItemGroups
    path('inventory-item-groups/', include(get_model_urls('netbox_inventory', 'inventoryitemgroup', detail=False))),
    path('inventory-item-groups/<int:pk>/',include(get_model_urls('netbox_inventory', 'inventoryitemgroup'))),

    # InventoryItemTypes
    path('inventory-item-types/', include(get_model_urls('netbox_inventory', 'inventoryitemtype', detail=False))),
    path('inventory-item-types/<int:pk>/', include(get_model_urls('netbox_inventory', 'inventoryitemtype'))),

    # Assets
    path('assets/', include(get_model_urls('netbox_inventory', 'asset', detail=False))),
    path('assets/<int:pk>/', include(get_model_urls('netbox_inventory', 'asset'))),
    path('assets/<int:pk>/assign/', views.AssetAssignView.as_view(), name='asset_assign'),
    path('assets/device/create/', views.AssetDeviceCreateView.as_view(), name='asset_device_create'),
    path('assets/module/create/', views.AssetModuleCreateView.as_view(), name='asset_module_create'),
    path('assets/inventory-item/create/', views.AssetInventoryItemCreateView.as_view(), name='asset_inventoryitem_create'),
    path('assets/rack/create/', views.AssetRackCreateView.as_view(),name='asset_rack_create'),
    path('assets/device/<int:pk>/reassign/', views.AssetDeviceReassignView.as_view(), name='asset_device_reassign'),
    path('assets/module/<int:pk>/reassign/', views.AssetModuleReassignView.as_view(), name='asset_module_reassign'),
    path('assets/inventoryitem/<int:pk>/reassign/', views.AssetInventoryItemReassignView.as_view(), name='asset_inventoryitem_reassign'),
    path('assets/rack/<int:pk>/reassign/', views.AssetRackReassignView.as_view(), name='asset_rack_reassign'),

    # Contracts
    path('contracts/', include(get_model_urls('netbox_inventory', 'contract', detail=False))),
    path('contracts/<int:pk>/', include(get_model_urls('netbox_inventory', 'contract'))),

    # Contract Assignments
    #path('contract-assignments/', include(get_model_urls('netbox_inventory', 'contractassignment', detail=False))),
    #path('contract-assignments/<int:pk>/', include(get_model_urls('netbox_inventory', 'contractassignment'))),
    path('contract-assignments/', views.ContractAssignmentListView.as_view(), \
        name='contractassignment_list'),
    path('contract-assignments/add', views.ContractAssignmentEditView.as_view(), \
        name='contractassignment_add'),
    path('contract-assignments/edit/', views.ContractAssignmentBulkEditView.as_view(), \
        name='contractassignment_bulk_edit'),
    path('contract-assignments/delete/', views.ContractAssignmentBulkDeleteView.as_view(), \
        name='contractassignment_bulk_delete'),
    path('contract-assignments/<int:pk>', views.ContractAssignmentView.as_view(), \
        name='contractassignment'),
    path('contract-assignments/<int:pk>/edit', views.ContractAssignmentEditView.as_view(), \
        name='contractassignment_edit'),
    path('contract-assignments/<int:pk>/delete', views.ContractAssignmentDeleteView.as_view(), \
        name='contractassignment_delete'),
    path('contract-assignment/<int:pk>/changelog', ObjectChangeLogView.as_view(), \
        name='contractassignment_changelog', kwargs={'model': ContractAssignment}),

    # Contract SKUs
    path('contract-skus/', include(get_model_urls('netbox_inventory', 'contractsku', detail=False))),
    path('contract-sku/<int:pk>/', include(get_model_urls('netbox_inventory', 'contractsku'))),

    # Contract Vendors
    path('contract-vendors/', include(get_model_urls('netbox_inventory', 'contractvendor', detail=False))),
    path('contract-vendors/<int:pk>/', include(get_model_urls('netbox_inventory', 'contractvendor'))),

    # Suppliers
    path('suppliers/', include(get_model_urls('netbox_inventory', 'supplier', detail=False))),
    path('suppliers/<int:pk>/', include(get_model_urls('netbox_inventory', 'supplier'))),

    # Purchases
    path('purchases/', include(get_model_urls('netbox_inventory', 'purchase', detail=False))),
    path('purchases/<int:pk>/',include(get_model_urls('netbox_inventory', 'purchase'))),

    # Orders
    path('orders/', include(get_model_urls('netbox_inventory', 'order', detail=False))),
    path('orders/<int:pk>/', include(get_model_urls('netbox_inventory', 'order'))),

    # Hardware Lifecycles
    path('lifecycle/', views.HardwareLifecycleListView.as_view(),
        name='hardwarelifecycle_list',
    ),
    path('lifecycle/add',views.HardwareLifecycleEditView.as_view(),
        name='hardwarelifecycle_add',
    ),
    path('lifecycle/edit', views.HardwareLifecycleBulkEditView.as_view(),
        name='hardwarelifecycle_bulk_edit',
    ),
    path('lifecycle/delete', views.HardwareLifecycleBulkDeleteView.as_view(),
        name='hardwarelifecycle_bulk_delete',
    ),
    path('lifecycle/<int:pk>', views.HardwareLifecycleView.as_view(),
        name='hardwarelifecycle',
    ),
    path('lifecycle/<int:pk>/edit', views.HardwareLifecycleEditView.as_view(),
        name='hardwarelifecycle_edit',
    ),
    path('lifecycle/<int:pk>/delete', views.HardwareLifecycleDeleteView.as_view(),
        name='hardwarelifecycle_delete',
    ),
    path('lifecycle/<int:pk>/changelog', ObjectChangeLogView.as_view(),
        name='hardwarelifecycle_changelog',
        kwargs={'model': HardwareLifecycle},
    ),

    # AuditFlows (for clarity above AuditFlowPages)
    path('audit-flows/', include(get_model_urls('netbox_inventory', 'auditflow', detail=False))),
    path('audit-flows/<int:pk>/', include(get_model_urls('netbox_inventory', 'auditflow'))),

    # AuditFlowPages
    path('audit-flowpages/', include(get_model_urls('netbox_inventory', 'auditflowpage', detail=False))),
    path('audit-flowpages/<int:pk>/', include(get_model_urls('netbox_inventory', 'auditflowpage'))),

    # AuditFlowPageAssignments
    path('audit-flowpage-assignments/', include(get_model_urls('netbox_inventory', 'auditflowpageassignment', detail=False))),
    path('audit-flowpage-assignments/<int:pk>/', include(get_model_urls('netbox_inventory', 'auditflowpageassignment'))),

    # AuditTrailSources
    path('audit-trail-sources/',include(get_model_urls('netbox_inventory', 'audittrailsource', detail=False))),
    path('audit-trail-sources/<int:pk>/', include(get_model_urls('netbox_inventory', 'audittrailsource'))),

    # AuditTrails
    path('audit-trails/', include(get_model_urls('netbox_inventory', 'audittrail', detail=False))),
    path('audit-trails/<int:pk>/', include(get_model_urls('netbox_inventory', 'audittrail'))),

    # Vendor Programs
    path("vendor-programs/", views.VendorProgramListView.as_view(), name="vendorprogram_list"),
    path("vendor-programs/add/", views.VendorProgramEditView.as_view(), name="vendorprogram_add"),
    path("vendor-programs/<int:pk>/", views.VendorProgramView.as_view(), name="vendorprogram"),
    path("vendor-programs/<int:pk>/edit/", views.VendorProgramEditView.as_view(), name="vendorprogram_edit"),
    path("vendor-programs/<int:pk>/delete/", views.VendorProgramDeleteView.as_view(), name="vendorprogram_delete"),
    path('vendor-programs/<int:pk>/changelog', ObjectChangeLogView.as_view(),
        name='vendorprogram_changelog',
        kwargs={'model': VendorProgram},
    ),

    # Asset Program Coverage
    path("asset-program-coverages/", views.AssetProgramCoverageListView.as_view(), name="assetprogramcoverage_list"),
    path("asset-program-coverages/add/", views.AssetProgramCoverageEditView.as_view(), name="assetprogramcoverage_add"),
    path("asset-program-coverages/<int:pk>/", views.AssetProgramCoverageView.as_view(), name="assetprogramcoverage"),
    path("asset-program-coverages/<int:pk>/edit/", views.AssetProgramCoverageEditView.as_view(), name="assetprogramcoverage_edit"),
    path("asset-program-coverages/<int:pk>/delete/", views.AssetProgramCoverageDeleteView.as_view(), name="assetprogramcoverage_delete"),
    path("asset-program-coverages/<int:pk>/activate/", views.AssetProgramCoverageActivateView.as_view(), name="assetprogramcoverage_activate"),
    path('asset-program-coverages/<int:pk>/changelog', ObjectChangeLogView.as_view(),
            name='assetprogramcoverage_changelog',
            kwargs={'model': AssetProgramCoverage},
        ),

    # License SKUs
    path("license-skus/", views.LicenseSKUListView.as_view(), name="licensesku_list"),
    path("license-skus/add/", views.LicenseSKUEditView.as_view(), name="licensesku_add"),
    path("license-skus/<int:pk>/", views.LicenseSKUView.as_view(), name="licensesku"),
    path("license-skus/<int:pk>/edit/", views.LicenseSKUEditView.as_view(), name="licensesku_edit"),
    path("license-skus/<int:pk>/delete/", views.LicenseSKUDeleteView.as_view(), name="licensesku_delete"),
]
