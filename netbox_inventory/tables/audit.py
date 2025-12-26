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
    'AuditFlowPageAssignmentTable',
    'AuditFlowPageTable',
    'AuditFlowTable',
    'AuditTrailTable',
    'AuditTrailSourceTable',
)

class BaseFlowTable(NetBoxTable):
    """
    Internal base table class for audit flow models.
    """

    name = tables.Column(
        linkify=True,
    )
    object_type = columns.ContentTypeColumn(
        verbose_name=_('Object Type'),
    )

    class Meta(NetBoxTable.Meta):
        fields = (
            'pk',
            'id',
            'name',
            'description',
            'object_type',
            'object_filter',
            'comments',
            'actions',
        )
        default_columns = (
            'name',
            'object_type',
        )


class AuditFlowPageTable(BaseFlowTable):
    class Meta(BaseFlowTable.Meta):
        model = AuditFlowPage


class AuditFlowTable(BaseFlowTable):
    enabled = columns.BooleanColumn()

    class Meta(BaseFlowTable.Meta):
        model = AuditFlow
        fields = BaseFlowTable.Meta.fields + ('enabled',)
        default_columns = BaseFlowTable.Meta.default_columns + ('enabled',)


class AuditFlowPageAssignmentTable(NetBoxTable):
    flow = tables.Column(
        linkify=True,
    )
    page = tables.Column(
        linkify=True,
    )

    actions = columns.ActionsColumn(
        actions=(
            'edit',
            'delete',
        ),
    )

    class Meta(NetBoxTable.Meta):
        model = AuditFlowPageAssignment
        fields = (
            'pk',
            'id',
            'flow',
            'page',
            'weight',
            'actions',
        )
        default_columns = (
            'flow',
            'page',
            'weight',
        )


class AuditTrailSourceTable(NetBoxTable):
    name = tables.Column(
        linkify=True,
    )

    class Meta(NetBoxTable.Meta):
        model = AuditTrailSource
        fields = (
            'pk',
            'id',
            'name',
            'description',
            'comments',
            'actions',
        )
        default_columns = ('name',)


class AuditTrailTable(NetBoxTable):
    object_type = columns.ContentTypeColumn(
        verbose_name=_('Object Type'),
    )
    object = tables.Column(
        verbose_name=_('Object'),
        linkify=True,
        orderable=False,
    )
    source = tables.Column(
        linkify=True,
    )
    created = columns.DateTimeColumn(
        verbose_name=_('Time'),
        timespec='minutes',
    )
    actions = columns.ActionsColumn(
        actions=('delete',),
    )

    # Access the audit user via the first associated object change.
    auditor_user = tables.Column(
        accessor=tables.A('object_changes__first__user_name'),
        verbose_name=_('Auditor Username'),
        orderable=False,
    )
    auditor_full_name = tables.Column(
        accessor=tables.A('object_changes__first__user__get_full_name'),
        verbose_name=_('Auditor Full Name'),
        linkify=True,
        orderable=False,
    )

    class Meta(NetBoxTable.Meta):
        model = AuditTrail
        fields = (
            'pk',
            'id',
            'object_type',
            'object',
            'auditor_user',
            'auditor_full_name',
            'source',
            'created',
            'last_changed',
            'actions',
        )
        default_columns = (
            'pk',
            'created',
            'object_type',
            'object',
            'auditor_user',
            'auditor_full_name',
            'source',
        )


# ========================
# DCIM model table columns
# ========================

asset_count = columns.LinkedCountColumn(
    viewname='plugins:netbox_inventory:asset_list',
    url_params={'device_type_id': 'pk'},
    verbose_name=_('Assets'),
    accessor='assets__count',
)

register_table_column(asset_count, 'assets', DeviceTypeTable)


asset_count = columns.LinkedCountColumn(
    viewname='plugins:netbox_inventory:asset_list',
    url_params={'module_type_id': 'pk'},
    verbose_name=_('Assets'),
    accessor='assets__count',
)

register_table_column(asset_count, 'assets', ModuleTypeTable)


asset_count = columns.LinkedCountColumn(
    viewname='plugins:netbox_inventory:asset_list',
    url_params={'rack_type_id': 'pk'},
    verbose_name=_('Assets'),
    accessor='assets__count',
)

register_table_column(asset_count, 'assets', RackTypeTable)


asset_count = columns.LinkedCountColumn(
    viewname='plugins:netbox_inventory:asset_list',
    url_params={'storage_location_id': 'pk'},
    verbose_name=_('Assets'),
    # accessor='assets__count',
    accessor=tables.A('assets__count_with_children'),
)

register_table_column(asset_count, 'assets', LocationTable)
