from datetime import datetime, timezone
import unittest

from travel.free_sources import NominatimAdapter, OpenMeteoAdapter, WikimediaAdapter, public_result_evidence, public_source_catalog
from travel.providers import ProviderResult


NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


class FreeSourcesTests(unittest.TestCase):
    def test_catalog_marks_only_no_key_sources_available(self):
        entries = {entry.id: entry for entry in public_source_catalog()}
        self.assertEqual(entries["nominatim"].state, "available_no_key")
        self.assertEqual(entries["open_meteo"].state, "available_no_key")
        self.assertEqual(entries["open_meteo"].commercial_use, "commercial_subscription_required")
        self.assertIn("1 request/second", entries["nominatim"].constraint)
        self.assertEqual(entries["official_gtfs"].state, "feed_selection_required")

    def test_nominatim_uses_one_bounded_user_query(self):
        called = []
        adapter = NominatimAdapter(lambda url: called.append(url) or [{"display_name": "京都", "osm_type": "relation", "osm_id": 1, "lat": "1", "lon": "2"}])
        result = adapter.search_destination("京都")
        self.assertEqual(result.state, "available")
        self.assertEqual(len(called), 1)
        self.assertIn("limit=1", called[0])
        self.assertIn("q=%E4%BA%AC%E9%83%BD", called[0])

    def test_wikimedia_and_nominatim_results_remain_unverified(self):
        wiki = WikimediaAdapter(lambda _url: {"pages": [{"title": "京都", "key": "京都", "description": "都市"}]})
        evidence = public_result_evidence(wiki.search_destination("京都"), NOW)
        self.assertEqual(evidence[0]["verification_status"], "unverified")
        self.assertIn("Wikimedia", evidence[0]["source_type"])
        geo = ProviderResult("available", [{"display_name": "京都", "osm_type": "relation", "osm_id": 1, "lat": "1", "lon": "2"}], "nominatim", "v1")
        self.assertEqual(public_result_evidence(geo, NOW)[0]["verification_status"], "unverified")

    def test_invalid_or_failed_results_do_not_create_evidence(self):
        self.assertEqual(public_result_evidence(ProviderResult("unavailable", provider="nominatim"), NOW), [])
        self.assertEqual(NominatimAdapter(lambda _url: {}).search_destination("京都").state, "invalid")
        with self.assertRaises(ValueError):
            WikimediaAdapter(lambda _url: {}).search_destination("京都", 11)

    def test_open_meteo_is_bounded_and_remains_a_forecast_candidate(self):
        called = []
        adapter = OpenMeteoAdapter(lambda url: called.append(url) or {"timezone": "Asia/Tokyo", "hourly": {"time": []}})
        result = adapter.forecast(35.0, 135.0)
        self.assertEqual(result.state, "available")
        self.assertIn("forecast_days=7", called[0])
        evidence = public_result_evidence(result, NOW)
        self.assertEqual(evidence[0]["verification_status"], "unverified")
        self.assertIn("Forecast", evidence[0]["source_type"])
