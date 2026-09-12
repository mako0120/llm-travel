"""Deterministic plan checks; supplied provenance is checked, not independently verified."""

from datetime import datetime, timezone
from decimal import Decimal, localcontext
import math
from statistics import mean, median, pstdev
from urllib.parse import urlsplit


def _number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _timestamp(value):
    if not isinstance(value, str):
        return None
    if "Z" in value and not value.endswith("Z"):
        return None
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.utcoffset() is not None else None
    except (ValueError, OverflowError):
        return None


def validate_plan(plan, now=None, require_verified=False):
    """Return issues without accepting missing evidence as valid.

    Required fields: start/end (aware ISO timestamps), budget,
    required_activity_ids, and activities. Each activity requires id, start/end,
    cost, transit_minutes (travel before this activity), and source containing
    url and expires_at. A valid URL is provenance metadata, not proof of accuracy.
    """
    issues = []

    def add(code, path, message):
        issues.append({"code": code, "path": path, "message": message})

    if not isinstance(plan, dict):
        add("invalid_plan", "plan", "Plan must be an object.")
        return issues
    if now is None:
        now = datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        add("invalid_now", "now", "Reference time must be timezone-aware.")
        return issues
    start, end = _timestamp(plan.get("start")), _timestamp(plan.get("end"))
    for key, value in (("start", start), ("end", end)):
        if value is None:
            add("invalid_time", key, "An ISO timestamp with timezone is required.")
    if start is not None and end is not None and end <= start:
        add("invalid_range", "end", "Plan end must follow start.")
    budget = plan.get("budget")
    if not _number(budget) or budget < 0:
        add("invalid_budget", "budget", "Budget must be finite and nonnegative.")
        budget = None
    required = plan.get("required_activity_ids")
    if not isinstance(required, list) or any(not isinstance(x, str) or not x.strip() for x in required):
        add("invalid_required", "required_activity_ids", "A list of nonempty IDs is required.")
        required = []
    activities = plan.get("activities")
    if not isinstance(activities, list):
        add("invalid_activities", "activities", "Activities must be a list.")
        return issues
    if not activities:
        add("empty_activities", "activities", "At least one activity is required.")
    seen = set()
    costs = []
    previous_end = start
    previous_start = None
    for i, activity in enumerate(activities):
        path = f"activities[{i}]"
        if not isinstance(activity, dict):
            add("invalid_activity", path, "Activity must be an object.")
            continue
        identifier = activity.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            add("invalid_id", path + ".id", "A nonempty activity ID is required.")
        elif identifier in seen:
            add("duplicate_id", path + ".id", "Activity IDs must be unique.")
        else:
            seen.add(identifier)
        a_start = _timestamp(activity.get("start"))
        a_end = _timestamp(activity.get("end"))
        for key, value in (("start", a_start), ("end", a_end)):
            if value is None:
                add("invalid_time", path + "." + key, "An ISO timestamp with timezone is required.")
        if a_start is not None and a_end is not None and a_end <= a_start:
            add("invalid_range", path, "Activity end must follow start.")
        if a_start is not None:
            if start is not None and a_start < start:
                add("outside_plan", path + ".start", "Activity starts before the plan.")
            if previous_start is not None and a_start < previous_start:
                add("unordered", path + ".start", "Activities must be ordered by start time.")
            if previous_end is not None and a_start < previous_end:
                add("overlap", path + ".start", "Activity overlaps the previous activity.")
            previous_start = a_start
        if a_end is not None and end is not None and a_end > end:
            add("outside_plan", path + ".end", "Activity ends after the plan.")
        transit = activity.get("transit_minutes")
        if not _number(transit) or transit < 0:
            add("invalid_transit", path + ".transit_minutes", "Transit must be finite nonnegative minutes.")
        elif a_start is not None and previous_end is not None:
            if (a_start - previous_end).total_seconds() / 60 < transit:
                add("insufficient_transit", path, "The preceding gap is too short for transit.")
        if a_end is not None:
            previous_end = max(previous_end, a_end) if previous_end else a_end
        cost = activity.get("cost")
        if not _number(cost) or cost < 0:
            add("invalid_cost", path + ".cost", "Cost must be finite and nonnegative.")
        else:
            costs.append(Decimal(str(cost)))
        source = activity.get("source")
        if not isinstance(source, dict):
            add("missing_source", path + ".source", "Source provenance is required.")
        else:
            url = source.get("url")
            try:
                parts = urlsplit(url) if isinstance(url, str) else None
                valid_url = parts and parts.scheme in ("http", "https") and parts.hostname and not any(c.isspace() for c in url)
            except ValueError:
                valid_url = False
            if not valid_url:
                add("invalid_source", path + ".source.url", "A source HTTP(S) URL is required.")
            expiry = _timestamp(source.get("expires_at"))
            if expiry is None:
                add("invalid_source_expiry", path + ".source.expires_at", "A timezone-aware source expiry is required.")
            elif expiry <= now:
                add("expired_source", path + ".source.expires_at", "Source evidence has expired.")
            status = source.get("verification_status", "unverified")
            if status not in ("verified", "unverified"):
                add("invalid_source_status", path + ".source.verification_status", "Source verification status is invalid.")
            elif require_verified and status != "verified":
                add("unverified_source", path + ".source.verification_status", "Trip-ready plans require verified source evidence.")
    if budget is not None:
        # Preserve decimal currency boundaries across both tiny and large finite
        # floats. Precision covers the full float exponent span plus carry digits.
        with localcontext() as context:
            context.prec = 700 + len(str(len(costs)))
            if sum(costs, Decimal(0)) > Decimal(str(budget)):
                add("over_budget", "budget", "Activity costs exceed the budget.")
    for identifier in dict.fromkeys(required):
        if identifier not in seen:
            add("missing_required", "required_activity_ids", f"Required activity missing: {identifier}")
    return issues


def validate_trip_ready(plan, use_at=None):
    """Revalidate supplied plan evidence at presentation time, not save time."""
    return validate_plan(plan, now=use_at, require_verified=True)


def summarize_ratings(ratings):
    """Summarize numeric ratings in [1, 7]; reject invalid input explicitly."""
    if not isinstance(ratings, (list, tuple)):
        raise ValueError("Ratings must be a list or tuple.")
    if any(not _number(value) or not 1 <= value <= 7 for value in ratings):
        raise ValueError("Ratings must be finite numbers between 1 and 7 (not booleans).")
    if not ratings:
        return {"count": 0, "mean": None, "median": None, "stdev": None}
    return {"count": len(ratings), "mean": mean(ratings), "median": median(ratings), "stdev": pstdev(ratings)}
