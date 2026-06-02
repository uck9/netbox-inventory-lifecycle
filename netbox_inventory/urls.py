from django.urls import include, path

from netbox.views.generic import ObjectChangeLogView
from utilities.urls import get_model_urls

from . import views
from .models import (
    AssetLicense,
    ContractAssignment,
    HardwareLifecycle,
    Subscription,
)
from .views.jobs import run_cisco_eox_sync

urlpatterns = [
    # InventoryItemGroups - To be deperecated
    path('inventory-item-groups/', include(get_model_urls('netbox_inventory', 'inventoryitemgroup', detail=False))),
    path('inventory-item-groups/<int:pk>/',include(get_model_urls('netbox_inventory', 'inventoryitemgroup'))),

    # InventoryItemTypes - To be deperecated
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

    # Installed-At Locations
    path('installed-at-locations/', include(get_model_urls('netbox_inventory', 'installedatlocation', detail=False))),
    path('installed-at-locations/<int:pk>/', include(get_model_urls('netbox_inventory', 'installedatlocation'))),

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

    # License SKUs
    path("license-skus/", views.LicenseSKUListView.as_view(), name="licensesku_list"),
    path("license-skus/add/", views.LicenseSKUEditView.as_view(), name="licensesku_add"),
    path("license-skus/<int:pk>/", views.LicenseSKUView.as_view(), name="licensesku"),
    path("license-skus/<int:pk>/edit/", views.LicenseSKUEditView.as_view(), name="licensesku_edit"),
    path("license-skus/<int:pk>/delete/", views.LicenseSKUDeleteView.as_view(), name="licensesku_delete"),

    # Subscriptions
    path("subscriptions/", include(get_model_urls('netbox_inventory', 'subscription', detail=False))),
    path("subscriptions/<int:pk>/", include(get_model_urls('netbox_inventory', 'subscription'))),

    # Asset Licenses
    path("asset-licenses/", include(get_model_urls('netbox_inventory', 'assetlicense', detail=False))),
    path("asset-licenses/<int:pk>/", include(get_model_urls('netbox_inventory', 'assetlicense'))),
    path("asset-licenses/bulk-assign/", views.AssetLicenseBulkAssignView.as_view(), name="assetlicense_bulk_assign"),
    path("asset-licenses/<int:pk>/changelog/", ObjectChangeLogView.as_view(),
        name="assetlicense_changelog",
        kwargs={"model": AssetLicense},
    ),
    path("subscriptions/<int:pk>/changelog/", ObjectChangeLogView.as_view(),
        name="subscription_changelog",
        kwargs={"model": Subscription},
    ),

    #EoX Button
    path("jobs/run-cisco-eox-sync/", run_cisco_eox_sync, name="run_cisco_eox_sync"),

    # Cisco Smart Accounts
    path('cisco-smart-accounts/', include(get_model_urls('netbox_inventory', 'ciscosmartaccount', detail=False))),
    path('cisco-smart-accounts/<int:pk>/', include(get_model_urls('netbox_inventory', 'ciscosmartaccount'))),

    # Virtual Accounts
    path('virtual-accounts/', include(get_model_urls('netbox_inventory', 'virtualaccount', detail=False))),
    path('virtual-accounts/<int:pk>/', include(get_model_urls('netbox_inventory', 'virtualaccount'))),

    # License Orders
    path('license-orders/', include(get_model_urls('netbox_inventory', 'licenseorder', detail=False))),
    path('license-orders/<int:pk>/', include(get_model_urls('netbox_inventory', 'licenseorder'))),

    # License Order Line Items
    path('license-order-line-items/', include(get_model_urls('netbox_inventory', 'licenseorderlineitem', detail=False))),
    path('license-order-line-items/<int:pk>/', include(get_model_urls('netbox_inventory', 'licenseorderlineitem'))),

    # License Line Item Allocations
    path('license-line-item-allocations/', include(get_model_urls('netbox_inventory', 'licenselineitemallocation', detail=False))),
    path('license-line-item-allocations/<int:pk>/', include(get_model_urls('netbox_inventory', 'licenselineitemallocation'))),
]
