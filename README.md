# llm-travel

継続的改善型AI旅行計画プラットフォームの研究用プロトタイプ。

現段階は **ローカルの研究用プロトタイプ** です。CLIの検証・保存処理と、ブラウザー内で完結する旅行条件の入力・確認・JSON保存画面があります。ホーム画面は外部AI APIもローカルAPIも呼び出しません。実旅行向けの自動計画生成・予約・Claude常駐接続・AWS公開には対応していません。

画面を開くには `python -m travel.webapp` を実行し、`http://127.0.0.1:8765` にアクセスします。入力はタブ内だけに保持され、再読み込みで消えます。合成サンプルを使って試してください。[UI設計と保存形式](docs/local-planner-ui.md)も参照してください。

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
