import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0226_modulebay_rebuild_tree'),
        ('netbox_inventory', '0043_asset_warranty_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='contractvendor',
            name='manufacturer',
            field=models.ForeignKey(
                blank=True,
                help_text='Hardware manufacturer this vendor is contracted through (e.g. Cisco)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='contract_vendors',
                to='dcim.manufacturer',
                verbose_name='Manufacturer',
            ),
        ),
    ]
