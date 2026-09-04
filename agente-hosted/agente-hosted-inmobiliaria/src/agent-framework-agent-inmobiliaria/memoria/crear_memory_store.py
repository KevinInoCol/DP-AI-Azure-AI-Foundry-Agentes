"""
Crea (o verifica) el memory store de Foundry para el agente inmobiliario de Alpha State.

Memoria de Foundry (preview) guarda hechos estables de cada cliente entre
conversaciones: nombre, forma de contacto, qué busca (operación, barrio,
presupuesto, dormitorios, mascotas) y la propiedad que le interesó. El agente
la usa mediante `FoundryMemoryProvider` (Agent Framework) con `scope`
por usuario, así cada cliente tiene su memoria aislada.

Idempotente: si el store ya existe, lo deja como está.

Requisitos: `az login`; rol Foundry User + Cognitive Services OpenAI User en el
recurso de Foundry (tanto para tu usuario como para la identidad del agente
hospedado). Modelos desplegados: gpt-5-mini (chat) y text-embedding-3-small.

Ejecutar desde src/agent-framework-agent-inmobiliaria/:
    .venv/bin/python memoria/crear_memory_store.py
"""

import os

import yaml
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MemoryStoreDefaultDefinition, MemoryStoreDefaultOptions
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

FOUNDRY_PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]

RUTA_MODEL_CONFIG = os.path.join(os.path.dirname(__file__), "..", "model_config", "model_config.yaml")


def main() -> None:
    with open(RUTA_MODEL_CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)["memory"]
    nombre = os.getenv("MEMORY_STORE_NAME") or cfg["store_name"]

    with DefaultAzureCredential() as credential, AIProjectClient(
        endpoint=FOUNDRY_PROJECT_ENDPOINT, credential=credential, allow_preview=True
    ) as project:
        try:
            existente = project.beta.memory_stores.get(name=nombre)
            print(f"El memory store '{existente.name}' ya existe (id={existente.id}); no se modifica.")
            return
        except ResourceNotFoundError:
            pass

        definicion = MemoryStoreDefaultDefinition(
            chat_model=cfg["chat_model"],
            embedding_model=cfg["embedding_model"],
            options=MemoryStoreDefaultOptions(
                user_profile_enabled=True,
                chat_summary_enabled=bool(cfg.get("chat_summary_enabled", True)),
                user_profile_details=cfg["user_profile_details"],
            ),
        )
        creado = project.beta.memory_stores.create(
            name=nombre,
            description=cfg.get("description", "Memoria de clientes del agente inmobiliario de Alpha State"),
            definition=definicion,
        )
        print(f"Memory store '{creado.name}' creado (id={creado.id}).")


if __name__ == "__main__":
    main()
