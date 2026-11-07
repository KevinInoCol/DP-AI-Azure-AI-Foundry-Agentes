"""Herramientas (function calling) del asistente virtual de la Alcaldía de Girardota."""

from tools.knowledge_base import (
    BaseConocimiento,
    crear_tool_consultar_tramites,
    crear_tool_consultar_tramites_pendiente,
)

__all__ = [
    "BaseConocimiento",
    "crear_tool_consultar_tramites",
    "crear_tool_consultar_tramites_pendiente",
]
