# Hand-written (makemigrations disabled in this install; see 0046 for why).

import django.db.models.deletion
import netbox.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_inventory', '0055_asset_exclude_from_lifecycle_planning'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssetSystemOfRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('system', models.CharField(max_length=50)),
                ('record_id', models.CharField(max_length=200)),
                ('validation_status', models.CharField(default='pending', max_length=30)),
                ('last_validated', models.DateField(blank=True, null=True)),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sor_records', to='netbox_inventory.asset')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'System of Record',
                'verbose_name_plural': 'System of Record Records',
                'ordering': ('asset', 'system'),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.AddConstraint(
            model_name='assetsystemofrecord',
            constraint=models.UniqueConstraint(fields=('asset', 'system'), name='netbox_inventory_assetsystemofrecord_unique_asset_system', violation_error_message='This asset already has a record for this system.'),
        ),
        migrations.AddConstraint(
            model_name='assetsystemofrecord',
            constraint=models.UniqueConstraint(fields=('system', 'record_id'), name='netbox_inventory_assetsystemofrecord_unique_system_record_id', violation_error_message='This SOR ID is already assigned to another asset in this system.'),
        ),
    ]
