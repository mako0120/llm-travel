# llm-travel

継続的改善型AI旅行計画プラットフォームの研究用プロトタイプ。

現段階は **ローカルCLIの開発基盤** です。実旅行向けの計画生成・予約・Web UI・Claude接続・AWS公開は未実装です。

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
