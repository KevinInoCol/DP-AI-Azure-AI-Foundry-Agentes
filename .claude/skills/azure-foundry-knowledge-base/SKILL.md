---
name: azure-foundry-knowledge-base
description: Crea una base de conocimiento de Foundry IQ (Azure AI Search, agentic retrieval) a partir de PDFs u otros documentos, la conecta al proyecto de Microsoft Foundry para que aparezca en Compilación → Conocimiento, y la expone a un agente hospedado de Microsoft Agent Framework como tool que llama a la acción retrieve. Cubre Storage + contenedor, creación del servicio AI Search (Free, con la trampa de regiones sin capacidad), knowledge source azureBlob, knowledge base con modelo de planificación, conexión CognitiveSearch del proyecto, roles RBAC (Search Index Data Reader para usuario, identidad del proyecto e identidad del agente) y verificación. Use when the user asks to "crear una base de conocimiento", "Foundry IQ", "subir un PDF para RAG en Foundry", "knowledge base / knowledge source en AI Search", "conectar AI Search al proyecto", "agente que responda con documentos", or types /azure-foundry-knowledge-base.
---

# Base de conocimiento en Foundry IQ (Azure AI Search) para un agente hospedado

Flujo probado el 2026-09-03 con un proyecto de Foundry existente (`datapath-inofuente`, East US 2) y un PDF de políticas de una inmobiliaria. Las plantillas de `templates/` son el código real que quedó funcionando; adáptalas cambiando las constantes de la cabecera.

## Conceptos en 30 segundos

| Objeto | Dónde vive | Qué es |
|---|---|---|
| **Knowledge source** | Azure AI Search | Conexión a los datos (blob con PDFs, índice existente, web, SharePoint). Para `azureBlob`, AI Search crea solo el datasource, el skillset (chunking + embeddings), el índice y el indexador. |
| **Knowledge base** | Azure AI Search | Agrupa una o más fuentes y define el comportamiento de recuperación (agentic retrieval: un LLM planifica subconsultas, búsqueda híbrida, reranking semántico). Se consulta con `POST /knowledgebases/{kb}/retrieve` o por MCP. |
| **Conexión del proyecto** | Foundry (ARM) | Conexión `CognitiveSearch` en el proyecto; hace que el servicio y sus bases aparezcan en el portal (Compilación → Conocimiento). |
| **Tool del agente** | Tu código | Para un hosted agent de Agent Framework, una function tool que llama a `retrieve` con la identidad del contenedor. La tool MCP con conexión de proyecto está pensada para prompt agents. |

API REST de AI Search: `2026-08-01-preview` (planificación de consultas y salida sintetizada) o `2026-04-01` (GA, extractiva).

## Prerequisitos

- `az login` en el tenant correcto; el usuario debe ser Owner (o Search Service Contributor + Search Index Data Contributor + User Access Administrator para roles).
- Proyecto de Foundry con un despliegue de **embeddings** (`text-embedding-3-small`) y un **chat model** soportado para la KB (gpt-5-mini, gpt-5.4-mini, gpt-4.1-mini…).
- Python 3.13 con `requests`, `azure-identity`, `pyyaml`; el SDK `azure-search-documents --pre` es opcional (las plantillas usan REST).

## Paso 0: Confirmar el destino (OBLIGATORIO, antes de crear nada)

Una suscripción puede tener **varios recursos de Foundry** (p. ej. `datapath-inofuente-resource` y `Datapath-AI-Engineer-KAIC`). Si el script apunta al recurso equivocado, la KB se crea y el agente hasta puede consultarla, pero la **conexión queda en otro proyecto** y en Compilación → Conocimiento del proyecto del agente solo aparece "Conexión a un recurso de AI Search para empezar". Pasó el 2026-11-06 al mover el agente de Girardota a KAIC: el script conservaba las constantes del recurso anterior.

