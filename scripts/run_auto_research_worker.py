"""Personal-use worker that turns pending research runs into a local audit log.

See Issue #54, Phase 1.5. Run this only on a machine you control, never
inside the public web server process.

This script never holds or sends a GitHub token. AGENTS.md prohibits any
runtime in this project from holding GitHub write or deploy credentials --
not only the public web server -- so results are appended to a local,
operator-owned log file only. If you want a record on GitHub, copy an
entry from that log and post it yourself (GitHub web UI or your own `gh`
CLI session); that also gives you a chance to redact anything sensitive
before it becomes public.

Usage:
  LLM_TRAVEL_AUTO_RESEARCH=1 python scripts/run_auto_research_worker.py [--once]
"""

import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from travel.auto_worker import append_audit_log_entry, auto_research_enabled, process_pending_run
from travel.storage import Repository


def run_once(repo, workspace, log_path=None):
    """Process every currently 'requested' run once. Returns the list of summaries."""
    summaries = []
    for run in repo.list_research_runs(state="requested"):
        summary = process_pending_run(repo, run, workspace)
        summaries.append(summary)
        if log_path:
            append_audit_log_entry(log_path, summary)
    return summaries


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not auto_research_enabled():
        print('LLM_TRAVEL_AUTO_RESEARCH is not "1", or LLM_TRAVEL_DEPLOYMENT_MODE is "commercial"; refusing to run.', file=sys.stderr)
        return 1
    try:
        interval = float(os.environ.get("LLM_TRAVEL_AUTO_WORKER_INTERVAL_SECONDS", "60"))
    except ValueError:
        interval = 60.0
    db_path = os.environ.get("LLM_TRAVEL_DB", "data/travel.sqlite3")
    log_path = os.environ.get("LLM_TRAVEL_AUTO_WORKER_LOG", "data/auto_worker_audit.log")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    repo = Repository(db_path)
    try:
        run_forever = "--once" not in argv
        while True:
            for summary in run_once(repo, PROJECT_ROOT, log_path):
                print(summary)
            if not run_forever:
                break
            time.sleep(interval)
    finally:
        repo.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
