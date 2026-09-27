from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect, render
from django.template import Context
from django.utils.translation import gettext_lazy as _
from django.views import View

from dcim.models import Device
from netbox.views import generic
from utilities.views import ViewTab, register_model_view

from .. import filtersets, forms, models, tables

__all__ = (
    # WarrantyType
    'WarrantyTypeListView',
    'WarrantyTypeView',
    'WarrantyTypeEditView',
    'WarrantyTypeDeleteView',
    # LicenseSKU
    'LicenseSKUListView',
    'LicenseSKUView',
    'LicenseSKUEditView',
    'LicenseSKUDeleteView',
    # Subscription
    'SubscriptionListView',
    'SubscriptionView',
    'SubscriptionEditView',
    'SubscriptionDeleteView',
    'SubscriptionBulkEditView',
    'SubscriptionBulkDeleteView',
    # LicenseBundle
    'LicenseBundleListView',
    'LicenseBundleView',
    'LicenseBundleEditView',
    'LicenseBundleDeleteView',
    'LicenseBundleBulkEditView',
    'LicenseBundleBulkDeleteView',
    # AssetLicense
    'AssetLicenseListView',
    'AssetLicenseView',
    'AssetLicenseEditView',
    'AssetLicenseDeleteView',
    'AssetLicenseBulkEditView',
    'AssetLicenseBulkDeleteView',
    'AssetLicenseBulkAssignView',
    # Asset tab
    'AssetLicenseTabView',
    # Device tab
    'DeviceLicenseTabView',
)


# ---------------------------------------------------------------------------
# WarrantyType
# ---------------------------------------------------------------------------

class WarrantyTypeListView(generic.ObjectListView):
    queryset = models.WarrantyType.objects.all()
    filterset = filtersets.WarrantyTypeFilterSet
    filterset_form = forms.WarrantyTypeFilterForm
    table = tables.WarrantyTypeTable


class WarrantyTypeView(generic.ObjectView):
    queryset = models.WarrantyType.objects.all()


class WarrantyTypeEditView(generic.ObjectEditView):
    queryset = models.WarrantyType.objects.all()
    form = forms.WarrantyTypeForm


class WarrantyTypeDeleteView(generic.ObjectDeleteView):
    queryset = models.WarrantyType.objects.all()


# ---------------------------------------------------------------------------
# LicenseSKU
# ---------------------------------------------------------------------------

class LicenseSKUListView(generic.ObjectListView):
    queryset = models.LicenseSKU.objects.all()
    filterset = filtersets.LicenseSKUFilterSet
    filterset_form = forms.LicenseSKUFilterForm
    table = tables.LicenseSKUTable


class LicenseSKUView(generic.ObjectView):
    queryset = models.LicenseSKU.objects.all()


class LicenseSKUEditView(generic.ObjectEditView):
    queryset = models.LicenseSKU.objects.all()
    form = forms.LicenseSKUForm


class LicenseSKUDeleteView(generic.ObjectDeleteView):
    queryset = models.LicenseSKU.objects.all()


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

@register_model_view(models.Subscription, 'list', path='', detail=False)
class SubscriptionListView(generic.ObjectListView):
    queryset = models.Subscription.objects.prefetch_related('manufacturer', 'order').annotate(
        license_count=Count('asset_licenses', distinct=True)
    )
    filterset = filtersets.SubscriptionFilterSet
    filterset_form = forms.SubscriptionFilterForm
    table = tables.SubscriptionTable
    actions = {
        'add': {'add'},
        'export': {'view'},
        'bulk_edit': {'change'},
        'bulk_delete': {'delete'},
    }


@register_model_view(models.Subscription)
class SubscriptionView(generic.ObjectView):
    queryset = models.Subscription.objects.all()

    def get_extra_context(self, request, instance):
        licenses = (
            models.AssetLicense.objects
            .filter(subscription=instance)
            .select_related(
                'asset', 'asset__device', 'asset__module__device', 'asset__inventoryitem__device', 'sku',
            )
            .order_by('asset__name', 'sku__sku', 'start_date')
        )
        licenses_table = tables.AssetLicenseTable(licenses)
        licenses_table.configure(request)
        return {
            'licenses_table': licenses_table,
            'license_count': licenses.count(),
        }


