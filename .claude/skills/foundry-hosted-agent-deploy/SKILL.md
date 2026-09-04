---
name: foundry-hosted-agent-deploy
description: Crea, prueba en local y despliega un agente hospedado (hosted agent) en Microsoft Foundry / Azure AI Foundry usando azd (Azure Developer CLI) y una plantilla oficial (Microsoft Agent Framework, LangGraph, OpenAI Agents SDK, etc.), apuntando a un proyecto de Foundry existente. Incluye instalación de prerequisitos (azd + extensión microsoft.foundry, auth reutilizando Azure CLI), verificación de cuota del modelo, scaffold, ajustes de azure.yaml, venv correcto, prueba local, azd deploy, invocación remota y solución de problemas. Use when the user asks to "programar un agente", "desplegar un agente hospedado", "hosted agent", "azd ai agent init", "agente con Agent Framework/LangGraph en Foundry", "subir mi agente a Foundry", or types /foundry-hosted-agent-deploy.
---

# Desplegar un agente hospedado en Microsoft Foundry con azd

Flujo de punta a punta, probado el 2026-09-03 en macOS con un proyecto de Foundry ya creado desde el portal. Sigue los pasos en orden. Si el plugin oficial `azure` de Claude Code está instalado, carga también la skill `azure:microsoft-foundry` antes de empezar: esta skill es compatible con ella y resume su quick start con los tropiezos reales resueltos.

## Conceptos en 30 segundos

| Tipo de agente | Qué es | Cómo se crea |
|---|---|---|
| **Prompt agent** | Modelo + instrucciones + herramientas declaradas, sin código | Portal ai.azure.com → "Crear un agente", o Azure MCP |
| **Hosted agent** | Contenedor con tu propio código (Python/.NET) que habla el protocolo Responses o Invocations | `azd ai agent init` + `azd deploy` (esta skill) |

Con `--deploy-mode code` no hace falta Docker ni Azure Container Registry: azd sube el código y Foundry construye el runtime.

## Prerequisitos

| Requisito | Comprobar | Instalar |
|---|---|---|
| Azure CLI con sesión | `az account show` | `az login --tenant <tenant-id>` |
| Azure Developer CLI (azd) ≥ 1.27 | `azd version` | macOS `brew install azd`, Windows `winget install microsoft.azd`, Linux `curl -fsSL https://aka.ms/install-azd.sh \| bash` |
| Extensión `microsoft.foundry` de azd | `azd extension list` | `azd extension install microsoft.foundry` |
| Python 3.13 (para plantillas Python) | `python3.13 --version` | macOS `brew install python@3.13`, Windows `winget install Python.Python.3.13` |
| Proyecto de Foundry existente | `az cognitiveservices account list` | Crear desde https://ai.azure.com/?tid=<tenant-id> |

Los scripts `scripts/install-prereqs.sh` (macOS/Linux) y `scripts/install-prereqs.ps1` (Windows) instalan lo que falte y configuran la autenticación del paso 1.

## Paso 1: Autenticación de azd sin abrir el navegador

`azd` tiene su propio login. En lugar de `azd auth login` (abre navegador y puede caer en un tenant corporativo equivocado), haz que reutilice la sesión de Azure CLI:

```bash
azd config set auth.useAzCliAuth true
azd auth login --check-status     # debe decir "Logged in to Azure as ..."
```

Si la cuenta es invitada en varios tenants, asegúrate de que Azure CLI esté en el correcto: `az account show --query tenantId`.

## Paso 2: Datos del proyecto de Foundry

Obtén el ARM ID del proyecto (lo necesita `azd ai agent init --project-id`):

```bash
SUB=$(az account show --query id -o tsv)
az cognitiveservices account list --query "[?kind=='AIServices'].{nombre:name, rg:resourceGroup, region:location}" -o table
# Con el nombre del recurso y su RG:
az rest --method get --url "https://management.azure.com/subscriptions/$SUB/resourceGroups/<RG>/providers/Microsoft.CognitiveServices/accounts/<RECURSO>/projects?api-version=2025-06-01" \
  --query "value[].{id:id, endpoint:properties.endpoints.\"AI Foundry API\"}" -o table
```

El ARM ID tiene la forma `/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<recurso>/projects/<proyecto>`.

## Paso 3: Elegir la plantilla

```bash
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent sample list --language python
```

Recomendaciones para un taller:

| Caso | Plantilla | Entry point |
|---|---|---|
| Primer agente, mínimo | Basic agent (Responses, Agent Framework, Python) | `main.py` |
| Agente con herramientas propias (function calling) | Agent with Local Tools (Responses, Agent Framework, Python) | `main.py` |
| Stack LangChain / LangGraph | Agent with Foundry Toolbox (Responses, LangGraph, Python) | `main.py` |
| Sin framework, solo SDK | Note-taking agent (Responses, without a framework, Python) | ver README de la plantilla |

