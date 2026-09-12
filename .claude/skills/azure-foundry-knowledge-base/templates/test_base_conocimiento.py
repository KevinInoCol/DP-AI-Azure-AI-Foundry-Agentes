"""
Pruebas offline de la tool consultar_politicas_alpha_state con la respuesta de retrieve simulada.

Ejecutar desde src/agent-framework-agent-inmobiliaria/:
    .venv/bin/python tests/test_base_conocimiento.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.knowledge_base import BaseConocimiento, crear_tool_consultar_politicas

CONFIG = {"search_endpoint": "https://ejemplo.search.windows.net", "knowledge_base": "kb-prueba", "max_fragmentos": 2}

RESPUESTA_SIMULADA = {
    "response": [{"content": [{"type": "text", "text": json.dumps([
        {"ref_id": 0, "content": "Multa por Pago Atrasado: 10.00% sobre el valor total de la factura."},
        {"ref_id": 1, "content": "Intereses de mora: 1% mensual prorrateado."},
        {"ref_id": 2, "content": "Texto extra que debe recortarse por max_fragmentos."},
    ])}]}],
    "references": [
        {"id": "0", "blobUrl": "https://x.blob.core.windows.net/c/Base%20de%20Conocimiento%20-%20Alpha%20State%20V2.pdf"},
        {"id": "1", "blobUrl": "https://x.blob.core.windows.net/c/Base%20de%20Conocimiento%20-%20Alpha%20State%20V2.pdf"},
    ],
}


class BaseSimulada(BaseConocimiento):
    def __init__(self, config, respuesta):
        super().__init__(config, credential=object())  # no se usa: _retrieve está simulado
        self.respuesta = respuesta

    def _retrieve(self, pregunta):
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta


def test_consultar_parsea_fragmentos():
    base = BaseSimulada(CONFIG, RESPUESTA_SIMULADA)
    r = base.consultar("¿multa por atraso?")
    assert r["total"] == 3 and len(r["fragmentos"]) == 2
    assert r["fragmentos"][0]["texto"].startswith("Multa por Pago Atrasado")
    assert r["fragmentos"][0]["documento"] == "Base de Conocimiento - Alpha State V2.pdf"


def test_tool_json_y_avisos():
    tool = crear_tool_consultar_politicas(BaseSimulada(CONFIG, RESPUESTA_SIMULADA))
    assert tool.name == "consultar_politicas_alpha_state"
    salida = json.loads(tool.func(pregunta="¿multa por atraso?"))
    assert salida["total"] == 3 and "aviso" not in salida

    vacia = json.loads(crear_tool_consultar_politicas(BaseSimulada(CONFIG, {"response": [], "references": []})).func(pregunta="x"))
    assert vacia["total"] == 0 and "aviso" in vacia

    error = json.loads(crear_tool_consultar_politicas(BaseSimulada(CONFIG, RuntimeError("HTTP 403"))).func(pregunta="x"))
    assert "error" in error and "403" in error["error"]


if __name__ == "__main__":
    for nombre, fn in list(globals().items()):
        if nombre.startswith("test_") and callable(fn):
            fn(); print(f"✅ {nombre}")
    print("Todas las pruebas pasaron.")
