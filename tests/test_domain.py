import copy
from datetime import datetime, timezone
import unittest

from travel.domain import summarize_ratings, validate_plan


NOW = datetime(2026, 9, 12, tzinfo=timezone.utc)


def fixture():
    return {
        "start": "2026-09-13T09:00:00+09:00", "end": "2026-09-13T18:00:00+09:00",
        "budget": 5000, "required_activity_ids": ["museum"],
        "activities": [{"id": "museum", "start": "2026-09-13T10:00:00+09:00",
                        "end": "2026-09-13T11:00:00+09:00", "cost": 1500, "transit_minutes": 60,
                        "source": {"url": "https://example.org/museum", "expires_at": "2026-09-14T00:00:00Z"}}],
    }


class PlanTests(unittest.TestCase):
    def codes(self, plan):
        return {issue["code"] for issue in validate_plan(plan, NOW)}

    def test_valid_and_transit_boundary(self):
        self.assertEqual(validate_plan(fixture(), NOW), [])
        plan = fixture()
        plan["activities"][0]["transit_minutes"] = 61
        self.assertIn("insufficient_transit", self.codes(plan))

    def test_missing_provenance_and_expiry_boundary(self):
        plan = fixture()
        del plan["activities"][0]["source"]
        self.assertIn("missing_source", self.codes(plan))
        plan = fixture()
        plan["activities"][0]["source"]["expires_at"] = NOW.isoformat()
        self.assertIn("expired_source", self.codes(plan))

    def test_budget_and_required(self):
        plan = fixture()
        plan["budget"] = 1499
        plan["required_activity_ids"].append("park")
        self.assertTrue({"over_budget", "missing_required"} <= self.codes(plan))

    def test_duplicates_overlap_and_order(self):
        plan = fixture()
        second = copy.deepcopy(plan["activities"][0])
        second["start"] = "2026-09-13T09:30:00+09:00"
        plan["activities"].append(second)
        self.assertTrue({"duplicate_id", "overlap", "unordered"} <= self.codes(plan))

    def test_decimal_budget_boundary(self):
        plan = fixture()
        plan["budget"] = 0.3
        plan["activities"][0]["cost"] = 0.1
        second = copy.deepcopy(plan["activities"][0])
        second.update(id="park", start="2026-09-13T12:00:00+09:00",
                      end="2026-09-13T13:00:00+09:00", cost=0.2)
        plan["activities"].append(second)
        self.assertEqual(validate_plan(plan, NOW), [])
        plan["budget"] = 0.2999999
        self.assertIn("over_budget", self.codes(plan))

    def test_naive_timestamps_and_reverse_range(self):
        plan = fixture()
        plan["start"] = "2026-09-13T09:00:00"
        plan["activities"][0]["end"] = "2026-09-13T09:00:00+09:00"
        self.assertTrue({"invalid_time", "invalid_range"} <= self.codes(plan))

    def test_non_trailing_z_is_not_rewritten(self):
        plan = fixture()
        plan["start"] = "2026-09-12Z09:00:00+00:00"
        self.assertIn("invalid_time", self.codes(plan))

    def test_numeric_rejection(self):
        for invalid in (True, False, float("nan"), float("inf"), -1, "20", None, {}, 10 ** 1000):
            for key, code in (("cost", "invalid_cost"), ("transit_minutes", "invalid_transit")):
                plan = fixture()
                plan["activities"][0][key] = invalid
                with self.subTest(key=key, invalid=invalid):
                    self.assertIn(code, self.codes(plan))

    def test_malformed_inputs_do_not_crash(self):
        for value in (None, [], 42, "plan", {}, {"activities": [None, [], {"id": []}]}):
            with self.subTest(value=value):
                self.assertTrue(validate_plan(value, NOW))
        for url in ("unknown", "https://[", [], "https://bad host/test"):
            plan = fixture()
            plan["activities"][0]["source"]["url"] = url
            self.assertIn("invalid_source", self.codes(plan))

    def test_no_mutation(self):
        plan = fixture()
        before = copy.deepcopy(plan)
        validate_plan(plan, NOW)
        self.assertEqual(plan, before)


class RatingTests(unittest.TestCase):
    def test_statistics(self):
        self.assertEqual(summarize_ratings([1, 3, 5]), {"count": 3, "mean": 3, "median": 3, "stdev": (8 / 3) ** 0.5})
        self.assertEqual(summarize_ratings([7])["mean"], 7)
        self.assertEqual(summarize_ratings([4])["stdev"], 0)
        self.assertIsNone(summarize_ratings([])["mean"])

    def test_reject_invalid_ratings(self):
        for value in ([True], [float("nan")], [float("inf")], [0], [8], ["3"], None, "123"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                summarize_ratings(value)


if __name__ == "__main__":
    unittest.main()
