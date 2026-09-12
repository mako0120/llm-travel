import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.db = self.folder / "travel.sqlite3"
        start = datetime.now(timezone.utc) + timedelta(days=1)
        self.plan = {
            "start": start.isoformat(),
            "end": (start + timedelta(hours=4)).isoformat(),
            "budget": 5000,
            "required_activity_ids": ["museum"],
            "activities": [{
                "id": "museum", "start": (start + timedelta(minutes=30)).isoformat(),
                "end": (start + timedelta(hours=2)).isoformat(),
                "cost": 1000, "transit_minutes": 20,
                "source": {"url": "https://example.org/museum",
                           "expires_at": (start + timedelta(days=1)).isoformat()},
            }],
        }

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, command, payload=None, identifier=None, expected=0, raw=None):
        args = [sys.executable, "-m", "travel", "--db", str(self.db), command]
        if payload is not None or raw is not None:
            path = self.folder / "input.json"
            path.write_text(raw if raw is not None else json.dumps(payload), encoding="utf-8")
            args.append(str(path))
        if identifier is not None:
            args.append(identifier)
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=20)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def test_full_feedback_and_rule_approval_cycle_across_processes(self):
        self.assertEqual(self.run_cli("validate", self.plan), {"valid": True, "issues": []})
        saved = self.run_cli("save", self.plan)
        self.assertEqual(saved["version"], 1)
        self.assertEqual(self.run_cli("show", identifier=saved["id"]), saved)
        first = self.run_cli("feedback", {
            "plan_id": saved["id"], "version": 1,
            "ratings": {"satisfaction": 2}, "comment": "移動が忙しかった",
        })
        self.run_cli("feedback", {"plan_id": saved["id"], "version": 1,
                                  "ratings": {"satisfaction": 4}})
        stats = self.run_cli("analytics", identifier=saved["id"])
        self.assertEqual(stats["satisfaction"], {"count": 2, "mean": 3, "median": 3, "stdev": 1})
        rule = self.run_cli("propose-rule", {
            "condition": {"region": "Kyoto", "transport": "walk"},
            "problem": "Rushed transfers", "improvement": "Allow more transit time",
            "evidence": {"evidence_type": "qualitative_comment_only", "feedback_ids": [first["id"]]},
        })
        self.assertEqual(rule["status"], "pending")
        metadata = {"region": "Kyoto", "transport": "walk"}
        self.assertEqual(self.run_cli("find-rules", metadata), [])
        approved = self.run_cli("approve-rule", identifier=rule["id"])
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(self.run_cli("find-rules", metadata), [approved])
        self.assertEqual(self.run_cli("find-rules", dict(metadata, region="Osaka")), [])

    def test_invalid_plan_cannot_be_saved(self):
        self.plan["budget"] = 100
        validation = self.run_cli("validate", self.plan, expected=1)
        self.assertFalse(validation["valid"])
        self.assertIn("over_budget", [issue["code"] for issue in validation["issues"]])
        result = self.run_cli("save", self.plan, expected=1)
        self.assertFalse(result["saved"])
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM plans").fetchone()[0], 0)

    def test_malformed_json_reports_error_without_creating_database(self):
        result = self.run_cli("save", raw="{broken", expected=2)
        self.assertIn("error", result)
        self.assertFalse(self.db.exists())

    def test_invalid_feedback_does_not_pollute_analytics(self):
        saved = self.run_cli("save", self.plan)
        for version, score in [(1, True), (999, 3)]:
            self.assertIn("error", self.run_cli("feedback", {
                "plan_id": saved["id"], "version": version, "ratings": {"score": score},
            }, expected=2))
        self.assertEqual(self.run_cli("analytics", identifier=saved["id"]), {})


if __name__ == "__main__":
    unittest.main()
