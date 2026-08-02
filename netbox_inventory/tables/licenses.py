import django_tables2 as tables
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from netbox.tables import NetBoxTable, columns

from ..models import AssetLicense, LicenseBundle, LicenseSKU, Subscription, WarrantyType

__all__ = (
    'LicenseSKUColumn',
    'SubscriptionColumn',
    'BundleColumn',
    'WarrantyTypeColumn',
    'WarrantyTypeTable',
    'LicenseSKUTable',
    'SubscriptionTable',
    'LicenseBundleTable',
    'AssetLicenseTable',
    'AssetLicenseForAssetTable',
)


class LicenseSKUColumn(tables.Column):
    """
    Renders a LicenseSKU FK as just the short SKU code (linked). By default
    the SKU's full name is shown as a hover tooltip rather than appended in
    brackets — keeps SKU columns compact when names run long. Pass
    show_name_tooltip=False for tables that already show the name as its
    own column, to avoid the redundant title attribute.
    """
    def __init__(self, *args, show_name_tooltip=True, **kwargs):
        self.show_name_tooltip = show_name_tooltip
        super().__init__(*args, **kwargs)

    def render(self, value):
        if self.show_name_tooltip:
            return format_html(
                '<a href="{}" title="{}">{}</a>',
                value.get_absolute_url(), value.name, value.sku,
            )
        return format_html(
            '<a href="{}">{}</a>',
            value.get_absolute_url(), value.sku,
        )

    def value(self, value):
        return value.sku


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

    def value(self, value):
        return value.subscription_id


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


class WarrantyTypeColumn(tables.Column):
    """
    Renders a WarrantyType FK as just the SKU code (linked), with the
    warranty type's name as a hover tooltip.
    """
    def render(self, value):
        return format_html(
            '<a href="{}" title="{}">{}</a>',
            value.get_absolute_url(), value.name, value.sku,
        )

    def value(self, value):
        return value.sku


class WarrantyTypeTable(NetBoxTable):
    sku = tables.Column(linkify=True)
    manufacturer = tables.Column(linkify=True)
    name = tables.Column()
    description = tables.Column()
    url = tables.URLColumn()
    tags = columns.TagColumn()

    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = WarrantyType
        fields = (
            "pk", "id", "manufacturer", "sku", "name", "description", "url", "tags", "actions",
        )
        default_columns = ("manufacturer", "sku", "name", "description")


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

    def value(self, value):
        return value.sku.sku


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
    do_not_renew = columns.BooleanColumn(
        verbose_name=_('Do Not Renew'),
    )
    tags = columns.TagColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = LicenseBundle
        fields = (
            'pk', 'id', 'asset', 'manufacturer', 'sku', 'order', 'start_date', 'end_date',
            'quantity', 'status', 'license_count', 'do_not_renew', 'notes', 'tags', 'actions',
        )
        default_columns = (
            'asset', 'manufacturer', 'sku', 'order',
            'start_date', 'end_date', 'quantity', 'status', 'license_count', 'do_not_renew',
        )


class AssetLicenseTable(NetBoxTable):
    asset = tables.Column(linkify=True)
    device = tables.Column(
        accessor='asset__installed_device',
        linkify=True,
        verbose_name=_('Device'),
        orderable=False,
    )
    subscription = SubscriptionColumn()
    order = tables.Column(linkify=True)
    bundle = BundleColumn()
    sku = LicenseSKUColumn(verbose_name=_('License SKU'), show_name_tooltip=False)
    license_name = tables.Column(
        accessor='sku__name',
        verbose_name=_('License Name'),
        orderable=True,
    )
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
    do_not_renew = columns.BooleanColumn(
        verbose_name=_('Do Not Renew'),
    )
    tags = columns.TagColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = AssetLicense
        fields = (
            'pk', 'id', 'asset', 'device', 'manufacturer', 'subscription', 'order', 'bundle', 'sku', 'license_name',
            'start_date', 'end_date', 'quantity', 'license_key', 'status', 'do_not_renew', 'notes', 'tags', 'actions',
        )
        default_columns = (
            'asset', 'device', 'manufacturer', 'subscription', 'order', 'sku', 'license_name',
            'start_date', 'end_date', 'quantity', 'status', 'do_not_renew',
        )


class AssetLicenseForAssetTable(NetBoxTable):
    """Compact table used on the Asset detail Licenses tab (and the Device
    'Inventory Info' tab, which reads through to the linked Asset)."""
    sku = LicenseSKUColumn(verbose_name=_('License SKU'), show_name_tooltip=False)
    license_name = tables.Column(
        accessor='sku__name',
        verbose_name=_('License Name'),
        orderable=True,
    )
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
    do_not_renew = columns.BooleanColumn(
        verbose_name=_('Do Not Renew'),
    )
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = AssetLicense
        fields = (
            'pk', 'id', 'sku', 'license_name', 'bundle', 'subscription', 'order', 'start_date', 'end_date',
            'quantity', 'license_key', 'status', 'do_not_renew', 'notes', 'actions',
        )
        default_columns = (
            'sku', 'license_name', 'bundle', 'subscription', 'order',
            'start_date', 'end_date', 'quantity', 'status', 'do_not_renew',
        )
