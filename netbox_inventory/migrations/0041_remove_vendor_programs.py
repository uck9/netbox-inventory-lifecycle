import django.db.models.deletion
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0226_modulebay_rebuild_tree'),
        ('netbox_inventory', '0040_subscription_assetlicense'),
    ]

    operations = [
        # Drop program FK from ContractAssignment first (references VendorProgram)
        migrations.RemoveField(
            model_name='contractassignment',
            name='program',
        ),
        # Drop activated_via FK on AssetProgramCoverage (references ContractAssignment)
        # — already gone when we drop the table, but explicit removal is cleaner
        migrations.DeleteModel(
            name='AssetProgramCoverage',
        ),
        migrations.DeleteModel(
            name='VendorProgram',
        ),
    ]
