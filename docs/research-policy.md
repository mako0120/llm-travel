# 旅行生成時リサーチの合意ポリシー

ClaudeとCodexのAI-001合意を実装に反映する。旅行計画は候補ごとに往復せず、**旅程セクション単位**でバッチ化する。各ResearchRequestは最大1回の再試行、最大30秒を宣言する。超過時は `unconfigured` / `failed` を返し、計画の事実を創作しない。

各source targetには `query`、`location`、`category`、`freshness_minutes`、`source_types` を必須とする。ResearchResultは `high` / `medium` / `low` / `unknown` のconfidenceと、`continue_with_labels` / `ask_user` / `exclude_candidate` / `stop` のfallbackを必ず持つ。

`verified` は、実装済みProviderの取得結果が、対象項目・出典・取得日時・有効期限を持ち、カテゴリの信頼方針を満たすことを指す。URL形式だけではverifiedにしない。営業時間・料金・交通時刻は公式または公式APIを優先し、TikTokは発見用途に限る。

低信頼の穴場候補は、ユーザーが明示的に許容する場合だけ `continue_with_labels` で「要確認」として表示する。それ以外は `exclude_candidate` または `ask_user` を使う。個人データの保持期間・削除・同意はIssue #5の人間決定まで未設定である。
