import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_inventory', '0038_asset_support_reason_asset_support_source_and_more'),
    ]

    operations = [
        # Change decision_reason from free-text CharField(100) to a structured
        # choice field. max_length reduced to 30 (all choice keys fit within this).
        # Existing free-text values will be preserved in the DB but will not match
        # any choice — they will appear blank in forms until manually corrected.
        migrations.AlterField(
            model_name='assetprogramcoverage',
            name='decision_reason',
            field=models.CharField(
                blank=True,
                null=True,
                default=None,
                choices=[
                    ('spare', 'Spare / Pool'),
                    ('lab', 'Lab Device'),
                    ('not_yet_onboarded', 'Not Yet Onboarded'),
                    ('decommission_planned', 'Decommission Planned'),
                    ('past_eos', 'Past End of Support'),
                    ('vendor_excluded', 'Vendor Excluded'),
                    ('never_supported', 'Never Supported'),
                    ('disposed', 'Disposed / Decommissioned'),
                ],
                max_length=100,
                help_text='Reason this asset is excluded or terminated from the program.',
            ),
        ),
        # Add FK from coverage → the ContractAssignment that activated it.
        # Allows direct navigation: coverage → contract → SKU → dates.
        migrations.AddField(
            model_name='assetprogramcoverage',
            name='activated_via',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='activated_coverages',
                to='netbox_inventory.contractassignment',
                help_text='The contract assignment record that activated this coverage.',
            ),
        ),
    ]
