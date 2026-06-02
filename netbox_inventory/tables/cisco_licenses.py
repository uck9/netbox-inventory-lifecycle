import django_tables2 as tables
from django.utils.translation import gettext_lazy as _
from netbox.tables import NetBoxTable, columns

from ..models import (
    CiscoSmartAccount,
    LicenseLineItemAllocation,
    LicenseOrder,
    LicenseOrderLineItem,
    VirtualAccount,
)

__all__ = (
    'CiscoSmartAccountTable',
    'VirtualAccountTable',
    'LicenseOrderTable',
    'LicenseOrderLineItemTable',
    'LicenseLineItemAllocationTable',
)


class CiscoSmartAccountTable(NetBoxTable):
    name = tables.Column(linkify=True)
    virtual_account_count = tables.Column(
        verbose_name=_('Virtual Accounts'),
        orderable=False,
    )
    tags = columns.TagColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = CiscoSmartAccount
        fields = ('pk', 'id', 'name', 'domain', 'virtual_account_count', 'tags', 'actions')
        default_columns = ('name', 'domain', 'virtual_account_count')


class VirtualAccountTable(NetBoxTable):
    name = tables.Column(linkify=True)
    smart_account = tables.Column(linkify=True)
    site = tables.Column(linkify=True)
    tenant = tables.Column(linkify=True)
    tags = columns.TagColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = VirtualAccount
        fields = ('pk', 'id', 'smart_account', 'name', 'site', 'tenant', 'tags', 'actions')
        default_columns = ('smart_account', 'name', 'site', 'tenant')


class LicenseOrderTable(NetBoxTable):
    cisco_order_number = tables.Column(linkify=True, verbose_name=_('Cisco Order'))
    source = columns.ChoiceFieldColumn()
    purchase = tables.Column(linkify=True)
    line_item_count = tables.Column(verbose_name=_('Line Items'), orderable=False)
    synced_at = tables.DateTimeColumn(verbose_name=_('Last Synced'))
    tags = columns.TagColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = LicenseOrder
        fields = (
            'pk', 'id', 'cisco_order_number', 'subscription_id', 'source',
            'purchase', 'line_item_count', 'synced_at', 'tags', 'actions',
        )
        default_columns = ('cisco_order_number', 'subscription_id', 'source', 'purchase', 'line_item_count')


class LicenseOrderLineItemTable(NetBoxTable):
    po_line_item_number = tables.Column(linkify=True, verbose_name=_('Line Item #'))
    license_order = tables.Column(linkify=True)
    license_type = columns.ChoiceFieldColumn()
    start_date = tables.DateColumn()
    end_date = tables.DateColumn()
    synced_at = tables.DateTimeColumn(verbose_name=_('Last Synced'))
    tags = columns.TagColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = LicenseOrderLineItem
        fields = (
            'pk', 'id', 'license_order', 'po_line_item_number', 'product_sku', 'product_name',
            'license_type', 'quantity_ordered', 'subscription_id',
            'start_date', 'end_date', 'synced_at', 'tags', 'actions',
        )
        default_columns = (
            'license_order', 'po_line_item_number', 'product_sku',
            'license_type', 'quantity_ordered', 'start_date', 'end_date',
        )


class LicenseLineItemAllocationTable(NetBoxTable):
    line_item = tables.Column(linkify=True)
    virtual_account = tables.Column(linkify=True)
    data_source = columns.ChoiceFieldColumn()
    synced_at = tables.DateTimeColumn(verbose_name=_('Last Synced'))
    tags = columns.TagColumn()
    actions = columns.ActionsColumn(actions=('edit', 'delete'))

    class Meta(NetBoxTable.Meta):
        model = LicenseLineItemAllocation
        fields = (
            'pk', 'id', 'line_item', 'virtual_account', 'quantity',
            'data_source', 'synced_at', 'tags', 'actions',
        )
        default_columns = ('line_item', 'virtual_account', 'quantity', 'data_source')
