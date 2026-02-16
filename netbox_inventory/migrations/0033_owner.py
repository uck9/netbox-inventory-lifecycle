import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0015_owner'),
        ('netbox_inventory', '0032_asset_vendor_instance_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryitemgroup',
            name='owner',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='users.owner'
            ),
        ),
    ]