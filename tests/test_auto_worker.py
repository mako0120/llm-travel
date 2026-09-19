import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from travel.auto_worker import auto_research_enabled, post_audit_comment, process_pending_run
from travel.providers import ProviderResult
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

    def test_skips_when_destination_is_missing(self):
        run = self.repo.create_research_run("solo-operator", {}, [])
        result = process_pending_run(self.repo, run, Path("."))
        self.assertEqual(result["outcome"], "skipped")

    @patch("travel.auto_worker.collect_public_evidence")
    def test_unresolved_when_no_public_evidence_is_found(self, collect):
        collect.return_value = ([], [])
        result = process_pending_run(self.repo, self.run, Path("."))
        self.assertEqual(result["outcome"], "unresolved")
        self.assertIn("no usable public evidence", result["reason"])

    @patch("travel.auto_worker.collect_public_evidence")
    def test_unresolved_when_codex_reports_needs_research(self, collect):
        collect.return_value = ([], [{"agent": "provider", "source_type": "OpenStreetMap Nominatim",
            "url": "https://example.test/kyoto", "title": "京都", "facts": {}, "retrieved_at": "2030-01-01T00:00:00Z",
            "expires_at": "2030-01-02T00:00:00Z", "verification_status": "unverified"}])
        codex_runner = codex_runner_writing(json.dumps({"state": "needs_research", "missing_evidence": ["営業時間"]}))
        result = process_pending_run(self.repo, self.run, Path("."), codex_runner=codex_runner)
        self.assertEqual(result["outcome"], "unresolved")
        self.assertEqual(result["reason"], "codex reported needs_research")
        self.assertEqual(result["evidence_collected"], 1)

    @patch("travel.auto_worker.collect_public_evidence")
    def test_unresolved_when_claude_requests_revision(self, collect):
        collect.return_value = ([], [{"agent": "provider", "source_type": "OpenStreetMap Nominatim",
            "url": "https://example.test/kyoto", "title": "京都", "facts": {}, "retrieved_at": "2030-01-01T00:00:00Z",
            "expires_at": "2030-01-02T00:00:00Z", "verification_status": "unverified"}])
        codex_runner = codex_runner_writing(json.dumps({"days": [{"focus": "京都"}]}))
        claude_runner = lambda args, **kwargs: ClaudeCompleted("needs_revision")
        result = process_pending_run(self.repo, self.run, Path("."), codex_runner=codex_runner, claude_runner=claude_runner)
        self.assertEqual(result["outcome"], "unresolved")
        self.assertEqual(result["reason"], "claude requested revision")

    @patch("travel.auto_worker.collect_public_evidence")
    def test_approval_never_saves_an_itinerary_because_evidence_stays_unverified(self, collect):
        collect.return_value = ([], [{"agent": "provider", "source_type": "OpenStreetMap Nominatim",
            "url": "https://example.test/kyoto", "title": "京都", "facts": {}, "retrieved_at": "2030-01-01T00:00:00Z",
            "expires_at": "2030-01-02T00:00:00Z", "verification_status": "unverified"}])
        codex_runner = codex_runner_writing(json.dumps({"days": [{"focus": "京都"}]}))
        claude_runner = lambda args, **kwargs: ClaudeCompleted("approved")
        result = process_pending_run(self.repo, self.run, Path("."), codex_runner=codex_runner, claude_runner=claude_runner)
        self.assertEqual(result["outcome"], "reviewed_not_saved")
        # The run must still be in "researching", never auto-advanced to "ready".
        self.assertEqual(self.repo.get_research_run(self.run["id"])["state"], "researching")
        self.assertEqual(self.repo.fresh_verified_evidence(self.run["id"]), [])


class PostAuditCommentTests(unittest.TestCase):
    def test_rejects_malformed_inputs(self):
        with self.assertRaises(ValueError):
            post_audit_comment("not-a-slug", 1, "token", "body")
        with self.assertRaises(ValueError):
            post_audit_comment("owner/repo", 0, "token", "body")
        with self.assertRaises(ValueError):
            post_audit_comment("owner/repo", 1, "", "body")

    def test_uses_the_injected_poster_with_the_right_url_and_token(self):
        captured = []
        def poster(url, token, body):
            captured.append((url, token, body))
            return 201
        status = post_audit_comment("mako0120/llm-travel", 54, "secret-token", "hello", poster=poster)
        self.assertEqual(status, 201)
        self.assertEqual(captured[0], ("https://api.github.com/repos/mako0120/llm-travel/issues/54/comments", "secret-token", "hello"))

    def test_transport_errors_become_a_runtime_error(self):
        def failing_poster(url, token, body):
            raise OSError("network is unreachable")
        with self.assertRaises(RuntimeError):
            post_audit_comment("mako0120/llm-travel", 54, "secret-token", "hello", poster=failing_poster)


class WebappNeverHoldsTheWorkerTokenTests(unittest.TestCase):
    """Canary: the public web server must never import the worker or its token."""

    def test_webapp_module_does_not_import_auto_worker(self):
        import travel.webapp as webapp
        self.assertNotIn("auto_worker", dir(webapp))

    def test_webapp_source_never_mentions_the_worker_github_token_variable(self):
        source = Path(__import__("travel.webapp", fromlist=["__file__"]).__file__).read_text(encoding="utf-8")
        self.assertNotIn("LLM_TRAVEL_AUTO_WORKER_GITHUB_TOKEN", source)


if __name__ == "__main__":
    unittest.main()
