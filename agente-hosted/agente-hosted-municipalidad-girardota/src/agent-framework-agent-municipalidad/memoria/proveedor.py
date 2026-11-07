"""
Proveedor de Memoria de Foundry con ámbito (scope) por ciudadano resuelto en cada petición.

`FoundryMemoryProvider` de Agent Framework recibe un `scope` fijo al construirse.
Con el marcador "{{$userId}}" la plataforma lo resuelve en el servicio, pero el
valor resultante es opaco: no se puede escribir en el filtro "Ámbito" del portal
ni consultarlo con `list_memories`. Esta subclase decide el ámbito en cada turno:

1. `scope_fijo` si se pasó (chat_local.py lo usa con MEMORY_SCOPE).
2. La identidad de usuario que inyecta la plataforma en la cabecera
   `x-agent-user-id` (`get_request_context().user_id`). En Foundry llega con el
   usuario del playground o con `azd ai agent invoke --user-identity <id>`; un
   canal propio (web, WhatsApp, ventanilla) envía ahí el id del ciudadano.
3. `scope_por_defecto` (model_config: memory.scope_por_defecto) cuando no hay
   identidad, para que los recuerdos queden en un ámbito conocido y visible.

Datos personales: el ámbito es un IDENTIFICADOR DE SESIÓN, no un dato del
ciudadano. No uses aquí la cédula ni el teléfono como scope; usa un id opaco
del canal. Qué se guarda (y qué no) dentro de cada ámbito se declara en
`memory.user_profile_details` de model_config.yaml.

Reutiliza `before_run`/`after_run` del proveedor base: solo cambia `self.scope`
de forma segura por petición (el base lo lee como `self.scope or session_id`).
"""

import logging
from contextvars import ContextVar
from typing import Any

from agent_framework import AgentSession, SessionContext
from agent_framework.foundry import FoundryMemoryProvider

try:  # solo existe dentro del host de Foundry / azd ai agent run
    from azure.ai.agentserver.core import get_request_context
except ImportError:  # pragma: no cover
    get_request_context = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_scope_actual: ContextVar[str | None] = ContextVar("scope_memoria_actual", default=None)


def resolver_scope(scope_fijo: str | None, scope_por_defecto: str) -> str:
    """Devuelve el ámbito de memoria para la petición actual (ver docstring del módulo)."""
    if scope_fijo:
        return scope_fijo
    if get_request_context is not None:
        try:
            user_id = getattr(get_request_context(), "user_id", None)
        except Exception:  # fuera de una petición HTTP no hay contexto
            user_id = None
        if user_id:
            return normalizar_scope(user_id)
    return scope_por_defecto


def normalizar_scope(valor: str) -> str:
    """El servicio solo admite letras, dígitos y _ - . % + @ /; el resto se sustituye por '_'."""
    permitidos = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.%+@/")
    return "".join(c if c in permitidos else "_" for c in valor.strip())[:200] or "ciudadano-sin-identificar"


class MemoriaPorCiudadano(FoundryMemoryProvider):
    """FoundryMemoryProvider cuyo scope se resuelve en cada petición."""

    def __init__(self, *args: Any, scope_fijo: str | None = None, scope_por_defecto: str = "ciudadano-sin-identificar", **kwargs: Any) -> None:
        # El base exige un scope no vacío; se sobrescribe en cada hook.
        super().__init__(*args, scope=scope_fijo or scope_por_defecto, **kwargs)
        self.scope_fijo = scope_fijo
        self.scope_por_defecto = scope_por_defecto

    @property  # type: ignore[override]
    def scope(self) -> str:
        return _scope_actual.get() or self.scope_fijo or self.scope_por_defecto

    @scope.setter
    def scope(self, valor: str) -> None:  # el __init__ del base asigna self.scope
        pass

    def _fijar_scope(self) -> str:
        scope = resolver_scope(self.scope_fijo, self.scope_por_defecto)
        _scope_actual.set(scope)
        return scope

    async def before_run(self, *, agent: Any, session: AgentSession, context: SessionContext, state: dict[str, Any]) -> None:
        scope = self._fijar_scope()
        if state.get("scope_memoria") != scope:  # otro ciudadano en la misma sesión: reiniciar búsqueda incremental
            state.pop("initialized", None); state.pop("previous_search_id", None); state.pop("previous_update_id", None)
            state["scope_memoria"] = scope
        logger.info("Memoria de Foundry: scope=%s store=%s", scope, self.memory_store_name)
        await super().before_run(agent=agent, session=session, context=context, state=state)

    async def after_run(self, *, agent: Any, session: AgentSession, context: SessionContext, state: dict[str, Any]) -> None:
        self._fijar_scope()
        await super().after_run(agent=agent, session=session, context=context, state=state)
