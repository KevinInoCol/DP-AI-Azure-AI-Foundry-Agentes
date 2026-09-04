"""
Construcción del agente inmobiliario de Alpha State con Microsoft Agent Framework.

Módulo compartido por `main.py` (servidor hospedado en Foundry) y
`chat_local.py` (consola interactiva). Junta las tres piezas del agente:

- model_config/model_config.yaml: identidad (bot, empresa, ciudad), modelo,
  opciones de llamada y configuración de las tools.
- prompt/system_prompt.yaml: solo las instrucciones, con placeholders que se
  rellenan con la sección `agent` de model_config.
- tools/: `buscar_propiedades_alquiler` (catálogo de alquileres en Google
  Sheets) y `consultar_politicas_alpha_state` (base de conocimiento Foundry IQ
  con políticas, pagos, requisitos y FAQ).

El historial de conversación lo gestiona el host (en Foundry) o una
AgentSession en memoria (en local), por eso `store: false` en model_config.
La memoria de largo plazo entre conversaciones es Memoria de Foundry
(FoundryMemoryProvider, sección `memory` de model_config).

Requiere en el .env (o en el entorno):
    FOUNDRY_PROJECT_ENDPOINT
    AZURE_AI_MODEL_DEPLOYMENT_NAME  (opcional: si falta se usa model.deployment_name del YAML)
    GOOGLE_SHEETS_ID                (si la tool usa origen google_sheets)
    MEMORY_STORE_NAME               (opcional: sobrescribe memory.store_name del YAML)
"""

import os
from pathlib import Path
from typing import Any

import yaml
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient, FoundryMemoryProvider
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from tools import BaseConocimiento, CatalogoAlquileres, crear_tool_buscar_propiedades, crear_tool_consultar_politicas

load_dotenv()

FOUNDRY_PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
MODEL_DEPLOYMENT_NAME_ENV = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME") or os.getenv("FOUNDRY_MODEL_NAME")
MEMORY_STORE_NAME_ENV = os.getenv("MEMORY_STORE_NAME")

BASE_DIR = Path(__file__).resolve().parent
RUTA_MODEL_CONFIG = BASE_DIR / "model_config" / "model_config.yaml"
RUTA_PROMPT = BASE_DIR / "prompt" / "system_prompt.yaml"


def cargar_yaml(ruta: Path) -> dict[str, Any]:
    with ruta.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def cargar_model_config() -> dict[str, Any]:
    """Lee model_config.yaml y resuelve el nombre del despliegue (env > YAML)."""
    cfg = cargar_yaml(RUTA_MODEL_CONFIG)
    cfg.setdefault("model", {})
    cfg["model"]["deployment_name"] = MODEL_DEPLOYMENT_NAME_ENV or cfg["model"].get("deployment_name")
    cfg["model"].setdefault("options", {})
    cfg.setdefault("agent", {})
    cfg.setdefault("tools", {})
    cfg.setdefault("memory", {})
    if MEMORY_STORE_NAME_ENV:
        cfg["memory"]["store_name"] = MEMORY_STORE_NAME_ENV
    return cfg


def verificar_configuracion(cfg: dict[str, Any]) -> None:
    """Falla rápido si falta algo imprescindible para arrancar el agente."""
    faltantes = []
    if not FOUNDRY_PROJECT_ENDPOINT:
        faltantes.append("FOUNDRY_PROJECT_ENDPOINT")
    if not cfg["model"].get("deployment_name"):
        faltantes.append("AZURE_AI_MODEL_DEPLOYMENT_NAME (o model.deployment_name en model_config.yaml)")
    if faltantes:
        raise RuntimeError("Configuración incompleta. Define en el .env: " + ", ".join(faltantes))
    for ruta in (RUTA_MODEL_CONFIG, RUTA_PROMPT):
        if not ruta.exists():
            raise RuntimeError(f"No se encontró {ruta}")
    for variable in ("bot_name", "empresa", "ciudad", "moneda_catalogo"):
        if not cfg["agent"].get(variable):
            raise RuntimeError(f"Falta agent.{variable} en {RUTA_MODEL_CONFIG}")


