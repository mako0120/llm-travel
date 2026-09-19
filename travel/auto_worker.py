"""Personal-use automation for a single trusted operator (Issue #54, Phase 1.5).

This module must never be imported by travel.webapp. The public web server
stays exactly as it is today: it only writes research requests to the local
database. Only a separate process the operator starts by hand (see
scripts/run_auto_research_worker.py) imports this module, holds a GitHub
token, and is allowed to post to GitHub. Keeping these two processes and
their credentials apart is the entire point of this design; do not merge
this module's responsibilities back into webapp.py.

The worker never invents opening hours, prices, or transit facts. The free
public sources it uses (Nominatim/Wikimedia/Open-Meteo) only ever produce
"unverified" evidence, and record_itinerary_proposal() already refuses to
save an itinerary that cites anything other than fresh, verified evidence.
So this worker cannot, by construction, turn a web search into a saved,
confirmed itinerary -- it can only collect candidates and run the same
Codex-proposes/Claude-reviews audit that a human would otherwise run by
hand, then post that audit outcome to GitHub as a record.
"""

import json
import os
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from travel.agent_handoff import build_research_brief, run_claude_review, run_codex_proposal
from travel.free_sources import collect_public_evidence


GITHUB_TOKEN_ENV_VAR = "LLM_TRAVEL_AUTO_WORKER_GITHUB_TOKEN"


def auto_research_enabled(environment=None):
    """The worker may run only when explicitly opted in and never in commercial mode."""
    source = os.environ if environment is None else environment
    if source.get("LLM_TRAVEL_DEPLOYMENT_MODE", "research").lower() == "commercial":
        return False
    return source.get("LLM_TRAVEL_AUTO_RESEARCH", "").strip() == "1"


def _default_poster(url, token, body):
    request = Request(url, data=json.dumps({"body": body}).encode("utf-8"), method="POST",
                       headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                "Content-Type": "application/json", "User-Agent": "llm-travel-auto-worker/0.1"})
    with urlopen(request, timeout=15) as response:  # nosec B310: fixed GitHub API host only
        return response.status


def post_audit_comment(repo_slug, issue_number, token, body, poster=_default_poster):
    """Post one audit record to GitHub. Only the worker process ever calls this."""
    if not isinstance(repo_slug, str) or "/" not in repo_slug:
        raise ValueError("repo_slug must be 'owner/repo'")
    if not isinstance(issue_number, int) or issue_number <= 0:
        raise ValueError("issue_number must be a positive integer")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("a GitHub token is required to post an audit record")
    url = f"https://api.github.com/repos/{repo_slug}/issues/{issue_number}/comments"
    try:
        return poster(url, token, body)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"could not post the audit record to GitHub: {exc}") from exc


def process_pending_run(repo, run, workspace, codex_runner=subprocess.run, claude_runner=subprocess.run):
    """Run one automated research/review cycle for a single 'requested' run.

    Returns a summary dict describing the outcome. Never marks a run "ready"
    itself; record_itinerary_proposal (unchanged) is the only path that can
    do that, and it still requires fresh verified evidence and both reviews.
    """
    destination = run["requirements"].get("destination")
    if not isinstance(destination, str) or not destination.strip():
        return {"run_id": run["id"], "outcome": "skipped", "reason": "requirements.destination is missing"}

    _, candidates = collect_public_evidence(destination)
    saved = []
    for item in candidates:
        try:
            saved.append(repo.record_evidence(run["id"], item))
        except ValueError:
            continue
    if not saved:
        return {"run_id": run["id"], "outcome": "unresolved", "reason": "no usable public evidence was found"}

    current = repo.get_research_run(run["id"])
    brief = build_research_brief(run["requirements"], current["evidence"])

    try:
        codex_result = run_codex_proposal(brief, workspace, runner=codex_runner)
    except (RuntimeError, ValueError) as exc:
        return {"run_id": run["id"], "outcome": "unresolved", "reason": f"codex proposal unavailable: {exc}",
                "evidence_collected": len(saved)}
    proposal_text = codex_result["proposal"]

    try:
        parsed_proposal = json.loads(proposal_text)
    except json.JSONDecodeError:
        parsed_proposal = None
    if isinstance(parsed_proposal, dict) and parsed_proposal.get("state") == "needs_research":
        return {"run_id": run["id"], "outcome": "unresolved", "reason": "codex reported needs_research",
                "missing_evidence": parsed_proposal.get("missing_evidence", []), "evidence_collected": len(saved)}

    try:
        review = run_claude_review(proposal_text, brief, runner=claude_runner)
    except (RuntimeError, ValueError) as exc:
        return {"run_id": run["id"], "outcome": "unresolved", "reason": f"claude review unavailable: {exc}",
                "evidence_collected": len(saved)}

    decision = review["review"]["decision"]
    if decision != "approved":
        return {"run_id": run["id"], "outcome": "unresolved", "reason": "claude requested revision",
                "required_evidence": review["review"].get("required_evidence", []), "evidence_collected": len(saved)}

    # Only public/unverified evidence is available through this path, so
    # record_itinerary_proposal (which requires fresh *verified* evidence)
    # cannot and must not be called here even on approval. A human or Codex,
    # working from an official source, must still finish a savable itinerary.
    return {"run_id": run["id"], "outcome": "reviewed_not_saved", "evidence_collected": len(saved),
            "reason": "Claude approved how the proposal used the supplied evidence, but it remains unverified, "
                      "so no confirmed itinerary was saved. See /api/workspace/runs/{id}/draft for a visible draft.",
            "codex_executed_at": codex_result["executed_at"], "claude_executed_at": review["executed_at"]}
