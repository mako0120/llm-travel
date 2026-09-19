import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).parents[1] / "scripts" / "run_free_research_demo.py"
SPEC = importlib.util.spec_from_file_location("run_free_research_demo", MODULE)
demo_script = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = demo_script
SPEC.loader.exec_module(demo_script)


class RunFreeResearchDemoTests(unittest.TestCase):
    def test_writes_evidence_and_error_when_nothing_is_found(self):
        with tempfile.TemporaryDirectory() as tmp, patch("run_free_research_demo.collect_public_evidence", return_value=([], [])):
            code = demo_script.run("架空の場所", 1, tmp)
            self.assertEqual(code, 1)
            self.assertEqual(json.loads((Path(tmp) / "evidence.json").read_text()), [])
            self.assertIn("error", json.loads((Path(tmp) / "draft.json").read_text()))

    def test_writes_evidence_and_draft_when_real_candidates_are_found(self):
        candidate = {"agent": "provider", "source_type": "OpenStreetMap Nominatim", "url": "https://example.test/kyoto",
                     "title": "京都", "facts": {}, "retrieved_at": "2030-01-01T00:00:00Z",
                     "expires_at": "2030-01-02T00:00:00Z", "verification_status": "unverified"}
        with tempfile.TemporaryDirectory() as tmp, patch("run_free_research_demo.collect_public_evidence", return_value=([], [candidate])):
            code = demo_script.run("京都", 2, tmp)
            self.assertEqual(code, 0)
            evidence = json.loads((Path(tmp) / "evidence.json").read_text())
            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0]["verification_status"], "unverified")
            draft = json.loads((Path(tmp) / "draft.json").read_text())
            self.assertEqual(draft["status"], "needs_research")
            self.assertEqual(draft["days"][0]["time"], "未確定")


if __name__ == "__main__":
    unittest.main()
