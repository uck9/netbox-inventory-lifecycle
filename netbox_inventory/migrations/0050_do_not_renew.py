# Hand-written (makemigrations disabled in this install; see 0046 for why).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_inventory', '0049_asset_planned_decommission_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='assetlicense',
            name='do_not_renew',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='licensebundle',
            name='do_not_renew',
            field=models.BooleanField(default=False),
        ),
    ]
