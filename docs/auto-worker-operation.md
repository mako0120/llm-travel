# 個人利用の自動リサーチワーカー(Issue #54, Phase 1.5)

`scripts/run_auto_research_worker.py` は、Webサイトが受け付けた調査リクエスト(`research_runs`が`requested`状態のもの)を、操作者本人のマシン上で自動的に処理し、結果をローカルの監査ログに記録するツールです。**Webアプリ(`travel/webapp.py`)からは一切呼び出されず、Webサーバーとは別プロセスとして操作者本人が明示的に起動する前提**です。

## 権限分離(この設計の核)

- 公開/常時稼働するWebサーバー(`travel/webapp.py`)は、今まで通りGitHubの資格情報を一切保持しません。
- **このワーカー自身もGitHubトークンを一切保持・送信しません。** `AGENTS.md`の「ランタイムはGitHub書き込み/デプロイ資格情報を持たない」という原則は、Webサーバーに限らずこのプロジェクトの自動化コンポーネント全般に適用されます(`scripts/github_webhook_bridge.py`の受信プロセスも同様にトークンを持ちません)。
- 実行結果は`LLM_TRAVEL_AUTO_WORKER_LOG`(既定値`data/auto_worker_audit.log`)にJSON Lines形式で追記されるだけです。GitHubへ記録を残したい場合は、そのログの内容を**操作者本人が**GitHubのWeb UIか自分の`gh` CLIセッションでコピー&ペーストして投稿してください。この一手間が、Codex/Claudeが要約に紛れ込ませた可能性のある個人情報・機微情報を、公開前に人間が確認する機会にもなります。

## できること・できないこと

このワーカーは、`travel/free_sources.py`の無料公開情報源(Nominatim/Wikimedia/Open-Meteo)から候補を集め、ローカルの`codex`/`claude` CLIを使って「Codex提案→Claude独立レビュー」の監査サイクルを1回実行し、結果をログに残します。

これらの情報源が返す証拠は常に`verification_status: "unverified"`です。`Repository.record_itinerary_proposal()`は`verified`かつ有効期限内の証拠しか旅程の根拠として受け付けないため、**このワーカーは確定した旅程を自動保存することはありません**。承認(`approved`)が出た場合でも、結果は`"reviewed_not_saved"`として記録されるだけです。確定旅程を保存するには、公式出典で裏取りした`verified`な証拠を別途用意する必要があります(人間またはCodexの作業)。

利用者がその場で見られる下書きは、引き続き`/api/workspace/runs/{id}/draft`(`travel/draft_itinerary.py`)が提供します。

## 並行実行時の安全性

`Repository.claim_research_run()`が、runを`requested`から`researching`へ**アトミックに**移すため、ワーカーを複数起動してしまっても同じrunを二重処理することはありません。証拠が見つからなかったrunも、claimされた時点で`requested`状態から外れるため、次回以降のポーリングで際限なく再試行されることもありません。

## 起動条件

- 環境変数`LLM_TRAVEL_AUTO_RESEARCH=1`が明示的に設定されている場合のみ動作します(デフォルトOFF)。
- `LLM_TRAVEL_DEPLOYMENT_MODE=commercial`のときは、上記の設定に関わらず動作しません。

## 使い方

```bash
export LLM_TRAVEL_AUTO_RESEARCH=1
python scripts/run_auto_research_worker.py            # 常駐して定期的に処理
python scripts/run_auto_research_worker.py --once     # 1回だけ処理して終了
```

結果は標準出力と、`LLM_TRAVEL_AUTO_WORKER_LOG`で指定したローカルファイル(既定`data/auto_worker_audit.log`)の両方に記録されます。


## Web UIでの結果確認

ワーカーはWebサーバーとは別プロセスのままです。各runの直近結果だけをSQLiteの
`auto_worker_results`へ保存し、Web側は読み取り専用の
`GET /api/workspace/runs/{id}/auto-worker-status` で確認します。

- `reviewed_not_saved`: AIレビューは通過したが、根拠が未検証なので確定旅程は保存していない。
- `unresolved`: 追加の根拠が必要。UIには `missing_evidence` / `required_evidence` の項目名だけを表示する。
- `skipped`: このワーカー実行では処理対象外だった。

APIはワーカーをimport・起動せず、保存済み結果を読むだけです。提案本文や未検証の旅行事実は
status用レコードへ保存しません。
