from django.test import override_settings

from core.models import ObjectType
from dcim.models import Device, DeviceRole, DeviceType, Location, Manufacturer, Site
from users.models import ObjectPermission
from utilities.testing import TestCase
from utilities.testing.utils import post_data

from ..settings import CONFIG_SYNC_ON
from netbox_inventory.models import Asset


class JoinPermissionTestCase(TestCase):
    """
    Joining an asset to hardware writes both objects, so both views must check the side they don't edit:
    Device -> "Reassign asset" checks the assets, Asset -> "Assign" checks the devices.
    """

    @override_settings(PLUGINS_CONFIG=CONFIG_SYNC_ON)
    def setUp(self):
        super().setUp()
        site = Site.objects.create(name='site1', slug='site1')
        self.location = Location.objects.create(site=site, name='location1', slug='location1')
        manufacturer = Manufacturer.objects.create(name='manufacturer1', slug='manufacturer1')
        device_type = DeviceType.objects.create(manufacturer=manufacturer, model='dt1', slug='dt1')
        role = DeviceRole.objects.create(name='role1', slug='role1')
        self.device1, self.device2 = (
            Device.objects.create(site=site, device_type=device_type, role=role, name=f'device{i}')
            for i in (1, 2)
        )
        self.asset_used = Asset.objects.create(
            asset_tag='used', serial='used', status='used', device_type=device_type,
            device=self.device1, storage_location=self.location,
        )
        self.asset_stored = Asset.objects.create(
            asset_tag='stored', serial='stored', status='stored', device_type=device_type,
            storage_location=self.location,
        )

    def grant(self, model, pks):
        perm = ObjectPermission.objects.create(
            name=f'change {model._meta.model_name}', actions=['change'], constraints={'pk__in': pks},
        )
        perm.users.add(self.user)
        perm.object_types.add(ObjectType.objects.get_for_model(model))

    def reassign(self, asset):
        return self.client.post(
            f'/plugins/inventory/assets/device/{self.device1.pk}/reassign/',
            post_data({'device_type': self.device1.device_type.pk, 'assigned_asset': asset.pk,
                       'asset_status': 'stored'}),
        )

    def assign(self, asset, device):
        return self.client.post(
            f'/plugins/inventory/assets/{asset.pk}/assign/',
            post_data({'device_type': asset.device_type.pk, 'device': device.pk,
                       'storage_location': self.location.pk}),
        )

    @override_settings(EXEMPT_VIEW_PERMISSIONS=['*'], PLUGINS_CONFIG=CONFIG_SYNC_ON)
    def test_reassign_with_change_on_both_assets(self):
        self.grant(Device, [self.device1.pk])
        self.grant(Asset, [self.asset_used.pk, self.asset_stored.pk])
        self.assertHttpStatus(self.reassign(self.asset_stored), 302)
        self.asset_stored.refresh_from_db()
        self.assertEqual(self.asset_stored.device, self.device1)

    @override_settings(EXEMPT_VIEW_PERMISSIONS=['*'], PLUGINS_CONFIG=CONFIG_SYNC_ON)
    def test_reassign_refused_without_change_on_new_asset(self):
        self.grant(Device, [self.device1.pk])
        self.grant(Asset, [self.asset_used.pk])
        self.assertHttpStatus(self.reassign(self.asset_stored), 200)
        self.asset_stored.refresh_from_db()
        self.asset_used.refresh_from_db()
        self.assertIsNone(self.asset_stored.device)
        self.assertEqual(self.asset_used.device, self.device1)

    @override_settings(EXEMPT_VIEW_PERMISSIONS=['*'], PLUGINS_CONFIG=CONFIG_SYNC_ON)
    def test_reassign_refused_without_change_on_old_asset(self):
        self.grant(Device, [self.device1.pk])
        self.grant(Asset, [self.asset_stored.pk])
        self.assertHttpStatus(self.reassign(self.asset_stored), 200)
        self.asset_used.refresh_from_db()
        self.assertEqual(self.asset_used.device, self.device1)

    @override_settings(EXEMPT_VIEW_PERMISSIONS=['*'], PLUGINS_CONFIG=CONFIG_SYNC_ON)
    def test_assign_with_change_on_device(self):
        self.grant(Asset, [self.asset_stored.pk])
        self.grant(Device, [self.device2.pk])
        self.assertHttpStatus(self.assign(self.asset_stored, self.device2), 302)
        self.asset_stored.refresh_from_db()
        self.assertEqual(self.asset_stored.device, self.device2)

    @override_settings(EXEMPT_VIEW_PERMISSIONS=['*'], PLUGINS_CONFIG=CONFIG_SYNC_ON)
    def test_assign_refused_without_change_on_device(self):
        self.grant(Asset, [self.asset_stored.pk])
        self.assertHttpStatus(self.assign(self.asset_stored, self.device2), 200)
        self.asset_stored.refresh_from_db()
        self.assertIsNone(self.asset_stored.device)

    @override_settings(EXEMPT_VIEW_PERMISSIONS=['*'], PLUGINS_CONFIG=CONFIG_SYNC_ON)
    def test_assign_refused_without_change_on_old_device(self):
        # moving an asset off a device the user can't change would clear that device's serial
        self.grant(Asset, [self.asset_used.pk])
        self.grant(Device, [self.device2.pk])
        self.assertHttpStatus(self.assign(self.asset_used, self.device2), 200)
        self.asset_used.refresh_from_db()
        self.assertEqual(self.asset_used.device, self.device1)
