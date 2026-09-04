from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site

from netbox_inventory.filtersets import AssetFilterSet
from netbox_inventory.models import Asset, InstalledAtLocation


class InstalledAtMismatchTest(TestCase):
    """
    Covers Asset.installed_at_mismatch and the matching
    AssetFilterSet.installed_at_mismatch filter, including the case where the
    vendor installed-at location has no NetBox sites linked at all.
    """

    @classmethod
    def setUpTestData(cls):
        cls.mfr = Manufacturer.objects.create(name='mfr', slug='mfr')
        cls.dt = DeviceType.objects.create(
            manufacturer=cls.mfr, model='dt', slug='dt'
        )
        cls.role = DeviceRole.objects.create(name='role', slug='role')

        cls.mfr_other = Manufacturer.objects.create(name='mfr2', slug='mfr2')

        cls.site_a = Site.objects.create(name='site A', slug='site-a', status='active')
        cls.site_b = Site.objects.create(name='site B', slug='site-b', status='active')

        # Vendor location linked to site A
        cls.loc_linked_a = InstalledAtLocation.objects.create(
            manufacturer=cls.mfr, vendor_site_id='LOC-A',
            address='1 A St', city='Town', country='US',
        )
        cls.loc_linked_a.sites.add(cls.site_a)

        # A SECOND vendor location, same manufacturer, also linked to site A
        cls.loc_linked_a2 = InstalledAtLocation.objects.create(
            manufacturer=cls.mfr, vendor_site_id='LOC-A2',
            address='2 A St', city='Town', country='US',
        )
        cls.loc_linked_a2.sites.add(cls.site_a)

        # Different manufacturer, also linked to site A (must never be suggested)
        cls.loc_other_mfr_a = InstalledAtLocation.objects.create(
            manufacturer=cls.mfr_other, vendor_site_id='LOC-OA',
            address='3 A St', city='Town', country='US',
        )
        cls.loc_other_mfr_a.sites.add(cls.site_a)

        # Vendor location with no NetBox sites linked
        cls.loc_unlinked = InstalledAtLocation.objects.create(
            manufacturer=cls.mfr, vendor_site_id='LOC-U',
            address='9 U St', city='Town', country='US',
        )

        def device(name, site):
            return Device.objects.create(
                site=site, status='active', device_type=cls.dt,
                role=cls.role, name=name,
            )

        # match: current site (A) is among linked sites (A)
        cls.asset_match = Asset.objects.create(
            serial='match', status='used', device_type=cls.dt,
            device=device('d-match', cls.site_a), installed_at=cls.loc_linked_a,
        )
        # mismatch: current site (B) not among linked sites (A)
        cls.asset_wrong_site = Asset.objects.create(
            serial='wrong', status='used', device_type=cls.dt,
            device=device('d-wrong', cls.site_b), installed_at=cls.loc_linked_a,
        )
        # mismatch: vendor location has no linked sites, but asset has a site
        cls.asset_unlinked = Asset.objects.create(
            serial='unlinked', status='used', device_type=cls.dt,
            device=device('d-unlinked', cls.site_a), installed_at=cls.loc_unlinked,
        )
        # neutral: vendor location has no linked sites and asset has no site
        cls.asset_unlinked_no_site = Asset.objects.create(
            serial='unlinked-no-site', status='stored', device_type=cls.dt,
            installed_at=cls.loc_unlinked,
        )
        # neutral: no installed_at at all
        cls.asset_no_loc = Asset.objects.create(
            serial='no-loc', status='used', device_type=cls.dt,
            device=device('d-no-loc', cls.site_a),
        )

    # ── property ──────────────────────────────────────────────────────────────

    def test_match_is_not_mismatch(self):
        self.assertFalse(self.asset_match.installed_at_mismatch)

    def test_wrong_site_is_mismatch(self):
        self.assertTrue(self.asset_wrong_site.installed_at_mismatch)

    def test_unlinked_location_with_current_site_is_mismatch(self):
        self.assertTrue(self.asset_unlinked.installed_at_mismatch)

    def test_unlinked_location_without_current_site_is_not_mismatch(self):
        self.assertFalse(self.asset_unlinked_no_site.installed_at_mismatch)

    def test_no_installed_at_is_not_mismatch(self):
        self.assertFalse(self.asset_no_loc.installed_at_mismatch)

    # ── suggested "correct" IA location ──────────────────────────────────────

    def _suggested(self, asset):
        return set(
            asset.installed_at_suggested_locations.values_list('vendor_site_id', flat=True)
        )

    def test_suggestion_lists_every_ia_location_mapped_to_current_site(self):
        # asset_unlinked's current site is A; two same-vendor locations map site A
        self.assertEqual(self._suggested(self.asset_unlinked), {'LOC-A', 'LOC-A2'})

    def test_suggestion_excludes_the_assets_own_installed_at(self):
        # asset_match sits at LOC-A already; only the *other* site-A location is a suggestion
        self.assertEqual(self._suggested(self.asset_match), {'LOC-A2'})

    def test_suggestion_ignores_other_manufacturers(self):
        self.assertNotIn('LOC-OA', self._suggested(self.asset_unlinked))

    def test_suggestion_empty_without_resolvable_current_site(self):
        self.assertEqual(self._suggested(self.asset_unlinked_no_site), set())

    def test_suggestion_empty_when_no_installed_at(self):
        self.assertEqual(self._suggested(self.asset_no_loc), set())

    def test_suggestion_empty_when_no_location_maps_the_site(self):
        # asset_wrong_site's current site is B; nothing maps site B
        self.assertEqual(self._suggested(self.asset_wrong_site), set())

    # ── filterset ─────────────────────────────────────────────────────────────

    def _filter(self, value):
        fs = AssetFilterSet(
            {'installed_at_mismatch': value}, queryset=Asset.objects.all()
        )
        self.assertTrue(fs.is_valid(), fs.errors)
        return set(fs.qs.values_list('serial', flat=True))

    def test_filter_true_returns_all_mismatches(self):
        self.assertEqual(self._filter(True), {'wrong', 'unlinked'})

    def test_filter_false_excludes_mismatches(self):
        self.assertEqual(
            self._filter(False),
            {'match', 'unlinked-no-site', 'no-loc'},
        )

    # ── asset detail page badge ──────────────────────────────────────────────

    def _render_asset(self, asset):
        user = get_user_model().objects.create_user('u', password='p')
        user.is_superuser = True
        user.save()
        client = Client()
        client.force_login(user)
        url = reverse('plugins:netbox_inventory:asset', args=[asset.pk])
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_badge_wrong_site_shows_address_mismatch(self):
        html = self._render_asset(self.asset_wrong_site)
        self.assertIn('Address Mismatch', html)

    def test_badge_unlinked_location_shows_site_not_linked_alert(self):
        html = self._render_asset(self.asset_unlinked)
        self.assertIn('Site Not Linked', html)
        self.assertNotIn('Sites Unlinked', html)

    def test_badge_unlinked_no_site_stays_neutral(self):
        html = self._render_asset(self.asset_unlinked_no_site)
        self.assertIn('Sites Unlinked', html)
        self.assertNotIn('Site Not Linked', html)

    def test_card_shows_correct_ia_location_and_not_full_site_list(self):
        html = self._render_asset(self.asset_unlinked)
        self.assertIn('Correct IA Location', html)
        # both same-vendor site-A locations are offered as the move target
        self.assertIn('LOC-A', html)
        self.assertIn('LOC-A2', html)
        # the old "list every linked site" row is gone
        self.assertNotIn('Linked NetBox Sites', html)

    def test_card_matching_asset_has_no_mismatch_rows(self):
        html = self._render_asset(self.asset_match)
        self.assertIn('Matches Site', html)
        self.assertNotIn('Correct IA Location', html)
