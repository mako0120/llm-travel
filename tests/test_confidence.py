import unittest

from travel.confidence import cost_presentation, display_label, fallback_for


class ConfidencePolicyTests(unittest.TestCase):
    def test_all_four_fallback_paths_are_deterministic(self):
        self.assertEqual(fallback_for("low"), "continue_with_labels")
        self.assertEqual(fallback_for("unknown", budget_sensitive=True), "ask_user")
        self.assertEqual(fallback_for("low", alternative_available=True), "exclude_candidate")
        self.assertEqual(fallback_for("unknown", required=True), "stop")

    def test_labels_and_uncertain_costs_are_explicit(self):
        self.assertEqual(display_label("low"), "情報未確定")
        self.assertEqual(display_label("unknown"), "未確認")
        self.assertEqual(cost_presentation([{"confidence": "high"}]), "合計")
        self.assertEqual(cost_presentation([{"confidence": "high"}, {"confidence": "unknown"}]), "概算")
