import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0226_modulebay_rebuild_tree'),
        ('netbox_inventory', '0041_remove_vendor_programs'),
        ('users', '0015_owner'),
    ]

    operations = [
        migrations.CreateModel(
            name='InstalledAtLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('description', models.CharField(blank=True, max_length=200)),
                ('comments', models.TextField(blank=True)),
                ('vendor_site_id', models.CharField(max_length=100, verbose_name='Vendor Site ID')),
                ('address', models.CharField(max_length=200, verbose_name='Street Address')),
                ('city', models.CharField(max_length=100)),
                ('state', models.CharField(blank=True, max_length=100, verbose_name='State / Region')),
                ('country', models.CharField(max_length=100)),
                ('postcode', models.CharField(blank=True, max_length=20, verbose_name='Postcode / ZIP')),
                ('manufacturer', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='installed_at_locations',
                    to='dcim.manufacturer',
                    verbose_name='Manufacturer',
                )),
                ('owner', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    to='users.owner',
                )),
            ],
            options={
                'verbose_name': 'Installed-At Location',
                'verbose_name_plural': 'Installed-At Locations',
                'ordering': ('manufacturer', 'vendor_site_id'),
            },
        ),
        migrations.AddField(
            model_name='installedatlocation',
            name='sites',
            field=models.ManyToManyField(
                blank=True,
                related_name='installed_at_locations',
                to='dcim.site',
            ),
        ),
        migrations.AddConstraint(
            model_name='installedatlocation',
            constraint=models.UniqueConstraint(
                fields=('manufacturer', 'vendor_site_id'),
                name='netbox_inventory_installedatlocation_unique_manufacturer_vendor_site_id',
                violation_error_message='An installed-at location with this vendor site ID already exists for this manufacturer.',
            ),
        ),
        migrations.AddField(
            model_name='asset',
            name='installed_at',
            field=models.ForeignKey(
                blank=True,
                help_text='Vendor-recorded physical location where this asset is installed',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assets',
                to='netbox_inventory.installedatlocation',
                verbose_name='Installed-At Location',
            ),
        ),
    ]
