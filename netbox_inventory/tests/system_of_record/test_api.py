from datetime import date, timedelta

from django.urls import reverse
from rest_framework import status

from utilities.testing import APIViewTestCases

from netbox_inventory.models import AssetSystemOfRecord

from ..custom import APITestCase
from .base import create_assets


class AssetSystemOfRecordAPITest(
    APITestCase,
    APIViewTestCases.GetObjectViewTestCase,
    APIViewTestCases.ListObjectsViewTestCase,
    APIViewTestCases.CreateObjectViewTestCase,
    APIViewTestCases.UpdateObjectViewTestCase,
    APIViewTestCases.DeleteObjectViewTestCase,
):
    model = AssetSystemOfRecord
    brief_fields = ['display', 'id', 'record_id', 'system', 'url', 'validation_status']
    bulk_update_data = {
        'validation_status': 'not_found',
    }

    @classmethod
    def setUpTestData(cls):
        assets = create_assets(4)
        cls.assets = assets
        today = date.today()
        AssetSystemOfRecord.objects.create(
            asset=assets[0], system='cmdb', record_id='CI0001',
            validation_status='valid', last_validated=today,
        )
        AssetSystemOfRecord.objects.create(
            asset=assets[0], system='cisco_iq', record_id='IQ0001',
            validation_status='mismatch', last_validated=today - timedelta(days=60),
        )
        AssetSystemOfRecord.objects.create(
            asset=assets[1], system='cmdb', record_id='CI0002',
        )
        cls.create_data = [
            {'asset': assets[2].pk, 'system': 'cmdb', 'record_id': 'CI0003'},
            {'asset': assets[2].pk, 'system': 'cisco_iq', 'record_id': 'IQ0003',
             'validation_status': 'valid', 'last_validated': today.isoformat()},
            {'asset': assets[3].pk, 'system': 'cmdb', 'record_id': 'CI0004',
             'validation_status': 'not_found'},
        ]
        cls.update_data = {
            'validation_status': 'error',
            'last_validated': today.isoformat(),
        }

    def _list(self, url, **params):
        self.add_permissions('netbox_inventory.view_assetsystemofrecord', 'netbox_inventory.view_asset')
        response = self.client.get(url, params, **self.header)
        self.assertHttpStatus(response, status.HTTP_200_OK)
        return response.data

    def test_filter_by_system_and_record_id(self):
        url = self._get_list_url()
        self.assertEqual(self._list(url, system='cmdb')['count'], 2)
        data = self._list(url, system='cmdb', record_id='CI0001')
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['asset']['id'], self.assets[0].pk)

    def test_filter_is_stale(self):
        url = self._get_list_url()
        # IQ0001 validated 60 days ago; CI0002 never validated.
        stale = {r['record_id'] for r in self._list(url, is_stale='true')['results']}
        self.assertEqual(stale, {'IQ0001', 'CI0002'})
        self.assertEqual(self._list(url, is_stale='false')['count'], 1)

    def test_duplicate_record_id_in_system_rejected(self):
        self.add_permissions('netbox_inventory.add_assetsystemofrecord', 'netbox_inventory.view_asset')
        response = self.client.post(
            self._get_list_url(),
            {'asset': self.assets[3].pk, 'system': 'cmdb', 'record_id': 'CI0001'},
            format='json', **self.header,
        )
        self.assertHttpStatus(response, status.HTTP_400_BAD_REQUEST)

    def test_asset_api_includes_sor_records_and_filters(self):
        asset_list = reverse('plugins-api:netbox_inventory-api:asset-list')
        data = self._list(asset_list, sor_record_id='IQ0001')
        self.assertEqual(data['count'], 1)
        asset = data['results'][0]
        self.assertEqual(asset['id'], self.assets[0].pk)
        self.assertEqual(
            {(r['system']['value'], r['validation_status']['value'], r['is_stale']) for r in asset['sor_records']},
            {('cmdb', 'valid', False), ('cisco_iq', 'mismatch', True)},
        )
        self.assertEqual(self._list(asset_list, sor_validation_status='mismatch')['count'], 1)
        self.assertEqual(self._list(asset_list, sor_system='cmdb')['count'], 2)
