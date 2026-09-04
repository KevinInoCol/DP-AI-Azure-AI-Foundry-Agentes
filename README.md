# Workshop: Agentes con Azure AI Foundry (DATAPATH)

Material del taller **Agentes con Azure AI Foundry** de DATAPATH. Se construyen y despliegan **agentes hospedados** (hosted agents) en Microsoft Foundry con **Microsoft Agent Framework** (Python) y **Azure Developer CLI (`azd`)**.

## Contenido

| Carpeta | Descripción |
|---|---|
| [`agente-hosted/agente-basico/`](agente-hosted/agente-basico/) | Agente hospedado mínimo (plantilla oficial Agent Framework + protocolo Responses). Punto de partida del taller. |
| [`agente-hosted/agente-hosted-inmobiliaria/`](agente-hosted/agente-hosted-inmobiliaria/) | **Proyecto principal**: asesor inmobiliario virtual de *Alpha State* con tools (catálogo de alquileres en Google Sheets), RAG con **Foundry IQ** (Azure AI Search) y **Memoria de Foundry** entre conversaciones. |
| [`.claude/skills/`](.claude/skills/) | Skills de Claude Code para el taller: `azure-mcp-install` (instalar el Azure MCP Server) y `foundry-hosted-agent-deploy` (crear, probar y desplegar un hosted agent con `azd`). |

Cada subproyecto tiene su propio `README.md` con los pasos detallados (prerequisitos, prueba local, despliegue e invocación).

## Prerequisitos generales

- Python 3.13, [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) (`az login`) y [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) con la extensión `microsoft.foundry`.
- Un proyecto de Microsoft Foundry con un despliegue de modelo (el taller usa `gpt-5.4-mini`, SKU `DataZoneStandard`).
- Copiar cada `.env.example` a `.env` y completar los valores. **Los `.env` y las credenciales no se suben al repositorio.**

## Flujo resumido

```bash
cd agente-hosted/agente-hosted-inmobiliaria
python3.13 -m venv src/agent-framework-agent-inmobiliaria/.venv
source src/agent-framework-agent-inmobiliaria/.venv/bin/activate
pip install -r src/agent-framework-agent-inmobiliaria/requirements.txt

azd ai agent run --no-client                 # ejecutar en local (http://localhost:8088)
azd ai agent invoke --local "Hola"           # probar el agente local
azd deploy --no-prompt                       # desplegar en Foundry
azd ai agent invoke "Hola"                   # invocar el agente desplegado
```
