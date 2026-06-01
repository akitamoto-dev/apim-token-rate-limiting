#!/usr/bin/env bash
# AI Gateway トークンレート制限検証のデプロイスクリプト
# what-if で差分確認 → デプロイ → 出力を .env に書き出す。再実行可能。
set -euo pipefail

cd "$(dirname "$0")"

# ------------------
#    設定
# ------------------
RESOURCE_GROUP_NAME="rg-ai-gateway-token-rate-limiting"
RESOURCE_GROUP_LOCATION="japaneast"
DEPLOYMENT_NAME="token-rate-limiting"
TEMPLATE_FILE="main.bicep"
PARAMETERS_FILE="params.json"

echo "==> リソースグループを作成 (存在しなければ): ${RESOURCE_GROUP_NAME} (${RESOURCE_GROUP_LOCATION})"
az group create \
  --name "${RESOURCE_GROUP_NAME}" \
  --location "${RESOURCE_GROUP_LOCATION}" \
  --output none

echo "==> what-if で差分を確認"
az deployment group what-if \
  --name "${DEPLOYMENT_NAME}" \
  --resource-group "${RESOURCE_GROUP_NAME}" \
  --template-file "${TEMPLATE_FILE}" \
  --parameters "@${PARAMETERS_FILE}" || true

echo "==> デプロイを実行"
az deployment group create \
  --name "${DEPLOYMENT_NAME}" \
  --resource-group "${RESOURCE_GROUP_NAME}" \
  --template-file "${TEMPLATE_FILE}" \
  --parameters "@${PARAMETERS_FILE}" \
  --output none

echo "==> デプロイ出力を取得"
OUTPUTS=$(az deployment group show \
  --name "${DEPLOYMENT_NAME}" \
  --resource-group "${RESOURCE_GROUP_NAME}" \
  --query properties.outputs \
  --output json)

GATEWAY_URL=$(echo "${OUTPUTS}" | python3 -c "import sys,json;print(json.load(sys.stdin)['apimResourceGatewayURL']['value'])")
SUBSCRIPTION_KEY=$(echo "${OUTPUTS}" | python3 -c "import sys,json;print(json.load(sys.stdin)['apimSubscriptions']['value'][0]['key'])")

echo "==> .env を書き出し (秘匿値を含むため git 管理外)"
cat > .env <<EOF
APIM_GATEWAY_URL=${GATEWAY_URL}
APIM_SUBSCRIPTION_KEY=${SUBSCRIPTION_KEY}
INFERENCE_API_PATH=inference
INFERENCE_API_VERSION=2025-03-01-preview
MODEL_NAME=gpt-4.1-mini
EOF

echo "==> 完了。ゲートウェイ URL: ${GATEWAY_URL}"
echo "    サブスクリプションキー: ****${SUBSCRIPTION_KEY: -4} (.env に保存済み)"
