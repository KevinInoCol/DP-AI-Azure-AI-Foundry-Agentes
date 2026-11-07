# Plan B — Desplegar un agente hospedado en Foundry desde cero

## 0. Variables (editar)

```bash
export TENANT_ID="<tenant-id>"
export SUB_ID="<subscription-id>"
export RG="rg-agentes-datapath"
export LOC="eastus2"
export ACCOUNT="datapath-foundry-$RANDOM"     # nombre del recurso Foundry (único global)
export PROJECT="datapath-agentes"
export MODEL="gpt-5.4-mini"
export MODEL_VERSION="2026-03-17"
export EMB_MODEL="text-embedding-3-small"
export AGENT_DIR="agente-hosted/agente-hosted-municipalidad-girardota"
export SERVICE="agent-framework-agent-municipalidad"
export ENDPOINT="https://$ACCOUNT.services.ai.azure.com/api/projects/$PROJECT"
```

## 1. Herramientas

```bash
# macOS
brew install azure-cli
brew install --cask azure/azd/azd
# Windows
winget install --exact --id Microsoft.AzureCLI
winget install --exact --id Microsoft.Azd
# Linux
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
curl -fsSL https://aka.ms/install-azd.sh | bash

azd extension install azure.ai.agents
azd extension upgrade --all
az version && azd version
```

## 2. Login

```bash
az logout
az login --tenant $TENANT_ID
az account set --subscription $SUB_ID
az account show -o table
azd config set auth.useAzCliAuth true
```

## 3. Proveedores

```bash
for NS in Microsoft.CognitiveServices Microsoft.MachineLearningServices Microsoft.Search \
          Microsoft.Storage Microsoft.App Microsoft.ContainerRegistry \
          Microsoft.OperationalInsights Microsoft.Insights; do
  az provider register -n $NS --wait
done
```

## 4. Recurso Foundry + proyecto + modelos

```bash
az group create -n $RG -l $LOC

az cognitiveservices account create -n $ACCOUNT -g $RG -l $LOC \
  --kind AIServices --sku S0 --custom-domain $ACCOUNT \
  --allow-project-management --assign-identity --yes

az cognitiveservices account project create -n $ACCOUNT -g $RG -l $LOC \
  --project-name $PROJECT --assign-identity

az cognitiveservices account deployment create -n $ACCOUNT -g $RG \
  --deployment-name $MODEL --model-name $MODEL --model-version $MODEL_VERSION \
  --model-format OpenAI --sku-name DataZoneStandard --sku-capacity 50

az cognitiveservices account deployment create -n $ACCOUNT -g $RG \
  --deployment-name $EMB_MODEL --model-name $EMB_MODEL --model-version 1 \
  --model-format OpenAI --sku-name Standard --sku-capacity 50

az cognitiveservices account deployment list -n $ACCOUNT -g $RG -o table
```

Si falla por cuota: cambiar `--sku-name` a `GlobalStandard` o bajar `--sku-capacity`.

```bash
az cognitiveservices usage list -l $LOC -o table | grep -i "$MODEL"
```

## 5. Roles (tu usuario + identidad del proyecto)

```bash
ACC_ID=$(az cognitiveservices account show -n $ACCOUNT -g $RG --query id -o tsv)
ME=$(az ad signed-in-user show --query id -o tsv)
PROJ_PID=$(az resource show --ids "$ACC_ID/projects/$PROJECT" --query identity.principalId -o tsv)

for ROLE in "Foundry User" "Cognitive Services OpenAI User"; do
  az role assignment create --assignee-object-id $ME       --assignee-principal-type User             --role "$ROLE" --scope $ACC_ID
  az role assignment create --assignee-object-id $PROJ_PID --assignee-principal-type ServicePrincipal --role "$ROLE" --scope $ACC_ID
done
```

## 6. Apuntar el agente al nuevo proyecto

