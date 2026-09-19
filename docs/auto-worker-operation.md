# 個人利用の自動リサーチワーカー(Issue #54, Phase 1.5)

`scripts/run_auto_research_worker.py` は、Webサイトが受け付けた調査リクエスト(`research_runs`が`requested`状態のもの)を、操作者本人のマシン上で自動的に処理し、結果をGitHubへ監査記録として投稿するツールです。**Webアプリ(`travel/webapp.py`)からは一切呼び出されず、Webサーバーとは別プロセスとして操作者本人が明示的に起動する前提**です。

## 権限分離(この設計の核)

- 公開/常時稼働するWebサーバー(`travel/webapp.py`)は、今まで通りGitHubの資格情報を一切保持しません。`tests/test_auto_worker.py`にこれを守るための回帰テスト(canary test)があります。
- GitHubへの書き込みは、このワーカースクリプトを起動したプロセスだけが行います。
- GitHubトークンは、対象リポジトリに対する **`Issues: write`権限のみ** のfine-grained PATを使ってください。`contents`(push)・`administration`・マージ権限は付与しないでください。個人利用であっても、この最小権限化は省略しないでください。

## できること・できないこと

このワーカーは、`travel/free_sources.py`の無料公開情報源(Nominatim/Wikimedia/Open-Meteo)から候補を集め、ローカルの`codex`/`claude` CLIを使って「Codex提案→Claude独立レビュー」の監査サイクルを1回実行し、結果をGitHubにコメントとして残します。

これらの情報源が返す証拠は常に`verification_status: "unverified"`です。`Repository.record_itinerary_proposal()`は`verified`かつ有効期限内の証拠しか旅程の根拠として受け付けないため、**このワーカーは確定した旅程を自動保存することはありません**。承認(`approved`)が出た場合でも、結果は`"reviewed_not_saved"`として記録されるだけです。確定旅程を保存するには、公式出典で裏取りした`verified`な証拠を別途用意する必要があります(人間またはCodexの作業)。

利用者がその場で見られる下書きは、引き続き`/api/workspace/runs/{id}/draft`(`travel/draft_itinerary.py`)が提供します。

## 起動条件

- 環境変数`LLM_TRAVEL_AUTO_RESEARCH=1`が明示的に設定されている場合のみ動作します(デフォルトOFF)。
- `LLM_TRAVEL_DEPLOYMENT_MODE=commercial`のときは、上記の設定に関わらず動作しません。

## 使い方

```bash
export LLM_TRAVEL_AUTO_RESEARCH=1
export LLM_TRAVEL_AUTO_WORKER_GITHUB_TOKEN="<issues:write のみのfine-grained PAT>"
export LLM_TRAVEL_AUTO_WORKER_GITHUB_REPO="mako0120/llm-travel"
export LLM_TRAVEL_AUTO_WORKER_GITHUB_ISSUE=54
python scripts/run_auto_research_worker.py            # 常駐して定期的に処理
python scripts/run_auto_research_worker.py --once     # 1回だけ処理して終了
```

`LLM_TRAVEL_AUTO_WORKER_GITHUB_REPO`/`_GITHUB_ISSUE`/`_GITHUB_TOKEN`のいずれかが未設定の場合、GitHubへの投稿は行わず、結果を標準出力に表示するだけになります。
