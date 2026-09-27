# Hand-written (makemigrations disabled in this install; see 0046 for why).
#
# Converts Asset.warranty_type from a free-text/choice CharField to a FK against the new
# WarrantyType catalog model (added in 0052). Seeds WarrantyType rows for the three known
# Cisco SKUs that used to be hardcoded choices, then repoints any existing Asset rows at
# them. Any legacy value that doesn't match a known SKU (e.g. the old 'other' choice) is
# NOT silently dropped: it's preserved verbatim in the asset's comments field so no data is
# lost, and a summary is printed for the operator running the migration.

import django.db.models.deletion
from django.db import migrations, models

LEGACY_SKU_TO_NAME = {
    'WARR-1YR-LTD-HW': '1-Year Limited Hardware Warranty',
    'WARR-ELTD-LIFE-HW': 'Enhanced Limited Lifetime Hardware Warranty',
    'WARR-LTD-LIFE-HW': 'Limited Lifetime Hardware Warranty',
}


def seed_warranty_types(apps, schema_editor):
    Manufacturer = apps.get_model('dcim', 'Manufacturer')
    WarrantyType = apps.get_model('netbox_inventory', 'WarrantyType')

    cisco = Manufacturer.objects.filter(name='Cisco').first()
    if cisco is None:
        cisco = Manufacturer.objects.filter(slug='cisco').first()
    if cisco is None:
        cisco = Manufacturer.objects.create(name='Cisco', slug='cisco')

    for sku, name in LEGACY_SKU_TO_NAME.items():
        WarrantyType.objects.get_or_create(
            sku=sku,
            defaults={'name': name, 'manufacturer': cisco},
        )


def convert_asset_warranty_type(apps, schema_editor):
    WarrantyType = apps.get_model('netbox_inventory', 'WarrantyType')
    Asset = apps.get_model('netbox_inventory', 'Asset')

    sku_to_warrantytype = {wt.sku: wt for wt in WarrantyType.objects.all()}

    converted = 0
    preserved_as_comment = 0
    for asset in Asset.objects.exclude(warranty_type__isnull=True).exclude(warranty_type=''):
        old_value = asset.warranty_type
        warranty_type = sku_to_warrantytype.get(old_value)
        if warranty_type is not None:
            asset.warranty_type_new_id = warranty_type.pk
            asset.save(update_fields=['warranty_type_new'])
            converted += 1
        else:
            note = f"[migration 0053] legacy warranty_type value not recognized: {old_value!r}"
            asset.comments = f"{asset.comments}\n{note}".strip()
            asset.save(update_fields=['comments'])
            preserved_as_comment += 1

    if converted or preserved_as_comment:
        print(
            f"\n    0053_asset_warranty_type_fk: converted {converted} asset(s) to WarrantyType FK, "
            f"preserved {preserved_as_comment} unrecognized legacy value(s) in Asset.comments."
        )


class Migration(migrations.Migration):

    # Postgres refuses to ALTER TABLE a table that still has pending trigger events from
    # earlier statements in the same transaction (here: the WarrantyType inserts in
    # seed_warranty_types, followed by the FK rename below touching WarrantyType's
    # referencing constraint). Running non-atomically lets each operation commit before
    # the next runs, avoiding "cannot ALTER TABLE ... because it has pending trigger events".
    atomic = False

    dependencies = [
        ('dcim', '0216_latitude_longitude_validators'),
        ('netbox_inventory', '0052_warrantytype'),
    ]

    operations = [
        migrations.RunPython(seed_warranty_types, migrations.RunPython.noop),
        migrations.AddField(
            model_name='asset',
            name='warranty_type_new',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assets',
                to='netbox_inventory.warrantytype',
            ),
        ),
        migrations.RunPython(convert_asset_warranty_type, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='asset',
            name='warranty_type',
        ),
        migrations.RenameField(
            model_name='asset',
            old_name='warranty_type_new',
            new_name='warranty_type',
        ),
    ]
