from datetime import date

from django.test import override_settings
from django.urls import NoReverseMatch, reverse

from utilities.testing import TestCase, ViewTestCases

from netbox_inventory.models import AssetSystemOfRecord

from ..custom import ModelViewTestCase
from .base import create_assets


class AssetSystemOfRecordViewTest(
    ModelViewTestCase,
    ViewTestCases.GetObjectViewTestCase,
    ViewTestCases.GetObjectChangelogViewTestCase,
    ViewTestCases.ListObjectsViewTestCase,
):
    model = AssetSystemOfRecord

    @classmethod
    def setUpTestData(cls):
        assets = create_assets(3)
        for i, asset in enumerate(assets, start=1):
            AssetSystemOfRecord.objects.create(
                asset=asset, system='cmdb', record_id=f'CI000{i}', last_validated=date.today(),
            )


class AssetSystemOfRecordUITest(TestCase):
    """SOR records are API-managed: the UI shows them but never edits them."""

    @classmethod
    def setUpTestData(cls):
        cls.asset, cls.bare_asset = create_assets(2)
        AssetSystemOfRecord.objects.create(
            asset=cls.asset, system='cmdb', record_id='CI-UI-1',
            validation_status='valid', last_validated=date.today(),
        )
        AssetSystemOfRecord.objects.create(
            asset=cls.asset, system='cisco_iq', record_id='IQ-UI-1', validation_status='mismatch',
        )

    def test_no_edit_views(self):
        for action in ('add', 'edit', 'delete', 'bulk_import', 'bulk_edit', 'bulk_delete'):
            with self.assertRaises(NoReverseMatch, msg=action):
                reverse(f'plugins:netbox_inventory:assetsystemofrecord_{action}')

    @override_settings(EXEMPT_VIEW_PERMISSIONS=['*'])
    def test_asset_panel_shows_system_and_status(self):
        self.add_permissions('netbox_inventory.view_assetsystemofrecord')
        response = self.client.get(self.asset.get_absolute_url())
        self.assertHttpStatus(response, 200)
        content = response.content.decode()
        self.assertIn('System of Record', content)
        self.assertIn('Cisco IQ', content)
        self.assertIn('Mismatch', content)
        self.assertIn('Stale', content)  # IQ record never validated

    @override_settings(EXEMPT_VIEW_PERMISSIONS=['*'])
    def test_asset_panel_empty(self):
        self.add_permissions('netbox_inventory.view_assetsystemofrecord')
        response = self.client.get(self.bare_asset.get_absolute_url())
        self.assertContains(response, 'No system of record entries.')

    @override_settings(EXEMPT_VIEW_PERMISSIONS=['*'])
    def test_asset_tab(self):
        self.add_permissions('netbox_inventory.view_assetsystemofrecord')
        url = reverse('plugins:netbox_inventory:asset_system-of-record', kwargs={'pk': self.asset.pk})
        response = self.client.get(url)
        self.assertHttpStatus(response, 200)
        self.assertContains(response, 'CI-UI-1')
        self.assertContains(response, 'IQ-UI-1')
        self.assertNotContains(response, '/edit/"')
