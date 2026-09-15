import unittest

from travel.itinerary import render_detailed_itinerary, validate_detailed_itinerary


class DetailedItineraryTests(unittest.TestCase):
    def test_render_includes_transport_food_lodging_alternatives_and_total(self):
        evidence_id = "evidence-1"
        proposal = {"primary": [{"time": "10:00", "schedule": "見学", "place": "京都駅", "label": "王道", "transport_mode": "公共交通機関", "transport_duration_minutes": 20, "route": "京都駅から移動", "cost": 100, "line_name": "地下鉄", "station_name": "京都駅", "departure_time": "09:40", "evidence_id": evidence_id}],
                    "spot_alternatives": [{"spot": "代案", "reason": "混雑回避", "evidence_id": evidence_id}],
                    "rainy_day_alternatives": [{"spot": "雨天案", "reason": "屋内", "evidence_id": evidence_id}],
                    "food_options": [{"name": "食事A", "rating": 4.5, "review_count": 100, "specialty": "湯豆腐", "evidence_id": evidence_id}, {"name": "食事B", "rating": 4.2, "review_count": 80, "specialty": "抹茶", "evidence_id": evidence_id}],
                    "lodging_options": [{"name": "宿A", "nightly_cost": 10000, "convenience": "駅近", "comfort": "静か", "evidence_id": evidence_id}],
                    "cost_totals": {"transport": 100, "lodging": 10000, "food": 2000, "admission": 500}}
        self.assertEqual(validate_detailed_itinerary(proposal), [])
        rendered = render_detailed_itinerary(proposal)
        for value in ("地下鉄／京都駅／09:40", "食事A", "宿A", "スポット代案：代案", "雨天時代案：雨天案", "合計費用：12600円"):
            self.assertIn(value, rendered)
