import django.db.models.deletion
import netbox.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0226_modulebay_rebuild_tree'),
        ('extras', '0134_owner'),
        ('netbox_inventory', '0041_remove_vendor_programs'),
    ]

    operations = [
        # ------------------------------------------------------------------
        # SmartAccount
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name='SmartAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('account_domain', models.CharField(help_text='Smart account identifier, e.g. "company.cisco.com".', max_length=200, verbose_name='Account Domain')),
                ('description', models.CharField(blank=True, max_length=200, verbose_name='Description')),
                ('comments', models.TextField(blank=True, verbose_name='Comments')),
                ('manufacturer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='smart_accounts', to='dcim.manufacturer', verbose_name='Manufacturer')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'Smart Account',
                'verbose_name_plural': 'Smart Accounts',
                'ordering': ('manufacturer', 'account_domain'),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.AddConstraint(
            model_name='smartaccount',
            constraint=models.UniqueConstraint(
                fields=('manufacturer', 'account_domain'),
                name='netbox_inventory_smartaccount_unique_manufacturer_domain',
                violation_error_message='Account domain must be unique per manufacturer.',
            ),
        ),

        # ------------------------------------------------------------------
        # VirtualAccount
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name='VirtualAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('name', models.CharField(help_text='Virtual account name within the smart account.', max_length=100, verbose_name='Name')),
                ('description', models.CharField(blank=True, max_length=200, verbose_name='Description')),
                ('comments', models.TextField(blank=True, verbose_name='Comments')),
                ('smart_account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='virtual_accounts', to='netbox_inventory.smartaccount', verbose_name='Smart Account')),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'Virtual Account',
                'verbose_name_plural': 'Virtual Accounts',
                'ordering': ('smart_account', 'name'),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.AddConstraint(
            model_name='virtualaccount',
            constraint=models.UniqueConstraint(
                fields=('smart_account', 'name'),
                name='netbox_inventory_virtualaccount_unique_smart_account_name',
                violation_error_message='Virtual account name must be unique within a smart account.',
            ),
        ),

        # ------------------------------------------------------------------
        # Subscription — new fields
        # ------------------------------------------------------------------
        migrations.AddField(
            model_name='subscription',
            name='subscription_type',
            # Default 'alc' is only used to populate existing rows; preserve_default=False
            # removes it from the model state after the migration runs.
            field=models.CharField(
                choices=[('alc', 'ALC (A La Carte)'), ('ea', 'EA (Enterprise Agreement)')],
                default='alc',
                max_length=8,
                verbose_name='Subscription Type',
                help_text='ALC = purchased pool; EA = per-device generated licenses.',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='subscription',
            name='virtual_account',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='subscriptions',
                to='netbox_inventory.virtualaccount',
                verbose_name='Virtual Account',
                help_text='Virtual account this subscription is placed into within the smart account.',
            ),
        ),
        migrations.AddField(
            model_name='subscription',
            name='quantity',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name='Purchased Quantity',
                help_text='Total license seats purchased (ALC only). Leave blank for EA.',
            ),
        ),
        migrations.AddField(
            model_name='subscription',
            name='start_date',
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name='Contract Start',
                help_text='Subscription/contract start date.',
            ),
        ),
        migrations.AddField(
            model_name='subscription',
            name='end_date',
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name='Contract End',
                help_text='Subscription/contract end date. EA: licenses inherit this date.',
            ),
        ),

        # ------------------------------------------------------------------
        # AssetLicense — license_source
        # ------------------------------------------------------------------
        migrations.AddField(
            model_name='assetlicense',
            name='license_source',
            field=models.CharField(
                blank=True,
                choices=[('auto', 'Auto (hardware shipment)'), ('manual', 'Manual (portal migration)')],
                max_length=8,
                null=True,
                verbose_name='License Source',
                help_text='EA only: how the license was generated.',
            ),
        ),
    ]