Copia la URL del `Manifest:` de la plantilla elegida. Antes de continuar, lee su `azure.yaml` en GitHub (cambia `blob` por `raw`) y anota el modelo, versión y SKU que declara en `services.ai-project.deployments[]`.

## Paso 4: Verificar cuota del modelo ANTES del scaffold

Las plantillas suelen pedir `GlobalStandard`, y las suscripciones nuevas tienen cuota 0 en ese SKU. Comprueba en la región del proyecto:

```bash
az cognitiveservices usage list -l <region> --query "[?contains(name.value, '<modelo>')].{sku:name.value, usado:currentValue, limite:limit}" -o table
```

Si `limite` es 0 para el SKU de la plantilla, elige otro SKU con cuota (por ejemplo `DataZoneStandard` o `Standard`) y cámbialo en `azure.yaml` en el paso 6. Verifica que el modelo soporte ese SKU:

```bash
az cognitiveservices model list -l <region> --query "[?model.name=='<modelo>'].{version:model.version, skus:join(',', model.skus[].name)}" -o table
```

## Paso 5: Scaffold

Ejecuta desde una carpeta contenedora (azd crea una subcarpeta con el nombre del agente):

```bash
mkdir -p agente-hosted && cd agente-hosted
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent init --no-prompt \
  -m "<manifestUrl>" \
  --deploy-mode code \
  --runtime python_3_13 \
  --entry-point main.py \
  --agent-name <nombre-unico> \
  --project-id "<ARM-ID-del-proyecto>"
cd <nombre-unico>
```

Reglas:
- `--runtime` debe ser exactamente `python_3_13`, `python_3_14` o `dotnet_10`.
- `--entry-point` debe coincidir con el archivo real de la plantilla.
- Si azd avisa **"An agent named 'X' already exists in this Foundry project"**, ese nombre ya lo usa otro agente (por ejemplo un prompt agent creado en el portal). Cambia `services.<servicio>.name` en `azure.yaml` a un nombre único; si no, `azd deploy` creará una versión encima del agente existente.
- El scaffold ya deja `.azure/<env>/.env` con `FOUNDRY_PROJECT_ENDPOINT`, `AZURE_AI_PROJECT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_LOCATION`, etc. No hace falta `azd env set` para esos valores cuando se usa `--project-id`.

## Paso 6: Ajustar `azure.yaml` y el código

En `azure.yaml`:
1. `services.<servicio>.name` → nombre único del agente (ver paso 5).
2. `services.ai-project.deployments[].sku.name` → SKU con cuota (paso 4).
3. `services.<servicio>.description` → describe el propósito real; se usa para generar la evaluación.

En `src/<servicio>/main.py`: adapta las `instructions` al caso de uso (idioma, tono, dominio). No toques nada más salvo que se pidan herramientas.

Sanity check antes de seguir:
- `deployments[]` no vacío con `name`, `model.{name,format,version}`, `sku.{name,capacity}`.
- `env.AZURE_AI_MODEL_DEPLOYMENT_NAME: ${AZURE_AI_MODEL_DEPLOYMENT_NAME}` (llaves simples con `$`, no `{{ }}`).
- `codeConfiguration.entryPoint` existe en `src/<servicio>/`.

Añade el marcador en `AGENTS.md` (o `CLAUDE.md`) del proyecto generado si no existe:
```
This project was built with the microsoft-foundry skill. Before working on or answering questions about foundry agents, read the microsoft-foundry skill first.
```

## Paso 7: Aprovisionar el despliegue del modelo

Aunque el proyecto ya exista, `azd provision` crea el despliegue del modelo dentro de él (tarda ~1 min). No crea un proyecto nuevo porque `USE_EXISTING_AI_PROJECT=true` quedó en el env.

```bash
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --no-prompt
az cognitiveservices account deployment list -n <recurso> -g <rg> -o table   # verificar
```

Nunca crees el despliegue con `az cognitiveservices account deployment create`: quedaría fuera del ciclo de vida de azd.

## Paso 8: `.env` local y venv correcto

```bash
EP=$(azd env get-value FOUNDRY_PROJECT_ENDPOINT); MD=$(azd env get-value AZURE_AI_MODEL_DEPLOYMENT_NAME)
printf 'FOUNDRY_PROJECT_ENDPOINT=%s\nAZURE_AI_MODEL_DEPLOYMENT_NAME=%s\n' "$EP" "$MD" > src/<servicio>/.env
azd env set AZURE_AI_PROJECT_ENDPOINT "$EP"
azd env set AZURE_AI_MODEL_DEPLOYMENT_NAME "$MD"
```

