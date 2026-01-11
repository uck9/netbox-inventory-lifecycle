import django_tables2 as tables
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from dcim.tables import (
    DeviceTypeTable,
    LocationTable,
    ModuleTypeTable,
    RackTypeTable,
)
from netbox.tables import NetBoxTable, columns, ChoiceFieldColumn
from tenancy.tables import ContactsColumnMixin
from utilities.tables import register_table_column

from ..models import *
from ..template_content import WARRANTY_PROGRESSBAR

__all__ = (
    'ContractTable',
    'ContractVendorTable',
    'ContractSKUTable',
    'ContractAssignmentTable',
)

class ContractTable(NetBoxTable):
    contract_id = tables.Column(
        linkify=True,
    )
    contract_type = tables.Column(
        linkify=True,
    )
    vendor = tables.Column(
        linkify=True,
    )
    status = columns.TemplateColumn(
        template_code='''
        {% load helpers %}
        {% if record.is_expired and record.status != 'expired' %}
            <span class="badge bg-danger" title="Contract expired on {{ record.end_date }}">
                <i class="mdi mdi-alert-circle"></i> {{ record.get_status_display }}
            </span>
        {% else %}
            {% badge record.get_status_display bg_color=record.get_status_color %}
        {% endif %}
        ''',
        verbose_name='Status',
    )
    description = columns.ChoiceFieldColumn(
        verbose_name=_('Description'),
    )
    start_date = columns.DateColumn()
    end_date = columns.DateColumn()
    renewal_date = columns.DateColumn()
    asset_count = tables.Column(
        accessor='asset_count',
        verbose_name='Assets',
        linkify=lambda record: (
            reverse('plugins:netbox_inventory:contract_assignments', kwargs={'pk': record.pk})
        ),
    )
    is_active = columns.BooleanColumn(
        accessor='is_active',
        verbose_name='Active',
    )
    days_until_expiry = columns.TemplateColumn(
        template_code='''
        {% if record.is_expired %}
            <span class="text-danger">
                <i class="mdi mdi-alert-circle"></i> Expired
            </span>
        {% elif record.days_until_expiry <= 30 %}
            <span class="text-warning">
                <i class="mdi mdi-alert"></i> {{ record.days_until_expiry }} days
            </span>
        {% elif record.days_until_expiry <= 90 %}
            <span class="text-info">
                {{ record.days_until_expiry }} days
            </span>
        {% else %}
            {{ record.days_until_expiry }} days
        {% endif %}
        ''',
        accessor='days_until_expiry',
        verbose_name='Days Until Expiry',
    )
    notes = columns.MarkdownColumn()
    tags = columns.TagColumn()

    def order_days_until_expiry(self, queryset, is_descending):
        """
        Custom ordering for days_until_expiry column.
        Orders by end_date (ascending = soonest expiry first, descending = latest expiry first)
        """
        direction = '-' if is_descending else ''
        return queryset.order_by(f'{direction}end_date'), True

    class Meta(NetBoxTable.Meta):
        model = Contract
        fields = (
            'pk',
            'id',
            'contract_id',
            'contract_type',
            'vendor',
            'status',
            'description',
            'start_date',
            'end_date',
            'renewal_date',
            'asset_count',
            'is_active',
            'days_until_expiry',
            'comments',
            'tags',
            'created',
            'last_updated',
            'actions',
        )
        default_columns = (
            'pk',
            'contract_id',
            'vendor',
            'contract_type',
            'status',
            'start_date',
            'end_date',
            'days_until_expiry',
            'asset_count',
            'is_active',
        )


class ContractVendorTable(NetBoxTable):
    name = tables.Column(
        linkify=True,
        verbose_name=_('Name')
    )

    class Meta(NetBoxTable.Meta):
        model = ContractVendor
        fields = (
            'id', 'pk', 'name',
        )
        default_columns = (
            'id', 'pk', 'name',
        )


class ContractSKUTable(NetBoxTable):
    sku = tables.Column(
        verbose_name=_('SKU'),
        linkify=True,
    )
    manufacturer = tables.Column(
        verbose_name=_('Manufacturer'),
        linkify=True,
    )

    class Meta(NetBoxTable.Meta):
        model = ContractSKU
        fields = (
            'id', 'pk', 'manufacturer', 'sku', 'description', 'comments',
        )
        default_columns = (
            'id', 'pk', 'manufacturer', 'sku',
        )


class ContractAssignmentTable(NetBoxTable):
    contract = tables.Column(
        verbose_name=_('Contract'),
        linkify=True,
    )
    sku = tables.Column(
        verbose_name=_('SKU'),
        linkify=True,
    )
    asset_name = tables.Column(
        verbose_name=_('Asset Name'),
        accessor='asset__name',
        linkify=('plugins:netbox_inventory:asset', [tables.A('asset__pk')]),
        orderable=True,
    )
    asset_serial = tables.Column(
        verbose_name=_('Serial Number'),
        accessor='asset__serial',
        orderable=True,
    )
    asset_model = tables.Column(
        verbose_name=_('Device Model'),
        accessor='asset__device_type__model',
        linkify=False,
        orderable=True,
    )
    asset_status = ChoiceFieldColumn(
        verbose_name=_('Asset Status'),
        accessor='asset__status',
        orderable=True,
    )
    renewal = tables.Column(
        verbose_name=_('Renewal Date'),
        accessor='contract__renewal_date',
    )
    end = tables.Column(
        verbose_name=_('End Date'),
        accessor='end_date',
        orderable=False,
    )
    tags = columns.TagColumn()

    class Meta(NetBoxTable.Meta):
        model = ContractAssignment
        fields = (
            'id', 'pk', 'contract', 'sku', 'asset_name', 'license_name', 'asset_model', 'asset_serial',
            'renewal_date', 'end_date', 'tags', 'description', 'comments',
        )
        default_columns = (
            'id', 'pk', 'contract', 'sku', 'asset_name', 'asset_model', 'asset_serial', 'end_date', 'tags'
        )