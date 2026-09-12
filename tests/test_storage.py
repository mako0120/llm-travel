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
        for ratings in [{}, {"score": True}, {"score": 0}, {"score": 6}, {"score": 3.5}, {"score": "4"}]:
            with self.subTest(ratings=ratings), self.assertRaises(ValueError):
                self.repo.add_feedback(plan["id"], 1, ratings, "")
        self.assertEqual(self.repo.list_feedback(plan["id"]), [])

    def test_only_approved_rules_with_all_exact_conditions_are_reused(self):
        rule = self.repo.propose_rule(
            {"region": "Kyoto", "transport": "walk"}, "rushed", "Allow more time", ["feedback-1"]
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

    def test_approve_rule_requires_an_approver_identity(self):
        rule = self.repo.propose_rule({"region": "Kyoto"}, "rushed", "Allow more time", ["feedback-1"])
        for approver in [None, "", "   ", 0, False]:
            with self.assertRaises(ValueError):
                self.repo.approve_rule(rule["id"], approver)
        self.assertEqual(self.repo.find_rules({"region": "Kyoto"}), [])

    def test_find_rules_supports_threshold_conditions(self):
        rule = self.repo.propose_rule(
            {"participants": {"op": "gte", "value": 10}, "drive_hours": {"op": "gte", "value": 2}},
            "driver fatigue", "add a second driver", ["feedback-1"],
        )
        self.repo.approve_rule(rule["id"], "operator-1")
        self.assertEqual(len(self.repo.find_rules({"participants": 10, "drive_hours": 2})), 1)
        self.assertEqual(len(self.repo.find_rules({"participants": 15, "drive_hours": 3})), 1)
        self.assertEqual(self.repo.find_rules({"participants": 9, "drive_hours": 2}), [])
        self.assertEqual(self.repo.find_rules({"participants": 10, "drive_hours": 1.9}), [])

    def test_threshold_condition_shape_is_validated_at_propose_time(self):
        for bad_condition in [
            {"participants": {"op": "unknown", "value": 10}},
            {"participants": {"op": "gte", "value": "10"}},
            {"participants": {"op": "gte", "value": True}},
            {"participants": {"op": "gte"}},
        ]:
            with self.assertRaises(ValueError):
                self.repo.propose_rule(bad_condition, "rushed", "Allow more time", ["feedback-1"])

    def test_empty_condition_and_missing_evidence_rejected(self):
        for condition, evidence in [({}, ["feedback-1"]), ({"region": "Kyoto"}, [])]:
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
        rule = self.repo.propose_rule(condition, "rushed", "More time", ["feedback-1"])
        approved = self.repo.approve_rule(rule["id"], "operator-1")
        self.assertEqual(self.repo.find_rules(condition), [approved])
        self.assertEqual(self.repo.find_rules({"party": {"children": [True], "accessible": True}}), [])
        self.assertEqual(self.repo.find_rules({"party": {"children": [1], "accessible": 1}}), [])


if __name__ == "__main__":
    unittest.main()
