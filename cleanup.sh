#!/usr/bin/env bash
# AI Gateway トークンレート制限検証のクリーンアップスクリプト
# リソースグループ削除 + ソフトデリート対象のパージまで実行。
set -euo pipefail

cd "$(dirname "$0")"

RESOURCE_GROUP_NAME="rg-ai-gateway-token-rate-limiting"

echo "==> パージ対象 (Cognitive Services) を採取"
COGNITIVE_ACCOUNTS=$(az cognitiveservices account list \
  --resource-group "${RESOURCE_GROUP_NAME}" \
  --query "[].{name:name, location:location}" \
  --output json 2>/dev/null || echo "[]")

echo "==> パージ対象 (APIM) を採取"
APIM_SERVICES=$(az apim list \
  --resource-group "${RESOURCE_GROUP_NAME}" \
  --query "[].{name:name, location:location}" \
  --output json 2>/dev/null || echo "[]")

echo "==> リソースグループを削除: ${RESOURCE_GROUP_NAME}"
az group delete --name "${RESOURCE_GROUP_NAME}" --yes --no-wait || true

echo "==> リソースグループ削除の完了を待機"
az group wait --name "${RESOURCE_GROUP_NAME}" --deleted || true

# 削除待機中にアクセストークンが失効すると後続のパージが ExpiredAuthenticationToken で失敗するため、
# パージ前にトークンを更新しておく (失効していれば再認証を促す)。
echo "==> アクセストークンを更新"
if ! az account get-access-token --output none 2>/dev/null; then
  echo "    トークンを更新できませんでした。'az login' を実行してから再度クリーンアップしてください。" >&2
  exit 1
fi

SUBSCRIPTION_ID=$(az account show --query id --output tsv)

echo "==> Cognitive Services をパージ"
echo "${COGNITIVE_ACCOUNTS}" | python3 -c "
import sys, json
for a in json.load(sys.stdin):
    print(f\"{a['name']} {a['location']}\")
" | while read -r name location; do
  [ -z "${name}" ] && continue
  echo "    purge: ${name} (${location})"
  az cognitiveservices account purge \
    --name "${name}" \
    --location "${location}" \
    --resource-group "${RESOURCE_GROUP_NAME}" || true
done

echo "==> APIM をパージ"
echo "${APIM_SERVICES}" | python3 -c "
import sys, json
for a in json.load(sys.stdin):
    print(f\"{a['name']} {a['location']}\")
" | while read -r name location; do
  [ -z "${name}" ] && continue
  echo "    purge: ${name} (${location})"
  az apim deletedservice purge \
    --service-name "${name}" \
    --location "${location}" || true
done

echo "==> 完了"
