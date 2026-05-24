import django_tables2 as tables
from django.utils.translation import gettext_lazy as _
from netbox.tables import NetBoxTable, columns

from ..models import AssetLicense, LicenseSKU, SmartAccount, Subscription, VirtualAccount

__all__ = (
    'LicenseSKUTable',
    'SmartAccountTable',
    'VirtualAccountTable',
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


class SmartAccountTable(NetBoxTable):
    account_domain = tables.Column(linkify=True, verbose_name=_('Account Domain'))
    manufacturer = tables.Column(linkify=True)
    virtual_account_count = tables.Column(
        verbose_name=_('Virtual Accounts'),
        orderable=False,
    )
    tags = columns.TagColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = SmartAccount
        fields = ('pk', 'id', 'manufacturer', 'account_domain', 'description', 'virtual_account_count', 'tags', 'actions')
        default_columns = ('manufacturer', 'account_domain', 'description', 'virtual_account_count')


class VirtualAccountTable(NetBoxTable):
    name = tables.Column(linkify=True)
    smart_account = tables.Column(linkify=True, verbose_name=_('Smart Account'))
    subscription_count = tables.Column(
        verbose_name=_('Subscriptions'),
        orderable=False,
    )
    tags = columns.TagColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = VirtualAccount
        fields = ('pk', 'id', 'smart_account', 'name', 'description', 'subscription_count', 'tags', 'actions')
        default_columns = ('smart_account', 'name', 'description', 'subscription_count')


class SubscriptionTable(NetBoxTable):
    subscription_id = tables.Column(linkify=True, verbose_name=_('Subscription ID'))
    manufacturer = tables.Column(linkify=True)
    subscription_type = tables.Column(verbose_name=_('Type'))
    virtual_account = tables.Column(linkify=True, verbose_name=_('Virtual Account'))
    order = tables.Column(linkify=True)
    quantity = tables.Column(verbose_name=_('Pool Size'))
    end_date = tables.DateColumn(verbose_name=_('Contract End'))
    license_count = tables.Column(
        verbose_name=_('Licenses'),
        orderable=False,
    )
    tags = columns.TagColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = Subscription
        fields = (
            'pk', 'id', 'subscription_id', 'subscription_type', 'description',
            'manufacturer', 'virtual_account', 'order',
            'quantity', 'start_date', 'end_date', 'license_count', 'tags', 'actions',
        )
        default_columns = (
            'subscription_id', 'subscription_type', 'manufacturer',
            'virtual_account', 'quantity', 'end_date', 'license_count',
        )


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
    license_source = tables.Column(verbose_name=_('Source'))
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
            'license_source', 'start_date', 'end_date', 'quantity', 'status', 'notes', 'tags', 'actions',
        )
        default_columns = (
            'asset', 'manufacturer', 'subscription', 'sku',
            'start_date', 'end_date', 'status',
        )


class AssetLicenseForAssetTable(NetBoxTable):
    """Compact table used on the Asset detail Licenses tab."""
    subscription = tables.Column(linkify=True)
    sku = tables.Column(linkify=True, verbose_name=_('License SKU'))
    license_source = tables.Column(verbose_name=_('Source'))
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
            'pk', 'id', 'subscription', 'sku', 'license_source',
            'start_date', 'end_date', 'quantity', 'status', 'notes', 'actions',
        )
        default_columns = ('subscription', 'sku', 'license_source', 'start_date', 'end_date', 'status')
