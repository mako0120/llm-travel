import json
import unittest

from pathlib import Path
import tempfile

from travel.agent_handoff import (build_research_brief, claude_review_prompt,
                                  codex_proposal_prompt, run_claude_review, run_codex_proposal)


class Completed:
    returncode = 0
    stdout = json.dumps({"decision": "needs_revision", "rationale": "No official timetable.", "unsupported_claims": [], "required_evidence": ["GTFS"], "safe_alternatives": []})


class AgentHandoffTests(unittest.TestCase):
    def test_brief_never_converts_unverified_evidence_to_facts(self):
        brief = build_research_brief({"destination": "京都"}, [{"verification_status": "unverified"}])
        self.assertEqual(brief["evidence"][0]["verification_status"], "unverified")
        self.assertIn("Do not invent", brief["rules"][0])

    def test_claude_prompt_and_runner_record_an_actual_response_shape(self):
        brief = build_research_brief({"destination": "京都"}, [])
        prompt = claude_review_prompt("候補案", brief)
        self.assertIn("候補案", prompt)
        captured = []
        review = run_claude_review("候補案", brief, lambda args, **kwargs: captured.append((args, kwargs)) or Completed())
        self.assertEqual(captured[0][0][:4], ["claude", "-p", "--tools", ""])
        self.assertEqual(review["author"], "claude")
        self.assertEqual(review["review"]["decision"], "needs_revision")

    def test_bad_claude_output_is_rejected(self):
        class Bad:
            returncode = 0
            stdout = "not json"
        with self.assertRaises(ValueError):
            run_claude_review("案", build_research_brief({"destination": "京都"}, []), lambda *args, **kwargs: Bad())

    def test_codex_turn_is_read_only_and_requires_a_real_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            captured = []
            def runner(args, **kwargs):
                captured.append((args, kwargs))
                Path(args[args.index("--output-last-message") + 1]).write_text('{"state":"needs_research"}', encoding="utf-8")
                return type("Done", (), {"returncode": 0})()
            result = run_codex_proposal(build_research_brief({"destination": "京都"}, []), workspace, runner)
            self.assertEqual(result["author"], "chatgpt_codex")
            self.assertIn("--sandbox", captured[0][0])
            self.assertIn("read-only", captured[0][0])
            self.assertIn("Do not call tools", captured[0][1]["input"])

    def test_codex_prompt_marks_missing_facts_as_research_needed(self):
        self.assertIn("needs_research", codex_proposal_prompt(build_research_brief({"destination": "京都"}, [])))
