import django_tables2 as tables
from django.utils.translation import gettext_lazy as _
from netbox.tables import NetBoxTable, columns

from ..models import AssetSystemOfRecord

__all__ = (
    'AssetSystemOfRecordTable',
    'AssetSystemOfRecordForAssetTable',
)


STALE_TEMPLATE = """
{% if record.is_stale %}<span class="badge text-bg-warning">Stale</span>{% else %}<span class="text-muted">&mdash;</span>{% endif %}
"""


class AssetSystemOfRecordTable(NetBoxTable):
    """Read-only list of SOR records. No edit/delete: records are API-managed."""
    asset = tables.Column(linkify=True)
    system = columns.ChoiceFieldColumn()
    record_id = tables.Column(linkify=True, verbose_name=_('SOR ID'))
    validation_status = columns.ChoiceFieldColumn()
    last_validated = columns.DateColumn()
    stale = columns.TemplateColumn(
        template_code=STALE_TEMPLATE,
        verbose_name=_('Stale'),
        orderable=False,
    )
    tags = columns.TagColumn()
    actions = columns.ActionsColumn(actions=('changelog',))

    class Meta(NetBoxTable.Meta):
        model = AssetSystemOfRecord
        fields = (
            'pk', 'id', 'asset', 'system', 'record_id', 'validation_status', 'last_validated',
            'stale', 'tags', 'created', 'last_updated', 'actions',
        )
        default_columns = (
            'asset', 'system', 'record_id', 'validation_status', 'last_validated', 'stale',
        )


class AssetSystemOfRecordForAssetTable(AssetSystemOfRecordTable):
    """Asset detail 'System of Record' tab — asset column omitted."""

    class Meta(AssetSystemOfRecordTable.Meta):
        fields = (
            'pk', 'id', 'system', 'record_id', 'validation_status', 'last_validated',
            'stale', 'tags', 'created', 'last_updated', 'actions',
        )
        default_columns = (
            'system', 'record_id', 'validation_status', 'last_validated', 'stale', 'last_updated',
        )
