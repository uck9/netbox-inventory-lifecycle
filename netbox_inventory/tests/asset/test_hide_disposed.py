from django.contrib.auth import get_user_model
from unittest import mock

from django.http import QueryDict
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.models import ObjectType
from dcim.models import DeviceType, Manufacturer
from users.models import ObjectPermission

from netbox_inventory.filtersets import AssetFilterSet, AssetListFilterSet
from netbox_inventory.models import Asset
from netbox_inventory.utils import INCLUDE_DISPOSED_PREFERENCE


class HideDisposedAssetsTest(TestCase):
    """
    Disposed assets are hidden from the UI asset list (and its bulk "select
    all") unless asked for, while the API filterset is unchanged.
    """

    @classmethod
    def setUpTestData(cls):
        mfr = Manufacturer.objects.create(name='mfr', slug='mfr')
        dt = DeviceType.objects.create(manufacturer=mfr, model='dt', slug='dt')
        cls.stored = Asset.objects.create(
            name='kept', serial='S1', status='stored', device_type=dt,
        )
        cls.disposed = Asset.objects.create(
            name='gone', serial='S2', status='disposed', device_type=dt,
        )
        cls.user = get_user_model().objects.create_user(username='u', password='p')

    def _ids(self, data, filterset=AssetListFilterSet):
        request = RequestFactory().get('/')
        request.user = self.user
        query = QueryDict(mutable=True)
        query.update(data)
        qs = filterset(query, Asset.objects.all(), request=request).qs
        return set(qs.values_list('pk', flat=True))

    def _set_pref(self, value):
        self.user.config.set(INCLUDE_DISPOSED_PREFERENCE, value, commit=True)

    def test_hidden_by_default(self):
        self.assertEqual(self._ids({}), {self.stored.pk})

    def test_api_filterset_unchanged(self):
        self.assertEqual(self._ids({}, AssetFilterSet), {self.stored.pk, self.disposed.pk})

    def test_include_disposed_param(self):
        self.assertEqual(self._ids({'include_disposed': 'true'}), {self.stored.pk, self.disposed.pk})
        self.assertEqual(self._ids({'include_disposed': 'false'}), {self.stored.pk})

    def test_status_filter_shows_disposed(self):
        self.assertEqual(self._ids({'status': 'disposed'}), {self.disposed.pk})
        self.assertEqual(self._ids({'status__n': 'stored'}), {self.disposed.pk})

    def test_quick_search_finds_disposed(self):
        self.assertEqual(self._ids({'q': 'gone'}), {self.disposed.pk})

    def test_user_preference(self):
        self._set_pref('true')
        self.assertEqual(self._ids({}), {self.stored.pk, self.disposed.pk})
        # explicit No overrides the preference
        self.assertEqual(self._ids({'include_disposed': 'false'}), {self.stored.pk})
        self._set_pref('false')
        self.assertEqual(self._ids({}), {self.stored.pk})

    @mock.patch('netbox_inventory.utils.get_plugin_setting', return_value=True)
    def test_plugin_setting_default(self, _setting):
        self.assertEqual(self._ids({}), {self.stored.pk, self.disposed.pk})
        # user preference beats the plugin setting
        self._set_pref('false')
        self.assertEqual(self._ids({}), {self.stored.pk})

    def test_list_view(self):
        obj_perm = ObjectPermission.objects.create(name='view assets', actions=['view'])
        obj_perm.users.add(self.user)
        obj_perm.object_types.add(ObjectType.objects.get_for_model(Asset))
        self.client.force_login(self.user)
        url = reverse('plugins:netbox_inventory:asset_list')
        body = self.client.get(url).content.decode()
        self.assertIn('kept', body)
        self.assertNotIn('>gone<', body)
        body = self.client.get(url, {'include_disposed': 'true'}).content.decode()
        self.assertIn('>gone<', body)

    def test_api_status_exclusion_used_by_dropdowns(self):
        # Asset dropdowns send status__n=disposed to the API.
        self.assertEqual(self._ids({'status__n': 'disposed'}, AssetFilterSet), {self.stored.pk})
