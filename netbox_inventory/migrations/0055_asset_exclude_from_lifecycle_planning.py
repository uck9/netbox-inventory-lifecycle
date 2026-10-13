# Hand-written (makemigrations disabled in this install; see 0046 for why).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_inventory', '0054_installedatlocation_customer_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='asset',
            name='exclude_from_lifecycle_planning',
            field=models.BooleanField(default=False),
        ),
    ]
