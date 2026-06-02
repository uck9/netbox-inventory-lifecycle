import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dcim', '0226_modulebay_rebuild_tree'),
        ('netbox_inventory', '0042_installedatlocation'),
        ('tenancy', '0023_add_mptt_tree_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='CiscoSmartAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('comments', models.TextField(blank=True, verbose_name='Comments')),
                ('name', models.CharField(
                    max_length=200,
                    verbose_name='Name',
                    help_text='e.g. WOODSIDE ENERGY LTD',
                )),
                ('domain', models.CharField(
                    max_length=200,
                    unique=True,
                    verbose_name='Domain',
                    help_text='e.g. woodside.com',
                )),
            ],
            options={
                'verbose_name': 'Cisco Smart Account',
                'verbose_name_plural': 'Cisco Smart Accounts',
                'ordering': ('name',),
            },
        ),
        migrations.CreateModel(
            name='VirtualAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('comments', models.TextField(blank=True, verbose_name='Comments')),
                ('name', models.CharField(
                    max_length=200,
                    verbose_name='Name',
                    help_text='e.g. AusOps - IT - MB2',
                )),
                ('va_token', models.CharField(
                    blank=True,
                    max_length=500,
                    verbose_name='Registration Token',
                )),
                ('va_token_expiry', models.DateTimeField(
                    blank=True,
                    null=True,
                    verbose_name='Token Expiry',
                )),
                ('smart_account', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='virtual_accounts',
                    to='netbox_inventory.ciscosmartaccount',
                    verbose_name='Smart Account',
                )),
                ('site', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='virtual_accounts',
                    to='dcim.site',
                    verbose_name='Site',
                )),
                ('tenant', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='virtual_accounts',
                    to='tenancy.tenant',
                    verbose_name='Tenant',
                )),
            ],
            options={
                'verbose_name': 'Virtual Account',
                'verbose_name_plural': 'Virtual Accounts',
                'ordering': ('smart_account', 'name'),
            },
        ),
        migrations.AddConstraint(
            model_name='virtualaccount',
            constraint=models.UniqueConstraint(
                fields=('smart_account', 'name'),
                name='netbox_inventory_virtualaccount_unique_smart_account_name',
                violation_error_message='Virtual Account name must be unique within a Smart Account.',
            ),
        ),
        migrations.CreateModel(
            name='LicenseOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('comments', models.TextField(blank=True, verbose_name='Comments')),
                ('cisco_order_number', models.CharField(
                    blank=True,
                    max_length=100,
                    verbose_name='Cisco Order Number',
                )),
                ('subscription_id', models.CharField(
                    blank=True,
                    max_length=128,
                    verbose_name='Subscription ID',
                )),
                ('source', models.CharField(
                    default='standard',
                    max_length=20,
                    verbose_name='Source',
                )),
                ('notes', models.TextField(blank=True, verbose_name='Notes')),
                ('synced_at', models.DateTimeField(
                    blank=True,
                    null=True,
                    verbose_name='Last Synced',
                )),
                ('purchase', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='license_orders',
                    to='netbox_inventory.purchase',
                    verbose_name='Purchase',
                )),
            ],
            options={
                'verbose_name': 'License Order',
                'verbose_name_plural': 'License Orders',
                'ordering': ('cisco_order_number', 'subscription_id'),
            },
        ),
        migrations.CreateModel(
            name='LicenseOrderLineItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('comments', models.TextField(blank=True, verbose_name='Comments')),
                ('po_line_item_number', models.CharField(
                    max_length=100,
                    verbose_name='PO Line Item Number',
                )),
                ('product_sku', models.CharField(
                    max_length=100,
                    verbose_name='Product SKU',
                )),
                ('product_name', models.CharField(
                    max_length=200,
                    verbose_name='Product Name',
                )),
                ('license_type', models.CharField(
                    default='term',
                    max_length=20,
                    verbose_name='License Type',
                )),
                ('quantity_ordered', models.PositiveIntegerField(
                    verbose_name='Quantity Ordered',
                )),
                ('subscription_id', models.CharField(
                    blank=True,
                    max_length=128,
                    verbose_name='Subscription ID',
                )),
                ('start_date', models.DateField(
                    blank=True,
                    null=True,
                    verbose_name='Start Date',
                )),
                ('end_date', models.DateField(
                    blank=True,
                    null=True,
                    verbose_name='End Date',
                )),
                ('synced_at', models.DateTimeField(
                    blank=True,
                    null=True,
                    verbose_name='Last Synced',
                )),
                ('license_order', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='line_items',
                    to='netbox_inventory.licenseorder',
                    verbose_name='License Order',
                )),
            ],
            options={
                'verbose_name': 'License Order Line Item',
                'verbose_name_plural': 'License Order Line Items',
                'ordering': ('license_order', 'po_line_item_number'),
            },
        ),
        migrations.AddConstraint(
            model_name='licenseorderlineitem',
            constraint=models.UniqueConstraint(
                fields=('license_order', 'po_line_item_number'),
                name='netbox_inventory_licenseorderlineitem_unique_order_line_item',
                violation_error_message='Line item number must be unique within a license order.',
            ),
        ),
        migrations.CreateModel(
            name='LicenseLineItemAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('comments', models.TextField(blank=True, verbose_name='Comments')),
                ('quantity', models.PositiveIntegerField(
                    verbose_name='Quantity',
                )),
                ('data_source', models.CharField(
                    default='manual',
                    max_length=20,
                    verbose_name='Data Source',
                )),
                ('synced_at', models.DateTimeField(
                    blank=True,
                    null=True,
                    verbose_name='Last Synced',
                )),
                ('line_item', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='allocations',
                    to='netbox_inventory.licenseorderlineitem',
                    verbose_name='Line Item',
                )),
                ('virtual_account', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='allocations',
                    to='netbox_inventory.virtualaccount',
                    verbose_name='Virtual Account',
                )),
            ],
            options={
                'verbose_name': 'License Line Item Allocation',
                'verbose_name_plural': 'License Line Item Allocations',
                'ordering': ('line_item', 'virtual_account'),
            },
        ),
        migrations.AddConstraint(
            model_name='licenselineitemallocation',
            constraint=models.UniqueConstraint(
                fields=('line_item', 'virtual_account'),
                name='netbox_inventory_licenselineitemallocation_unique_line_item_virtual_account',
                violation_error_message='An allocation for this line item and Virtual Account already exists.',
            ),
        ),
    ]
