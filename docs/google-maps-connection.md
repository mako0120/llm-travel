# Google Maps 接続

Gemini のAPIキーと Google Maps Platform のAPIキーは別の用途です。同じ Google Cloud 請求先アカウントを使えますが、旅行プランナーには Maps Platform 側で **Places API (New)** と **Routes API** を有効にした制限付きキーが必要です。

1. Google Cloud Console で、請求先が有効なプロジェクトを選ぶ。
2. Places API (New) と Routes API を有効にする。
3. キーを作成し、Maps API と必要なWebサーバーの送信元に制限する。
4. Webサーバーを起動する端末でだけ `GOOGLE_MAPS_API_KEY` を環境変数に設定する。
5. `python -m travel.webapp` を再起動する。

キーは `.env`、Git、SQLite、ブラウザ、レスポンス、ログには書き込まない。`POST /api/connected-research` はキーを受け取らず、サーバー環境変数からだけ読み取る。取得したPlaces候補はすべて `unverified` として根拠パケットへ入り、評価、営業時間、料金、交通時刻を自動確定しない。

Google Maps Platform の認証と課金の前提は [Google公式ガイド](https://developers.google.com/maps/documentation/places/web-service/get-api-key) を参照する。
