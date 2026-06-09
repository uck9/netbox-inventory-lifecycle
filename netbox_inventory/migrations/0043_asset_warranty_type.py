from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_inventory', '0042_installedatlocation'),
    ]

    operations = [
        migrations.AddField(
            model_name='asset',
            name='warranty_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('WARR-1YR-LTD-HW', '1-Year Limited Hardware Warranty'),
                    ('WARR-ELTD-LIFE-HW', 'Enhanced Limited Lifetime Hardware Warranty'),
                    ('WARR-LTD-LIFE-HW', 'Limited Lifetime Hardware Warranty'),
                    ('other', 'Other'),
                ],
                help_text='Warranty type for this asset',
                max_length=30,
                null=True,
                verbose_name='Warranty Type',
            ),
        ),
    ]
