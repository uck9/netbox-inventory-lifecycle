from dcim.models import DeviceType, Manufacturer

from netbox_inventory.models import Asset


def create_assets(count=4):
    manufacturer = Manufacturer.objects.create(name='SOR Manufacturer', slug='sor-manufacturer')
    device_type = DeviceType.objects.create(
        model='SOR Device Type', slug='sor-devicetype', manufacturer=manufacturer
    )
    return [
        Asset.objects.create(
            name=f'SOR Asset {i}',
            serial=f'SORSERIAL{i}',
            asset_tag=f'SORTAG{i}',
            status='stored',
            device_type=device_type,
        )
        for i in range(1, count + 1)
    ]
