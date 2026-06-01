# APIM による LLM のトークンレート制限

Azure API Management（APIM）の `llm-token-limit` ポリシーで、サブスクリプション単位に 1 分あたりのトークン消費量を制限し、上限を超えたリクエストへ HTTP 429 を返す構成の検証

元ネタは [AI-Gateway リポジトリの token-rate-limiting ラボ](https://github.com/Azure-Samples/AI-Gateway/tree/main/labs/token-rate-limiting)。

## ファイル

| ファイル | 役割 |
| --- | --- |
| `main.bicep` / `params.json` | インフラ定義とパラメータ |
| `policy.xml` | APIM の API ポリシー（`llm-token-limit`） |
| `deploy.sh` / `cleanup.sh` | デプロイ・クリーンアップ |
| `01-token-limit.py` | 負荷生成とトークン消費・ステータスの収集 |
| `02-plot.py` | 結果のグラフ化 |
| `requirements.txt` | Python の依存パッケージ |

## 構成

- APIM（Basicv2、システム割り当てマネージド ID）
- 単一リージョンの Microsoft Foundry アカウントと `gpt-4.1-mini` デプロイ
  - foundry1: Japan East
- APIM 上の Inference API と `llm-token-limit` ポリシー（`counter-key` = サブスクリプション単位）
- Foundry への `Cognitive Services OpenAI User` ロール割り当て

## 前提

- Azure CLI（`az`）でログイン済み、対象サブスクリプションを選択済み
- `gpt-4.1-mini`（GlobalStandard）のクォータ
- [uv](https://docs.astral.sh/uv/)（Python 実行）

## デプロイ

`deploy.sh` を実行すると、次の手順が自動で進む。再実行可能。

1. デプロイされるリソースの差分を事前表示（`az deployment group what-if`）
2. Bicep （`main.bicep` + `params.json`）をデプロイ
3. ゲートウェイ URL とサブスクリプションキーを `.env` に書き出し（検証コードが読み込む）

```bash
./deploy.sh
```

トークン上限（`tokens-per-minute`）は [policy.xml](./policy.xml) で定義する。少ないリクエストで上限到達を観測するため低め（既定 100）に設定している。

## 検証の実行

`uv` が [requirements.txt](./requirements.txt) の依存を解決して実行する。事前のインストールは不要。

```bash
# APIM 経由で繰り返しリクエストする
uv run --with-requirements requirements.txt 01-token-limit.py

# 結果を棒グラフ画像に保存する
uv run --with-requirements requirements.txt 02-plot.py
```

各時間窓（1 分）の先頭で 200 が返り、累積トークンが `tokens-per-minute` を超えた以降は 429 に切り替わる。1 分の時間窓が明けるとカウンタがリセットされ、再び 200 が返る。既定の 10 秒間隔×18 回（約 3 分）は複数の時間窓をまたぐため、「200 → 429 → （約 1 分後）回復」というノコギリ状のパターンがグラフに現れる。間隔を短くするとバーストが時間窓をまたがず、回復が見えない点に注意。

実行パラメータは環境変数で上書きできる。

| 変数 | 既定値 | 説明 |
| --- | --- | --- |
| `MODEL_NAME` | `gpt-4.1-mini` | デプロイ名 |
| `RUNS` | `18` | リクエスト回数 |
| `MAX_TOKENS` | `50` | 1 リクエストの出力上限 |
| `SLEEP_TIME_MS` | `10000` | リクエスト間隔（ミリ秒。時間窓をまたぐため長め） |

## クリーンアップ

リソースグループの削除に加え、ソフトデリート対象のパージまで行う。

```bash
./cleanup.sh
```
