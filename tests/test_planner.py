import unittest

from travel.planner import PLANNER_SYSTEM_PROMPT, PlannerSession, next_turn, planning_brief, render_model_route


class PlannerConversationTests(unittest.TestCase):
    def test_consent_then_question_only_collection(self):
        session = PlannerSession()
        session, turn = next_turn(session)
        self.assertEqual(turn["reply"], "AI旅行計画を作成しますか？")
        session, turn = next_turn(session, "はい")
        self.assertEqual(turn["step"], 1)
        self.assertNotIn("planning_brief", turn)
        answers = ["大阪", "京都", "1", "神社とグルメ", "両方", "50000円", "ホテル", "公共交通機関", "子連れ"]
        for index, answer in enumerate(answers):
            session, turn = next_turn(session, answer)
            if index < len(answers) - 1:
                self.assertEqual(set(turn), {"state", "step", "reply"})
        self.assertTrue(session.ready)
        self.assertEqual(turn["state"], "ready")
        self.assertEqual(turn["planning_brief"]["requirements"]["destination"], "京都")

    def test_plan_brief_requires_completion_and_blocks_invention(self):
        with self.assertRaises(ValueError):
            planning_brief(PlannerSession())
        self.assertIn("創作", PLANNER_SYSTEM_PROMPT)

    def test_model_route_has_requested_fields_and_total(self):
        output = render_model_route([{"time": "09:00", "schedule": "移動", "place": "大阪駅", "cost": "800円", "notes": "王道", "route": "JR 京都線"}],
                                    {"transport": 800, "lodging": 10000, "food": 2000, "admission": 500})
        self.assertIn("時間：09:00｜スケジュール：移動｜場所：大阪駅", output)
        self.assertIn("合計費用：13300円", output)