@register_model_view(models.Subscription, 'add', detail=False)
@register_model_view(models.Subscription, 'edit')
class SubscriptionEditView(generic.ObjectEditView):
    queryset = models.Subscription.objects.all()
    form = forms.SubscriptionForm


@register_model_view(models.Subscription, 'delete')
class SubscriptionDeleteView(generic.ObjectDeleteView):
    queryset = models.Subscription.objects.all()


@register_model_view(models.Subscription, 'bulk_edit', detail=False)
class SubscriptionBulkEditView(generic.BulkEditView):
    queryset = models.Subscription.objects.all()
    filterset = filtersets.SubscriptionFilterSet
    table = tables.SubscriptionTable
    form = forms.SubscriptionBulkEditForm


@register_model_view(models.Subscription, 'bulk_delete', detail=False)
class SubscriptionBulkDeleteView(generic.BulkDeleteView):
    queryset = models.Subscription.objects.all()
    filterset = filtersets.SubscriptionFilterSet
    table = tables.SubscriptionTable


# ---------------------------------------------------------------------------
# LicenseBundle
# ---------------------------------------------------------------------------

@register_model_view(models.LicenseBundle, 'list', path='', detail=False)
class LicenseBundleListView(generic.ObjectListView):
    queryset = models.LicenseBundle.objects.select_related(
        'asset', 'sku', 'sku__manufacturer', 'order',
    ).annotate(
        license_count=Count('asset_licenses', distinct=True)
    )
    filterset = filtersets.LicenseBundleFilterSet
    filterset_form = forms.LicenseBundleFilterForm
    table = tables.LicenseBundleTable


@register_model_view(models.LicenseBundle)
class LicenseBundleView(generic.ObjectView):
    queryset = models.LicenseBundle.objects.select_related('asset', 'sku', 'sku__manufacturer', 'order')


@register_model_view(models.LicenseBundle, 'add', detail=False)
@register_model_view(models.LicenseBundle, 'edit')
class LicenseBundleEditView(generic.ObjectEditView):
    queryset = models.LicenseBundle.objects.all()
    form = forms.LicenseBundleForm


@register_model_view(models.LicenseBundle, 'delete')
class LicenseBundleDeleteView(generic.ObjectDeleteView):
    queryset = models.LicenseBundle.objects.all()


@register_model_view(models.LicenseBundle, 'bulk_edit', detail=False)
class LicenseBundleBulkEditView(generic.BulkEditView):
    queryset = models.LicenseBundle.objects.all()
    filterset = filtersets.LicenseBundleFilterSet
    table = tables.LicenseBundleTable
    form = forms.LicenseBundleBulkEditForm


@register_model_view(models.LicenseBundle, 'bulk_delete', detail=False)
class LicenseBundleBulkDeleteView(generic.BulkDeleteView):
    queryset = models.LicenseBundle.objects.all()
    filterset = filtersets.LicenseBundleFilterSet
    table = tables.LicenseBundleTable


# ---------------------------------------------------------------------------
# AssetLicense
# ---------------------------------------------------------------------------

@register_model_view(models.AssetLicense, 'list', path='', detail=False)
class AssetLicenseListView(generic.ObjectListView):
    queryset = models.AssetLicense.objects.select_related(
        'asset', 'asset__device', 'asset__module__device', 'asset__inventoryitem__device',
        'subscription', 'order', 'bundle', 'bundle__sku', 'sku', 'sku__manufacturer',
    )
    filterset = filtersets.AssetLicenseFilterSet
    filterset_form = forms.AssetLicenseFilterForm
    table = tables.AssetLicenseTable
    actions = {
        'add': {'add'},
        'export': {'view'},
        'bulk_edit': {'change'},
        'bulk_delete': {'delete'},
    }


@register_model_view(models.AssetLicense)
class AssetLicenseView(generic.ObjectView):
    queryset = models.AssetLicense.objects.select_related(
        'asset', 'subscription', 'order', 'bundle', 'bundle__sku', 'sku', 'sku__manufacturer'
    )


