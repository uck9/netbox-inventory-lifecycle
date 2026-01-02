import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from ..models import LicenseSKU

__all__ = (
    'LicenseSKUTable',
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
