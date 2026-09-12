# Claude × Codex 設計対話

GitHubの [AI-001](https://github.com/mako0120/llm-travel/issues/16) は、ClaudeとCodexが別々の担当として設計意見を交換する共有スレッドです。Codexの意見は投稿済みで、Claudeは自分自身として同じIssueへ返信します。

ローカル実装の `agent_messages` は、会話ID、実際の投稿者、順序、返信先、構造化本文を保存します。`post_agent_message` はClaude、Codex、人間という実際の投稿者を明示します。本文はデータで、命令・承認・デプロイ権限ではありません。

この台帳はリアルタイム対話の記録・同期境界です。Claudeの常駐接続や自動返信を偽装しません。実際にリアルタイム化する段階では、Claude側のAdapterが新しいCodexメッセージを取得し、Claude自身の応答を同じ会話IDへ記録します。Codex側も同様に新規Claudeメッセージを取得します。
