"""
API HTTP (FastAPI) del chat con el asistente virtual de la Alcaldía de Girardota.

Solo expone endpoints y traduce entre HTTP y los módulos:
- call_ai_azure_agent.AgenteFoundry: invoca al agente hospedado en Foundry.
- session_store.SessionStore: recuerda qué sesión corresponde a cada ciudadano.

Endpoints:
    GET    /api/health                          → agente, versión y sesiones abiertas
    POST   /api/chat                            → {user_id, message, session_id?} → {session_id, reply, blocked}
    DELETE /api/sessions/{session_id}?user_id=  → cierra la sesión del agente

Datos personales: los mensajes de la ciudadanía pueden traer cédulas, teléfonos o
direcciones aunque el agente no los pida. Por eso esta API **no escribe el
contenido de los mensajes en el log** (solo identificadores recortados) y el
`user_id` que recibe es un identificador opaco que genera el navegador, no un
dato personal.

Ejecutar:
    .venv/bin/uvicorn main:app --reload --port 8001

Puertos 8001/5174 (y no 8000/5173) para poder correr a la vez que la app del
agente inmobiliario del taller.
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from call_ai_azure_agent import AgenteFoundry, MensajeBloqueado, RespuestaFallida
from session_store import SessionStore

load_dotenv()

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5174").split(",") if o.strip()]

MENSAJE_BLOQUEADO = (
    "Su mensaje fue bloqueado por las políticas de seguridad de contenido. "
    "Reformúlelo, por favor, y seguimos con su trámite."
)
MENSAJE_ERROR = "En este momento no puedo responder. Inténtelo de nuevo en unos segundos."
MENSAJE_SATURADO = "El servicio está saturado en este momento. Inténtelo en unos segundos."

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("api")

agente = AgenteFoundry()
sesiones = SessionStore()

app = FastAPI(title="Alcaldía de Girardota · consumo del agente", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


class ChatIn(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=120, description="Identificador opaco de la sesión del ciudadano (no un dato personal)")
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = Field(None, description="Devuelto por la primera respuesta; omitir para empezar de cero")


class ChatOut(BaseModel):
    session_id: str
    reply: str
    blocked: bool = False


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "agent_name": agente.agent_name, "agent_version": agente.agent_version, "sessions": len(sesiones)}


@app.post("/api/chat", response_model=ChatOut)
def chat(body: ChatIn) -> ChatOut:
    sesion = sesiones.obtener(body.session_id, body.user_id)
    if sesion is None:
        sesion = agente.abrir_sesion()
        sesiones.guardar(body.user_id, sesion)
        log.info("sesión %s abierta para %s", sesion.session_id[:8], body.user_id[:12])

    try:
        # Nunca se registra body.message: puede contener datos personales.
        texto = agente.enviar(sesion, body.message, user_id=body.user_id)
    except MensajeBloqueado:
        log.warning("mensaje bloqueado por el filtro de contenido (sesión %s)", sesion.session_id[:8])
        return ChatOut(session_id=sesion.session_id, reply=MENSAJE_BLOQUEADO, blocked=True)
    except RespuestaFallida as exc:
        log.error("respuesta fallida (sesión %s): %s", sesion.session_id[:8], str(exc)[:300])
        raise HTTPException(status_code=503, detail=MENSAJE_SATURADO if "rate limit" in str(exc).lower() else MENSAJE_ERROR) from exc
    except Exception as exc:  # error del servicio: no filtrar detalles internos al cliente
        log.exception("error llamando al agente")
        raise HTTPException(status_code=502, detail=MENSAJE_ERROR) from exc

    return ChatOut(session_id=sesion.session_id, reply=texto or MENSAJE_ERROR)


@app.delete("/api/sessions/{session_id}", status_code=204)
def cerrar_sesion(session_id: str, user_id: str) -> None:
    sesion = sesiones.quitar(session_id, user_id)
    if sesion is None:
        return
    try:
        agente.cerrar_sesion(sesion)
    except Exception as exc:  # la sesión puede haber expirado en Foundry
        log.warning("no se pudo borrar la sesión %s: %s", session_id[:8], exc)
