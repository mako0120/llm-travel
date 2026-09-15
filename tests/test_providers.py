import unittest
from datetime import datetime, timezone

from travel.providers import (GOOGLE_PLACES_TEXT_SEARCH_URL, GOOGLE_ROUTES_URL,
                               GoogleMapsAdapter, ProviderResult, google_places_evidence,
                               public_provider_catalog, provider_catalog)


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

    def test_google_adapter_does_not_call_network_without_a_key(self):
        calls = []
        result = GoogleMapsAdapter(transport=lambda *args: calls.append(args)).search_places("京都 カフェ")
        self.assertEqual(result.state, "unconfigured")
        self.assertEqual(calls, [])

    def test_google_places_request_uses_official_endpoint_and_minimal_fields(self):
        captured = {}
        def transport(url, headers, payload):
            captured.update(url=url, headers=headers, payload=payload)
            return {"places": []}
        result = GoogleMapsAdapter("secret-do-not-store", transport).search_places("京都 カフェ", max_result_count=3)
        self.assertEqual(result.state, "available")
        self.assertEqual(captured["url"], GOOGLE_PLACES_TEXT_SEARCH_URL)
        self.assertEqual(captured["payload"]["maxResultCount"], 3)
        self.assertIn("places.rating", captured["headers"]["X-Goog-FieldMask"])
        self.assertNotIn("secret-do-not-store", repr(result))

    def test_google_routes_request_validates_mode_and_uses_official_endpoint(self):
        captured = {}
        def transport(url, headers, payload):
            captured.update(url=url, headers=headers, payload=payload)
            return {"routes": []}
        result = GoogleMapsAdapter("key", transport).compute_route("京都駅", "清水寺", "TRANSIT")
        self.assertEqual(result.state, "available")
        self.assertEqual(captured["url"], GOOGLE_ROUTES_URL)
        self.assertEqual(captured["payload"]["travelMode"], "TRANSIT")
        with self.assertRaises(ValueError):
            GoogleMapsAdapter("key", transport).compute_route("A", "B", "FLY")

    def test_google_places_are_unverified_evidence_until_reviewed(self):
        result = ProviderResult("available", {"places": [
            {"id": "place/1", "displayName": {"text": "候補店"}, "formattedAddress": "京都",
             "rating": 4.4, "userRatingCount": 12, "googleMapsUri": "https://maps.example/place/1"},
            {"displayName": {"text": "URLなし"}},
        ]}, provider="google_maps", version="v1")
        items = google_places_evidence(result, datetime(2030, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["verification_status"], "unverified")
        self.assertEqual(items[0]["agent"], "provider")
        self.assertEqual(items[0]["retrieved_at"], "2030-01-01T00:00:00Z")
        self.assertEqual(items[0]["expires_at"], "2030-01-02T00:00:00Z")

    def test_non_available_google_result_creates_no_evidence(self):
        self.assertEqual(google_places_evidence(ProviderResult("unconfigured", provider="google_maps")), [])
