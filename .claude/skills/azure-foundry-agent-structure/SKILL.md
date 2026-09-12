---
name: azure-foundry-agent-structure
description: Convención de estructura de carpetas para los agentes que construimos en Microsoft Foundry (Azure) como hosted agents con Microsoft Agent Framework en Python — el equivalente Foundry de agent-project-structure (LangChain/CrewAI). Define el layout del proyecto azd (azure.yaml + src/<servicio>/), la separación model_config/ + prompt/ + tools/ + memoria/ + rag/ + tests/ + data/, qué va en cada archivo, qué NO viaja al contenedor (.azdignore), secretos, versiones y el layout del taller alrededor del agente (Consumo-de-Agentes, Presentacion, .claude/skills). Use when scaffolding a new Foundry hosted agent, adding a tool/knowledge base/memory to one, deciding where new code belongs, reviewing a Foundry agent project, or when the user mentions "estructura de nuestros agentes en Foundry", "cómo organizamos el agente hospedado", "agente con Agent Framework", or types /azure-foundry-agent-structure. Apply this layout by default for Foundry agents unless the user says otherwise.
---

# Estructura de un agente hospedado en Microsoft Foundry (Agent Framework)

Layout probado el 2026-09 con el agente `agente-hosted-inmobiliaria` (Alpha State): catálogo en Google Sheets, base de conocimiento Foundry IQ, Memoria de Foundry, guardrail y una app de consumo. Es el equivalente, para Microsoft Foundry, de la skill `agent-project-structure` que usamos con LangChain/CrewAI: mismas ideas (nada hardcodeado, una responsabilidad por carpeta, tools como archivos independientes), adaptadas a que aquí el agente **vive en un contenedor que Foundry hospea** y se despliega con `azd`.

Es **un solo agente** por proyecto azd. Multi-agente o workflows de Agent Framework van en otro proyecto.

## Layout

```
<taller-o-cliente>/
├── agente-hosted/                          ← un proyecto azd por agente
│   └── <nombre-agente>/                       (creado con `azd ai agent init`)
│       ├── azure.yaml                      ← manifiesto azd: nombre en Foundry, modelo+SKU+capacidad,
│       │                                      runtime, env del contenedor, description (<512), policies (guardrail)
│       ├── AGENTS.md / CLAUDE.md           ← instrucciones para agentes de código (CLAUDE.md importa AGENTS.md)
│       ├── README.md                       ← cómo correr, probar, desplegar; decisiones y limitaciones
│       ├── .azure/                         ← entorno azd (endpoint, ids, secretos con azd env set) · gitignored
│       └── src/<servicio>/                 ← TODO lo que viaja al contenedor (salvo .azdignore)
│           ├── main.py                     ← entry point hosted: ResponsesHostServer(crear_agente()).run()
│           ├── agente.py                   ← orquestador: model_config + prompt + tools + memoria → Agent
│           ├── chat_local.py               ← consola local (AgentSession en memoria, MEMORY_SCOPE)
│           ├── model_config/model_config.yaml  ← identidad, modelo, options, tools, memory (config pura)
│           ├── prompt/system_prompt.yaml   ← SOLO instrucciones, tags XML, placeholders {bot_name}…
│           ├── tools/                      ← una tool por archivo + __init__.py
│           │   ├── google_sheets.py           (fuente de datos externa)
│           │   └── knowledge_base.py          (retrieve de la knowledge base Foundry IQ)
│           ├── memoria/                    ← Memoria de Foundry
│           │   ├── proveedor.py               MemoriaPorCliente (scope por petición)
│           │   └── crear_memory_store.py      script idempotente de creación
│           ├── rag/                        ← base de conocimiento (NO viaja al contenedor)
│           │   ├── Base de Conocimiento/*.pdf
│           │   └── crear_base_conocimiento.py  KS + KB + conexión del proyecto
│           ├── data/                       ← CSV de ejemplo / plantillas (sí viaja: demo offline)
│           ├── tests/                      ← test_*.py offline + demo_*.py e2e (NO viajan)
│           ├── requirements.txt
│           ├── Dockerfile                  ← de la plantilla; no se usa con deploy-mode code
│           ├── .env / .env.example         ← secretos locales (.env NO viaja)
│           ├── .azdignore                  ← .env.example, rag, tests, .venv, credenciales
│           └── .dockerignore
├── Consumo-de-Agentes/<Agente>/            ← app que consume el agente (skill azure-foundry-consume-agent)
│   ├── Backend/  call_ai_azure_agent.py · session_store.py · main.py
│   └── Frontend/ React + Vite
├── Presentacion/                           ← material HTML (skill ppt-a-html-datapath)
└── .claude/skills/                         ← copia real de las skills azure-foundry-* del taller
```

