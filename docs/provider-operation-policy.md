# 情報提供元の運用ポリシー

このプロトタイプは、情報提供元の候補と検証済みの旅行事実を区別します。候補は常に `unverified` で保存され、営業時間、運賃、評価、空席、時刻表、予約可否を自動で旅程へ採用しません。

## 研究モード

| 提供元 | 利用目的 | 実装上の制約 |
| --- | --- | --- |
| OpenStreetMap Nominatim | 行き先の概略座標 | 利用者が明示実行した一件の検索のみ。毎秒一件以下、識別可能な User-Agent、帰属を要求する。[公式ポリシー](https://operations.osmfoundation.org/policies/nominatim/) |
| Wikimedia | 地域の説明・調査の入口 | User-Agent、レート制御、各ページのライセンスと帰属を確認する。[REST APIポリシー](https://www.mediawiki.org/wiki/API:REST_API/Policies) |
| Open-Meteo | ユーザー要求時の予報候補 | 予報は観測事実ではない。無料枠は評価・非商用用途として扱う。[公式価格・利用条件](https://open-meteo.com/en/pricing) |
| GTFS-JP | 交通の公式データ候補 | 事業者、対象日、ライセンス、`feed_info.txt` の鮮度を確認してから時刻表に使う。[GTFS-JP仕様](https://www.gtfs.jp/developpers-guide/format-reference.html) |

## 商用モード

`LLM_TRAVEL_DEPLOYMENT_MODE=commercial` では共有無料APIを呼び出しません。

- Nominatim: 自己ホストまたは商用プロバイダーを設定する。
- Open-Meteo: 商用ライセンスと専用エンドポイント・APIキーを設定する。
- Wikimedia: 表示するページ単位のライセンス・帰属を保存する。
- GTFS-JP: 事業者ごとの配布条件、対象日、更新時刻を検証する。
- Google Places: 有効なプロジェクト、表示上の帰属、キャッシュ制限、利用規約・プライバシーポリシーを満たした接続だけを使う。[公式ポリシー](https://developers.google.com/maps/documentation/places/web-service/policies)
- TikTok・食べログ: 許可済みの公式接続と利用条件がない限り取得・保存しない。スクレイピングは実装しない。

これらの確認が欠ける場合、UIは `commercial_provider_configuration_required` を表示し、候補・旅程・公開を進めない。
