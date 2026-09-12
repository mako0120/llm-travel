from datetime import datetime, timezone
import tempfile
import unittest

from travel.storage import Repository


NOW = datetime(2026, 9, 12, tzinfo=timezone.utc)


class ResearchMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Repository(self.temp.name + "/test.sqlite3")

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def evidence(self, agent="codex", status="verified"):
        return {"agent": agent, "source_type": "official", "url": "https://example.org/place", "title": "Synthetic place",
                "facts": {"hours": "09:00-17:00"}, "retrieved_at": "2026-09-12T00:00:00+00:00",
                "expires_at": "2026-09-13T00:00:00+00:00", "verification_status": status}

    def test_generation_time_research_records_agent_provenance_and_fresh_evidence(self):
        run = self.repo.create_research_run("profile-1", {"destination": "synthetic"}, ["official"])
        saved = self.repo.record_evidence(run["id"], self.evidence("claude"))
        self.assertEqual(len(saved["content_hash"]), 64)
        completed = self.repo.complete_research_run(run["id"], "ready")
        self.assertEqual(completed["state"], "ready")
        self.assertEqual(self.repo.fresh_verified_evidence(run["id"], NOW)[0]["agent"], "claude")
        self.assertEqual(self.repo.fresh_verified_evidence(run["id"], datetime(2026, 9, 13, tzinfo=timezone.utc)), [])

    def test_ready_requires_evidence_and_personal_signals_are_profile_scoped(self):
        run = self.repo.create_research_run("profile-1", {}, [])
        with self.assertRaises(ValueError):
            self.repo.complete_research_run(run["id"], "ready")
        one = self.repo.add_preference_signal("profile-1", "food", "spicy", 0.7)
        self.repo.add_preference_signal("profile-2", "food", "mild", 0.9)
        self.assertEqual(self.repo.profile_context("profile-1"), [one])

    def test_evidence_never_claims_unverified_is_fresh_verified(self):
        run = self.repo.create_research_run("profile-1", {}, [])
        self.repo.record_evidence(run["id"], self.evidence(status="unverified"))
        self.repo.complete_research_run(run["id"], "ready")
        self.assertEqual(self.repo.fresh_verified_evidence(run["id"], NOW), [])
