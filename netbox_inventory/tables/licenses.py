import django_tables2 as tables
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from netbox.tables import NetBoxTable, columns

from ..models import AssetLicense, LicenseBundle, LicenseSKU, Subscription

__all__ = (
    'LicenseSKUColumn',
    'SubscriptionColumn',
    'BundleColumn',
    'LicenseSKUTable',
    'SubscriptionTable',
    'LicenseBundleTable',
    'AssetLicenseTable',
    'AssetLicenseForAssetTable',
)


class LicenseSKUColumn(tables.Column):
    """
    Renders a LicenseSKU FK as just the short SKU code (linked), with the
    SKU's full name as a hover tooltip rather than appended in brackets —
    keeps SKU columns compact when names run long.
    """
    def render(self, value):
        return format_html(
            '<a href="{}" title="{}">{}</a>',
            value.get_absolute_url(), value.name, value.sku,
        )


class SubscriptionColumn(tables.Column):
    """
    Renders a Subscription FK as just the subscription ID (linked), with the
    manufacturer as a hover tooltip rather than appended in brackets.
    """
    def render(self, value):
        return format_html(
            '<a href="{}" title="{}">{}</a>',
            value.get_absolute_url(), value.manufacturer, value.subscription_id,
        )


class LicenseSKUTable(NetBoxTable):
    sku = tables.Column(linkify=True)
    manufacturer = tables.Column(linkify=True)
    license_kind = tables.Column()
    name = tables.Column()
    description = columns.ChoiceFieldColumn(
        verbose_name=('Description'),
    )
    renewal_budget_per_unit = tables.Column(
        verbose_name=_('Renewal Budget (per unit)'),
    )
    is_enterprise_wide = columns.BooleanColumn(
        verbose_name=_('Enterprise-Wide'),
    )
    tags = columns.TagColumn()

    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = LicenseSKU
        fields = (
            "pk", "id", "manufacturer", "sku", "name", "license_kind", "description",
            "renewal_budget_per_unit", "is_enterprise_wide", "tags", "actions",
        )
        default_columns = ("manufacturer", "sku", "name", "license_kind", "renewal_budget_per_unit")


class BundleColumn(tables.Column):
    """
    Renders a LicenseBundle FK as its component SKU code (linked to the
    bundle record itself), with the full bundle label as a hover tooltip.
    """
    def render(self, value):
        return format_html(
            '<a href="{}" title="{}">{}</a>',
            value.get_absolute_url(), value, value.sku.sku,
        )


class SubscriptionTable(NetBoxTable):
    subscription_id = tables.Column(linkify=True, verbose_name=_('Subscription ID'))
    manufacturer = tables.Column(linkify=True)
    order = tables.Column(linkify=True)
    license_count = tables.Column(
        verbose_name=_('Licenses'),
        orderable=False,
    )
    tags = columns.TagColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = Subscription
        fields = (
            'pk', 'id', 'subscription_id', 'description',
            'order', 'license_count', 'manufacturer', 'tags', 'actions',
        )
        default_columns = ('subscription_id', 'description', 'order', 'license_count', 'manufacturer')


class LicenseBundleTable(NetBoxTable):
    asset = tables.Column(linkify=True)
    sku = LicenseSKUColumn(verbose_name=_('Bundle SKU'))
    manufacturer = tables.Column(
        accessor='sku__manufacturer',
        linkify=True,
        verbose_name=_('Manufacturer'),
        orderable=True,
    )
    order = tables.Column(linkify=True)
    start_date = columns.DateColumn()
    end_date = columns.DateColumn()
    status = tables.Column(
        accessor='status_label',
        verbose_name=_('Status'),
        orderable=False,
    )
    license_count = tables.Column(
        verbose_name=_('Feature Licenses'),
        orderable=False,
    )
    tags = columns.TagColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = LicenseBundle
        fields = (
            'pk', 'id', 'asset', 'manufacturer', 'sku', 'order', 'start_date', 'end_date',
            'quantity', 'status', 'license_count', 'notes', 'tags', 'actions',
        )
        default_columns = (
            'asset', 'manufacturer', 'sku', 'order',
            'start_date', 'end_date', 'quantity', 'status', 'license_count',
        )


class AssetLicenseTable(NetBoxTable):
    asset = tables.Column(linkify=True)
    subscription = SubscriptionColumn()
    order = tables.Column(linkify=True)
    bundle = BundleColumn()
    sku = LicenseSKUColumn(verbose_name=_('License SKU'))
    manufacturer = tables.Column(
        accessor='sku__manufacturer',
        linkify=True,
        verbose_name=_('Manufacturer'),
        orderable=True,
    )
    license_key = tables.Column(verbose_name=_('License Key'))
    start_date = columns.DateColumn()
    end_date = columns.DateColumn()
    status = tables.Column(
        accessor='status_label',
        verbose_name=_('Status'),
        orderable=False,
    )
    tags = columns.TagColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = AssetLicense
        fields = (
            'pk', 'id', 'asset', 'manufacturer', 'subscription', 'order', 'bundle', 'sku',
            'start_date', 'end_date', 'quantity', 'license_key', 'status', 'notes', 'tags', 'actions',
        )
        default_columns = (
            'asset', 'manufacturer', 'subscription', 'order', 'sku',
            'start_date', 'end_date', 'quantity', 'status',
        )


class AssetLicenseForAssetTable(NetBoxTable):
    """Compact table used on the Asset detail Licenses tab (and the Device
    'Inventory Info' tab, which reads through to the linked Asset)."""
    sku = LicenseSKUColumn(verbose_name=_('License SKU'))
    bundle = BundleColumn()
    subscription = SubscriptionColumn()
    order = tables.Column(linkify=True)
    license_key = tables.Column(verbose_name=_('License Key'))
    start_date = columns.DateColumn()
    end_date = columns.DateColumn()
    status = tables.Column(
        accessor='status_label',
        verbose_name=_('Status'),
        orderable=False,
    )
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = AssetLicense
        fields = (
            'pk', 'id', 'sku', 'bundle', 'subscription', 'order', 'start_date', 'end_date',
            'quantity', 'license_key', 'status', 'notes', 'actions',
        )
        default_columns = ('sku', 'bundle', 'subscription', 'order', 'start_date', 'end_date', 'quantity', 'status')