```bash
cd $AGENT_DIR

# azure.yaml: endpoint del proyecto
sed -i '' "s#endpoint: https://.*/api/projects/.*#endpoint: $ENDPOINT#" azure.yaml   # macOS
# sed -i "s#endpoint: https://.*/api/projects/.*#endpoint: $ENDPOINT#" azure.yaml    # Linux/WSL

# azure.yaml: quitar/actualizar cualquier ruta /subscriptions/... vieja (rai_policy)
grep -n "subscriptions/" azure.yaml

# .env local del agente
cat > src/$SERVICE/.env <<EOF
FOUNDRY_PROJECT_ENDPOINT="$ENDPOINT"
AZURE_AI_MODEL_DEPLOYMENT_NAME="$MODEL"
MEMORY_STORE_NAME="municipalidad_girardota_memory"
EOF

# entorno azd nuevo (el viejo apunta a la suscripción anterior)
rm -rf .azure
azd env new ${PROJECT}-dev --subscription $SUB_ID --location $LOC
azd env set AZURE_TENANT_ID $TENANT_ID
azd env set AZURE_RESOURCE_GROUP $RG
azd env set AZURE_AI_ACCOUNT_NAME $ACCOUNT
azd env set AZURE_AI_PROJECT_NAME $PROJECT
azd env set AZURE_AI_PROJECT_ENDPOINT $ENDPOINT
azd env set FOUNDRY_PROJECT_ENDPOINT $ENDPOINT
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME $MODEL
azd env set USE_EXISTING_AI_PROJECT true
```

## 7. Memoria y base de conocimiento (si el agente las usa)

```bash
cd src/$SERVICE
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Memoria
python memoria/crear_memory_store.py

# RAG: editar primero las constantes de rag/crear_base_conocimiento.py
# (SUBSCRIPTION_ID, RESOURCE_GROUP, FOUNDRY_ACCOUNT, FOUNDRY_PROJECT, AOAI_ENDPOINT,
#  CHAT_DEPLOYMENT, SEARCH_SERVICE, STORAGE_ACCOUNT, PROJECT_CONNECTION)
python rag/crear_base_conocimiento.py

SEARCH_ID=$(az search service show -n <search-service> -g $RG --query id -o tsv)
az role assignment create --assignee-object-id $ME       --assignee-principal-type User             --role "Search Index Data Reader" --scope $SEARCH_ID
az role assignment create --assignee-object-id $PROJ_PID --assignee-principal-type ServicePrincipal --role "Search Index Data Reader" --scope $SEARCH_ID
cd ../..
```

## 8. Prueba local

```bash
cd src/$SERVICE && source .venv/bin/activate
python main.py                       # http://localhost:8088
# otra terminal:
curl -s localhost:8088/responses -H "Content-Type: application/json" \
  -d '{"input":"Hola, ¿qué trámites puedo hacer?"}'
cd ../..
```

## 9. Deploy

```bash
azd deploy $SERVICE
azd env get-values | grep -i AGENT_
```

## 10. Roles para la identidad del agente (después del primer deploy)

```bash
AGENT_PID=$(azd env get-value AGENT_AGENT_FRAMEWORK_AGENT_MUNICIPALIDAD_INSTANCE_IDENTITY_PRINCIPAL_ID)

for ROLE in "Foundry User" "Cognitive Services OpenAI User"; do
  az role assignment create --assignee-object-id $AGENT_PID --assignee-principal-type ServicePrincipal --role "$ROLE" --scope $ACC_ID
done
az role assignment create --assignee-object-id $AGENT_PID --assignee-principal-type ServicePrincipal --role "Search Index Data Reader" --scope $SEARCH_ID   # si usa RAG
```

## 11. Invocar el agente desplegado

```bash
RESP_URL=$(azd env get-value AGENT_AGENT_FRAMEWORK_AGENT_MUNICIPALIDAD_RESPONSES_ENDPOINT)
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
curl -s "$RESP_URL" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"input":"¿Cómo pago el predial?"}'
```

Portal: `https://ai.azure.com/?tid=$TENANT_ID` → proyecto → Agentes.

## 12. Consumo (app de chat)

```bash
cd ../../Consumo-de-Agentes/Agente-de-Municipalidad-Girardota
grep -rln "services.ai.azure.com" --include=*.env --include=*.py --include=*.ts .   # cambiar endpoint/proyecto
```

## Otro agente

Cambiar `AGENT_DIR` y `SERVICE` (nombre bajo `services:` en `azure.yaml`) y repetir 6 → 11.
La variable `AGENT_<SERVICE>_..._PRINCIPAL_ID` cambia según el servicio: `azd env get-values | grep PRINCIPAL_ID`.

## Errores rápidos

| Error | Comando |
|---|---|
| `SubscriptionNotRegistered` | Paso 3 |
| `ReadOnlyDisabledSubscription` | Suscripción deshabilitada → pagar/reactivar en el portal |
| `InsufficientQuota` | `--sku-name GlobalStandard` o menos `--sku-capacity` |
| `401` / `PermissionDenied` | Pasos 5 y 10, esperar 5–10 min |
| `retrieve` → 403 | `Search Index Data Reader` (pasos 7 y 10) |
| Extensión `Incompatible` | `brew upgrade azd && azd extension upgrade --all` |
| Login cae en otro tenant | `az login --tenant $TENANT_ID` |
