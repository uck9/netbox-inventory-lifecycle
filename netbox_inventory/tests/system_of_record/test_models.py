from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase

from netbox_inventory.models import AssetSystemOfRecord

from .base import create_assets


class AssetSystemOfRecordModelTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.asset1, cls.asset2 = create_assets(2)

    def test_one_record_per_system_per_asset(self):
        AssetSystemOfRecord.objects.create(asset=self.asset1, system='cmdb', record_id='CI001')
        dup = AssetSystemOfRecord(asset=self.asset1, system='cmdb', record_id='CI002')
        with self.assertRaises(ValidationError):
            dup.full_clean()

    def test_multiple_systems_per_asset(self):
        AssetSystemOfRecord.objects.create(asset=self.asset1, system='cmdb', record_id='CI001')
        other = AssetSystemOfRecord(asset=self.asset1, system='cisco_iq', record_id='CI001')
        other.full_clean()
        other.save()
        self.assertEqual(self.asset1.sor_records.count(), 2)

    def test_record_id_unique_within_system(self):
        AssetSystemOfRecord.objects.create(asset=self.asset1, system='cmdb', record_id='CI001')
        dup = AssetSystemOfRecord(asset=self.asset2, system='cmdb', record_id='CI001')
        with self.assertRaises(ValidationError):
            dup.full_clean()

    def test_default_status_pending(self):
        sor = AssetSystemOfRecord.objects.create(asset=self.asset1, system='cmdb', record_id='CI001')
        self.assertEqual(sor.validation_status, 'pending')

    def test_is_stale(self):
        sor = AssetSystemOfRecord(asset=self.asset1, system='cmdb', record_id='CI001')
        self.assertTrue(sor.is_stale, 'never validated counts as stale')
        sor.last_validated = date.today() - timedelta(days=30)
        self.assertFalse(sor.is_stale, 'exactly at the threshold is still current')
        sor.last_validated = date.today() - timedelta(days=31)
        self.assertTrue(sor.is_stale)
        sor.last_validated = date.today()
        self.assertFalse(sor.is_stale)

    def test_cascade_on_asset_delete(self):
        AssetSystemOfRecord.objects.create(asset=self.asset1, system='cmdb', record_id='CI001')
        self.asset1.delete()
        self.assertFalse(AssetSystemOfRecord.objects.exists())

    def test_vendor_instance_id_unaffected(self):
        self.asset1.vendor_instance_id = 'VIN-1'
        self.asset1.save()
        AssetSystemOfRecord.objects.create(asset=self.asset1, system='cisco_iq', record_id='IQ-1')
        self.asset1.refresh_from_db()
        self.assertEqual(self.asset1.vendor_instance_id, 'VIN-1')
