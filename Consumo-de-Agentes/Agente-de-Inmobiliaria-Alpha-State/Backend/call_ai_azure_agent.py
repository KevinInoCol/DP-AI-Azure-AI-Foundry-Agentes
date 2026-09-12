"""
Invocación del agente hospedado en Microsoft Foundry.

Encapsula el snippet "Call agent" del playground de Foundry (Agents → Playground →
Call agent) en una clase reutilizable, con la API real de azure-ai-projects ≥ 2.6:

- `project_client.agents.create_session(...)` crea una sesión (sandbox) del agente
  fijada a una versión.
- `project_client.get_openai_client(agent_name=...)` devuelve un cliente OpenAI
  apuntando al endpoint Responses del agente.
- `openai_client.conversations.create()` crea la conversación de Foundry que
  guarda el hilo entre turnos (la sesión sola no da continuidad).
- `openai_client.responses.create(input, conversation=..., extra_body={"agent_session_id"})`
  envía cada mensaje.

Este módulo no sabe nada de HTTP ni de FastAPI: recibe texto y devuelve texto.

Requiere en el .env (o en el entorno):
    FOUNDRY_PROJECT_ENDPOINT
    AGENT_NAME          (por defecto agente-hosted-inmobiliaria)
    AGENT_VERSION       (opcional: vacío = última versión al conectar)
"""

import logging
import os
from dataclasses import dataclass

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import VersionRefIndicator
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from openai import BadRequestError

load_dotenv()

FOUNDRY_PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
AGENT_NAME = os.getenv("AGENT_NAME", "agente-hosted-inmobiliaria")
AGENT_VERSION = os.getenv("AGENT_VERSION") or None

log = logging.getLogger(__name__)


class MensajeBloqueado(Exception):
    """El guardrail del agente rechazó el mensaje (HTTP 400 content_filter)."""


class RespuestaFallida(Exception):
    """El agente devolvió status 'failed' (p. ej. rate limit del modelo)."""


@dataclass
class SesionAgente:
    session_id: str        # sesión (sandbox) del agente hospedado
    conversation_id: str   # conversación de Foundry con el historial del hilo


class AgenteFoundry:
    """Cliente del agente hospedado: abre sesiones, envía mensajes y las cierra."""

    def __init__(self, endpoint: str = FOUNDRY_PROJECT_ENDPOINT, agent_name: str = AGENT_NAME, agent_version: str | None = AGENT_VERSION) -> None:
        self.agent_name = agent_name
        self._credential = DefaultAzureCredential()
        self._project = AIProjectClient(endpoint=endpoint, credential=self._credential, allow_preview=True)
        self.agent_version = agent_version or self._project.agents.get(agent_name=agent_name).versions["latest"].version
        self._openai = self._project.get_openai_client(agent_name=agent_name)
        log.info("Conectado al agente %s versión %s", agent_name, self.agent_version)

    def abrir_sesion(self) -> SesionAgente:
        """Crea la sesión del agente y la conversación que guardará el hilo."""
        sesion = self._project.agents.create_session(
            agent_name=self.agent_name,
            version_indicator=VersionRefIndicator(agent_version=self.agent_version),
        )
        conversacion = self._openai.conversations.create()
        return SesionAgente(session_id=sesion.agent_session_id, conversation_id=conversacion.id)

    def enviar(self, sesion: SesionAgente, mensaje: str, user_id: str | None = None) -> str:
        """Envía un mensaje dentro de la sesión y devuelve el texto de la respuesta.

        Lanza MensajeBloqueado si el guardrail lo rechaza y RespuestaFallida si el
        agente devuelve una respuesta con status 'failed'.
        """
        try:
            respuesta = self._openai.responses.create(
                input=mensaje,
                conversation=sesion.conversation_id,
                extra_body={"agent_session_id": sesion.session_id},
                # La familia x-client-* llega al contenedor del agente (útil para
                # identificar al cliente final si el agente la lee).
                extra_headers={"x-client-user-id": user_id} if user_id else None,
            )
        except BadRequestError as exc:
            if "content_filter" in str(exc):
                raise MensajeBloqueado(str(exc)) from exc
            raise
        if respuesta.status == "failed":
            detalle = respuesta.error.message if respuesta.error else "sin detalle"
            raise RespuestaFallida(detalle)
        return respuesta.output_text

    def cerrar_sesion(self, sesion: SesionAgente) -> None:
        self._project.agents.delete_session(agent_name=self.agent_name, session_id=sesion.session_id)


if __name__ == "__main__":  # prueba rápida: python call_ai_azure_agent.py "Hola"
    import sys
    logging.basicConfig(level=logging.INFO)
    agente = AgenteFoundry()
    s = agente.abrir_sesion()
    try:
        print(agente.enviar(s, " ".join(sys.argv[1:]) or "Hola, ¿en qué me puedes ayudar?"))
    finally:
        agente.cerrar_sesion(s)
