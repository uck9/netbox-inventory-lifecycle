import django_tables2 as tables
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from netbox.tables import NetBoxTable, columns

from ..models import AssetLicense, LicenseSKU, Subscription

__all__ = (
    'LicenseSKUColumn',
    'SubscriptionColumn',
    'LicenseSKUTable',
    'SubscriptionTable',
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
    tags = columns.TagColumn()

    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = LicenseSKU
        fields = (
            "pk", "id", "manufacturer", "sku", "name", "license_kind", "description",
            "renewal_budget_per_unit", "tags", "actions",
        )
        default_columns = ("manufacturer", "sku", "name", "license_kind", "renewal_budget_per_unit")


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


class AssetLicenseTable(NetBoxTable):
    asset = tables.Column(linkify=True)
    subscription = SubscriptionColumn()
    order = tables.Column(linkify=True)
    sku = LicenseSKUColumn(verbose_name=_('License SKU'))
    manufacturer = tables.Column(
        accessor='sku__manufacturer',
        linkify=True,
        verbose_name=_('Manufacturer'),
        orderable=True,
    )
    license_key = tables.Column(verbose_name=_('License Key'))
    start_date = tables.DateColumn()
    end_date = tables.DateColumn()
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
            'pk', 'id', 'asset', 'manufacturer', 'subscription', 'order', 'sku',
            'start_date', 'end_date', 'quantity', 'license_key', 'status', 'notes', 'tags', 'actions',
        )
        default_columns = (
            'asset', 'manufacturer', 'subscription', 'order', 'sku',
            'start_date', 'end_date', 'quantity', 'status',
        )


class AssetLicenseForAssetTable(NetBoxTable):
    """Compact table used on the Asset detail Licenses tab."""
    subscription = SubscriptionColumn()
    order = tables.Column(linkify=True)
    sku = LicenseSKUColumn(verbose_name=_('License SKU'))
    license_key = tables.Column(verbose_name=_('License Key'))
    start_date = tables.DateColumn()
    end_date = tables.DateColumn()
    status = tables.Column(
        accessor='status_label',
        verbose_name=_('Status'),
        orderable=False,
    )
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = AssetLicense
        fields = (
            'pk', 'id', 'subscription', 'order', 'sku', 'start_date', 'end_date',
            'quantity', 'license_key', 'status', 'notes', 'actions',
        )
        default_columns = ('subscription', 'order', 'sku', 'start_date', 'end_date', 'quantity', 'status')
