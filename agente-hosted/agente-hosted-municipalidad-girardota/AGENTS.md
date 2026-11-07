# Coding Agent Instructions

> This project was built with the microsoft-foundry skill. Before working on or answering questions about foundry agents, read the microsoft-foundry skill first.

This project is a **Microsoft Foundry hosted agent** — a containerized AI agent that runs in [Foundry Agent Service](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents). The platform handles containerization, hosting, security, scaling, and observability so you can focus on agent logic.

## Qué es este agente

Asistente virtual de la **Alcaldía Municipal de Girardota** (Antioquia, Colombia), construido con **Microsoft Agent Framework** (Python) para el taller **Agentes con Azure AI Foundry (DATAPATH)**.

- Tool `consultar_tramites_girardota` (`tools/knowledge_base.py`): acción `retrieve` de la knowledge base Foundry IQ `girardota-kb` con `DefaultAzureCredential` (identidad administrada del agente en Foundry, `az login` en local). `maxOutputSize` > 5000 obligatorio. **Activa desde el 2026-09-12.** Si se pusiera `enabled: false`, `crear_tools()` registra la versión *pendiente* de la tool (devuelve un error controlado): dejar al agente sin tool hace que el modelo escriba la llamada como texto plano al ciudadano.
- Base de conocimiento Foundry IQ `girardota-kb` en el Azure AI Search `srch-alphastate-datapath` (Free, Brazil South, compartido con el agente inmobiliario: el nivel Free solo permite un servicio por suscripción). Creada con `rag/crear_base_conocimiento.py` desde `rag/Base de Conocimiento/` ("MANUAL DE TRÁMITES - Municipio de Girardota.pdf", 147 fragmentos indexados). Storage propio `stgirardotadatapath/base-conocimiento`, knowledge source `girardota-tramites-ks`. Para añadir o cambiar documentos: copiarlos en esa carpeta y volver a ejecutar el script (idempotente). La identidad del agente tiene `Search Index Data Reader` en el servicio de búsqueda.
- Historial de la conversación: host de Foundry (protocolo Responses) o `AgentSession` en consola. Memoria entre conversaciones: **Memoria de Foundry** vía `memoria/proveedor.py` (`MemoriaPorCiudadano`, subclase de `FoundryMemoryProvider`; store `municipalidad_girardota_memory`; scope por petición: `MEMORY_SCOPE` en local, cabecera `x-agent-user-id` en Foundry, `memory.scope_por_defecto` si falta). Requiere `allow_preview=True` en `FoundryChatClient` y roles Foundry User + Cognitive Services OpenAI User para las identidades del proyecto y del agente.
- Guardrail del agente: la política RAI `munipalidad-girardota-guardrail` está creada en el recurso y versionada en `guardrails/`, pero **NO se aplica al agente**: la sección `policies` de `azure.yaml` está comentada porque los filtros de entrada bloqueaban de forma intermitente consultas ciudadanas legítimas (medición en `guardrails/LEEME.md`). El agente hereda el guardrail del despliegue del modelo. No la reactives sin pasar antes la batería de regresión de ese archivo.
- Separación de responsabilidades: `model_config/model_config.yaml` (identidad, modelo, opciones, tools, memoria) y `prompt/system_prompt.yaml` (solo instrucciones, con placeholders `{bot_name}` `{entidad}` `{municipio}` `{moneda}` `{canal_oficial}` que se rellenan desde `model_config`). **No hardcodear prompt ni configuración en `.py`.**
- El nombre de cada tool debe coincidir carácter por carácter en tres sitios: la función en `tools/`, la clave en `tools:` de `model_config.yaml` y `<Herramientas_Disponibles>` del prompt. Lo verifica `tests/test_configuracion.py`.

## Datos personales: la regla que no se toca

Es un agente de atención a la población: recibe cédulas, teléfonos, direcciones y números de factura sin pedirlos. La protección está en tres capas y **ninguna sustituye a las otras**:

