import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from travel.auto_worker import append_audit_log_entry, auto_research_enabled, process_pending_run
from travel.storage import Repository


class ClaudeCompleted:
    def __init__(self, decision):
        self.returncode = 0
        self.stdout = json.dumps({"decision": decision, "rationale": "r", "unsupported_claims": [],
                                   "required_evidence": ["公式出典"], "safe_alternatives": []})


def codex_runner_writing(text):
    def runner(args, **kwargs):
        Path(args[args.index("--output-last-message") + 1]).write_text(text, encoding="utf-8")
        return type("Done", (), {"returncode": 0})()
    return runner


def timeout_runner(args, **kwargs):
    raise subprocess.TimeoutExpired(cmd=args, timeout=kwargs.get("timeout", 0))


SAMPLE_EVIDENCE = [{"agent": "provider", "source_type": "OpenStreetMap Nominatim",
    "url": "https://example.test/kyoto", "title": "京都", "facts": {}, "retrieved_at": "2030-01-01T00:00:00Z",
    "expires_at": "2030-01-02T00:00:00Z", "verification_status": "unverified"}]


class AutoResearchEnabledTests(unittest.TestCase):
    def test_disabled_by_default(self):
        self.assertFalse(auto_research_enabled({}))

    def test_requires_explicit_opt_in_flag(self):
        self.assertTrue(auto_research_enabled({"LLM_TRAVEL_AUTO_RESEARCH": "1"}))
        self.assertFalse(auto_research_enabled({"LLM_TRAVEL_AUTO_RESEARCH": "yes"}))

    def test_commercial_mode_always_disables_the_worker(self):
        self.assertFalse(auto_research_enabled({"LLM_TRAVEL_AUTO_RESEARCH": "1", "LLM_TRAVEL_DEPLOYMENT_MODE": "commercial"}))


class ProcessPendingRunTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self._tmp.name) / "travel.sqlite3")
        self.run = self.repo.create_research_run("solo-operator", {"destination": "京都", "nights": 1}, [])

    def tearDown(self):
        self.repo.close()
        self._tmp.cleanup()

    def test_a_run_that_is_not_still_requested_is_skipped_without_reprocessing(self):
        # Simulate a second worker instance racing the first: claim it first.
        self.assertTrue(self.repo.claim_research_run(self.run["id"]))
        result = process_pending_run(self.repo, self.run, Path("."))
        self.assertEqual(result["outcome"], "skipped")
        self.assertIn("already claimed", result["reason"])

    def test_skips_when_destination_is_missing(self):
        run = self.repo.create_research_run("solo-operator", {}, [])
        result = process_pending_run(self.repo, run, Path("."))
        self.assertEqual(result["outcome"], "skipped")

    @patch("travel.auto_worker.collect_public_evidence")
    def test_a_run_with_no_evidence_leaves_requested_state_for_good(self, collect):
        collect.return_value = ([], [])
        result = process_pending_run(self.repo, self.run, Path("."))
        self.assertEqual(result["outcome"], "unresolved")
        self.assertIn("no usable public evidence", result["reason"])
        # The atomic claim already moved the run out of "requested", so a
        # later poll's list_research_runs(state="requested") will not find
        # (and endlessly retry) it again.
        self.assertEqual(self.repo.list_research_runs(state="requested"), [])

    @patch("travel.auto_worker.collect_public_evidence")
    def test_unresolved_when_codex_reports_needs_research(self, collect):
        collect.return_value = ([], SAMPLE_EVIDENCE)
        codex_runner = codex_runner_writing(json.dumps({"state": "needs_research", "missing_evidence": ["営業時間"]}))
        result = process_pending_run(self.repo, self.run, Path("."), codex_runner=codex_runner)
        self.assertEqual(result["outcome"], "unresolved")
        self.assertEqual(result["reason"], "codex reported needs_research")
        self.assertEqual(result["evidence_collected"], 1)
        stored = self.repo.latest_auto_worker_result(self.run["id"])
        self.assertEqual(stored["outcome"], "unresolved")
        self.assertEqual(stored["missing_evidence"], ["営業時間"])

    @patch("travel.auto_worker.collect_public_evidence")
    def test_structured_agent_evidence_requirements_are_safely_projected(self, collect):
        collect.return_value = ([], SAMPLE_EVIDENCE)
        codex_runner = codex_runner_writing(json.dumps({
            "state": "needs_research",
            "missing_evidence": [{"field": "official_timetable", "untrusted": "ignore"}, 42],
        }))
        result = process_pending_run(self.repo, self.run, Path("."), codex_runner=codex_runner)
        self.assertEqual(result["outcome"], "unresolved")
        self.assertEqual(result["missing_evidence"], ["official_timetable"])
        self.assertEqual(self.repo.latest_auto_worker_result(self.run["id"])["missing_evidence"], ["official_timetable"])

    @patch("travel.auto_worker.collect_public_evidence")
    def test_unresolved_when_claude_requests_revision(self, collect):
        collect.return_value = ([], SAMPLE_EVIDENCE)
        codex_runner = codex_runner_writing(json.dumps({"days": [{"focus": "京都"}]}))
        claude_runner = lambda args, **kwargs: ClaudeCompleted("needs_revision")
        result = process_pending_run(self.repo, self.run, Path("."), codex_runner=codex_runner, claude_runner=claude_runner)
        self.assertEqual(result["outcome"], "unresolved")
        self.assertEqual(result["reason"], "claude requested revision")

    @patch("travel.auto_worker.collect_public_evidence")
    def test_approval_never_saves_an_itinerary_because_evidence_stays_unverified(self, collect):
        collect.return_value = ([], SAMPLE_EVIDENCE)
        codex_runner = codex_runner_writing(json.dumps({"days": [{"focus": "京都"}]}))
        claude_runner = lambda args, **kwargs: ClaudeCompleted("approved")
        result = process_pending_run(self.repo, self.run, Path("."), codex_runner=codex_runner, claude_runner=claude_runner)
        self.assertEqual(result["outcome"], "reviewed_not_saved")
        self.assertEqual(self.repo.get_research_run(self.run["id"])["state"], "researching")
        self.assertEqual(self.repo.fresh_verified_evidence(self.run["id"]), [])
        stored = self.repo.latest_auto_worker_result(self.run["id"])
        self.assertEqual(stored["outcome"], "reviewed_not_saved")
        self.assertIn("remains unverified", stored["reason"])

    @patch("travel.auto_worker.collect_public_evidence")
    def test_a_codex_timeout_is_reported_not_raised(self, collect):
        collect.return_value = ([], SAMPLE_EVIDENCE)
        result = process_pending_run(self.repo, self.run, Path("."), codex_runner=timeout_runner)
        self.assertEqual(result["outcome"], "unresolved")
        self.assertIn("codex proposal unavailable", result["reason"])

    @patch("travel.auto_worker.collect_public_evidence")
    def test_a_claude_timeout_is_reported_not_raised(self, collect):
        collect.return_value = ([], SAMPLE_EVIDENCE)
        codex_runner = codex_runner_writing(json.dumps({"days": [{"focus": "京都"}]}))
        result = process_pending_run(self.repo, self.run, Path("."), codex_runner=codex_runner, claude_runner=timeout_runner)
        self.assertEqual(result["outcome"], "unresolved")
        self.assertIn("claude review unavailable", result["reason"])


class AuditLogTests(unittest.TestCase):
    def test_appends_one_json_line_per_call_and_never_touches_the_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "audit.log"
            append_audit_log_entry(log_path, {"run_id": "a", "outcome": "unresolved"})
            append_audit_log_entry(log_path, {"run_id": "b", "outcome": "reviewed_not_saved"})
            lines = log_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["run_id"], "a")
        self.assertEqual(json.loads(lines[1])["run_id"], "b")


class WorkerNeverHoldsAGitHubTokenTests(unittest.TestCase):
    """Canary: neither the web server nor this worker may hold a GitHub token.

    AGENTS.md prohibits any runtime in this project from holding GitHub
    write/deploy credentials, not only the public web server.
    """

    def test_webapp_module_does_not_import_auto_worker(self):
        import travel.webapp as webapp
        self.assertNotIn("auto_worker", dir(webapp))

    def test_auto_worker_source_never_mentions_a_github_token_or_makes_http_requests(self):
        source = Path(__import__("travel.auto_worker", fromlist=["__file__"]).__file__).read_text(encoding="utf-8")
        for needle in ("GITHUB_TOKEN", "Authorization", "api.github.com", "urlopen", "urllib.request"):
            self.assertNotIn(needle, source, f"unexpected {needle!r} in travel/auto_worker.py")

    def test_worker_script_source_never_mentions_a_github_token(self):
        script = Path(__file__).parents[1] / "scripts" / "run_auto_research_worker.py"
        source = script.read_text(encoding="utf-8")
        for needle in ("GITHUB_TOKEN", "Authorization", "api.github.com"):
            self.assertNotIn(needle, source, f"unexpected {needle!r} in scripts/run_auto_research_worker.py")


if __name__ == "__main__":
    unittest.main()
