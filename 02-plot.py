import json
import os

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle as pltRectangle

mpl.rcParams["figure.figsize"] = [15, 7]

with open("result.json", encoding="utf-8") as f:
    api_runs = json.load(f)

# result.json は (Tokens, Status Code) または (Tokens, Status Code, Elapsed) のいずれか
has_elapsed = len(api_runs[0]) >= 3
columns = ["Tokens", "Status Code", "Elapsed"] if has_elapsed else ["Tokens", "Status Code"]
df = pd.DataFrame(api_runs, columns=columns)
df["Run"] = range(1, len(df) + 1)

# ステータスコードごとの配色（200 = 成功 / 429 = レート制限）
def status_color(code: int) -> str:
    if code == 200:
        return "lightblue"
    if code == 429:
        return "lightsalmon"
    return "lightgray"

colors = [status_color(int(code)) for code in df["Status Code"]]
ax = df.plot(kind="bar", x="Run", y="Tokens", color=colors, legend=False)

# 429 のバーに注記を付ける
for i, code in enumerate(df["Status Code"]):
    if int(code) == 429:
        ax.text(i, 5, "429", ha="center", va="bottom", fontsize=8, color="red")

# 成功（200）の Run では消費トークンを注記する
for i, (code, tokens) in enumerate(zip(df["Status Code"], df["Tokens"])):
    if int(code) == 200:
        ax.text(i, tokens + 2, str(int(tokens)), ha="center", va="bottom", fontsize=8)

# 経過秒があれば、1 分（時間窓）の境界に縦線を引いて回復のタイミングを示す
if has_elapsed:
    max_elapsed = float(df["Elapsed"].max())
    for boundary in range(60, int(max_elapsed) + 60, 60):
        # 境界秒の直後にある最初の Run の位置に線を引く
        after = df[df["Elapsed"] >= boundary]
        if after.empty:
            continue
        pos = int(after.index[0])
        ax.axvline(pos - 0.5, color="gray", linestyle="--", linewidth=1)
        ax.text(pos - 0.5, df["Tokens"].max(), f"{boundary}s window reset",
                rotation=90, va="top", ha="right", fontsize=8, color="gray")

# 凡例（実際に出現したステータスのみ）
unique_codes = df["Status Code"].unique()
legend_labels = [
    pltRectangle((0, 0), 1, 1, color=status_color(int(code))) for code in unique_codes
]
ax.legend(legend_labels, [str(int(code)) for code in unique_codes], title="Status Code")

plt.title("Token Rate Limiting results (tokens-per-minute=100)")
plt.xlabel("Run #")
plt.ylabel("Total Tokens")
plt.xticks(rotation=0)

os.makedirs("images", exist_ok=True)
output_path = "images/token-rate-limiting-result.png"
plt.savefig(output_path, bbox_inches="tight", dpi=120)
print(f"保存しました: {output_path}")