1. **Guardrail** (`guardrails/`, hoy DESACTIVADO): contenido dañino, jailbreak, ataques indirectos y datos de tarjeta/bancarios. **No añadas los filtros de PII de identificación** (Name, Phone, Address, Email, documentos nacionales): para un agente solo existe la acción *anotar y bloquear*, y devolverían `400 content_filter` en cuanto alguien escriba su nombre o su barrio. Mientras esté desactivado, las capas 2 y 3 son las únicas que protegen: no las debilites.
2. **Prompt** (`<Proteccion_De_Datos_Personales>`): no pedir identificadores, no repetirlos, no consultar casos de terceros, no aceptar claves ni tarjetas.
3. **Memoria** (`memory.user_profile_details`): lista explícita de lo que NO se persiste. Cambiarla exige **borrar y recrear** el store (la definición no se puede actualizar).

Al añadir una tool nueva, revisa qué datos se le pasan: el prompt obliga a consultar por el trámite, nunca por la persona.

## Key files

- `azure.yaml` — manifiesto azd: nombre del agente en Foundry (`agente-hosted-municipalidad-girardota`), modelo (`gpt-5.4-mini`, SKU `DataZoneStandard`), runtime (`python_3_13`, deploy-mode code), variables del contenedor (`MEMORY_STORE_NAME`) y el guardrail en `policies`.
- `src/agent-framework-agent-municipalidad/model_config/model_config.yaml` — identidad (Girardo / Alcaldía de Girardota / COP), despliegue del modelo, opciones (`store: false`), tools y memoria.
- `src/agent-framework-agent-municipalidad/prompt/system_prompt.yaml` — instrucciones del agente, versionadas, con tags XML.
- `src/agent-framework-agent-municipalidad/agente.py` — une model_config + prompt + tools + memoria y construye el `Agent`.
- `src/agent-framework-agent-municipalidad/tools/knowledge_base.py` — `BaseConocimiento` (retrieve de Foundry IQ) y `crear_tool_consultar_tramites`.
- `src/agent-framework-agent-municipalidad/memoria/` — `proveedor.py` (scope por ciudadano) y `crear_memory_store.py`.
- `src/agent-framework-agent-municipalidad/rag/` — `crear_base_conocimiento.py` y la carpeta `Base de Conocimiento/` donde se dejan los documentos oficiales. No viaja al contenedor.
- `src/agent-framework-agent-municipalidad/guardrails/` — definición JSON de la política RAI y `crear_guardrail.sh`. No viaja al contenedor.
- `src/agent-framework-agent-municipalidad/tests/test_configuracion.py` — pruebas offline de YAML, tags, placeholders, nombres de tools, minimización de memoria y guardrail.
- `src/agent-framework-agent-municipalidad/main.py` — entry point del hosted agent (`ResponsesHostServer`, puerto 8088).
- `src/agent-framework-agent-municipalidad/chat_local.py` — consola interactiva con historial en memoria.
- `src/agent-framework-agent-municipalidad/Dockerfile` — de la plantilla; no se usa con deploy-mode code.

## Development workflow

El **Azure Developer CLI (`azd`)** gestiona el ciclo completo (ejecutar desde la raíz del proyecto, con el venv de `src/agent-framework-agent-municipalidad/.venv` activado):

```bash
azd ai agent run --no-client               # Local en http://localhost:8088
azd ai agent invoke --local "tu mensaje"   # Probar el agente local
azd deploy --no-prompt                     # Desplegar a Foundry
azd ai agent invoke "tu mensaje"           # Invocar el agente desplegado
```

Pruebas offline: `.venv/bin/python tests/test_configuracion.py`.

Para cambiar el comportamiento edita `prompt/system_prompt.yaml` (sube `version`); para cambiar identidad, modelo, tools o memoria edita `model_config.yaml`. Para añadir una tool: implementar en `tools/`, registrar en `crear_tools()` de `agente.py`, añadir su bloque en `tools:` de `model_config.yaml` y describirla en el prompt.

## Microsoft Foundry Skill

Install the **Microsoft Foundry Skill** for guided deployment, evaluation, and troubleshooting workflows.

```bash
npx skills add https://github.com/microsoft/azure-skills --skill microsoft-foundry
```

Or install the Azure Skills Plugin in Claude Code: `/plugin install azure@claude-plugins-official`.

## References

- [Hosted agents overview](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [Guardrails en agentes hospedados](https://learn.microsoft.com/azure/foundry/agents/how-to/add-hosted-agent-guardrails)
- [Memoria de Foundry](https://learn.microsoft.com/azure/foundry/agents/how-to/memory-usage)
