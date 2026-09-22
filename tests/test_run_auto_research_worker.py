import importlib.util
import json
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

    def test_processes_each_requested_run_and_appends_to_the_local_log(self):
        self.repo.create_research_run("solo-operator", {}, [])  # missing destination -> "skipped"
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "audit.log"
            with patch("run_auto_research_worker.process_pending_run",
                       return_value={"run_id": "x", "outcome": "skipped", "reason": "requirements.destination is missing"}):
                summaries = worker_script.run_once(self.repo, Path("."), log_path=log_path)
            self.assertEqual(len(summaries), 1)
            lines = log_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["outcome"], "skipped")

    def test_no_log_written_when_log_path_is_not_given(self):
        self.repo.create_research_run("solo-operator", {}, [])
        with patch("run_auto_research_worker.process_pending_run",
                   return_value={"run_id": "x", "outcome": "skipped", "reason": "..."}):
            summaries = worker_script.run_once(self.repo, Path("."))
        self.assertEqual(len(summaries), 1)

    def test_run_id_processes_only_the_requested_pending_run(self):
        first = self.repo.create_research_run("solo-operator", {"destination": "京都"}, [])
        second = self.repo.create_research_run("solo-operator", {"destination": "東京"}, [])
        with patch("run_auto_research_worker.process_pending_run",
                   return_value={"run_id": first["id"], "outcome": "skipped", "reason": "done"}) as process:
            summaries = worker_script.run_once(self.repo, Path("."), run_id=first["id"])
        self.assertEqual(len(summaries), 1)
        process.assert_called_once()
        self.assertEqual(process.call_args.args[1]["id"], first["id"])
        self.assertEqual(self.repo.get_research_run(second["id"])["state"], "requested")


class MainGatingTests(unittest.TestCase):
    def test_main_refuses_to_run_without_explicit_opt_in(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(worker_script.main(["--once"]), 1)

    def test_main_refuses_to_run_in_commercial_mode_even_when_opted_in(self):
        with patch.dict("os.environ", {"LLM_TRAVEL_AUTO_RESEARCH": "1", "LLM_TRAVEL_DEPLOYMENT_MODE": "commercial"}, clear=True):
            self.assertEqual(worker_script.main(["--once"]), 1)

    def test_main_processes_once_and_exits_when_opted_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"LLM_TRAVEL_AUTO_RESEARCH": "1", "LLM_TRAVEL_DB": str(Path(tmp) / "travel.sqlite3"),
                   "LLM_TRAVEL_AUTO_WORKER_LOG": str(Path(tmp) / "audit.log")}
            with patch.dict("os.environ", env, clear=True):
                self.assertEqual(worker_script.main(["--once"]), 0)

    def test_main_rejects_a_missing_run_id_value(self):
        with patch.dict("os.environ", {"LLM_TRAVEL_AUTO_RESEARCH": "1"}, clear=True):
            self.assertEqual(worker_script.main(["--once", "--run-id"]), 1)

    def test_main_never_reads_a_github_token_environment_variable(self):
        source = MODULE.read_text(encoding="utf-8")
        for needle in ("GITHUB_TOKEN", "Authorization", "api.github.com"):
            self.assertNotIn(needle, source)


if __name__ == "__main__":
    unittest.main()
