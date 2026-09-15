import unittest

from travel.providers import public_provider_catalog, provider_catalog


class ProviderCatalogTests(unittest.TestCase):
    def test_catalog_has_safe_states_and_no_live_adapter(self):
        catalog = {item.id: item for item in provider_catalog()}
        self.assertEqual(catalog['google_places'].state, 'configuration_required')
        self.assertEqual(catalog['official_gtfs'].state, 'feed_selection_required')
        self.assertIn('Do not scrape', catalog['tabelog'].constraint)

    def test_public_catalog_is_json_safe_and_never_contains_credential_values(self):
        catalog = public_provider_catalog()
        self.assertTrue(all('documentation_url' in item for item in catalog))
        self.assertTrue(all('credential' not in item for item in catalog))