@register_model_view(models.AssetLicense, 'add', detail=False)
@register_model_view(models.AssetLicense, 'edit')
class AssetLicenseEditView(generic.ObjectEditView):
    queryset = models.AssetLicense.objects.all()
    form = forms.AssetLicenseForm


@register_model_view(models.AssetLicense, 'delete')
class AssetLicenseDeleteView(generic.ObjectDeleteView):
    queryset = models.AssetLicense.objects.all()


@register_model_view(models.AssetLicense, 'bulk_edit', detail=False)
class AssetLicenseBulkEditView(generic.BulkEditView):
    queryset = models.AssetLicense.objects.all()
    filterset = filtersets.AssetLicenseFilterSet
    table = tables.AssetLicenseTable
    form = forms.AssetLicenseBulkEditForm


@register_model_view(models.AssetLicense, 'bulk_delete', detail=False)
class AssetLicenseBulkDeleteView(generic.BulkDeleteView):
    queryset = models.AssetLicense.objects.all()
    filterset = filtersets.AssetLicenseFilterSet
    table = tables.AssetLicenseTable


# ---------------------------------------------------------------------------
# Bulk assign: one subscription + SKU + term dates → many assets at once
# ---------------------------------------------------------------------------

class AssetLicenseBulkAssignView(View):
    """
    Custom view to bulk-assign a license (subscription + SKU + dates) to
    multiple assets in a single operation.  One AssetLicense record is created
    per asset.  Assets that already have a conflicting record are skipped and
    reported back to the user.
    """
    template_name = 'netbox_inventory/assetlicense_bulk_assign.html'

    def get(self, request):
        form = forms.AssetLicenseBulkAssignForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = forms.AssetLicenseBulkAssignForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        subscription = form.cleaned_data['subscription']
        order = form.cleaned_data['order']
        sku = form.cleaned_data['sku']
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']
        quantity = form.cleaned_data['quantity']
        license_key = form.cleaned_data['license_key']
        asset = form.cleaned_data['assets']

        # DynamicModelChoiceField returns a single object; wrap in list.
        assets = [asset] if asset else []

        created = []
        skipped = []

        for a in assets:
            obj = models.AssetLicense(
                asset=a,
                subscription=subscription,
                order=order,
                sku=sku,
                start_date=start_date,
                end_date=end_date,
                quantity=quantity,
                license_key=license_key,
            )
            try:
                with transaction.atomic():
                    obj.full_clean()
                    obj.save()
                    created.append(a)
            except (ValidationError, Exception) as exc:
                skipped.append((a, str(exc)))

        if created:
            messages.success(
                request,
                _('Created {count} asset license record(s).').format(count=len(created)),
            )
        if skipped:
            for asset_obj, reason in skipped:
                messages.warning(
                    request,
                    _('Skipped {asset}: {reason}').format(asset=asset_obj, reason=reason),
                )

        return redirect('plugins:netbox_inventory:assetlicense_list')


# ---------------------------------------------------------------------------
# Asset detail tab: Licenses
# ---------------------------------------------------------------------------

def _license_badge(asset: models.Asset) -> int:
    """Badge shows subscription license count only."""
    return models.AssetLicense.objects.filter(asset=asset).count()


def _license_tab_visible(asset: models.Asset) -> bool:
    """Tab is visible when any license (base or subscription) exists."""
    if asset.base_license_sku_id:
        return True
    return models.AssetLicense.objects.filter(asset=asset).exists()


