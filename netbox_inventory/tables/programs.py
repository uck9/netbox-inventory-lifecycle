import django_tables2 as tables

from netbox.tables import ChoiceFieldColumn, NetBoxTable, columns

from ..choices import ProgramCoverageStatusChoices
from ..models.programs import AssetProgramCoverage, VendorProgram

_all__ = (
    'VendorProgramTable',
    'AssetProgramCoverageTable',
    'AssetProgramCoverageForAssetTable',
)

class VendorProgramTable(NetBoxTable):
    name = tables.Column(linkify=True)
    manufacturer = tables.Column(linkify=True)
    slug = tables.Column()
    description = tables.Column()
    tags = columns.TagColumn(url_name="plugins:netbox_inventory:vendorprogram_list")

    class Meta(NetBoxTable.Meta):
        model = VendorProgram
        fields = ("pk", "id", "name", "manufacturer", "slug", "description", "tags")


class AssetProgramCoverageTable(NetBoxTable):
    asset = tables.Column(linkify=True)
    program = tables.Column(linkify=True)
    status = ChoiceFieldColumn()
    eligibility = ChoiceFieldColumn()
    effective_start = tables.Column()
    effective_end = tables.Column()
    decision_reason = tables.Column()
    source = ChoiceFieldColumn()
    last_synced = tables.DateTimeColumn()
    tags = columns.TagColumn(url_name="plugins:netbox_inventory:assetprogramcoverage_list")
    actions = columns.ActionsColumn(actions=("edit", "delete"))

    activate = tables.TemplateColumn(
        template_code="""
        {% if record.program and record.program.contract_type == 'support-ea' and record.status == 'planned' and record.eligibility != 'ineligible' %}
          <a class="btn btn-sm btn-primary"
             href="{% url 'plugins:netbox_inventory:assetprogramcoverage_activate' record.pk %}">
            Activate
          </a>
        {% endif %}
        """,
        verbose_name="",
        orderable=False,
    )

    class Meta(NetBoxTable.Meta):
        model = AssetProgramCoverage
        fields = (
            "pk",
            "id",
            "asset",
            "program",
            "status",
            "eligibility",
            "effective_start",
            "effective_end",
            "decision_reason",
            "source",
            "last_synced",
            "tags",
            'actions',
            'activate',
        )

    def get_actions(self, record):
        actions = ['edit', 'delete']

        if record.status == ProgramCoverageStatusChoices.PLANNED:
            actions.append('activate')

        return actions


class AssetProgramCoverageForAssetTable(AssetProgramCoverageTable):
    """A slimmer coverage table for rendering on an Asset detail tab."""
    class Meta(AssetProgramCoverageTable.Meta):
        fields = (
            "pk",
            "id",
            "program",
            "status",
            "eligibility",
            "effective_start",
            "effective_end",
            "decision_reason",
            "source",
            "last_synced",
            "tags",
        )
