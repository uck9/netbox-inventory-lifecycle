# Hand-written (makemigrations disabled in this install; see 0046 for why).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_inventory', '0046_assetlicense_order_license_key_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='licensesku',
            name='is_enterprise_wide',
            field=models.BooleanField(default=False),
        ),
    ]
