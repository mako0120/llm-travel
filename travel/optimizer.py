"""Bounded deterministic candidate selection over a supplied route fixture."""

from time import monotonic
import math


def _valid_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def optimize(candidates, route_provider, *, start_id, budget, available_minutes,
             max_evaluations=1_000, timeout_seconds=1.0, clock=monotonic):
    """Return an explicit state; never invent travel data or relax constraints."""
    if (not isinstance(candidates, list) or not isinstance(start_id, str)
            or not _valid_number(budget) or budget < 0
            or type(available_minutes) is not int or available_minutes < 0
            or type(max_evaluations) is not int or max_evaluations < 1
            or not _valid_number(timeout_seconds) or timeout_seconds < 0):
        return {"state": "invalid_input", "selected": [], "reason": "invalid optimizer input"}
    started = clock()
    selected, used_cost, used_minutes, current, evaluations = [], 0, 0, start_id, 0
    def ranking(item):
        if not isinstance(item, dict) or not _valid_number(item.get("score")):
            return (float("inf"), "")
        return (-item["score"], str(item.get("id", "")))

    remaining = sorted(candidates, key=ranking)
    while remaining:
        if clock() - started >= timeout_seconds:
            return {"state": "timeout", "selected": selected, "reason": "search deadline reached", "evaluations": evaluations}
        if evaluations >= max_evaluations:
            return {"state": "timeout", "selected": selected, "reason": "search evaluation limit reached", "evaluations": evaluations}
        candidate = remaining.pop(0)
        evaluations += 1
        if not isinstance(candidate, dict) or not isinstance(candidate.get("id"), str) or not candidate["id"]:
            continue
        if (type(candidate.get("visit_minutes")) is not int or candidate["visit_minutes"] < 0
                or not _valid_number(candidate.get("cost")) or candidate["cost"] < 0
                or not _valid_number(candidate.get("score"))
                or candidate.get("source", {}).get("verification_status") != "verified"):
            continue
        route = route_provider.route_minutes(current, candidate["id"])
        if route.state == "unconfigured":
            return {"state": "unconfigured", "selected": selected, "reason": "route provider is not configured", "evaluations": evaluations}
        if route.state != "available":
            continue
        total_minutes = used_minutes + route.value + candidate["visit_minutes"]
        total_cost = used_cost + candidate["cost"]
        if total_minutes > available_minutes or total_cost > budget:
            continue
        selected.append(dict(candidate, inbound_transit_minutes=route.value))
        used_minutes, used_cost, current = total_minutes, total_cost, candidate["id"]
    state = "success" if selected else "infeasible"
    return {"state": state, "selected": selected, "total_minutes": used_minutes,
            "total_cost": used_cost, "evaluations": evaluations}
