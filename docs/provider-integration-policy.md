# 許諾ベースの外部情報連携

旅行生成時の情報は、DBの既存値だけに依存せず、目的地・日程・予算に応じて取得します。ただし、各取得は公式 API、事業者公開の GTFS、または契約・利用条件が確認済みの接続に限ります。スクレイピング、未許諾の自動操作、資格情報の保存・画面返却は行いません。

`GET /api/providers` は利用可能性を表すカタログです。`configuration_required`、`feed_selection_required`、`approval_required`、`official_connection_required` は、まだ旅行事実を取得できない状態です。未設定の項目は旅行計画で「未確認」とし、数値・時刻表・営業情報を補完しません。

## 接続候補

| 情報 | 接続 | 実装条件 |
| --- | --- | --- |
| 観光地・飲食店候補 | Google Maps Places API | Cloud プロジェクト、制限した API キー、表示・帰属ポリシー |
| ルート・所要時間 | Google Maps Routes API | Cloud プロジェクト、制限した API キー、必要最小限の field mask |
| 路線・駅・時刻表 | 事業者公式 GTFS / GTFS-Realtime、ODPT | 事業者または認可済み公開元、対象日の有効性、利用許諾 |
| 発見候補 | TikTok 公式 API | 承認済みプロダクトと必要な利用者認可。時刻・料金の確定根拠には使わない |
| 食べログ候補 | 公式またはライセンス済み接続のみ | 許諾範囲を文書化するまで `official_connection_required` |

Google Places Text Search はテキスト検索と location bias、評価条件などを提供します。Google Routes の Compute Routes は経路・区間・所要時間を返し、返却 field mask を要求します。GTFS の `stop_times.txt` は便ごとの到着・出発時刻を表しますが、計画対象日の有効期間を確認してから表示します。

各ライブ Adapter は、取得 URL、取得時刻、期限、検証状態、出典種別を `ResearchEvidence` として記録してから候補化します。SNSや口コミは発見・比較の補助であり、営業時間、料金、予約可否、時刻表を単独で確定しません。

Google Maps Adapter は、明示的に渡された API キーがある場合だけ、公式の Places Text Search と Routes Compute Routes へ POST します。未設定時は通信せず `unconfigured` を返します。Places は候補名・住所・評価・口コミ数・Google Maps URLだけ、Routes は所要時間・距離・公共交通の区間だけを field mask で要求します。各応答は候補表示前に `ResearchEvidence` の検証・鮮度ゲートを通します。

Places の変換器は結果を `verification_status: unverified` の `ResearchEvidence` としてのみ作ります。取得時刻と最大24時間の期限を付けますが、これだけで営業・価格・予約可否・時刻表の確認済みにはなりません。Claudeの候補レビューと、必要に応じた事業者公式根拠の確認後にだけ `verified` として旅程候補へ利用できます。

## 設定の境界

プロトタイプにはキーやトークンをコミットしません。実装時はローカルまたは承認済みのシークレットストアから短時間だけ読み、ログ・DB・API レスポンスには値を残しません。GitHub 書き込みやデプロイ権限を旅行アプリの実行環境へ渡しません。
