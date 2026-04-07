import django_tables2 as tables
from django.utils.translation import gettext_lazy as _
from netbox.tables import NetBoxTable, columns

from ..models import AssetLicense, LicenseSKU, Subscription

__all__ = (
    'LicenseSKUTable',
    'SubscriptionTable',
    'AssetLicenseTable',
    'AssetLicenseForAssetTable',
)


class LicenseSKUTable(NetBoxTable):
    sku = tables.Column(linkify=True)
    manufacturer = tables.Column(linkify=True)
    license_kind = tables.Column()
    name = tables.Column()
    description = columns.ChoiceFieldColumn(
        verbose_name=('Description'),
    )
    tags = columns.TagColumn()

    actions = columns.ActionsColumn(actions=("edit", "delete"))

    class Meta(NetBoxTable.Meta):
        model = LicenseSKU
        fields = ("pk", "id", "manufacturer", "sku", "name", "license_kind", "description", "tags", "actions")
        default_columns = ("manufacturer", "sku", "name", "license_kind")


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
    subscription = tables.Column(linkify=True)
    sku = tables.Column(linkify=True, verbose_name=_('License SKU'))
    manufacturer = tables.Column(
        accessor='sku__manufacturer',
        linkify=True,
        verbose_name=_('Manufacturer'),
        orderable=True,
    )
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
            'pk', 'id', 'asset', 'manufacturer', 'subscription', 'sku',
            'start_date', 'end_date', 'quantity', 'status', 'notes', 'tags', 'actions',
        )
        default_columns = (
            'asset', 'manufacturer', 'subscription', 'sku',
            'start_date', 'end_date', 'status',
        )


class AssetLicenseForAssetTable(NetBoxTable):
    """Compact table used on the Asset detail Licenses tab."""
    subscription = tables.Column(linkify=True)
    sku = tables.Column(linkify=True, verbose_name=_('License SKU'))
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
            'pk', 'id', 'subscription', 'sku', 'start_date', 'end_date',
            'quantity', 'status', 'notes', 'actions',
        )
        default_columns = ('subscription', 'sku', 'start_date', 'end_date', 'status')
