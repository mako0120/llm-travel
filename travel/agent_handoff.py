"""A local, explicit handoff format for independent ChatGPT/Codex and Claude turns."""

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from travel.storage import validate_evidence_payload
from travel.subprocess_env import safe_subprocess_env


def _local_cli(name):
    """Resolve a Windows `.cmd` shim when Python cannot execute the shell alias."""
    path = shutil.which(f"{name}.cmd") or shutil.which(name)
    if path is None:
        raise RuntimeError(f"{name} CLI is not available on PATH")
    return path


def build_research_brief(requirements, evidence):
    """Create a bounded prompt payload; supplied evidence remains unverified unless marked so."""
    if not isinstance(requirements, dict) or not requirements:
        raise ValueError("requirements must be a nonempty object")
    if not isinstance(evidence, list):
        raise ValueError("evidence must be a list")
    validated_evidence = [validate_evidence_payload(item) for item in evidence]
    return {
        "format": "llm-travel-agent-handoff", "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "requirements": requirements, "evidence": validated_evidence,
        "required_output": ["hourly itinerary", "mainstream_or_hidden_gem labels", "alternatives", "transport and costs", "uncertainties"],
        "rules": ["Do not invent current opening hours, prices, availability, ratings, review counts, route times, line names, stations, or departures.",
                  "Only cite supplied evidence. Mark all unverified evidence as unverified.",
                  "A public transport timetable needs an applicable operator-published GTFS or official source.",
                  "Do not book, pay, or publish anything."],
    }


def claude_review_prompt(chatgpt_proposal, research_brief):
    if not isinstance(chatgpt_proposal, str) or not chatgpt_proposal.strip():
        raise ValueError("chatgpt_proposal must be a nonempty string")
    return """You are the independent Claude research reviewer for a local travel-planning prototype.\n\nReview the proposal using only the supplied research brief. Return valid JSON with: decision (approved|needs_revision), rationale, unsupported_claims (array), required_evidence (array), and safe_alternatives (array). Do not invent travel facts, call tools, make bookings, or change files.\n\nRESEARCH_BRIEF:\n""" + json.dumps(research_brief, ensure_ascii=False) + "\n\nCHATGPT_OR_CODEX_PROPOSAL:\n" + chatgpt_proposal


def codex_proposal_prompt(research_brief):
    """Prompt the ChatGPT/Codex turn to make a candidate, never a factual claim."""
    return """You are the ChatGPT/Codex planning turn for a local travel research prototype. Use only the supplied research brief. Produce a Japanese candidate itinerary in valid JSON matching the detailed-itinerary contract when the evidence supports every required fact. If it does not, return a JSON object with state: needs_research and an explicit missing_evidence array. Never invent current times, route durations, prices, opening hours, ratings, review counts, availability, line names, stations, or departures. Do not call tools, change files, book, pay, or publish anything.\n\nRESEARCH_BRIEF:\n""" + json.dumps(research_brief, ensure_ascii=False)


def run_codex_proposal(research_brief, workspace, runner=subprocess.run):
    """Explicit local ChatGPT/Codex turn. The web server never calls this helper."""
    root = Path(workspace).resolve()
    if not root.is_dir():
        raise ValueError("workspace must be an existing directory")
    prompt = codex_proposal_prompt(research_brief)
    with tempfile.TemporaryDirectory(prefix="llm-travel-codex-") as directory:
        output = Path(directory) / "proposal.txt"
        executable = _local_cli("codex") if runner is subprocess.run else "codex"
        completed = runner(
            [executable, "exec", "-C", str(root), "--sandbox", "read-only", "--ephemeral", "--output-last-message", str(output), "-"],
            input=prompt, capture_output=True, text=True, timeout=240, check=False,
            env=safe_subprocess_env(),
        )
        if completed.returncode != 0 or not output.is_file():
            raise RuntimeError("ChatGPT/Codex proposal did not return a response")
        proposal = output.read_text(encoding="utf-8").strip()
    if not proposal:
        raise RuntimeError("ChatGPT/Codex proposal was empty")
    return {"author": "chatgpt_codex", "executed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "proposal": proposal}


def run_claude_review(chatgpt_proposal, research_brief, runner=subprocess.run):
    """Run Claude only when called by an explicit local command, not from web requests."""
    prompt = claude_review_prompt(chatgpt_proposal, research_brief)
    executable = _local_cli("claude") if runner is subprocess.run else "claude"
    schema = json.dumps({"type": "object", "properties": {
        "decision": {"enum": ["approved", "needs_revision"]},
        "rationale": {"type": "string"}, "unsupported_claims": {"type": "array"},
        "required_evidence": {"type": "array"}, "safe_alternatives": {"type": "array"},
    }, "required": ["decision", "rationale", "unsupported_claims", "required_evidence", "safe_alternatives"]})
    completed = runner(
        [executable, "-p", "--tools", "", "--output-format", "json", "--json-schema", schema, prompt],
        capture_output=True, text=True, timeout=120, check=False, env=safe_subprocess_env(),
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError("Claude review did not return a response")
    try:
        review = json.loads(completed.stdout)
        if isinstance(review, dict) and isinstance(review.get("result"), str):
            review = json.loads(review["result"])
    except json.JSONDecodeError as exc:
        raise ValueError("Claude review was not valid JSON") from exc
    if not isinstance(review, dict) or review.get("decision") not in {"approved", "needs_revision"}:
        raise ValueError("Claude review has an invalid decision")
    return {"author": "claude", "executed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "review": review}
