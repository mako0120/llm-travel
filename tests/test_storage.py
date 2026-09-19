import tempfile
import unittest
from pathlib import Path

from travel.storage import Repository


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "travel.db"
        self.repo = Repository(self.path)

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_revisions_are_immutable_and_persist_after_reopen(self):
        first = self.repo.create_plan({"destination": "Kyoto", "items": ["temple"]})
        second = self.repo.create_plan(dict(first, destination="Osaka"))
        first["items"].append("mutation")
        self.repo.close()
        self.repo = Repository(self.path)
        self.assertEqual(self.repo.get_plan(first["id"], 1)["destination"], "Kyoto")
        self.assertEqual(self.repo.get_plan(first["id"], 1)["items"], ["temple"])
        self.assertEqual(self.repo.get_plan(first["id"]), second)
        self.assertEqual(second["version"], 2)

    def test_feedback_keeps_exact_revision_and_rejects_invalid_references(self):
        first = self.repo.create_plan({"destination": "Kyoto"})
        self.repo.create_plan(first)
        feedback = self.repo.add_feedback(first["id"], 1, {"satisfaction": 4}, "Too rushed")
        self.assertEqual(self.repo.list_feedback(first["id"]), [feedback])
        for plan_id, version in [(first["id"], 3), ("missing", 1), (first["id"], True)]:
            with self.assertRaises(ValueError):
                self.repo.add_feedback(plan_id, version, {"score": 4}, "")

    def test_invalid_rating_values_are_rejected(self):
        plan = self.repo.create_plan({})
        for ratings in [{}, {"score": True}, {"score": 0}, {"score": 8}, {"score": 3.5}, {"score": "4"}]:
            with self.subTest(ratings=ratings), self.assertRaises(ValueError):
                self.repo.add_feedback(plan["id"], 1, ratings, "")
        self.assertEqual(self.repo.list_feedback(plan["id"]), [])

    def test_seven_point_ratings_are_accepted_for_monitoring(self):
        plan = self.repo.create_plan({})
        feedback = self.repo.add_feedback(plan["id"], 1, {"scenery": 7, "lodging": 5}, "The view was memorable")
        self.assertEqual(feedback["ratings"], {"scenery": 7, "lodging": 5})

    def test_only_approved_rules_with_all_exact_conditions_are_reused(self):
        plan = self.repo.create_plan({})
        feedback = self.repo.add_feedback(plan["id"], 1, {"satisfaction": 4}, "Allow more time between visits")
        rule = self.repo.propose_rule_from_comments(
            {"region": "Kyoto", "transport": "walk"}, "rushed", "Allow more time", [feedback["id"]]
        )
        metadata = {"region": "Kyoto", "transport": "walk", "people": 2}
        self.assertEqual(rule["status"], "pending")
        self.assertEqual(self.repo.find_rules(metadata), [])
        approved = self.repo.approve_rule(rule["id"], "operator-1")
        self.assertEqual(approved["approved_by"], "operator-1")
        self.assertEqual(self.repo.find_rules(metadata), [approved])
        self.assertEqual(self.repo.find_rules({"region": "Kyoto"}), [])
        self.assertEqual(self.repo.find_rules(dict(metadata, transport="car")), [])
        self.assertEqual(self.repo.approve_rule(rule["id"], "operator-2"), approved)
        with self.assertRaises(ValueError):
            self.repo.approve_rule("missing", "operator-1")

    def test_approval_requires_explicit_operator(self):
        plan = self.repo.create_plan({})
        feedback = self.repo.add_feedback(plan["id"], 1, {"score": 4}, "Need a break")
        rule = self.repo.propose_rule_from_comments({"region": "Kyoto"}, "rushed", "Add break", [feedback["id"]])
        for operator in (None, "", "   ", 0, False):
            with self.assertRaises(ValueError):
                self.repo.approve_rule(rule["id"], operator)

    def test_empty_condition_and_missing_evidence_rejected(self):
        for condition, evidence in [({}, {"evidence_type": "qualitative_comment_only", "feedback_ids": ["feedback-1"]}), ({"region": "Kyoto"}, {"evidence_type": "qualitative_comment_only", "feedback_ids": []})]:
            with self.assertRaises(ValueError):
                self.repo.propose_rule(condition, "rushed", "Allow more time", evidence)

    def test_values_do_not_become_sql(self):
        plan = self.repo.create_plan({"id": "'; DROP TABLE plans;--", "destination": "Kyoto"})
        self.assertEqual(self.repo.get_plan(plan["id"]), plan)
        self.assertIsNotNone(self.repo.create_plan({}))

    def test_invalid_ids_consistently_raise_value_error(self):
        for identifier in [None, False, 0, [], {}, "", "   "]:
            operations = [
                lambda: self.repo.create_plan({"id": identifier}),
                lambda: self.repo.get_plan(identifier),
                lambda: self.repo.list_feedback(identifier),
                lambda: self.repo.approve_rule(identifier, "operator-1"),
                lambda: self.repo.add_feedback(identifier, 1, {"score": 4}, ""),
            ]
            for index, operation in enumerate(operations):
                with self.subTest(identifier=identifier, operation=index), self.assertRaises(ValueError):
                    operation()

    def test_nested_rule_conditions_require_matching_types(self):
        condition = {"party": {"children": [1], "accessible": True}}
        plan = self.repo.create_plan({})
        feedback = self.repo.add_feedback(plan["id"], 1, {"score": 4}, "Need a longer rest")
        rule = self.repo.propose_rule_from_comments(condition, "rushed", "More time", [feedback["id"]])
        approved = self.repo.approve_rule(rule["id"], "operator-1")
        self.assertEqual(self.repo.find_rules(condition), [approved])
        self.assertEqual(self.repo.find_rules({"party": {"children": [True], "accessible": True}}), [])
        self.assertEqual(self.repo.find_rules({"party": {"children": [1], "accessible": 1}}), [])

    def test_threshold_conditions_reuse_compliant_qualitative_rules(self):
        plan = self.repo.create_plan({})
        feedback = self.repo.add_feedback(plan["id"], 1, {"score": 3}, "Long drives were tiring")
        rule = self.repo.propose_rule_from_comments(
            {"participants": {"op": "gte", "value": 10}, "drive_hours": {"op": "gte", "value": 2}},
            "driver fatigue", "Add a second driver", [feedback["id"]],
        )
        approved = self.repo.approve_rule(rule["id"], "operator-1")
        self.assertEqual(self.repo.find_rules({"participants": 10, "drive_hours": 2}), [approved])
        self.assertEqual(self.repo.find_rules({"participants": 9, "drive_hours": 2}), [])

    def test_invalid_threshold_condition_is_rejected(self):
        plan = self.repo.create_plan({})
        feedback = self.repo.add_feedback(plan["id"], 1, {"score": 3}, "Long drives were tiring")
        for condition in ({"participants": {"op": "unknown", "value": 10}}, {"participants": {"op": "gte", "value": True}}):
            with self.assertRaises(ValueError):
                self.repo.propose_rule_from_comments(condition, "fatigue", "Add break", [feedback["id"]])

    def test_rule_rejects_ratings_only_or_empty_qualitative_evidence(self):
        plan = self.repo.create_plan({})
        ratings_only = self.repo.add_feedback(plan["id"], 1, {"overall": 5}, "")
        with self.assertRaises(ValueError):
            self.repo.propose_rule_from_comments({"region": "Kyoto"}, "rushed", "More time", [ratings_only["id"]])
        with self.assertRaises(ValueError):
            self.repo.propose_rule({"region": "Kyoto"}, "rushed", "More time", {"ratings": {"overall": 1}})

    def test_rule_evidence_retains_only_qualitative_feedback_references(self):
        plan = self.repo.create_plan({})
        feedback = self.repo.add_feedback(plan["id"], 1, {"overall": 1}, "The drive felt unsafe in rain")
        rule = self.repo.propose_rule_from_comments(
            {"transport": "car"}, "Safety anxiety", "Offer rail alternative and rainy-day plan", [feedback["id"]]
        )
        self.assertEqual(rule["evidence"], {"evidence_type": "qualitative_comment_only", "feedback_ids": [feedback["id"]]})

    def test_claim_research_run_is_atomic_and_single_use(self):
        run = self.repo.create_research_run("solo-operator", {"destination": "Kyoto"}, [])
        self.assertTrue(self.repo.claim_research_run(run["id"]))
        self.assertEqual(self.repo.get_research_run(run["id"])["state"], "researching")
        # A second, overlapping claim attempt (e.g. a second worker instance) must fail.
        self.assertFalse(self.repo.claim_research_run(run["id"]))

    def test_claim_research_run_rejects_a_run_that_is_already_past_requested(self):
        run = self.repo.create_research_run("solo-operator", {"destination": "Kyoto"}, [])
        self.repo.record_evidence(run["id"], {"agent": "human", "source_type": "manual", "url": "https://example.test",
            "title": "t", "facts": {}, "retrieved_at": "2030-01-01T00:00:00Z", "expires_at": "2030-01-02T00:00:00Z",
            "verification_status": "unverified"})
        self.assertFalse(self.repo.claim_research_run(run["id"]))

    def test_list_research_runs_filters_by_state(self):
        requested = self.repo.create_research_run("solo-operator", {"destination": "Kyoto"}, [])
        self.repo.create_research_run("solo-operator", {"destination": "Osaka"}, [])
        self.repo.claim_research_run(requested["id"])
        remaining = self.repo.list_research_runs(state="requested")
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["requirements"]["destination"], "Osaka")


if __name__ == "__main__":
    unittest.main()
