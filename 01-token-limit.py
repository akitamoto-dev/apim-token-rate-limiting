import json
import os
import time

from dotenv import load_dotenv
from openai import APIStatusError, AzureOpenAI

load_dotenv()

GATEWAY_URL = os.environ["APIM_GATEWAY_URL"]
SUBSCRIPTION_KEY = os.environ["APIM_SUBSCRIPTION_KEY"]
INFERENCE_API_PATH = os.environ.get("INFERENCE_API_PATH", "inference")
API_VERSION = os.environ.get("INFERENCE_API_VERSION", "2025-03-01-preview")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-4.1-mini")

RUNS = int(os.environ.get("RUNS", "18"))
# llm-token-limit の時間窓は 1 分。スリープを長めにとり複数の時間窓をまたぐことで、
# 「上限到達で 429 → 1 分後に窓がリセットされ再び 200」という回復の様子を観測する。
# 間隔が短いと 30 回が数秒で終わり、窓をまたがず回復が見えない。
SLEEP_TIME_MS = int(os.environ.get("SLEEP_TIME_MS", "10000"))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "50"))

client = AzureOpenAI(
    azure_endpoint=f"{GATEWAY_URL}/{INFERENCE_API_PATH}",
    api_key=SUBSCRIPTION_KEY,
    api_version=API_VERSION,
    # 429 (レート制限) を即座に観測するため SDK 側の自動リトライを無効化する。
    # 既定では指数バックオフで数十秒待つため、検証が長時間ハングする。
    max_retries=0,
)

# (消費トークン, ステータスコード, 経過秒) を記録する
api_runs: list[tuple[int, int, float]] = []
start = time.monotonic()

for i in range(RUNS):
    elapsed = round(time.monotonic() - start, 1)
    print(f"Run {i + 1}/{RUNS} (t={elapsed}s):")

    try:
        raw_response = client.chat.completions.with_raw_response.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": "You are a sarcastic, unhelpful assistant."},
                {"role": "user", "content": "Can you tell me the time, please?"},
            ],
        )
    except APIStatusError as exc:
        # トークン上限超過時は llm-token-limit ポリシーが 429 を返す。記録して継続する。
        remaining = exc.response.headers.get("x-ratelimit-remaining-tokens", "0")
        print(f"  status={exc.status_code} (rate limited) / remaining-tokens={remaining}")
        api_runs.append((0, exc.status_code, elapsed))
        time.sleep(SLEEP_TIME_MS / 1000)
        continue

    status = raw_response.http_response.status_code
    remaining = raw_response.headers.get("x-ratelimit-remaining-tokens", "")
    response = raw_response.parse()
    total_tokens = response.usage.total_tokens if response.usage else 0
    print(f"  status={status} / total_tokens={total_tokens} / remaining-tokens={remaining}")

    api_runs.append((total_tokens, status, elapsed))
    time.sleep(SLEEP_TIME_MS / 1000)

with open("result.json", "w", encoding="utf-8") as f:
    json.dump(api_runs, f, ensure_ascii=False, indent=2)

print(f"\n保存しました: result.json ({len(api_runs)} 件)")

# ステータスコード別の件数を集計して表示する
counts: dict[int, int] = {}
for _, status, _elapsed in api_runs:
    counts[status] = counts.get(status, 0) + 1
print("ステータス別件数:")
for status, count in sorted(counts.items()):
    print(f"  {status}: {count}")
