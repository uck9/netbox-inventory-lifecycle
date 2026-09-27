# Hand-written (makemigrations disabled in this install; see 0046 for why).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_inventory', '0050_do_not_renew'),
    ]

    operations = [
        migrations.AddField(
            model_name='hardwarelifecycle',
            name='estimated_replacement_cost',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
