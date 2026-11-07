"""
Crea (o verifica) el memory store de Foundry del asistente municipal de Girardota.

Memoria de Foundry (preview) guarda hechos estables de cada ciudadano entre
conversaciones. En una entidad pública la memoria es el punto donde más fácil
se persisten datos personales, así que `memory.user_profile_details` de
model_config.yaml está redactado en modo MINIMIZACIÓN: solo nombre de pila,
barrio o vereda, el trámite consultado y la preferencia de contacto; nunca
cédula, teléfono, dirección exacta, facturas, datos bancarios ni datos
sensibles. El agente la usa mediante `FoundryMemoryProvider` con `scope` por
ciudadano, así cada persona tiene su memoria aislada.

Idempotente: si el store ya existe, lo deja como está.

IMPORTANTE: `memory_stores.update` solo cambia description/metadata. Para
cambiar los modelos o `user_profile_details` hay que BORRAR y RECREAR el store
(se pierden los recuerdos):
    project.beta.memory_stores.delete(name="municipalidad_girardota_memory")

Requisitos: `az login`; rol Foundry User + Cognitive Services OpenAI User en el
recurso de Foundry (para tu usuario, la identidad del proyecto y la identidad
del agente hospedado). Modelos desplegados: gpt-5-mini y text-embedding-3-small.

Ejecutar desde src/agent-framework-agent-municipalidad/:
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
            # MEMORY_CHAT_MODEL permite usar otro despliegue si el del YAML no existe en el proyecto.
            chat_model=os.getenv("MEMORY_CHAT_MODEL") or cfg["chat_model"],
            embedding_model=cfg["embedding_model"],
            options=MemoryStoreDefaultOptions(
                user_profile_enabled=True,
                chat_summary_enabled=bool(cfg.get("chat_summary_enabled", True)),
                user_profile_details=cfg["user_profile_details"],
            ),
        )
        creado = project.beta.memory_stores.create(
            name=nombre,
            description=cfg.get("description", "Memoria de ciudadanos del asistente virtual de la Alcaldía de Girardota"),
            definition=definicion,
        )
        print(f"Memory store '{creado.name}' creado (id={creado.id}).")


if __name__ == "__main__":
    main()
