import django_tables2 as tables
from django.utils.html import format_html

from netbox.tables import NetBoxTable, PrimaryModelTable, columns

from ..models import InstalledAtLocation

__all__ = ('InstalledAtLocationTable',)


class InstalledAtLocationTable(PrimaryModelTable):
    manufacturer = tables.Column(linkify=True)
    vendor_site_id = tables.Column(linkify=True, verbose_name='Vendor Site ID')
    sites = columns.ManyToManyColumn(linkify_item=True, verbose_name='NetBox Sites')
    full_address = tables.Column(
        accessor='full_address',
        orderable=False,
        verbose_name='Address',
    )
    asset_count = columns.LinkedCountColumn(
        viewname='plugins:netbox_inventory:asset_list',
        url_params={'installed_at_id': 'pk'},
        verbose_name='Assets',
    )
    tags = columns.TagColumn()

    class Meta(NetBoxTable.Meta):
        model = InstalledAtLocation
        fields = (
            'pk',
            'id',
            'manufacturer',
            'vendor_site_id',
            'address',
            'city',
            'state',
            'postcode',
            'country',
            'sites',
            'full_address',
            'description',
            'asset_count',
            'tags',
            'created',
            'last_updated',
            'actions',
        )
        default_columns = (
            'manufacturer',
            'vendor_site_id',
            'city',
            'country',
            'sites',
            'asset_count',
        )
