"""Validated, evidence-backed detailed travel itinerary output."""

import math


def _text(value):
    return isinstance(value, str) and value.strip()


def _amount(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def validate_detailed_itinerary(proposal):
    """Return human-readable validation failures; never fill missing travel facts."""
    issues = []
    if not isinstance(proposal, dict):
        return ["itinerary proposal must be an object"]
    for field in ("primary", "spot_alternatives", "rainy_day_alternatives", "food_options", "lodging_options"):
        if not isinstance(proposal.get(field), list) or not proposal[field]:
            issues.append(f"{field} must be a nonempty list")
    totals = proposal.get("cost_totals")
    if not isinstance(totals, dict) or any(not _amount(totals.get(key)) for key in ("transport", "lodging", "food", "admission")):
        issues.append("cost_totals must include nonnegative transport, lodging, food, and admission amounts")
    for index, item in enumerate(proposal.get("primary", [])):
        required = ("time", "schedule", "place", "label", "transport_mode", "transport_duration_minutes", "route", "cost", "evidence_id")
        if not isinstance(item, dict) or any(not _text(item.get(key)) for key in required if key not in ("transport_duration_minutes", "cost")):
            issues.append(f"primary[{index}] is missing required itinerary fields")
            continue
        if item.get("label") not in ("王道", "穴場"):
            issues.append(f"primary[{index}].label must be 王道 or 穴場")
        if item.get("transport_mode") not in ("公共交通機関", "タクシー", "レンタカー", "徒歩"):
            issues.append(f"primary[{index}].transport_mode is invalid")
        if not isinstance(item.get("transport_duration_minutes"), int) or item["transport_duration_minutes"] < 0 or not _amount(item.get("cost")):
            issues.append(f"primary[{index}] requires nonnegative duration and cost")
        if item.get("transport_mode") == "公共交通機関" and any(not _text(item.get(key)) for key in ("line_name", "station_name", "departure_time")):
            issues.append(f"primary[{index}] public transport requires line_name, station_name, and departure_time")
    for field in ("spot_alternatives", "rainy_day_alternatives"):
        for index, item in enumerate(proposal.get(field, [])):
            if not isinstance(item, dict) or any(not _text(item.get(key)) for key in ("spot", "reason", "evidence_id")):
                issues.append(f"{field}[{index}] needs spot, reason, and evidence_id")
    for index, item in enumerate(proposal.get("food_options", [])):
        if (not isinstance(item, dict) or any(not _text(item.get(key)) for key in ("name", "specialty", "evidence_id"))
                or not isinstance(item.get("rating"), (int, float)) or isinstance(item.get("rating"), bool) or not 0 <= item["rating"] <= 5
                or not isinstance(item.get("review_count"), int) or isinstance(item.get("review_count"), bool) or item["review_count"] < 0):
            issues.append(f"food_options[{index}] needs name, rating, review_count, specialty, and evidence_id")
    if isinstance(proposal.get("food_options"), list) and len(proposal["food_options"]) < 2:
        issues.append("food_options must offer multiple restaurants")
    for index, item in enumerate(proposal.get("lodging_options", [])):
        if (not isinstance(item, dict) or any(not _text(item.get(key)) for key in ("name", "convenience", "comfort", "evidence_id"))
                or not _amount(item.get("nightly_cost"))):
            issues.append(f"lodging_options[{index}] needs name, nightly_cost, convenience, comfort, and evidence_id")
    if "map_points" in proposal:
        if not isinstance(proposal["map_points"], list) or not proposal["map_points"]:
            issues.append("map_points must be a nonempty list when provided")
        for index, point in enumerate(proposal.get("map_points", [])):
            if (not isinstance(point, dict) or any(not _text(point.get(key)) for key in ("label", "evidence_id"))
                    or not isinstance(point.get("latitude"), (int, float)) or isinstance(point.get("latitude"), bool)
                    or not isinstance(point.get("longitude"), (int, float)) or isinstance(point.get("longitude"), bool)
                    or not -90 <= point["latitude"] <= 90 or not -180 <= point["longitude"] <= 180):
                issues.append(f"map_points[{index}] needs label, valid coordinates, and evidence_id")
    return issues


def evidence_ids(proposal):
    """Return all cited IDs after structural validation."""
    ids = {item["evidence_id"] for item in proposal["primary"]}
    for field in ("spot_alternatives", "rainy_day_alternatives", "food_options", "lodging_options"):
        ids.update(item["evidence_id"] for item in proposal[field])
    ids.update(point["evidence_id"] for point in proposal.get("map_points", []))
    return ids


def render_detailed_itinerary(proposal):
    """Render the required Japanese traveler-facing fields from validated data."""
    issues = validate_detailed_itinerary(proposal)
    if issues:
        raise ValueError("; ".join(issues))
    rows = []
    for item in proposal["primary"]:
        route = item["route"]
        if item["transport_mode"] == "公共交通機関":
            route = f"{route}（{item['line_name']}／{item['station_name']}／{item['departure_time']}）"
        rows.append(f"時間：{item['time']}｜スケジュール：{item['schedule']}｜場所：{item['place']}｜{item['label']}｜費用：{item['cost']}円｜備考：移動 {item['transport_mode']} {item['transport_duration_minutes']}分｜移動ルート：{route}")
    rows.append("食事候補：" + " ／ ".join(f"{item['name']}（評価 {item['rating']}・口コミ {item['review_count']}件・名物 {item['specialty']}）" for item in proposal["food_options"]))
    rows.append("宿泊候補：" + " ／ ".join(f"{item['name']}（{item['nightly_cost']}円、利便性：{item['convenience']}、快適さ：{item['comfort']}）" for item in proposal["lodging_options"]))
    rows.append("スポット代案：" + " ／ ".join(item["spot"] for item in proposal["spot_alternatives"]))
    rows.append("雨天時代案：" + " ／ ".join(item["spot"] for item in proposal["rainy_day_alternatives"]))
    totals = proposal["cost_totals"]
    total = sum(totals[key] for key in ("transport", "lodging", "food", "admission"))
    rows.append(f"合計費用：{total}円（移動費：{totals['transport']}円、宿泊費：{totals['lodging']}円、食費：{totals['food']}円、入場料：{totals['admission']}円）")
    return "\n".join(rows)
