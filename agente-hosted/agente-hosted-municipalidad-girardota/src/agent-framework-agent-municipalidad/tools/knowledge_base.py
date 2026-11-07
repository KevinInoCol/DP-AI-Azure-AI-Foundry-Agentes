"""
Tool de consulta a la base de conocimiento municipal de Girardota en Foundry IQ.

La base `girardota-kb` vive en Azure AI Search y contiene los documentos
oficiales del municipio: trámites y servicios, requisitos, costos y descuentos,
plazos, dependencias responsables, horarios, puntos de atención y preguntas
frecuentes. Este módulo llama a la acción `retrieve` de la knowledge base
(agentic retrieval: planificación de subconsultas con un LLM, búsqueda híbrida
y reranking semántico) y devuelve al modelo los fragmentos más relevantes con
sus referencias.

Autenticación: token de Microsoft Entra para https://search.azure.com con
DefaultAzureCredential. En local usa la sesión de `az login`; en Foundry usa la
identidad administrada del agente hospedado, que necesita el rol
"Search Index Data Reader" en el servicio de búsqueda.

Datos personales: la tool consulta por el TRÁMITE, nunca por la persona. El
system prompt obliga a quitar cédulas, teléfonos, direcciones y números de
factura de la pregunta antes de llamar aquí; esta función además recorta la
pregunta para que no se envíen textos largos pegados por el ciudadano.
"""

import json
from typing import Annotated, Any
from urllib.parse import unquote

import requests
from agent_framework import FunctionTool, tool
from azure.identity import DefaultAzureCredential

SEARCH_SCOPE = "https://search.azure.com/.default"
TIMEOUT_SEGUNDOS = 60
MAX_CARACTERES_PREGUNTA = 500


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
            raise RuntimeError("La tool consultar_tramites_girardota necesita search_endpoint y knowledge_base en model_config.yaml")

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
        datos = self._retrieve(pregunta[:MAX_CARACTERES_PREGUNTA])
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
                        "documento": unquote((doc.get("blobUrl") or "").rsplit("/", 1)[-1]) or None,
                    })
        return {"total": len(fragmentos), "fragmentos": fragmentos[: self.max_fragmentos]}


def crear_tool_consultar_tramites(base: BaseConocimiento) -> FunctionTool:
    """Envuelve la knowledge base en la FunctionTool `consultar_tramites_girardota`."""

    @tool
    def consultar_tramites_girardota(
        pregunta: Annotated[
            str,
            "Pregunta sobre un trámite o servicio municipal, en lenguaje natural y SIN datos personales "
            "(sin cédula, teléfono, dirección, número de factura, predio o comparendo). "
            "Ejemplo: '¿qué requisitos piden para el certificado de residencia?'",
        ],
    ) -> str:
        """Consulta la información oficial de la Alcaldía Municipal de Girardota: trámites y servicios,
        requisitos y documentos, costos, descuentos y plazos (impuesto predial, industria y comercio),
        certificados y licencias, SISBÉN y programas sociales, PQRSD, dependencias responsables, horarios
        y puntos de atención, y preguntas frecuentes. Devuelve un JSON con los fragmentos relevantes de los
        documentos oficiales. Úsala siempre que el ciudadano pregunte por un trámite, un requisito, un costo,
        un plazo, un horario o una dependencia. Consulta SIEMPRE por el trámite, nunca por una persona:
        no sirve para consultar deudas, multas, expedientes ni datos de un ciudadano concreto."""
        try:
            resultado = base.consultar(pregunta)
        except Exception as exc:  # el modelo debe poder explicar el fallo al ciudadano
            return json.dumps({"error": f"No se pudo consultar la información oficial: {exc}"}, ensure_ascii=False)
        if resultado["total"] == 0:
            resultado["aviso"] = (
                "La información oficial no cubre esta pregunta; indica al ciudadano que debe confirmarlo "
                "en el canal oficial de atención de la Alcaldía."
            )
        return json.dumps(resultado, ensure_ascii=False)

    return consultar_tramites_girardota


def crear_tool_consultar_tramites_pendiente() -> FunctionTool:
    """Misma tool, en modo "pendiente": se registra mientras la base de conocimiento no existe.

    Sin ninguna tool registrada, el modelo ve el nombre `consultar_tramites_girardota`
    en el system prompt, intenta llamarla e improvisa la sintaxis de llamada como texto
    plano (se observó `to=consultar_tramites_girardota ...json {...}` en la respuesta al
    ciudadano). Registrando una tool real que devuelve un `error` controlado, el modelo
    la invoca por el canal correcto, recibe el error y aplica la regla del prompt:
    decir que no puede consultar la información oficial y derivar al canal de atención.

    Desaparece en cuanto `tools.consultar_tramites_girardota.enabled` pasa a true.
    """

    @tool
    def consultar_tramites_girardota(
        pregunta: Annotated[
            str,
            "Pregunta sobre un trámite o servicio municipal, en lenguaje natural y SIN datos personales.",
        ],
    ) -> str:
        """Consulta la información oficial de la Alcaldía Municipal de Girardota: trámites y servicios,
        requisitos y documentos, costos, descuentos y plazos, certificados y licencias, programas sociales,
        PQRSD, dependencias, horarios y puntos de atención. Úsala siempre que el ciudadano pregunte por un
        trámite, un requisito, un costo, un plazo, un horario o una dependencia. Consulta SIEMPRE por el
        trámite, nunca por una persona."""
        return json.dumps(
            {
                "error": "La base de conocimiento oficial del municipio todavía no está conectada, "
                         "así que no hay ninguna información oficial que consultar.",
                "instruccion": "No inventes requisitos, costos, plazos ni horarios. Dile al ciudadano que "
                               "por ahora no puedes darle esa información y derívalo al canal oficial de atención.",
            },
            ensure_ascii=False,
        )

    return consultar_tramites_girardota
