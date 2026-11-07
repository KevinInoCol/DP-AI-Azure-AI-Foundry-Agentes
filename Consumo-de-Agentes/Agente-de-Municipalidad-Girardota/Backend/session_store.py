"""
Registro de sesiones de chat abiertas: session_id → (user_id, SesionAgente).

Guarda en memoria del proceso qué sesión del agente y qué conversación de Foundry
corresponden a cada ciudadano conectado. Sirve para el taller; en producción se
sustituiría por Redis u otra caché compartida sin cambiar la API.

No guarda el contenido de los mensajes: el historial vive en la conversación de
Foundry, y aquí solo se conservan identificadores.
"""

import time
from dataclasses import dataclass, field
from threading import Lock

from call_ai_azure_agent import SesionAgente


@dataclass
class EntradaSesion:
    user_id: str
    sesion: SesionAgente
    creada_en: float = field(default_factory=time.time)


class SessionStore:
    def __init__(self) -> None:
        self._datos: dict[str, EntradaSesion] = {}
        self._lock = Lock()

    def guardar(self, user_id: str, sesion: SesionAgente) -> None:
        with self._lock:
            self._datos[sesion.session_id] = EntradaSesion(user_id=user_id, sesion=sesion)

    def obtener(self, session_id: str | None, user_id: str) -> SesionAgente | None:
        """Devuelve la sesión solo si existe y pertenece a ese usuario."""
        if not session_id:
            return None
        with self._lock:
            entrada = self._datos.get(session_id)
        return entrada.sesion if entrada and entrada.user_id == user_id else None

    def quitar(self, session_id: str, user_id: str) -> SesionAgente | None:
        with self._lock:
            entrada = self._datos.get(session_id)
            if entrada is None or entrada.user_id != user_id:
                return None
            del self._datos[session_id]
        return entrada.sesion

    def __len__(self) -> int:
        return len(self._datos)
