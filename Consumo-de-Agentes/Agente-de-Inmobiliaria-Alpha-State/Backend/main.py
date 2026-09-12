"""
API HTTP (FastAPI) del chat con el agente inmobiliario de Alpha State.

Solo expone endpoints y traduce entre HTTP y los módulos:
- call_ai_azure_agent.AgenteFoundry: invoca al agente hospedado en Foundry.
- session_store.SessionStore: recuerda qué sesión corresponde a cada cliente web.

Endpoints:
    GET    /api/health                       → agente, versión y sesiones abiertas
    POST   /api/chat                         → {user_id, message, session_id?} → {session_id, reply, blocked}
    DELETE /api/sessions/{session_id}?user_id=  → cierra la sesión del agente

Ejecutar:
    .venv/bin/uvicorn main:app --reload --port 8000
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

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]

MENSAJE_BLOQUEADO = "Tu mensaje fue bloqueado por las políticas de seguridad de Alpha State. Reformúlalo, por favor, y seguimos."
MENSAJE_ERROR = "Ahora mismo no puedo responder. Inténtalo de nuevo en unos segundos."
MENSAJE_SATURADO = "El modelo está saturado en este momento. Inténtalo en unos segundos."

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("api")

agente = AgenteFoundry()
sesiones = SessionStore()

app = FastAPI(title="Alpha State · consumo del agente", version="1.1.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


class ChatIn(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=120, description="Teléfono, correo o id del cliente")
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
        log.info("sesión %s abierta para %s", sesion.session_id[:8], body.user_id)

    try:
        texto = agente.enviar(sesion, body.message, user_id=body.user_id)
    except MensajeBloqueado:
        log.warning("mensaje bloqueado por guardrail (sesión %s)", sesion.session_id[:8])
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
