"""Run one local ChatGPT/Codex candidate turn and one independent Claude review.

Usage:
  python scripts/run_dual_agent_review.py input.json output.json

The input is a local JSON object with nonempty `requirements` and optional
`evidence`. This script is intentionally manual: it invokes the locally signed
in Codex and Claude CLIs only after an operator starts it. It never runs from
the web application, reads API keys, accepts arbitrary executable commands, or
books/pays/publishes anything.
"""

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from travel.agent_handoff import build_research_brief, run_claude_review, run_codex_proposal


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print("usage: python scripts/run_dual_agent_review.py input.json output.json", file=sys.stderr)
        return 2
    source, target = (Path(value).resolve() for value in argv)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        brief = build_research_brief(payload.get("requirements"), payload.get("evidence", []))
        proposal = run_codex_proposal(brief, PROJECT_ROOT)
        review = run_claude_review(proposal["proposal"], brief)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"research_brief": brief, "chatgpt_codex": proposal, "claude": review}, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"review failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