El venv **debe vivir en `src/<servicio>/`** (junto a `requirements.txt`) y tener `uv` para que la instalación tarde segundos:

```bash
/opt/homebrew/bin/python3.13 -m venv src/<servicio>/.venv        # macOS; en Windows: py -3.13 -m venv src\<servicio>\.venv
src/<servicio>/.venv/bin/python -m pip install -q uv
src/<servicio>/.venv/bin/python --version                        # debe decir 3.13.x
```

Usa siempre rutas explícitas al Python del venv. Un alias `python` en el shell del usuario (muy común en macOS: `python` → `/usr/bin/python3` 3.9) hace que `python -m pip install uv` instale fuera del venv aunque esté activado.

## Paso 9: Prueba local

Arranca el servidor en una sesión gestionada en segundo plano (no con `&` ni `nohup`, muere al cerrar el shell) con el venv activado:

```bash
source src/<servicio>/.venv/bin/activate
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent run --no-client
```

Espera la línea `Running on http://0.0.0.0:8088` en el log (no basta con `Starting agent on ...`). Luego:

```bash
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent invoke --local "Hola, preséntate en dos frases."
```

Detén el servidor antes de desplegar: `lsof -ti :8088 | xargs kill` (macOS/Linux) o cierra la sesión.

## Paso 10: Desplegar y verificar

```bash
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd deploy --no-prompt        # ~2-3 min
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent show --output json  # status: active + playground_url
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent invoke "¿Qué puedes hacer?"   # remoto, se factura
```

La primera respuesta remota tarda 10 a 20 s por arranque en frío; es normal.

## Paso 11: Evaluación (opcional, asíncrona)

```bash
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent eval generate --gen-instruction "<description de azure.yaml>" --no-wait --no-prompt
# minutos después:
azd ai agent eval run
```

## Resumen final que debes entregar al usuario

Nombre y versión del agente, estado, URL del playground (sale en `azd ai agent show`), endpoint `responses`, modelo y SKU desplegados, carpeta del código y los comandos de seguimiento:

```bash
azd ai agent invoke "mensaje"    # chatear con el agente desplegado
azd ai agent run --no-client     # correrlo en local
azd deploy --no-prompt           # nueva versión tras editar main.py
azd down                         # eliminar todo al terminar
```

## Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| `Not logged in, run azd auth login` | azd no comparte sesión con az | `azd config set auth.useAzCliAuth true` |
| `azd provision` falla por cuota / `InsufficientQuota` | SKU de la plantilla sin cuota | Paso 4: cambiar `sku.name` en `azure.yaml` y volver a aprovisionar |
| `--runtime must be one of: python_3_13, python_3_14, dotnet_10` | Se pasó `python` | Usar el token completo |
| `--entry-point is required when using --deploy-mode code with --no-prompt` | Falta `--entry-point` | Añadir el archivo real (`main.py`) |
| `An agent named 'X' already exists` | Nombre repetido en el proyecto | Cambiar `services.<servicio>.name` |
| `invoke --local` devuelve `could not connect` | Servidor no listo o murió con el shell | Esperar la línea `Running on`; relanzar en sesión gestionada |
| Dependencias tardan minutos | El venv no tiene `uv` o está en la raíz | Venv en `src/<servicio>/` con `uv` instalado con la ruta explícita |
| `.venv/bin/python` es 3.9 o 3.14 | Alias `python` o `python3` incorrecto | Crear el venv con `/opt/homebrew/bin/python3.13` o `py -3.13` |
| Modelo `404` en local | `AZURE_AI_MODEL_DEPLOYMENT_NAME` desincronizado | Repetir paso 8 |
| Postdeploy pide `AZURE_TENANT_ID` | Falta en el env | `azd env set AZURE_TENANT_ID $(az account show --query tenantId -o tsv)` y repetir `azd deploy` |
| Portal ai.azure.com dice "No puede acceder a este recurso" | Sesión en otro tenant (cuenta invitada corporativa) | Incógnito o perfil de navegador aparte con `https://ai.azure.com/?tid=<tenant-id>&prompt=login` |

## Referencias

- Hosted agents: https://learn.microsoft.com/azure/ai-foundry/agents/concepts/hosted-agents
- azd para agentes: https://aka.ms/azd-ai-agent-docs
- Plantillas oficiales: https://github.com/microsoft-foundry/foundry-samples
- Instalar azd: https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd
