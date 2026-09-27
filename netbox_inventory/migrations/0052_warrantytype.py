# Hand-written (makemigrations disabled in this install; see 0046 for why).

import django.db.models.deletion
import netbox.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0216_latitude_longitude_validators'),
        ('extras', '0133_make_cf_minmax_decimal'),
        ('netbox_inventory', '0051_hardwarelifecycle_estimated_replacement_cost'),
    ]

    operations = [
        migrations.CreateModel(
            name='WarrantyType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('sku', models.CharField(max_length=64, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('description', models.CharField(blank=True, max_length=200)),
                ('url', models.URLField(blank=True)),
                ('manufacturer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='warranty_types', to='dcim.manufacturer')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'Warranty Type',
                'verbose_name_plural': 'Warranty Types',
                'ordering': ('manufacturer', 'sku'),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
    ]
