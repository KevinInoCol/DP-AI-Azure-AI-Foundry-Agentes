"""
Tool de consulta a la base de conocimiento de Alpha State en Foundry IQ.

La base `alpha-state-kb` vive en Azure AI Search y contiene el PDF de políticas
de alquiler, composición del boleto (alquiler, IPTU, SANASA, seguro), multas y
recargos, requisitos, garantías y preguntas frecuentes. Este módulo llama a la
acción `retrieve` de la knowledge base (agentic retrieval: planificación de
subconsultas con un LLM, búsqueda híbrida y reranking semántico) y devuelve al
modelo los fragmentos más relevantes con sus referencias.

Autenticación: token de Microsoft Entra para https://search.azure.com con
DefaultAzureCredential. En local usa la sesión de `az login`; en Foundry usa la
identidad administrada del agente hospedado, que necesita el rol
"Search Index Data Reader" en el servicio de búsqueda.
"""

import json
from typing import Annotated, Any

import requests
from agent_framework import FunctionTool, tool
from azure.identity import DefaultAzureCredential

SEARCH_SCOPE = "https://search.azure.com/.default"
TIMEOUT_SEGUNDOS = 60


class BaseConocimiento:
    """Cliente mínimo de una knowledge base de Azure AI Search (acción retrieve)."""

    def __init__(self, config: dict[str, Any], credential: DefaultAzureCredential | None = None) -> None:
        self.endpoint = config["search_endpoint"].rstrip("/")
        self.knowledge_base = config["knowledge_base"]
        self.api_version = config.get("api_version", "2026-08-01-preview")
        self.max_fragmentos = int(config.get("max_fragmentos", 5))
        self.max_output_size = max(int(config.get("max_output_size_tokens", 8000)), 5001)  # el servicio exige > 5000
        self.credential = credential or DefaultAzureCredential()

    def verificar_configuracion(self) -> None:
        if not self.endpoint.startswith("https://") or not self.knowledge_base:
            raise RuntimeError("La tool consultar_politicas_alpha_state necesita search_endpoint y knowledge_base en model_config.yaml")

    def _headers(self) -> dict[str, str]:
        token = self.credential.get_token(SEARCH_SCOPE).token
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _retrieve(self, pregunta: str) -> dict[str, Any]:
        url = f"{self.endpoint}/knowledgebases/{self.knowledge_base}/retrieve?api-version={self.api_version}"
        cuerpo = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": pregunta}]}],
            "maxOutputSize": self.max_output_size,
        }
        respuesta = requests.post(url, headers=self._headers(), json=cuerpo, timeout=TIMEOUT_SEGUNDOS)
        if respuesta.status_code >= 300:
            raise RuntimeError(f"retrieve -> HTTP {respuesta.status_code}: {respuesta.text[:300]}")
        return respuesta.json()

    def consultar(self, pregunta: str) -> dict[str, Any]:
        """Devuelve {'fragmentos': [{ref, texto, documento}], 'total': n}."""
        datos = self._retrieve(pregunta)
        referencias = {str(r.get("id")): r for r in datos.get("references", [])}
        fragmentos: list[dict[str, Any]] = []
        for item in datos.get("response", []):
            for contenido in item.get("content", []):
                texto = contenido.get("text") or ""
                try:
                    piezas = json.loads(texto)
                except json.JSONDecodeError:
                    piezas = [{"ref_id": None, "content": texto}]
                for pieza in piezas:
                    ref = str(pieza.get("ref_id"))
                    doc = referencias.get(ref, {})
                    fragmentos.append({
                        "ref": ref,
                        "texto": (pieza.get("content") or "").strip(),
                        "documento": (doc.get("blobUrl") or "").rsplit("/", 1)[-1].replace("%20", " ") or None,
                    })
        return {"total": len(fragmentos), "fragmentos": fragmentos[: self.max_fragmentos]}


def crear_tool_consultar_politicas(base: BaseConocimiento) -> FunctionTool:
    """Envuelve la knowledge base en la FunctionTool `consultar_politicas_alpha_state`."""

    @tool
    def consultar_politicas_alpha_state(
        pregunta: Annotated[str, "Pregunta del cliente en lenguaje natural, con el contexto necesario. Ejemplo: '¿qué multa se cobra por pagar el alquiler con atraso?'"],
    ) -> str:
        """Consulta la base de conocimiento oficial de Alpha State: políticas de alquiler, qué incluye el boleto
        mensual (alquiler, IPTU, agua SANASA, seguro de incendio, gastos bancarios), multas e intereses por atraso,
        reajuste anual, requisitos y documentos para alquilar, garantías aceptadas (fiador, depósito, seguro fianza),
        responsabilidades de reparaciones, datos de contacto de la inmobiliaria y preguntas frecuentes.
        Devuelve un JSON con los fragmentos relevantes del documento oficial. Úsala siempre que el cliente pregunte
        por condiciones, procesos, pagos, requisitos o políticas; NO sirve para buscar propiedades disponibles."""
        try:
            resultado = base.consultar(pregunta)
        except Exception as exc:  # el modelo debe poder explicar el fallo al cliente
            return json.dumps({"error": f"No se pudo consultar la base de conocimiento: {exc}"}, ensure_ascii=False)
        if resultado["total"] == 0:
            resultado["aviso"] = "La base de conocimiento no tiene información sobre esta pregunta; indica al cliente que un asesor lo confirmará."
        return json.dumps(resultado, ensure_ascii=False)

    return consultar_politicas_alpha_state