1. **Lee el destino del agente**, no lo supongas: endpoint de `azure.yaml` (`services.ai-project.endpoint` → `https://<recurso>.services.ai.azure.com/api/projects/<proyecto>`), `.env` local y `azd env get-values`. Si hay un `CLAUDE.md`/bitácora con un "DESTINO ACTUAL", contrástalo.
2. **Lista lo que hay** y resuelve el RG real de cada recurso (no asumas que comparten RG):
   ```bash
   az cognitiveservices account list --query "[?kind=='AIServices'].{name:name,rg:resourceGroup,loc:location}" -o table
   az search service list --query "[].{name:name,rg:resourceGroup,sku:sku.name}" -o table   # el AI Search puede estar en otro RG
   az cognitiveservices account deployment list -n <recurso> -g <rg> --query "[].name" -o tsv  # embeddings + chat existen AQUÍ
   ```
3. **Pregunta al usuario** (AskUserQuestion) recurso + proyecto cuando haya más de un recurso de Foundry, o cuando `azure.yaml` y las constantes del script no coincidan. Nunca reutilices las constantes de otro agente/proyecto sin confirmarlo.
4. Ajusta en la cabecera del script `FOUNDRY_RESOURCE_GROUP`, `FOUNDRY_ACCOUNT`, `FOUNDRY_PROJECT`, `AOAI_ENDPOINT`, `CHAT_DEPLOYMENT` (que exista en ese recurso), `SEARCH_RESOURCE_GROUP` y `STORAGE_RESOURCE_GROUP`.
5. El script ejecuta `verificar_destino()` antes de crear nada: compara con `azure.yaml`, comprueba que recurso, despliegues y AI Search existen, imprime el destino y pide confirmación (`--yes` para omitirla tras confirmar con el usuario).

Si la KB ya existe en un AI Search compartido y solo cambió el proyecto del agente, **vuelve a correr el script con el destino nuevo** (todo es `PUT` idempotente): actualiza el modelo de planificación de la KB y crea la conexión en el proyecto correcto, sin reindexar desde cero.

## Paso 1: Storage y subida del documento

```bash
RG=<rg>; LOC=<region-del-proyecto>; SA=st<nombre>$(openssl rand -hex 3)
az storage account create -n "$SA" -g $RG -l $LOC --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 --allow-blob-public-access false
az storage container create --account-name "$SA" -n base-conocimiento --auth-mode key
az storage blob upload --account-name "$SA" -c base-conocimiento -f "<ruta>/documento.pdf" -n "documento.pdf" --auth-mode key --overwrite
```

Usa `--auth-mode key`: ser Owner no da roles de datos de blob (`--auth-mode login` falla con "You do not have the required permissions").

Si el PDF está dentro de la carpeta del agente hospedado, añade su carpeta a `.azdignore` para que no viaje en el paquete de código.

## Paso 2: Servicio de Azure AI Search

Decidir el nivel con el usuario (es un recurso facturable):

| Nivel | Costo | Cuándo |
|---|---|---|
| **free** | 0 | Taller / PoC. 50 MB, 3 índices, 1 por suscripción. Sin identidad administrada → conexiones a Storage y modelos con claves. Solo en regiones marcadas con "agentic retrieval en free tier" (East US 2, Brazil South, Central US no, etc.). |
| **basic** | ~US$ 74/mes | Identidad administrada, RBAC sin claves, 15 GB. |

```bash
az search service create -n <nombre> -g $RG -l <region> --sku free \
  --auth-options aadOrApiKey --aad-auth-failure-mode http401WithBearerChallenge
```

**Trampa real:** East US 2 devolvió `InsufficientResourcesAvailable: The region 'eastus2' is currently out of the resources required to provision new services`. La lista de regiones marca East US, East US 2, North Europe, Germany West Central y UAE North como "high demand". Elige otra región con agentic retrieval en Free (por ejemplo **Brazil South**). El servicio de búsqueda puede estar en una región distinta al Storage y a los modelos; no afecta.

