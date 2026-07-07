# Hand-written (makemigrations disabled in this install; see 0046 for why).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_inventory', '0048_licensebundle'),
    ]

    operations = [
        migrations.AddField(
            model_name='asset',
            name='planned_decommission_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
