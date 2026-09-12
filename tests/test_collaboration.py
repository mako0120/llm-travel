import tempfile
import unittest

from travel.collaboration import codex_position
from travel.storage import Repository


class CollaborationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Repository(self.temp.name + "/test.sqlite3")

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_distinct_participants_can_exchange_ordered_replies(self):
        first = codex_position(self.repo, "ai-001", "generation-time research", "Use live evidence with freshness.", ["Claude review"])
        second = self.repo.post_agent_message("ai-001", "claude", "response", {"position": "Review required."}, first["id"])
        messages = self.repo.read_agent_messages("ai-001")
        self.assertEqual([message["author"] for message in messages], ["codex", "claude"])
        self.assertEqual(messages[1]["reply_to"], second["reply_to"])
        self.assertEqual(self.repo.read_agent_messages("ai-001", messages[0]["sequence"]), [messages[1]])

    def test_cannot_impersonate_or_reply_to_unknown_message(self):
        with self.assertRaises(ValueError):
            self.repo.post_agent_message("ai-001", "system", "position", {})
        with self.assertRaises(ValueError):
            self.repo.post_agent_message("ai-001", "codex", "response", {}, "missing")