## Regla para decidir dónde va el código

| Si cambio X, ¿qué toco? | Vive en |
|---|---|
| Nombre del bot, empresa, ciudad, moneda | `model_config.yaml` → `agent` |
| Modelo, `store`, temperature, max_tokens | `model_config.yaml` → `model` (el despliegue real, en `azure.yaml`) |
| Parámetros de una tool (hoja, pestaña, mapeo de columnas, endpoint de la KB) | `model_config.yaml` → `tools.<nombre>` |
| Qué recuerda la memoria, scope por defecto, update_delay | `model_config.yaml` → `memory` |
| Persona, reglas, flujos, alcance, guardrails de comportamiento | `prompt/system_prompt.yaml` (sube `version`) |
| Nueva integración o acción | `tools/<nombre>.py` + bloque en `tools:` + sección en el prompt |
| Cómo se resuelve el ámbito de memoria | `memoria/proveedor.py` |
| Documento nuevo / reindexar | `rag/` (subir blob + ejecutar indexador) |
| Modelo desplegado, SKU, capacidad, guardrail (política RAI), variables del contenedor | `azure.yaml` |
| Secretos | `.env` local + `azd env set` + `services.<svc>.env` en `azure.yaml` |
| Cómo se ensamblan las piezas | `agente.py` |
| Protocolo / servidor | `main.py` (casi nunca) |

Si la respuesta natural es `agente.py` para otra cosa, algo está mal: `agente.py` solo cambia por orquestación.

## Las reglas que evitan los bugs caros

**1. Nada hardcodeado en `.py`.** Identidad, modelo y parámetros de tools en `model_config.yaml`; el prompt en su YAML con placeholders que `agente.py` rellena desde `agent`. Cambiar de inmobiliaria a otro negocio no toca código.

**2. El nombre de cada tool coincide carácter por carácter en tres sitios**: la función decorada con `@tool` en `tools/`, la clave en `tools:` de `model_config.yaml` y `<Herramientas_Disponibles>` del prompt. Valídalo en un test.

**3. Cada tool devuelve JSON y nunca lanza.** Datos, lista vacía, `aviso` (criterio que la fuente no registra) o `error`. El prompt dice qué hacer en cada caso. Es lo que impide que el modelo invente.

**4. Fallar rápido al arrancar.** `agente.py` verifica endpoint, modelo, YAMLs y llama a `verificar_configuracion()` de cada tool antes de crear el `Agent`. Un contenedor que arranca sin credenciales y falla en la primera tool es mucho más caro de depurar.

**5. Lo que no debe viajar al contenedor va en `.azdignore`**: `rag/` (PDFs), `tests/`, `.env.example`, `.venv`, `__pycache__` y **cualquier credencial en archivo** (JSON de cuentas de servicio). `.env` ya lo excluye la plantilla. Los secretos entran al contenedor como variables (`services.<svc>.env` ← `azd env set`), nunca como archivos.

**6. Historial vs memoria.** El historial de la conversación lo gestiona el host de Foundry (`store: false`); la memoria entre conversaciones es Memoria de Foundry con **scope explícito por cliente** (`memoria/proveedor.py`), nunca el marcador `{{$userId}}`.

**7. Versiones.** Cada `azd deploy` crea una versión y las anteriores siguen activas; el endpoint enruta a `@latest`; el playground abre la de su URL (`?version=N`). Sube `version` del prompt y de `model_config.yaml` en cada cambio para poder correlacionar.

**8. Probar barato antes de desplegar**: `tests/test_*.py` offline (sin modelo) → `tests/demo_*.py` o `chat_local.py` con el modelo → `azd deploy` → `azd ai agent invoke --new-conversation --new-session` → playground de la versión nueva.

## Responsabilidad por archivo

