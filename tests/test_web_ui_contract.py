import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class UnifiedWebUiContractTests(unittest.TestCase):
    def test_root_entry_is_deprecated_in_favor_of_workspace_planner(self):
        index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("workspace.html?screen=assistant", index)
        self.assertNotIn('src="app.js"', index)

    def test_workspace_and_public_pages_share_travia_design_language(self):
        workspace = (ROOT / "web" / "workspace.html").read_text(encoding="utf-8")
        public = (ROOT / "web" / "public.html").read_text(encoding="utf-8")
        for html in (workspace, public):
            self.assertIn("TRAVIA", html)
            self.assertIn('href="theme.css"', html)

    def test_auto_worker_ui_has_all_safe_outcome_branches(self):
        workflow = (ROOT / "web" / "workflow.js").read_text(encoding="utf-8")
        for outcome in ("reviewed_not_saved", "unresolved", "skipped"):
            self.assertIn(outcome, workflow)
        self.assertIn("/auto-worker-status", workflow)
        self.assertIn("未検証情報のため確定旅程として保存していません", workflow)
        self.assertIn("不足している根拠", workflow)
        self.assertIn("Webサーバーは自動ワーカーを起動せず", workflow)
        self.assertIn("自動生成した旅程下書き", workflow)
        self.assertIn("assistant-draft", workflow)
        self.assertIn("/api/workspace/draft-preview", workflow)
        self.assertIn("インターネット検索済みの公開候補", workflow)
        self.assertIn("インターネット上の無料公開情報を検索しています", workflow)

    def test_shared_theme_has_mobile_and_worker_status_styles(self):
        theme = (ROOT / "web" / "theme.css").read_text(encoding="utf-8")
        self.assertIn("@media(max-width:850px)", theme)
        self.assertIn(".auto-worker-card.status-unresolved", theme)
        self.assertIn(".worker-state.reviewed", theme)


if __name__ == "__main__":
    unittest.main()
