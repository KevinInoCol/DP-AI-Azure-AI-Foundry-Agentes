#!/usr/bin/env bash
# Crea (o actualiza) la política RAI `munipalidad-girardota-guardrail` en el recurso
# de Foundry a partir de munipalidad-girardota-guardrail.json. Idempotente (PUT).
#
# El agente la usa porque azure.yaml la declara en services.<svc>.policies con el
# ID ARM completo. Si cambias la política aquí, NO hace falta volver a desplegar:
# el agente la referencia por nombre. Si quitas la línea de azure.yaml, el
# siguiente `azd deploy` crea una versión SIN guardrail.
#
# Uso (desde src/agent-framework-agent-municipalidad/):
#   ./guardrails/crear_guardrail.sh
#   ./guardrails/crear_guardrail.sh --ver      # muestra la política actual
set -euo pipefail

SUBSCRIPTION_ID="57ff11aa-f7e9-4f80-a643-565666f00aed"
RESOURCE_GROUP="Datapath-ai-engineer-ka-ic"
FOUNDRY_ACCOUNT="Datapath-AI-Engineer-KAIC"
POLITICA="munipalidad-girardota-guardrail"
API_VERSION="2025-06-01"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CUENTA="https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.CognitiveServices/accounts/${FOUNDRY_ACCOUNT}"

if [[ "${1:-}" == "--ver" ]]; then
  az rest --method get --url "${CUENTA}/raiPolicies/${POLITICA}?api-version=${API_VERSION}"
  exit 0
fi

echo "Aplicando ${POLITICA} en ${FOUNDRY_ACCOUNT}..."
az rest --method put \
  --url "${CUENTA}/raiPolicies/${POLITICA}?api-version=${API_VERSION}" \
  --headers "Content-Type=application/json" \
  --body "@${DIR}/${POLITICA}.json" \
  --query "{nombre:name, modo:properties.mode, base:properties.basePolicyName}" -o json

echo
echo "ID ARM para services.<svc>.policies de azure.yaml:"
echo "${CUENTA#https://management.azure.com}/raiPolicies/${POLITICA}"