def cargar_system_prompt(cfg: dict[str, Any]) -> str:
    """Lee prompt/system_prompt.yaml e inyecta los placeholders con la sección agent de model_config."""
    prompt_cfg = cargar_yaml(RUTA_PROMPT)
    texto = prompt_cfg["system_prompt"]
    for variable in prompt_cfg.get("variables", []):
        if variable not in cfg["agent"]:
            raise RuntimeError(f"El prompt usa {{{variable}}} pero no está en agent.* de model_config.yaml")
        texto = texto.replace(f"{{{variable}}}", str(cfg["agent"][variable]))
    return texto


def crear_tools(cfg: dict[str, Any]) -> list:
    """Instancia las tools habilitadas en model_config.yaml (sección tools)."""
    tools = []
    cfg_sheets = cfg["tools"].get("buscar_propiedades_alquiler", {})
    if cfg_sheets.get("enabled", False):
        catalogo = CatalogoAlquileres(cfg_sheets, base_dir=BASE_DIR)
        catalogo.verificar_configuracion()
        tools.append(crear_tool_buscar_propiedades(catalogo))
    cfg_kb = cfg["tools"].get("consultar_politicas_alpha_state", {})
    if cfg_kb.get("enabled", False):
        base = BaseConocimiento(cfg_kb)
        base.verificar_configuracion()
        tools.append(crear_tool_consultar_politicas(base))
    return tools


def crear_context_providers(cfg: dict[str, Any], client: FoundryChatClient, scope_memoria: str | None = None) -> list:
    """Memoria de Foundry (preview) si está habilitada en model_config.yaml.

    `scope` aísla los recuerdos por cliente. En Foundry el valor "{{$userId}}" lo
    resuelve el host con la identidad del usuario que llama; en local hay que
    pasar un scope explícito (chat_local.py usa la variable MEMORY_SCOPE).
    Reutiliza el AIProjectClient del chat client (creado con allow_preview=True).
    """
    cfg_mem = cfg.get("memory", {})
    if not cfg_mem.get("enabled", False):
        return []
    if not cfg_mem.get("store_name"):
        raise RuntimeError("memory.enabled=true pero falta memory.store_name (o MEMORY_STORE_NAME)")
    return [
        FoundryMemoryProvider(
            project_client=client.project_client,
            memory_store_name=cfg_mem["store_name"],
            scope=scope_memoria or cfg_mem.get("scope", "{{$userId}}"),
            context_prompt=cfg_mem.get("context_prompt"),
            update_delay=int(cfg_mem.get("update_delay", 300)),
        )
    ]


def crear_agente(scope_memoria: str | None = None) -> Agent:
    """Crea el agente inmobiliario de Alpha State listo para usar.

    Args:
        scope_memoria: identificador del cliente para la memoria de Foundry. Solo
            hace falta en local; en Foundry se deja None y el host resuelve "{{$userId}}".
    """
    cfg = cargar_model_config()
    verificar_configuracion(cfg)

    client = FoundryChatClient(
        project_endpoint=FOUNDRY_PROJECT_ENDPOINT,
        model=cfg["model"]["deployment_name"],
        credential=DefaultAzureCredential(),
        # Necesario para que el mismo AIProjectClient pueda usar la API preview de memoria.
        allow_preview=True,
    )

    return Agent(
        client=client,
        name=cfg["agent"]["bot_name"],
        description=cfg["agent"].get("description"),
        instructions=cargar_system_prompt(cfg),
        tools=crear_tools(cfg),
        context_providers=crear_context_providers(cfg, client, scope_memoria),
        default_options=cfg["model"]["options"],
    )


# Nombre visible del bot, para chat_local.py.
BOT_NAME = cargar_model_config()["agent"].get("bot_name", "Asesor")
