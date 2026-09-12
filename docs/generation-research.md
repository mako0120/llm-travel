# 生成時リサーチと個別最適化

旅行計画は、保存済みDBだけから作りません。対話完了後に `research_request` が、目的地・予算・交通・テーマ・個別要望を含む `ResearchRequest` を作ります。ClaudeまたはCodexは、その旅行生成時に独立して必要な情報を調査し、`ResearchResult` として返します。

`Repository.create_research_run`、`record_evidence`、`complete_research_run` は、その依頼・担当・情報源・取得日時・期限・検証状態・内容ハッシュを保存します。これはエージェントの代行実行ではありません。実際のClaude/Codex担当がGitHubのIssueまたはアプリのAdapter経由で返した証拠を記録する境界です。

個別最適化には、旅行者を直接識別しない不透明な `profile_id` と、Feedbackに基づく `preference_signals` を使います。個人の嗜好シグナルはグローバル改善ルールではなく、そのprofileだけの文脈です。実参加者データには、Issue #5の同意・保持・認可設計が先に必要です。

計画生成時の順序は次です。

```text
対話条件 + 個人嗜好 → ResearchRequest → Claude/Codexによるその時点の調査
→ 根拠・鮮度・検証状態を保存 → Candidate生成 → Solver → Validator → 計画
→ 実績・Feedback → 個人嗜好と改善知識を更新
```

Google、食べログ、TikTok等の名称は対象カテゴリを表すだけです。実サイトの取得は、各サイトの利用条件、Provider Adapter、出典・取得時刻・検証方針を実装した後に有効化します。SNSは発見に使えても、営業時間・料金・時刻表の確定根拠にはしません。
