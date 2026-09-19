import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from travel.storage import Repository

MODULE = Path(__file__).parents[1] / "scripts" / "run_auto_research_worker.py"
SPEC = importlib.util.spec_from_file_location("run_auto_research_worker", MODULE)
worker_script = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = worker_script  # let unittest.mock.patch("run_auto_research_worker....") resolve this module
SPEC.loader.exec_module(worker_script)


class RunOnceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Repository(Path(self._tmp.name) / "travel.sqlite3")

    def tearDown(self):
        self.repo.close()
        self._tmp.cleanup()

    def test_skips_runs_that_are_not_requested(self):
        run = self.repo.create_research_run("solo-operator", {"destination": "京都"}, [])
        self.repo.record_evidence(run["id"], {"agent": "human", "source_type": "manual", "url": "https://example.test",
            "title": "t", "facts": {}, "retrieved_at": "2030-01-01T00:00:00Z", "expires_at": "2030-01-02T00:00:00Z",
            "verification_status": "unverified"})
        # run is now "researching", not "requested"; run_once must not touch it again.
        with patch("run_auto_research_worker.process_pending_run") as mock_process:
            summaries = worker_script.run_once(self.repo, Path("."))
        mock_process.assert_not_called()
        self.assertEqual(summaries, [])

    def test_posts_one_audit_comment_per_processed_run_when_configured(self):
        self.repo.create_research_run("solo-operator", {}, [])  # missing destination -> "skipped"
        captured = []
        def poster(url, token, body):
            captured.append((url, token, body))
            return 201
        with patch("run_auto_research_worker.process_pending_run", return_value={"run_id": "x", "outcome": "skipped", "reason": "requirements.destination is missing"}):
            summaries = worker_script.run_once(self.repo, Path("."), github_repo="mako0120/llm-travel",
                                                github_issue=54, github_token="secret", poster=poster)
        self.assertEqual(len(summaries), 1)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0][0], "https://api.github.com/repos/mako0120/llm-travel/issues/54/comments")
        self.assertIn("skipped", captured[0][2])

    def test_no_github_posting_when_not_configured(self):
        self.repo.create_research_run("solo-operator", {}, [])
        with patch("run_auto_research_worker.process_pending_run", return_value={"run_id": "x", "outcome": "skipped", "reason": "..."}), \
             patch("run_auto_research_worker.post_audit_comment") as mock_post:
            worker_script.run_once(self.repo, Path("."))
        mock_post.assert_not_called()


class MainGatingTests(unittest.TestCase):
    def test_main_refuses_to_run_without_explicit_opt_in(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(worker_script.main(["--once"]), 1)

    def test_main_refuses_to_run_in_commercial_mode_even_when_opted_in(self):
        with patch.dict("os.environ", {"LLM_TRAVEL_AUTO_RESEARCH": "1", "LLM_TRAVEL_DEPLOYMENT_MODE": "commercial"}, clear=True):
            self.assertEqual(worker_script.main(["--once"]), 1)

    def test_main_processes_once_and_exits_when_opted_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"LLM_TRAVEL_AUTO_RESEARCH": "1", "LLM_TRAVEL_DB": str(Path(tmp) / "travel.sqlite3")}
            with patch.dict("os.environ", env, clear=True):
                self.assertEqual(worker_script.main(["--once"]), 0)


if __name__ == "__main__":
    unittest.main()
