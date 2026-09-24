import unittest

from travel.agent_research import agent_web_research_request, validate_agent_web_evidence


class AgentWebResearchTests(unittest.TestCase):
    def evidence(self, **overrides):
        result = {"agent": "codex", "source_type": "Google web research", "url": "https://www.google.com/search?q=kyoto",
                  "title": "京都の調査候補", "facts": {"query": "京都"}, "retrieved_at": "2030-01-01T00:00:00Z",
                  "expires_at": "2030-01-01T01:00:00Z", "verification_status": "unverified"}
        result.update(overrides)
        return result

    def test_request_is_data_only_and_explicit_about_unverified_results(self):
        request = agent_web_research_request({"destination": "京都"})
        self.assertEqual(request["sources"][0]["source_type"], "Google web research")
        self.assertIn("unverified", request["output_rule"])

    def test_rejects_wrong_origin_or_verified_agent_claim(self):
        self.assertEqual(validate_agent_web_evidence(self.evidence())["agent"], "codex")
        with self.assertRaisesRegex(ValueError, "match"):
            validate_agent_web_evidence(self.evidence(url="https://example.test/kyoto"))
        with self.assertRaisesRegex(ValueError, "unverified"):
            validate_agent_web_evidence(self.evidence(verification_status="verified"))
        with self.assertRaisesRegex(ValueError, "codex or claude"):
            validate_agent_web_evidence(self.evidence(agent="provider"))
