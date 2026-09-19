"""Contracts for explicitly run Codex/Claude web research.

This module never launches an agent or scrapes a provider.  It defines the
data boundary for results returned by an independently run research turn.
"""

from urllib.parse import urlsplit


AGENT_WEB_SOURCE_TYPES = {
    "Google web research": {"google.com", "google.co.jp", "googleusercontent.com", "maps.google.com"},
    "TikTok discovery": {"tiktok.com", "www.tiktok.com", "vm.tiktok.com"},
}


def agent_web_research_request(requirements):
    """Create an explicit, data-only brief for an independent web-research turn."""
    if not isinstance(requirements, dict) or not isinstance(requirements.get("destination"), str) or not requirements["destination"].strip():
        raise ValueError("requirements.destination must be a nonempty string")
    return {
        "format": "llm-travel-agent-web-research", "version": "1.0",
        "requirements": requirements,
        "sources": [
            {"source_type": "Google web research", "purpose": "discovery leads and official-site links",
             "rules": ["Record the result URL and retrieval time.", "Do not assert hours, prices, ratings, availability, routes, or timetables without official verification."]},
            {"source_type": "TikTok discovery", "purpose": "traveler-interest discovery links only",
             "rules": ["Use only an accessible public TikTok URL or an approved official API result.", "Do not convert a video into a factual travel claim or recommendation without separate evidence."]},
        ],
        "output_rule": "Return evidence objects only. Every object remains unverified until a human verifies an authoritative source.",
    }


def validate_agent_web_evidence(evidence):
    """Validate a URL-backed agent result before persistence or prompt use."""
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be an object")
    if evidence.get("agent") not in {"codex", "claude"}:
        raise ValueError("agent web research must identify codex or claude")
    source_type = evidence.get("source_type")
    if source_type not in AGENT_WEB_SOURCE_TYPES:
        raise ValueError("source_type is not an allowed agent web research source")
    url = evidence.get("url")
    parsed = urlsplit(url) if isinstance(url, str) else None
    if not parsed or parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("agent web research requires an https source URL")
    hostname = parsed.hostname.lower()
    if not any(hostname == domain or hostname.endswith("." + domain) for domain in AGENT_WEB_SOURCE_TYPES[source_type]):
        raise ValueError("source URL does not match the declared research source")
    if evidence.get("verification_status") != "unverified":
        raise ValueError("agent web research must remain unverified")
    return evidence
