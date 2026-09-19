"""Fetch real public evidence and build a visible (unverified) draft.

Unlike this project's sandboxed dev environments, a GitHub Actions runner
has ordinary internet access, so this script can make real calls to
Nominatim/Wikimedia/Open-Meteo instead of the network being blocked.

This is intentionally the free-source half only: it never invokes the
codex/claude CLIs (see travel/agent_handoff.py and
scripts/run_dual_agent_review.py for that, which require locally signed-in
CLIs and are not meant to run unattended in CI), and it never calls
Repository.record_itinerary_proposal(), so it can never produce a
saved/confirmed itinerary -- only the same "unverified candidates + a
draft with unknown times/costs" that this project always produces from
free sources alone.

Usage:
  python scripts/run_free_research_demo.py 京都 --nights 2 --out out
"""

import argparse
import json
from pathlib import Path
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from travel.draft_itinerary import create_research_draft
from travel.free_sources import collect_public_evidence
from travel.storage import Repository


def run(destination, nights, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _, candidates = collect_public_evidence(destination)

    with tempfile.TemporaryDirectory() as tmp:
        repo = Repository(Path(tmp) / "travel.sqlite3")
        try:
            requirements = {"destination": destination, "nights": nights}
            run_record = repo.create_research_run("actions-demo", requirements, [])
            saved = []
            for item in candidates:
                try:
                    saved.append(repo.record_evidence(run_record["id"], item))
                except ValueError:
                    continue
            (out_dir / "evidence.json").write_text(
                json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
            if not saved:
                (out_dir / "draft.json").write_text(
                    json.dumps({"error": "no usable public evidence was found for this destination"},
                               ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"No usable evidence found for {destination!r}; wrote evidence.json only.")
                return 1
            draft = create_research_draft(requirements, saved)
            (out_dir / "draft.json").write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Collected {len(saved)} real, unverified candidates for {destination!r}.")
            print(json.dumps(draft, ensure_ascii=False, indent=2))
            return 0
        finally:
            repo.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    parser.add_argument("--nights", type=int, default=1)
    parser.add_argument("--out", default="out")
    args = parser.parse_args(argv)
    return run(args.destination, args.nights, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
