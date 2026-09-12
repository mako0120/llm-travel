"""Japanese travel-planner conversation and safe model-route presentation."""

from dataclasses import dataclass, field
from decimal import Decimal


START_PROMPT = "AI旅行計画を作成しますか？"
QUESTIONS = (
    ("home_region", "ありがとうございます！ まずは、あなたのお住まいの地域を教えていただけますか？この情報をもとに、移動費などの計画を立てやすくなります。"),
    ("destination", "行き先について教えていただけますか？行きたい国や地域、都市はありますか？特定の場所があればお知らせください。"),
    ("nights", "旅行は何泊しますか？"),
    ("themes", "どのアクティビティやテーマに興味がありますか？観光名所、自然散策、グルメツアー、温泉、神社、テーマパークなど具体的に教えていただけると嬉しいです。"),
    ("spot_preference", "穴場スポットと王道観光地、どちらも希望ですか？特に重視したい方があれば教えてください。"),
    ("budget", "旅行全体の予算はどれくらいを想定していますか?"),
    ("lodging_type", "宿泊はどのようなタイプを希望しますか？ホテル、Airbnb、リゾートなどから選んでください。"),
    ("transport", "現地での移動手段について、レンタカー、公共交通機関、自家用車、タクシーなど、どのような方法がお好みですか？"),
    ("special_requests", "特別に希望することや不安な点があれば教えてください。たとえば、健康に関する配慮が必要、子連れ旅行、言語のサポートが必要などです。"),
)


PLANNER_SYSTEM_PROMPT = """あなたは旅行プランナーです。ユーザーの旅行条件を確認し、根拠がある情報だけで具体的なモデルルートを作成します。
計画は時間単位の行動予定、王道・穴場の区分、移動手段・所要時間、公共交通の路線名・駅名・時刻、タクシー・レンタカー移動時間、食事候補、宿泊候補、移動費・宿泊費・食費・入場料・合計費用、余裕時の候補を含めます。
飲食は評価・口コミ数・地元性を根拠付きで比較します。Google、TikTok、食べログなどから得た情報は、取得時刻・出典・検証状態を保存し、料金・営業時間・時刻表をSNSだけで確定しません。
情報が未設定・未確認・期限切れなら、数値や時刻表を創作せず、その状態を明示します。予約、決済、安全判断を自動実行しません。"""


@dataclass
class PlannerSession:
    started: bool = False
    step: int = 0
    answers: dict = field(default_factory=dict)

    @property
    def ready(self):
        return self.started and self.step == len(QUESTIONS)


def _yes(value):
    return isinstance(value, str) and value.strip().lower() in {"はい", "yes", "y"}


def next_turn(session, user_message=None):
    """Advance one turn. Until ready, replies are only the required question."""
    if not isinstance(session, PlannerSession):
        raise ValueError("session must be a PlannerSession")
    if not session.started:
        if not _yes(user_message):
            return session, {"state": "awaiting_consent", "reply": START_PROMPT}
        session = PlannerSession(started=True)
        return session, {"state": "collecting", "step": 1, "reply": QUESTIONS[0][1]}
    if session.ready:
        return session, {"state": "ready", "reply": "旅行計画に必要な条件は確認済みです。"}
    if not isinstance(user_message, str) or not user_message.strip():
        return session, {"state": "collecting", "step": session.step + 1, "reply": QUESTIONS[session.step][1]}
    key = QUESTIONS[session.step][0]
    updated = dict(session.answers, **{key: user_message.strip()})
    step = session.step + 1
    session = PlannerSession(started=True, step=step, answers=updated)
    if session.ready:
        return session, {"state": "ready", "reply": "詳細な旅行プランを作成します。", "planning_brief": planning_brief(session)}
    return session, {"state": "collecting", "step": step + 1, "reply": QUESTIONS[step][1]}


def planning_brief(session):
    if not isinstance(session, PlannerSession) or not session.ready:
        raise ValueError("all planner questions must be answered before creating a planning brief")
    return {"contract_version": "1.0", "trace_id": "planner-session", "requirements": session.answers,
            "system_prompt": PLANNER_SYSTEM_PROMPT,
            "required_retrieval": ["official transport timetable", "official opening hours and prices", "lodging availability", "restaurant ratings and review counts", "source freshness"],
            "output_format": ["時間", "スケジュール", "場所", "費用", "備考", "移動ルート"],
            "unconfigured_behavior": "Do not invent ratings, timetable times, prices, routes, or availability."}


def research_request(session, profile_id, trace_id):
    """Create a data-only request for Claude or Codex to research at generation time."""
    if not isinstance(profile_id, str) or not profile_id.strip() or not isinstance(trace_id, str) or not trace_id.strip():
        raise ValueError("profile_id and trace_id must be nonempty strings")
    brief = planning_brief(session)
    return {"contract_version": "1.0", "trace_id": trace_id, "profile_id": profile_id,
            "requirements": brief["requirements"],
            "source_targets": [
                {"query": "opening hours prices reservations", "location": session.answers["destination"], "category": "attractions", "freshness_minutes": 1440, "source_types": ["official"]},
                {"query": "route stations timetable duration", "location": session.answers["destination"], "category": "transport", "freshness_minutes": 60, "source_types": ["official", "route_provider"]},
                {"query": "restaurants ratings reviews local specialties", "location": session.answers["destination"], "category": "food", "freshness_minutes": 1440, "source_types": ["Google", "Tabelog", "official"]},
                {"query": "hidden gems discovery", "location": session.answers["destination"], "category": "discovery", "freshness_minutes": 10080, "source_types": ["TikTok", "Google"]},
            ],
            "batch_unit": "section", "retry_limit": 1, "timeout_seconds": 30}


def render_model_route(rows, cost_totals):
    """Format a retrieved-and-validated route. Missing facts remain 未確認."""
    if not isinstance(rows, list) or not isinstance(cost_totals, dict):
        raise ValueError("rows and cost_totals must be objects of the expected type")
    lines = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each route row must be an object")
        value = lambda key: str(row.get(key, "未確認"))
        lines.append("時間：{0}｜スケジュール：{1}｜場所：{2}｜費用：{3}｜備考：{4}｜移動ルート：{5}".format(
            value("time"), value("schedule"), value("place"), value("cost"), value("notes"), value("route")))
    amounts = []
    for key in ("transport", "lodging", "food", "admission"):
        amount = cost_totals.get(key, 0)
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise ValueError("cost totals must be numeric")
        amounts.append(Decimal(str(amount)))
    lines.append("合計費用：{0}円（移動費：{1}円、宿泊費：{2}円、食費：{3}円、入場料：{4}円）".format(
        sum(amounts), *amounts))
    return "\n".join(lines)
