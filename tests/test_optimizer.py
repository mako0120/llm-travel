from datetime import datetime
import unittest

from travel.domain import validate_trip_ready
from travel.optimizer import optimize
from travel.providers import FixtureRouteProvider, FixtureSourceProvider


def candidate(identifier, score=1, cost=100, visit=30, status="verified"):
    return {"id": identifier, "score": score, "cost": cost, "visit_minutes": visit,
            "source": {"verification_status": status}}


class OptimizerTests(unittest.TestCase):
    def test_uses_verified_fixture_routes_and_hard_constraints(self):
        provider = FixtureRouteProvider({("origin", "a"): 10, ("a", "b"): 5})
        result = optimize([candidate("b", 2), candidate("a", 4)], provider,
                          start_id="origin", budget=250, available_minutes=80)
        self.assertEqual(result["state"], "success")
        self.assertEqual([item["id"] for item in result["selected"]], ["a", "b"])
        self.assertEqual(result["total_minutes"], 75)

    def test_excludes_unverified_and_reports_unconfigured_or_infeasible(self):
        self.assertEqual(optimize([candidate("a")], FixtureRouteProvider(configured=False),
                                  start_id="origin", budget=200, available_minutes=60)["state"], "unconfigured")
        result = optimize([candidate("a", status="unverified")], FixtureRouteProvider({("origin", "a"): 1}),
                          start_id="origin", budget=200, available_minutes=60)
        self.assertEqual(result["state"], "infeasible")
        self.assertEqual(result["excluded"], [{"id": "a", "reason": "unverified_source"}])

    def test_malformed_source_is_excluded_not_a_crash(self):
        for source in (None, "not-a-dict", 42, []):
            result = optimize([dict(candidate("a"), source=source)], FixtureRouteProvider({("origin", "a"): 1}),
                              start_id="origin", budget=200, available_minutes=60)
            self.assertEqual(result["state"], "infeasible")
            self.assertEqual(result["excluded"], [{"id": "a", "reason": "unverified_source"}])

    def test_timeout_is_bounded(self):
        ticks = iter((0, 2))
        result = optimize([candidate("a")], FixtureRouteProvider({("origin", "a"): 1}),
                          start_id="origin", budget=200, available_minutes=60, timeout_seconds=1, clock=lambda: next(ticks))
        self.assertEqual(result["state"], "timeout")

    def test_fixture_source_has_explicit_unconfigured_state(self):
        self.assertEqual(FixtureSourceProvider(configured=False).lookup("x").state, "unconfigured")

    def test_malformed_source_field_is_treated_as_unverified_not_a_crash(self):
        for bad_source in [None, "not-a-dict", 42, []]:
            malformed = dict(candidate("a"), source=bad_source)
            result = optimize([malformed], FixtureRouteProvider({("origin", "a"): 1}),
                              start_id="origin", budget=200, available_minutes=60)
            self.assertEqual(result["state"], "infeasible")


class TripReadinessTests(unittest.TestCase):
    def test_requires_verified_fresh_provenance_at_time_of_use(self):
        plan = {"start": "2026-09-13T09:00:00+00:00", "end": "2026-09-13T11:00:00+00:00", "budget": 100,
                "required_activity_ids": ["a"], "activities": [{"id": "a", "start": "2026-09-13T09:30:00+00:00",
                "end": "2026-09-13T10:00:00+00:00", "cost": 1, "transit_minutes": 0,
                "source": {"url": "https://example.org/a", "expires_at": "2026-09-13T12:00:00+00:00", "verification_status": "verified"}}]}
        self.assertEqual(validate_trip_ready(plan, datetime.fromisoformat("2026-09-13T10:30:00+00:00")), [])
        self.assertIn("expired_source", {x["code"] for x in validate_trip_ready(plan, datetime.fromisoformat("2026-09-13T12:00:00+00:00"))})
