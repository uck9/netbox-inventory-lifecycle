import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable, columns
from tenancy.tables import ContactsColumnMixin

from ..models import *

__all__ = (
    'SupplierTable',
    'PurchaseTable',
    'OrderTable',
)


class SupplierTable(ContactsColumnMixin, NetBoxTable):
    name = tables.Column(
        linkify=True,
    )
    purchase_count = columns.LinkedCountColumn(
        viewname='plugins:netbox_inventory:purchase_list',
        url_params={'supplier_id': 'pk'},
        verbose_name='Purchases',
    )
    order_count = columns.LinkedCountColumn(
        viewname='plugins:netbox_inventory:order_list',
        url_params={'supplier_id': 'pk'},
        verbose_name='Orders',
    )
    asset_count = columns.LinkedCountColumn(
        viewname='plugins:netbox_inventory:asset_list',
        url_params={'supplier_id': 'pk'},
        verbose_name='Assets',
    )
    comments = columns.MarkdownColumn()
    tags = columns.TagColumn()

    class Meta(NetBoxTable.Meta):
        model = Supplier
        fields = (
            'pk',
            'id',
            'name',
            'slug',
            'description',
            'comments',
            'contacts',
            'purchase_count',
            'order_count',
            'asset_count',
            'tags',
            'created',
            'last_updated',
            'actions',
        )
        default_columns = (
            'name',
            'asset_count',
        )


class PurchaseTable(NetBoxTable):
    supplier = tables.Column(
        linkify=True,
    )
    name = tables.Column(
        linkify=True,
    )
    status = columns.ChoiceFieldColumn()
    order_count = columns.LinkedCountColumn(
        viewname='plugins:netbox_inventory:order_list',
        url_params={'purchase_id': 'pk'},
        verbose_name='Orders',
    )
    asset_count = columns.LinkedCountColumn(
        viewname='plugins:netbox_inventory:asset_list',
        url_params={'purchase_id': 'pk'},
        verbose_name='Assets',
    )
    comments = columns.MarkdownColumn()
    tags = columns.TagColumn()

    class Meta(NetBoxTable.Meta):
        model = Purchase
        fields = (
            'pk',
            'id',
            'name',
            'supplier',
            'status',
            'date',
            'description',
            'comments',
            'order_count',
            'asset_count',
            'tags',
            'created',
            'last_updated',
            'actions',
        )
        default_columns = (
            'name',
            'supplier',
            'date',
            'asset_count',
        )


class OrderTable(NetBoxTable):
    supplier = tables.Column(
        accessor=columns.Accessor('purchase__supplier'),
        linkify=True,
    )
    purchase = tables.Column(
        linkify=True,
    )
    purchase_date = columns.DateColumn(
        accessor=columns.Accessor('purchase__date'),
        verbose_name='Purchase Date',
    )
    manufacturer = tables.Column(
        linkify=True,
    )
    name = tables.Column(
        linkify=True,
        verbose_name='Vendor ID',
    )
    asset_count = columns.LinkedCountColumn(
        viewname='plugins:netbox_inventory:asset_list',
        url_params={'order_id': 'pk'},
        verbose_name='Assets',
    )
    comments = columns.MarkdownColumn()
    tags = columns.TagColumn()

    class Meta(NetBoxTable.Meta):
        model = Order
        fields = (
            'pk',
            'id',
            'name',
            'purchase',
            'supplier',
            'purchase_date',
            'description',
            'comments',
            'asset_count',
            'tags',
            'created',
            'last_updated',
            'actions',
        )
        default_columns = (
            'name',
            'purchase',
            'date',
            'asset_count',
        )
