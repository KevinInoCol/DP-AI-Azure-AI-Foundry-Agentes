# Coding Agent Instructions

> This project was built with the microsoft-foundry skill. Before working on or answering questions about foundry agents, read the microsoft-foundry skill first.

This project is a **Microsoft Foundry hosted agent** — a containerized AI agent that runs in [Foundry Agent Service](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents). The platform handles containerization, hosting, security, scaling, and observability so you can focus on agent logic.

## Qué es este agente

Asesor inmobiliario virtual de **Alpha State**, construido con **Microsoft Agent Framework** (Python) para el taller **Agentes con Azure AI Foundry (DATAPATH)**.

- Tool `buscar_propiedades_alquiler` (`tools/google_sheets.py`): catálogo de alquileres en Google Sheets (hoja privada con cuenta de servicio vía gspread; pública por CSV export; `origen: csv_local` para demos).
- Tool `consultar_politicas_alpha_state` (`tools/knowledge_base.py`): acción `retrieve` de la knowledge base Foundry IQ `alpha-state-kb` con `DefaultAzureCredential` (identidad administrada del agente en Foundry, `az login` en local). `maxOutputSize` > 5000 obligatorio.
- Base de conocimiento Foundry IQ `alpha-state-kb` en Azure AI Search `srch-alphastate-datapath` (Free, Brazil South), creada con `rag/crear_base_conocimiento.py`.
- Historial de la conversación: host de Foundry (protocolo Responses) o `AgentSession` en consola. Memoria entre conversaciones: **Memoria de Foundry** vía `memoria/proveedor.py` (`MemoriaPorCliente`, subclase de `FoundryMemoryProvider`; store `alpha_state_memory`; scope por petición: `MEMORY_SCOPE` en local, cabecera `x-agent-user-id` en Foundry, `memory.scope_por_defecto` si falta; sección `memory` de `model_config.yaml`; `memoria/crear_memory_store.py` crea el store). Requiere `allow_preview=True` en `FoundryChatClient` y roles Foundry User + Cognitive Services OpenAI User para las identidades del proyecto y del agente.
- Separación de responsabilidades: `model_config/model_config.yaml` (identidad, modelo, opciones, tools) y `prompt/system_prompt.yaml` (solo instrucciones, con placeholders `{bot_name}` `{empresa}` `{ciudad}` que se rellenan desde `model_config`). **No hardcodear prompt ni configuración en `.py`.**
- Guardrail del agente: política RAI `alpha-state-guardrail` referenciada en `azure.yaml` → `policies: [{type: rai_policy, raiPolicyName: <ID ARM>}]`. No quitarla del YAML (el deploy la perdería). Creada por REST; la del asistente del portal bloqueaba todo (skill `azure-foundry-guardrails`).
- El nombre de cada tool debe coincidir carácter por carácter en tres sitios: la función en `tools/`, la clave en `tools:` de `model_config.yaml` y `<Herramientas_Disponibles>` del prompt.

## Key files

- `azure.yaml` — manifiesto azd: nombre del agente en Foundry (`agente-hosted-inmobiliaria`), modelo (`gpt-5.4-mini`, SKU `DataZoneStandard`), runtime (`python_3_13`, deploy-mode code) y variables de entorno del contenedor (`GOOGLE_SHEETS_ID`).
- `src/agent-framework-agent-inmobiliaria/model_config/model_config.yaml` — identidad (Alpha / Alpha State / Lima), despliegue del modelo, opciones (`store: false`) y configuración de tools.
- `src/agent-framework-agent-inmobiliaria/agente.py` — une model_config + prompt + tools y construye el `Agent`.
- `src/agent-framework-agent-inmobiliaria/tools/google_sheets.py` — `CatalogoAlquileres` (carga con caché, normalización, filtros) y `crear_tool_buscar_propiedades`.
- `src/agent-framework-agent-inmobiliaria/tools/knowledge_base.py` — `BaseConocimiento` (retrieve de Foundry IQ) y `crear_tool_consultar_politicas`.
- `src/agent-framework-agent-inmobiliaria/rag/crear_base_conocimiento.py` — crea knowledge source, knowledge base y conexión del proyecto (idempotente).
- `src/agent-framework-agent-inmobiliaria/data/propiedades_alquiler_ejemplo.csv` — plantilla de columnas de la hoja y datos de demo.
- `src/agent-framework-agent-inmobiliaria/tests/` — `test_catalogo.py` (offline) y `demo_tool_csv_local.py` (end-to-end con el modelo).
- `src/agent-framework-agent-inmobiliaria/main.py` — entry point del hosted agent (`ResponsesHostServer`, puerto 8088).
- `src/agent-framework-agent-inmobiliaria/chat_local.py` — consola interactiva con historial en memoria.
- `src/agent-framework-agent-inmobiliaria/prompt/system_prompt.yaml` — instrucciones del agente, versionadas.
- `src/agent-framework-agent-inmobiliaria/Dockerfile` — definición del contenedor (no se usa con deploy-mode code).

## Development workflow

The **Azure Developer CLI (`azd`)** manages the full lifecycle (ejecutar desde la raíz del proyecto, con el venv de `src/agent-framework-agent-inmobiliaria/.venv` activado):

```bash
azd ai agent run --no-client               # Run locally on http://localhost:8088
azd ai agent invoke --local "your message" # Test the local agent
azd deploy --no-prompt                     # Deploy to Foundry
azd ai agent invoke "your message"         # Invoke the deployed agent
```

Antes de desplegar: `azd env set GOOGLE_SHEETS_ID "<id>"` (se inyecta vía `services.<servicio>.env` en `azure.yaml`). Pruebas offline: `.venv/bin/python tests/test_catalogo.py`.

Para cambiar el comportamiento edita `prompt/system_prompt.yaml` (sube `version`); para cambiar identidad, modelo u opciones edita `model_config.yaml`. Para añadir una tool: implementar en `tools/`, registrar en `crear_tools()` de `agente.py`, añadir su bloque en `tools:` de `model_config.yaml` y describirla en el prompt.

## Microsoft Foundry Skill

Install the **Microsoft Foundry Skill** for guided deployment, evaluation, and troubleshooting workflows.

```bash
npx skills add https://github.com/microsoft/azure-skills --skill microsoft-foundry
```

Or install the Azure Skills Plugin in Claude Code: `/plugin install azure@claude-plugins-official`.

## References

- [Hosted agents overview](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [Microsoft Foundry Skill](https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/use-microsoft-foundry-skill)