Verifica acceso al plano de datos con tu token:

```bash
TOKEN=$(az account get-access-token --scope https://search.azure.com/.default --query accessToken -o tsv)
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" "https://<svc>.search.windows.net/indexes?api-version=2026-08-01-preview"   # 200
```

## Paso 3: Knowledge source + knowledge base + conexión (script)

Copia `templates/crear_base_conocimiento.py` a `rag/` del agente, ajusta las constantes con el destino confirmado en el Paso 0 (suscripción, RG de cada recurso, recurso y proyecto de Foundry, endpoint `https://<recurso>.openai.azure.com/`, despliegues de embedding y chat, nombre del servicio de búsqueda, storage, contenedor, nombres de KS/KB/conexión) y ejecútalo con el venv del agente. Es idempotente (todo son `PUT`).

Qué hace:
1. Obtiene con `az` (sin imprimir) la connection string del Storage, la clave del recurso de Foundry y la admin key del servicio de búsqueda. Necesarias porque el nivel Free no tiene identidad administrada.
2. `PUT /knowledgesources/<ks>` kind `azureBlob`, `contentExtractionMode: minimal`, `disableImageVerbalization: true`, embedding con `apiKey`.
3. `PUT /knowledgebases/<kb>` con `knowledgeSources`, `models` (chat con `apiKey`), `outputMode: extractiveData`, `retrievalInstructions` en español y `retrievalReasoningEffort: low`.
4. `PUT` de la conexión del proyecto (ARM, `api-version=2025-06-01`): `category: CognitiveSearch`, `authType: ApiKey`, `credentials.key` = admin key, `metadata: {ApiType: Azure, ResourceId, location}`.
5. Espera `status: active` del knowledge source y lanza una consulta de prueba.

Comprueba la indexación real (el `status: active` del KS no garantiza que el indexador terminó):

```bash
curl -s -H "Authorization: Bearer $TOKEN" "https://<svc>.search.windows.net/indexers/<ks>-indexer/status?api-version=2026-08-01-preview" | jq '.lastResult | {status, itemsProcessed, itemsFailed}'
curl -s -H "Authorization: Bearer $TOKEN" "https://<svc>.search.windows.net/indexes/<ks>-index/stats?api-version=2026-08-01-preview"
```

## Paso 4: Roles para consultar (retrieve)

`retrieve` devuelve **403 aunque seas Owner**: hace falta **Search Index Data Reader** en el servicio de búsqueda para cada identidad que consulta:

```bash
SEARCH_ID=$(az search service show -n <svc> -g $RG --query id -o tsv)
az role assignment create --assignee-object-id $(az ad signed-in-user show --query id -o tsv) --assignee-principal-type User --role "Search Index Data Reader" --scope "$SEARCH_ID"
# identidad del proyecto de Foundry (para tools MCP / portal):
az role assignment create --assignee-object-id <principalId del proyecto> --assignee-principal-type ServicePrincipal --role "Search Index Data Reader" --scope "$SEARCH_ID"
# identidad de instancia del agente hospedado (azd ai agent show → Instance Identity Principal ID):
az role assignment create --assignee-object-id <principalId del agente> --assignee-principal-type ServicePrincipal --role "Search Index Data Reader" --scope "$SEARCH_ID"
```

La propagación tarda de 1 a 10 minutos.

Prueba directa:

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "https://<svc>.search.windows.net/knowledgebases/<kb>/retrieve?api-version=2026-08-01-preview" \
  -d '{"messages":[{"role":"user","content":[{"type":"text","text":"¿Qué multa hay por pagar con atraso?"}]}],"maxOutputSize":8000}'
```

La respuesta trae `response[0].content[0].text` (JSON con `ref_id` y `content` por fragmento), `references` (con `blobUrl`) y `activity` (planificación, subconsultas, reranking).

## Paso 5: Tool para el agente hospedado (Agent Framework)

Copia `templates/tool_knowledge_base.py` a `tools/knowledge_base.py`. Expone `crear_tool_consultar_politicas(BaseConocimiento(cfg))`; la clase llama a `retrieve` con `DefaultAzureCredential().get_token("https://search.azure.com/.default")` (sesión de `az login` en local, identidad administrada del agente en Foundry). Regístrala en `crear_tools()` de `agente.py`, añade su bloque en `tools:` de `model_config.yaml` y descríbela en `<Herramientas_Disponibles>`, `<Fuentes_De_Datos>` y `<Reglas_De_Uso_De_Tools>` del system prompt (skill `azure-foundry-agent-tools`). Renombra la tool al dominio del cliente si no es una inmobiliaria.

Reglas que evitan errores reales:
- `maxOutputSize` debe ser **mayor que 5000** (`InvalidRequestParameter: Configuration max output size must be greater than 5000`). La plantilla fuerza el mínimo.
- Si la tool devuelve una lista vacía, añade un `aviso` para que el modelo diga que la base no cubre la duda y derive a un humano; en el prompt prohíbe completar políticas con conocimiento general.
- Prueba offline con `templates/test_base_conocimiento.py` (retrieve simulado) y end-to-end en local antes de `azd deploy`.

## Paso 6: Verificación end-to-end

1. Local: crear el agente, preguntar algo que solo esté en el documento y algo que no esté (debe decir que no lo encontró).
2. `azd deploy --no-prompt` y `azd ai agent invoke "..."` remoto: confirma que la identidad del agente puede consultar (si 403, revisa el rol del paso 4).
3. Portal: Compilación → Conocimiento debe mostrar el servicio conectado y la base.

## Mantenimiento

- Documento nuevo o cambiado: sube el blob y ejecuta el indexador (`POST /indexers/<ks>-indexer/run`) o vuelve a correr el script.
- Cambiar modelo o instrucciones de la KB: vuelve a correr el script (PUT idempotente).
- Alternativa MCP para prompt agents: endpoint `https://<svc>.search.windows.net/knowledgebases/<kb>/mcp?api-version=2026-08-01-preview`, tool `knowledge_base_retrieve`, conexión `RemoteTool` con `ProjectManagedIdentity`.

## Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| `InsufficientResourcesAvailable` al crear AI Search | Región sin capacidad | Otra región con agentic retrieval en Free (Brazil South) |
| `az storage blob upload --auth-mode login` → permisos | Owner no tiene rol de datos de blob | `--auth-mode key` o rol Storage Blob Data Contributor |
| `retrieve` → 403 | Falta Search Index Data Reader | Paso 4 y esperar propagación |
| `retrieve` → 400 `max output size must be greater than 5000` | `maxOutputSize` bajo | ≥ 5001 (plantilla usa 8000) |
| `azd deploy` → `String length N exceeds maximum 512, param description` | Descripción del servicio en azure.yaml muy larga | Acortar `services.<svc>.description` a < 512 caracteres |
| La KB no aparece en Compilación → Conocimiento | Falta la conexión del proyecto, o se creó en **otro** recurso/proyecto de Foundry | Paso 0 (confirmar destino) y volver a correr el script; verifica con `az rest --method get --url "https://management.azure.com<PROJECT_ARM_ID>/connections?api-version=2025-06-01"` |
| `DESTINO DISTINTO` al ejecutar el script | Constantes del script ≠ endpoint de `azure.yaml` | Corregir `FOUNDRY_*` (Paso 0) |
| Indexador `success` pero `documentCount: 0` | Contenedor vacío o formato no soportado | Revisa el blob y `lastResult.errors` |

## Referencias

- Crear knowledge base: https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base
- Knowledge source blob: https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-blob
- Regiones y niveles: https://learn.microsoft.com/azure/search/search-region-support
- Conectar agentes a Foundry IQ: https://learn.microsoft.com/azure/foundry/agents/how-to/foundry-iq-connect
