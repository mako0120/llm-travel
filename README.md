# llm-travel

継続的改善型AI旅行計画プラットフォームの研究用プロトタイプ。

現段階は **ローカルの研究用プロトタイプ** です。CLIの検証・保存処理と、ブラウザー内で完結する旅行条件の入力・確認・JSON保存画面があります。ホーム画面は外部AI APIもローカルAPIも呼び出しません。実旅行向けの予約・決済・AWS公開には対応していません。

画面を開くには `python -m travel.webapp` を実行し、`http://127.0.0.1:8765` にアクセスします。入力はタブ内だけに保持され、再読み込みで消えます。合成サンプルを使って試してください。[UI設計と保存形式](docs/local-planner-ui.md)も参照してください。

キー不要の公開情報源のカタログは `GET /api/free-sources` で確認できます。Nominatim・Wikimedia・事業者公開GTFSの用途と制約を表示するだけで、ホーム画面から自動検索しません。[個別計画と無料情報源の方針](docs/personalized-research.md)を確認してから使ってください。

ローカルでログイン済みのCodex/Claude CLIを使う場合だけ、オペレーターが `python scripts/run_dual_agent_review.py input.json output.json` を起動できます。これはChatGPT/Codex案とClaudeの独立レビューを同じ根拠パケットで往復させる手順です。Webアプリからの自動実行、予約・決済、未実行レビューの表示は行いません。

## Run

Python 3.12+、外部Python依存なし。

```sh
python -m unittest discover -v
python -m evals.run
python -m travel --help
python -m travel validate path/to/plan.json
python -m travel save path/to/plan.json
python -m travel show PLAN_ID
python -m travel feedback path/to/feedback.json
python -m travel analytics PLAN_ID
python -m travel propose-rule path/to/rule.json
python -m travel approve-rule RULE_ID
python -m travel find-rules path/to/metadata.json
```

保存先は `data/travel.sqlite3`。Gitには含めません。`--db PATH` はサブコマンドより前に指定します。
合成データだけで使用してください。ローカルの承認コマンドは運用者の明示操作用で、認証・権限管理を代替しません。

## Handoff

- [設計と制限](docs/architecture.md)
- [担当別バックログ](docs/backlog.md)
- [Claudeが取得するプロンプト](docs/handoffs/claude.md)
- [元の要求](docs/master-prompt.md)

Claudeのレビュー結果は対象コミットとともにGitHubへ保存します。プロンプトの保存だけではレビュー完了になりません。
