"""Deterministic, non-factual itinerary drafts derived from collected evidence."""


def create_research_draft(requirements, evidence):
    """Create a visible planning draft without inventing operational travel facts.

    This is intentionally not a detailed itinerary and cannot be saved or published.
    Every suggested stop is tied to an unverified evidence record supplied by the
    explicit research action.  Times, fares, hours and reservations stay unknown.
    """
    if not isinstance(requirements, dict):
        raise ValueError("requirements must be an object")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("one or more evidence records are required")
    destination = str(requirements.get("destination", "")).strip()
    if not destination:
        raise ValueError("requirements.destination is required")
    try:
        nights = max(0, int(requirements.get("nights", 0)))
    except (TypeError, ValueError):
        nights = 0
    days = max(1, nights + 1)
    candidates = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        evidence_id = str(item.get("id", "")).strip()
        if title and evidence_id:
            candidates.append({"title": title, "evidence_id": evidence_id,
                               "source": str(item.get("source_type", "候補情報"))})
    if not candidates:
        raise ValueError("evidence needs titles and ids")
    # Prefer named discovery leads over broad areas or operators.  The fallback
    # preserves a visible research draft when a small destination has no such
    # result, while keeping every entry tied to its original evidence.
    generic_suffixes = ("市", "区", "府", "都", "県")
    generic_terms = ("交通局", "観光協会", "観光案内")
    generic_titles = {"観光", "観光地", "旅行", "日本"}
    discovery = [candidate for candidate in candidates if candidate["source"] == "Wikimedia"]
    specific = [candidate for candidate in discovery
                if not candidate["title"].endswith(generic_suffixes)
                and not any(term in candidate["title"] for term in generic_terms)]
    specific = [candidate for candidate in specific if candidate["title"] not in generic_titles]
    if specific:
        candidates = specific
    elif discovery:
        candidates = discovery
    itinerary_days = []
    for number in range(1, days + 1):
        candidate = candidates[(number - 1) % len(candidates)]
        itinerary_days.append({
            "day": number,
            "label": "王道" if number == 1 else "候補",
            "focus": candidate["title"],
            "evidence_id": candidate["evidence_id"],
            "source": candidate["source"],
            "time": "未確定",
            "transport": "未確認（公式時刻表・経路の検証が必要）",
            "cost": "未確定",
        })
    return {
        "kind": "research_draft",
        "status": "needs_research",
        "title": f"{destination} {nights}泊{days}日・調査下書き",
        "destination": destination,
        "days": itinerary_days,
        "evidence_count": len(candidates),
        "notice": "明示実行した情報収集から自動作成した下書きです。候補は未検証で、営業時間・時刻・運賃・料金・予約可否は含めていません。",
        "save_blocked_reason": "公式根拠の検証と Codex / Claude の独立レビューが未完了です。",
    }
