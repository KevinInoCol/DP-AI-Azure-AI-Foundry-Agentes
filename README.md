# Workshop: Agentes con Azure AI Foundry (DATAPATH)

Material del taller **Agentes con Azure AI Foundry** de DATAPATH. Se construye, despliega y consume un **agente hospedado** (hosted agent) en Microsoft Foundry con **Microsoft Agent Framework** (Python) y **Azure Developer CLI (`azd`)**.

El caso práctico es **Alpha State**, una inmobiliaria de Campinas (Brasil): el agente busca propiedades en el catálogo real de la empresa, responde políticas y requisitos desde un PDF indexado, recuerda a cada cliente entre conversaciones y está protegido por límites de contenido.

## Contenido

| Carpeta | Descripción |
|---|---|
| [`agente-hosted/agente-basico/`](agente-hosted/agente-basico/) | Agente hospedado mínimo (plantilla oficial Agent Framework + protocolo Responses). Punto de partida del taller. |
| [`agente-hosted/agente-hosted-inmobiliaria/`](agente-hosted/agente-hosted-inmobiliaria/) | **Proyecto principal**: asesor inmobiliario *Alpha State*. Tools, RAG, memoria y guardrail. |
| [`Consumo-de-Agentes/`](Consumo-de-Agentes/) | App que consume el agente desde fuera del portal: backend FastAPI + frontend React/Vite con interfaz de chat. |
| [`Presentacion/`](Presentacion/) | Presentación HTML autocontenida con la arquitectura del agente (diagramas animados, recorridos paso a paso y cuestionario). |
| [`.claude/skills/`](.claude/skills/) | Skills de Claude Code que documentan cada pieza del taller. |

## Capacidades del agente inmobiliario

| Capacidad | Cómo está resuelta |
|---|---|
| Catálogo de alquileres | Tool `buscar_propiedades_alquiler` sobre una hoja privada de **Google Sheets** (cuenta de servicio), con mapeo de columnas configurable |
| Políticas, pagos, garantías y FAQ | Tool `consultar_politicas_alpha_state` sobre una base de conocimiento **Foundry IQ** (Azure AI Search) creada a partir de un PDF |
| Memoria entre conversaciones | **Memoria de Foundry** (memory store) con ámbito por cliente |
| Seguridad de contenido | **Guardrail** (política RAI) asignado al agente, declarado en `azure.yaml` |
| Alcance | El prompt restringe al agente a temas inmobiliarios de Alpha State y protege sus instrucciones |

## Skills incluidas

Las skills viven en `.claude/skills/` y se activan solas en Claude Code según lo que pidas.

| Skill | Para qué |
|---|---|
| `azure-foundry-agent-structure` | Convención de estructura de un agente de Foundry (dónde va cada archivo) |
| `azure-foundry-hosted-agent-deploy` | Crear, probar y desplegar un hosted agent con `azd` |
| `azure-foundry-agent-tools` | Añadir tools (function calling), con el ejemplo de Google Sheets |
| `azure-foundry-knowledge-base` | Base de conocimiento en Foundry IQ (Azure AI Search) a partir de documentos |
| `azure-foundry-memory` | Memoria persistente entre conversaciones |
| `azure-foundry-guardrails` | Límites de protección aplicados al agente |
| `azure-foundry-consume-agent` | Backend y frontend para consumir el agente desde una app propia |
| `azure-mcp-install` | Instalar el Azure MCP Server en Claude Code |
| `ppt-a-html-datapath` | Convertir material de clase en HTML interactivo |

## Prerequisitos generales

- Python 3.13, [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) (`az login`) y [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) con la extensión `microsoft.foundry`.
- Node.js 20+ si vas a levantar el frontend de consumo.
- Un proyecto de Microsoft Foundry con un despliegue de modelo (el taller usa `gpt-5.4-mini`, SKU `DataZoneStandard`) y uno de embeddings (`text-embedding-3-small`) para la base de conocimiento.
- Copiar cada `.env.example` a `.env` y completar los valores. **Los `.env` y las credenciales no se suben al repositorio.**

## Flujo resumido

```bash
# 1) Agente: probar en local y desplegar
cd agente-hosted/agente-hosted-inmobiliaria
python3.13 -m venv src/agent-framework-agent-inmobiliaria/.venv
source src/agent-framework-agent-inmobiliaria/.venv/bin/activate
pip install -r src/agent-framework-agent-inmobiliaria/requirements.txt

azd ai agent run --no-client                                  # local en http://localhost:8088
azd ai agent invoke --local --new-conversation "Hola"         # probar el agente local
azd deploy --no-prompt                                        # desplegar (crea una versión nueva)
azd ai agent invoke --new-conversation "Hola"                 # invocar el agente desplegado

# 2) Consumo: backend + frontend
cd ../../Consumo-de-Agentes/Agente-de-Inmobiliaria-Alpha-State
(cd Backend  && .venv/bin/uvicorn main:app --reload --port 8000)
(cd Frontend && npm install && npm run dev)                   # http://localhost:5173
```

## Nota sobre secretos

Este repositorio es material didáctico. Las credenciales (JSON de la cuenta de servicio de Google, endpoints con clave) viajan como **variables de entorno** y quedan guardadas en la definición del agente en Foundry, visibles para quien tenga permiso de lectura sobre el agente. En producción deben guardarse en **Azure Key Vault** y leerse con la identidad administrada del agente.
