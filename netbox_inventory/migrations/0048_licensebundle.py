# Hand-written (makemigrations disabled in this install; see 0046 for why).

import django.db.models.deletion
import netbox.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_inventory', '0047_licensesku_is_enterprise_wide'),
    ]

    operations = [
        migrations.CreateModel(
            name='LicenseBundle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('notes', models.CharField(blank=True, max_length=255)),
                ('comments', models.TextField(blank=True)),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='license_bundles', to='netbox_inventory.asset')),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='license_bundles', to='netbox_inventory.order')),
                ('sku', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bundles', to='netbox_inventory.licensesku')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'License Bundle',
                'verbose_name_plural': 'License Bundles',
                'ordering': ('asset', 'sku', 'start_date'),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.AddConstraint(
            model_name='licensebundle',
            constraint=models.UniqueConstraint(fields=('asset', 'sku', 'start_date'), name='netbox_inventory_licensebundle_unique_asset_sku_start', violation_error_message='A license bundle record already exists for this asset, SKU, and start date.'),
        ),
        migrations.AddField(
            model_name='assetlicense',
            name='bundle',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='asset_licenses', to='netbox_inventory.licensebundle'),
        ),
    ]