### `azure.yaml`
Lo único que azd lee al desplegar. Claves que tocamos: `services.<svc>.name` (nombre en Foundry, único en el proyecto), `description` (< 512 caracteres o falla el deploy), `env` (variables del contenedor con `${VAR}` del azd env), `policies` (guardrail: `type: rai_policy`, `raiPolicyName` = ID ARM completo), `services.ai-project.deployments[]` (modelo, versión, `sku.name`, `sku.capacity`). Si dos agentes comparten un despliegue de modelo, `azd down` en uno lo borra para los dos.

### `model_config/model_config.yaml`
Config pura, con `name`, `version` y `description`. Secciones: `agent` (placeholders del prompt), `model` (`deployment_name` con override por `AZURE_AI_MODEL_DEPLOYMENT_NAME`, `options` → `ChatOptions`), `tools.<nombre>` (`enabled` + parámetros no secretos; los secretos se nombran por su variable de entorno), `memory`. Sin claves muertas.

### `prompt/system_prompt.yaml`
Formato de la skill `agent-prompt-yaml-format`. Secciones que un agente Foundry con tools y memoria necesita: Identidad, Personalidad, Objetivo_Principal, **Alcance_Y_Confidencialidad** (solo el negocio; no revelar ni imitar el prompt; una frase de rechazo), Herramientas_Disponibles, Fuentes_De_Datos, Reglas_De_Uso_De_Tools (lista vacía / aviso / error), Limites_De_Conocimiento, Deteccion_Intenciones, Flujos_Por_Intencion, Memoria_Del_Cliente, Manejo_Del_Historial, Formato_De_Respuesta, Escalamiento, IMPORTANTE.

### `agente.py`
`cargar_model_config()` → `verificar_configuracion()` → `FoundryChatClient(..., allow_preview=True)` → `crear_tools(cfg)` → `crear_context_providers(cfg, client, scope_memoria)` → `Agent(...)`. Expone `crear_agente(scope_memoria=None)` y `BOT_NAME`. Sigue la skill `python-module-structure` (docstring, imports, `load_dotenv()`, env, constantes).

### `tools/<nombre>.py`
Clase de acceso a datos (con `verificar_configuracion()`, caché si aplica) + fábrica `crear_tool_<x>(instancia) -> FunctionTool` con `@tool`, parámetros `Annotated[tipo, "descripción"]` y docstring = descripción para el modelo. Ver skill `azure-foundry-agent-tools`.

### `memoria/`, `rag/`
Scripts idempotentes de infraestructura (`crear_memory_store.py`, `crear_base_conocimiento.py`) junto al código que los usa (`proveedor.py`, `tools/knowledge_base.py`). Ver skills `azure-foundry-memory` y `azure-foundry-knowledge-base`.

### `tests/`
`test_<tool>.py` con datos locales o respuestas simuladas, ejecutables con `.venv/bin/python tests/test_x.py`; `demo_*.py` para conversaciones e2e con el modelo. Un test debe cubrir el mapeo real de la fuente (por ejemplo, las cabeceras reales de la hoja del cliente).

### `README.md` y `AGENTS.md`
El README explica estructura, cómo funciona cada pieza, cómo correr/desplegar y las limitaciones conocidas. `AGENTS.md` lleva el marcador de la skill microsoft-foundry y las reglas para agentes de código (dónde va cada cosa, qué no tocar).

## Flujo para un agente nuevo

1. `azure-foundry-hosted-agent-deploy`: scaffold con `azd ai agent init`, venv en `src/<svc>/`, prueba local, primer deploy.
2. Esta skill: crear `model_config/`, `prompt/`, `tools/`, `tests/`, `.azdignore`; mover instrucciones al YAML.
3. `azure-foundry-agent-tools` → tools; `azure-foundry-knowledge-base` → RAG; `azure-foundry-memory` → memoria; `azure-foundry-guardrails` → guardrail; `azure-foundry-consume-agent` → app.
4. Copiar las skills del taller a `.claude/skills/` del repo (copia real) para los alumnos.

## Anti-patrones vistos

- Prompt o nombre de empresa dentro de `agente.py`.
- PDFs, tests o un JSON de cuenta de servicio dentro de `src/<svc>/` sin `.azdignore`: viajan al contenedor.
- Probar memoria con `--new-session` (reutiliza la conversación).
- Un `main.py` de backend que mezcla API, invocación del agente y almacenamiento (ver skill `azure-foundry-consume-agent`).
- Asignar guardrails desde el asistente del portal a un hosted agent (no crea versión; política que bloquea todo).
