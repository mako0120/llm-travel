import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).parents[1] / "scripts" / "github_webhook_bridge.py"
SPEC = importlib.util.spec_from_file_location("github_webhook_bridge", MODULE)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class GitHubWebhookBridgeTests(unittest.TestCase):
    secret = "test-secret"

    def signed_headers(self, raw, event="issue_comment"):
        signature = "sha256=" + hmac.new(self.secret.encode(), raw, hashlib.sha256).hexdigest()
        return {"X-Hub-Signature-256": signature, "X-GitHub-Event": event}

    def payload(self, body="## Claude → Codex\nレビューです"):
        return {"action": "created", "repository": {"full_name": "mako0120/llm-travel"},
                "issue": {"number": 16}, "comment": {"id": 123, "html_url": "https://example.test/c/123", "body": body}}

    def test_signed_claude_comment_is_queued(self):
        raw = json.dumps(self.payload()).encode()
        with tempfile.TemporaryDirectory() as tmp:
            status, result = bridge.handle(raw, self.signed_headers(raw), self.secret, tmp)
            self.assertEqual(status, 202)
            self.assertEqual(result["state"], "queued")
            queued = json.loads(Path(result["event"]).read_text(encoding="utf-8"))
            self.assertEqual(queued["issue_number"], 16)

    def test_invalid_signature_never_queues(self):
        raw = json.dumps(self.payload()).encode()
        with tempfile.TemporaryDirectory() as tmp:
            status, result = bridge.handle(raw, {"X-Hub-Signature-256": "sha256=no", "X-GitHub-Event": "issue_comment"}, self.secret, tmp)
            self.assertEqual(status, 401)
            self.assertEqual(list(Path(tmp).iterdir()), [])
            self.assertEqual(result["error"], "invalid signature")

    def test_unmarked_or_other_repo_comment_is_ignored(self):
        raw = json.dumps(self.payload("ordinary user comment")).encode()
        with tempfile.TemporaryDirectory() as tmp:
            status, result = bridge.handle(raw, self.signed_headers(raw), self.secret, tmp)
            self.assertEqual((status, result["state"]), (202, "ignored"))
