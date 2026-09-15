# GitHub コメントで Codex 開発を起動する

`scripts/github_webhook_bridge.py` は、GitHub の `issue_comment` Webhook をローカルで受信します。受信は時間間隔の監視ではありません。コメント作成イベントが GitHub から届いた時だけ動きます。

受信条件は次のすべてです。

1. `X-Hub-Signature-256` が `LLM_TRAVEL_WEBHOOK_SECRET` で検証できる。
2. リポジトリが `mako0120/llm-travel` である。
3. `issue_comment` の `created` イベントである。
4. 本文に `Claude → Codex` がある。

合格したイベントは `data/webhook-inbox` に JSON として保存されます。`CODEX_WEBHOOK_AUTORUN=1` のときだけ、固定の安全プロンプトで `codex exec` を別 worktree に起動します。コメント本文は設計入力として渡すだけで、シェルとして実行しません。自動マージ、デプロイ、秘密情報変更はプロンプトで禁止されています。

## ローカル起動

`.env.example` を `.env` にコピーして長いランダムな secret を入れ、環境変数を読み込んで起動します。

```powershell
$env:LLM_TRAVEL_WEBHOOK_SECRET = "your-long-random-secret"
$env:LLM_TRAVEL_WORKSPACE = (Get-Location).Path
python scripts/github_webhook_bridge.py
```

ローカルホストは GitHub から直接届かないため、公開 URL から `http://127.0.0.1:8766/github-webhook` へ安全に中継するトンネルが必要です。中継 URL を GitHub リポジトリの Webhooks に登録し、イベントは `Issue comments`、Content type は `application/json`、Secret は同じ値にします。公開中継を使う場合は、Issue コメント本文が中継事業者を通過する点を理解してから使います。

`.env` を設定済みなら、次で受信サーバーと Smee 中継をバックグラウンド起動できます。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_webhook_bridge.ps1
```
