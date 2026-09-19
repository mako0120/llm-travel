import unittest

from travel.planner import PLANNER_SYSTEM_PROMPT, PlannerSession, next_turn, planning_brief, render_model_route, research_request


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

    def test_questions_match_the_requested_nine_step_interview(self):
        session, turn = next_turn(PlannerSession(), "はい")
        self.assertEqual(turn["reply"], "ありがとうございます！ まずは、あなたのお住まいの地域を教えていただけますか？この情報をもとに、移動費などの計画を立てやすくなります。")
        session, turn = next_turn(session, "東京")
        self.assertEqual(turn["reply"], "行き先について教えていただけますか？行きたい国や地域、都市はありますか？特定の場所があればお知らせください。")

    def test_plan_brief_requires_completion_and_blocks_invention(self):
        with self.assertRaises(ValueError):
            planning_brief(PlannerSession())
        self.assertIn("創作", PLANNER_SYSTEM_PROMPT)

    def test_model_route_has_requested_fields_and_total(self):
        output = render_model_route([{"time": "09:00", "schedule": "移動", "place": "大阪駅", "cost": "800円", "notes": "王道", "route": "JR 京都線", "confidence": "high"}],
                                    {"transport": 800, "lodging": 10000, "food": 2000, "admission": 500,
                                     "confidence": {"transport": "high", "lodging": "high", "food": "high", "admission": "high"}})
        self.assertIn("時間：09:00｜スケジュール：移動｜場所：大阪駅", output)
        self.assertIn("合計費用：13300円", output)

    def test_model_route_labels_low_confidence_and_estimated_cost(self):
        output = render_model_route([{"time": "未確認", "confidence": "low"}], {
            "transport": 1, "lodging": 2, "food": 3, "admission": 4,
            "confidence": {"transport": "high", "lodging": "unknown", "food": "high", "admission": "high"},
        })
        self.assertIn("情報未確定", output)
        self.assertIn("概算費用：10円", output)

    def test_model_route_shows_unconfirmed_for_null_fields(self):
        output = render_model_route([{"time": "09:00", "schedule": None, "cost": None, "confidence": "high"}], {
            "transport": 0, "lodging": 0, "food": 0, "admission": 0,
            "confidence": {"transport": "high", "lodging": "high", "food": "high", "admission": "high"},
        })
        self.assertIn("スケジュール：未確認", output)
        self.assertIn("費用：未確認", output)
        self.assertNotIn("None", output)

    def test_ready_session_creates_a_data_only_generation_time_research_request(self):
        session = PlannerSession(started=True, step=9, answers={key: "x" for key, _ in __import__("travel.planner", fromlist=["QUESTIONS"]).QUESTIONS})
        request = research_request(session, "profile-opaque", "trace-3")
        self.assertEqual(request["experience_value_policy"]["priority_dimensions"], ["scenery", "place_appeal", "food"])
        self.assertEqual(request["experience_value_policy"]["improvement_evidence"], "qualitative_comment_only")
        self.assertIn("route_provider", request["source_targets"][1]["source_types"])
        self.assertEqual(request["requirements"]["destination"], "x")