@register_model_view(models.Asset, name='licenses')
class AssetLicenseTabView(generic.ObjectView):
    """
    Licenses tab on the Asset detail page.
    Visible whenever the asset has a base license or subscription licenses.
    Badge shows subscription license count only.
    """
    queryset = models.Asset.objects.all()
    template_name = 'netbox_inventory/asset/licenses.html'

    tab = ViewTab(
        label='Licenses',
        badge=_license_badge,
        visible=_license_tab_visible,
        weight=510,
    )

    def get_extra_context(self, request, instance: models.Asset):
        qs = (
            models.AssetLicense.objects
            .filter(asset=instance)
            .select_related('subscription', 'order', 'bundle', 'bundle__sku', 'sku', 'sku__manufacturer')
            .order_by('sku__sku', 'start_date')
        )
        license_table = tables.AssetLicenseForAssetTable(qs)
        license_table.configure(request)
        # inc/table.html (unlike {% render_table %}) doesn't set table.context itself,
        # and ActionsColumn needs table.context['request'] to resolve the current user's
        # permissions — without it every row falls back to AnonymousUser and renders no
        # edit/delete/changelog links at all. Must be a real Context (not a plain dict) —
        # some column types call context.update(...) as a context manager.
        license_table.context = Context({'request': request})
        bundles = (
            models.LicenseBundle.objects
            .filter(asset=instance)
            .select_related('sku', 'sku__manufacturer', 'order')
            .order_by('sku__sku', 'start_date')
        )
        return {
            'licenses_table': license_table,
            'license_count': qs.count(),
            'bundles': bundles,
        }


# ---------------------------------------------------------------------------
# Device detail tab: "Inventory Info" — licenses + contracts, pulled through
# from the linked Asset
# ---------------------------------------------------------------------------

def _device_asset(device: Device):
    return models.Asset.objects.filter(device=device).first()


def _device_license_badge(device: Device) -> int:
    asset = _device_asset(device)
    if not asset:
        return 0
    return (
        models.AssetLicense.objects.filter(asset=asset).count()
        + asset.contracts.count()
    )


def _device_license_tab_visible(device: Device) -> bool:
    asset = _device_asset(device)
    if not asset:
        return False
    if asset.base_license_sku_id:
        return True
    if asset.contracts.exists():
        return True
    return models.AssetLicense.objects.filter(asset=asset).exists()


class DeviceLicenseTabView(generic.ObjectView):
    """
    "Inventory Info" tab on the core Device detail page: licenses and
    contract assignments, pulled through from the linked Asset. The
    contracts table used to live in its own right_page panel on the Device
    page (formerly AssetContractInfo/inc/contract_info.html) but moved here
    to stop that page accumulating more cards; Support Status/Reason stayed
    on the main page, in the existing Asset panel (inc/asset_info.html).
    Visible whenever the linked asset has a base license, a subscription
    license, or a contract assignment.

    Registered against dcim.Device in NetBoxInventoryConfig.ready() (see
    netbox_inventory/__init__.py) rather than via a decorator here: dcim's
    urls.py is imported before this plugin's urls.py in netbox/urls.py, so
    registering only when this module is imported would be too late for
    dcim's get_model_urls('dcim', 'device') call to pick it up.
    """
    queryset = Device.objects.all()
    template_name = 'netbox_inventory/device/licenses.html'

    tab = ViewTab(
        label='Inventory Info',
        badge=_device_license_badge,
        visible=_device_license_tab_visible,
        weight=3900,
    )

    def get_extra_context(self, request, instance: Device):
        asset = _device_asset(instance)
        if not asset:
            return {
                'asset': None,
                'licenses_table': None,
                'license_count': 0,
                'contracts': [],
                'bundles': [],
            }

        qs = (
            models.AssetLicense.objects
            .filter(asset=asset)
            .select_related('subscription', 'order', 'bundle', 'bundle__sku', 'sku', 'sku__manufacturer')
            .order_by('sku__sku', 'start_date')
        )
        license_table = tables.AssetLicenseForAssetTable(qs)
        license_table.configure(request)
        # See AssetLicenseTabView.get_extra_context for why this is needed.
        license_table.context = Context({'request': request})

        contracts = (
            asset.contracts
            .select_related('contract', 'sku')
            .order_by('contract__contract_id')
        )

        bundles = (
            models.LicenseBundle.objects
            .filter(asset=asset)
            .select_related('sku', 'sku__manufacturer', 'order')
            .order_by('sku__sku', 'start_date')
        )

        return {
            'asset': asset,
            'licenses_table': license_table,
            'license_count': qs.count(),
            'contracts': contracts,
            'bundles': bundles,
        }
