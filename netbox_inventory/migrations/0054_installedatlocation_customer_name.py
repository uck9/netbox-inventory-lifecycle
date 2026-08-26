# Hand-written (makemigrations disabled in this install; see 0046 for why).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_inventory', '0053_asset_warranty_type_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='installedatlocation',
            name='customer_name',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
