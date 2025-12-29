import django_tables2 as tables
from django.db.models.functions import Coalesce
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
    'HardwareLifecycleTable',
)


class HardwareLifecycleTable(NetBoxTable):
    name = tables.Column(
        linkify=True,
        accessor='name',
        orderable=False,
    )
    assigned_object = tables.Column(
        linkify=True,
        verbose_name=_('Hardware'),
        orderable=False,
    )
    assigned_object_count = tables.Column(
        verbose_name=_('Assigned Object Count'),
        orderable=False,
    )

    class Meta(NetBoxTable.Meta):
        model = HardwareLifecycle
        fields = (
            'pk',
            'name',
            'assigned_object',
            'end_of_sale',
            'end_of_maintenance',
            'end_of_security',
            'end_of_support',
            'last_contract_attach',
            'last_contract_renewal',
            'description',
            'comments',
        )
        default_columns = (
            'pk',
            'name',
            'assigned_object',
            'end_of_sale',
            'end_of_maintenance',
        )
