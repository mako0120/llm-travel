import unittest

from travel.draft_itinerary import create_research_draft


def evidence(title, item_id):
    return {"id": item_id, "title": title, "source_type": "Wikimedia"}


class ResearchDraftTests(unittest.TestCase):
    def test_prefers_named_discovery_leads_over_areas_and_operators(self):
        draft = create_research_draft(
            {"destination": "京都市", "nights": 1},
            [evidence("京都市", "a"), evidence("観光地", "b"), evidence("京都市交通局", "c"), evidence("清水寺", "d"),
             {"id": "e", "title": "User-requested weather forecast", "source_type": "Open-Meteo Forecast API"}],
        )
        self.assertEqual([day["focus"] for day in draft["days"]], ["清水寺", "清水寺"])
        self.assertEqual(draft["days"][0]["time"], "未確定")


if __name__ == "__main__":
    unittest.main()
