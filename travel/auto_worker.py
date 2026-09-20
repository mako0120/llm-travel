"""Personal-use automation for a single trusted operator (Issue #54, Phase 1.5).

This module must never be imported by travel.webapp. The public web server
stays exactly as it is today: it only writes research requests to the local
database. Only a separate process the operator starts by hand (see
scripts/run_auto_research_worker.py) imports this module.

This worker does not hold or use a GitHub token at all. AGENTS.md prohibits
any runtime in this project from holding GitHub write or deploy credentials,
not only the public web server (see the receiver process in
scripts/github_webhook_bridge.py, which follows the same rule). Its outcome
is written to a local audit log only; if the operator wants a record on
GitHub, they post it themselves with their own already-authenticated tools
(the GitHub web UI or their own `gh` CLI session), which also gives them a
chance to redact anything sensitive before it becomes public.

The worker never invents opening hours, prices, or transit facts. The free
public sources it uses (Nominatim/Wikimedia/Open-Meteo) only ever produce
"unverified" evidence, and record_itinerary_proposal() already refuses to
save an itinerary that cites anything other than fresh, verified evidence.
So this worker cannot, by construction, turn a web search into a saved,
confirmed itinerary -- it can only collect candidates and run the same
Codex-proposes/Claude-reviews audit that a human would otherwise run by
hand, then record that audit outcome locally.
"""

import json
import os
import subprocess

from travel.agent_handoff import build_research_brief, run_claude_review, run_codex_proposal
from travel.free_sources import collect_public_evidence


_SUBPROCESS_FAILURE_TYPES = (RuntimeError, ValueError, subprocess.SubprocessError, OSError)


def _finish(repo, run_id, outcome, reason, **details):
    """Persist only the bounded status fields intended for operator-facing UI."""
    summary = {"run_id": run_id, "outcome": outcome, "reason": reason, **details}
    repo.record_auto_worker_result(run_id, summary)
    return summary


def auto_research_enabled(environment=None):
    """The worker may run only when explicitly opted in and never in commercial mode."""
    source = os.environ if environment is None else environment
    if source.get("LLM_TRAVEL_DEPLOYMENT_MODE", "research").lower() == "commercial":
        return False
    return source.get("LLM_TRAVEL_AUTO_RESEARCH", "").strip() == "1"


def append_audit_log_entry(log_path, summary):
    """Append one JSON-line audit record to a local, operator-owned log file.

    This never leaves the local machine on its own; nothing in this project
    posts it to GitHub automatically.
    """
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(summary, ensure_ascii=False) + "\n")


def process_pending_run(repo, run, workspace, codex_runner=subprocess.run, claude_runner=subprocess.run):
    """Run one automated research/review cycle for a single 'requested' run.

    Returns a summary dict describing the outcome. Never marks a run "ready"
    itself; record_itinerary_proposal (unchanged) is the only path that can
    do that, and it still requires fresh verified evidence and both reviews.

    Claims the run atomically first, so two overlapping worker instances
    cannot both process (and pay to process) the same run.
    """
    if not repo.claim_research_run(run["id"]):
        return _finish(repo, run["id"], "skipped", "already claimed by another worker instance")

    destination = run["requirements"].get("destination")
    if not isinstance(destination, str) or not destination.strip():
        return _finish(repo, run["id"], "skipped", "requirements.destination is missing")

    _, candidates = collect_public_evidence(destination)
    saved = []
    for item in candidates:
        try:
            saved.append(repo.record_evidence(run["id"], item))
        except ValueError:
            continue
    if not saved:
        # The claim above already moved this run out of "requested", so it
        # will not be picked up and retried again on every future poll.
        return _finish(repo, run["id"], "unresolved", "no usable public evidence was found")

    current = repo.get_research_run(run["id"])
    brief = build_research_brief(run["requirements"], current["evidence"])

    try:
        codex_result = run_codex_proposal(brief, workspace, runner=codex_runner)
    except _SUBPROCESS_FAILURE_TYPES as exc:
        return _finish(repo, run["id"], "unresolved", f"codex proposal unavailable: {exc}",
                       evidence_collected=len(saved))
    proposal_text = codex_result["proposal"]

    try:
        parsed_proposal = json.loads(proposal_text)
    except json.JSONDecodeError:
        parsed_proposal = None
    if isinstance(parsed_proposal, dict) and parsed_proposal.get("state") == "needs_research":
        return _finish(repo, run["id"], "unresolved", "codex reported needs_research",
                       missing_evidence=parsed_proposal.get("missing_evidence", []),
                       evidence_collected=len(saved))

    try:
        review = run_claude_review(proposal_text, brief, runner=claude_runner)
    except _SUBPROCESS_FAILURE_TYPES as exc:
        return _finish(repo, run["id"], "unresolved", f"claude review unavailable: {exc}",
                       evidence_collected=len(saved))

    decision = review["review"]["decision"]
    if decision != "approved":
        return _finish(repo, run["id"], "unresolved", "claude requested revision",
                       required_evidence=review["review"].get("required_evidence", []),
                       evidence_collected=len(saved))

    # Only public/unverified evidence is available through this path, so
    # record_itinerary_proposal (which requires fresh *verified* evidence)
    # cannot and must not be called here even on approval. A human or Codex,
    # working from an official source, must still finish a savable itinerary.
    return _finish(
        repo, run["id"], "reviewed_not_saved",
        "Claude approved how the proposal used the supplied evidence, but it remains unverified, "
        "so no confirmed itinerary was saved. See /api/workspace/runs/{id}/draft for a visible draft.",
        evidence_collected=len(saved), codex_executed_at=codex_result["executed_at"],
        claude_executed_at=review["executed_at"],
    )
