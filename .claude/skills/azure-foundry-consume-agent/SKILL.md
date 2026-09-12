---
name: azure-foundry-consume-agent
description: Construye una aplicación que consume un agente hospedado de Microsoft Foundry desde fuera del portal — backend FastAPI (sesión del agente + conversación de Foundry + Responses API con azure-ai-projects ≥ 2.6) y frontend de chat en React + Vite con proxy /api — a partir del snippet "Call agent" del playground. Cubre la API real del SDK (project_client.agents.create_session, no beta.agents ni isolation_key), la continuidad del hilo con conversation, el manejo de bloqueos del guardrail (400 content_filter) y de respuestas fallidas por rate limit (status failed), y la limitación de memoria por cliente desde un backend. Use when the user asks to "consumir el agente", "llamar al agente desde mi app", "interfaz de chat para el agente", "frontend React para el agente", "Call agent del playground", or types /azure-foundry-consume-agent.
---

# Consumir un agente hospedado desde una app propia (FastAPI + React)

Probado el 2026-09-11 con `agente-hosted-inmobiliaria` v9 (proyecto `datapath-inofuente`). Las plantillas de `templates/` son el código real que quedó funcionando: `backend/` (tres módulos) y `frontend/`.

## Arquitectura

```
Navegador ──/api/chat──▶ Backend FastAPI (:8000, credenciales Azure) ──Responses API──▶ Foundry ──▶ agente hospedado
```

El navegador nunca habla con Foundry. El backend usa `DefaultAzureCredential` (`az login` en local, identidad administrada en Azure) y necesita el rol **Foundry User** en el recurso.

## El snippet del portal y la API real del SDK

El playground (Agents → Playground → Call agent) genera un ejemplo con `project_client.beta.agents.create_session(..., isolation_key=...)`. En `azure-ai-projects` 2.6.0 eso **no existe**; la API es:

```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import VersionRefIndicator

pc = AIProjectClient(endpoint=ENDPOINT, credential=DefaultAzureCredential(), allow_preview=True)
version = pc.agents.get(agent_name=AGENTE).versions["latest"].version           # o una fija
sesion = pc.agents.create_session(agent_name=AGENTE, version_indicator=VersionRefIndicator(agent_version=version))
oc = pc.get_openai_client(agent_name=AGENTE)
conv = oc.conversations.create()                                                   # el hilo vive en Foundry
r = oc.responses.create(input="Hola", conversation=conv.id, extra_body={"agent_session_id": sesion.agent_session_id})
print(r.status, r.output_text)
pc.agents.delete_session(agent_name=AGENTE, session_id=sesion.agent_session_id)
```

Reglas aprendidas:
- **Continuidad**: pasa siempre `conversation=conv.id`. Solo `agent_session_id` no basta para que el agente recuerde el turno anterior; la sesión es el sandbox del contenedor, la conversación es el historial.
- **Respuestas fallidas no lanzan excepción**: revisa `r.status == "failed"` y `r.error.message`. El rate limit del modelo ("Model deployment rate limit exceeded") llega así, con `output_text` vacío. Con capacidad 10 (10K TPM) un agente con prompt largo, tools y memoria se satura en pocas llamadas; sube la capacidad del despliegue en `azure.yaml` (`sku.capacity`) y `azd provision`.
- **Guardrail**: un mensaje bloqueado llega como `openai.BadRequestError` con `content_filter`; conviértelo en una respuesta amable con `blocked: true`.
- `extra_headers={"x-client-user-id": ...}`: la familia `x-client-*` se reenvía al contenedor del agente; sirve si el agente la lee.
- Cada `create_session` deja una sesión en Foundry; bórrala al cerrar la conversación o se acumulan (quedan en estado IDLE).

## Backend (plantilla `backend/`, tres módulos)

Separación que pidió el usuario y conviene mantener: `call_ai_azure_agent.py` (clase `AgenteFoundry`: abrir_sesion / enviar / cerrar_sesion; excepciones `MensajeBloqueado` y `RespuestaFallida`; sin nada de HTTP), `session_store.py` (registro session_id → usuario + sesión, en memoria) y `main.py` (solo la API FastAPI). Endpoints: `GET /api/health`, `POST /api/chat {user_id, message, session_id?} → {session_id, reply, blocked}`, `DELETE /api/sessions/{id}?user_id=`. Mapa en memoria `session_id → {user_id, conversation_id}` (Redis en producción). Variables: `FOUNDRY_PROJECT_ENDPOINT`, `AGENT_NAME`, `AGENT_VERSION` (vacío = última), `CORS_ORIGINS`.

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --reload --port 8000
```

## Frontend (plantilla `frontend/`)

`npm create vite@latest Frontend -- --template react --no-interactive`, luego copia `vite.config.js` (proxy `/api` → `:8000`), `src/App.jsx`, `src/components/Mensaje.jsx`, `src/api.js`, `src/index.css`. Flujo: pide un identificador del cliente (teléfono/correo, guardado en localStorage) → chat con burbujas, indicador "escribiendo", botón "Nueva conversación" (borra la sesión) y pie con agente/versión/sesión. `npm run build` para producción.

## Limitación: memoria por cliente desde un backend

El agente guarda recuerdos por ámbito con la identidad de quien llama (`x-agent-user-id`), que desde el backend es siempre la misma. Todos los usuarios web comparten un ámbito salvo que el agente lea `x-client-user-id` (cambio en su proveedor de memoria) o se use un canal que pase la identidad del usuario final.

## Verificación

1. `curl localhost:8000/api/health` → agente y versión.
2. Dos `POST /api/chat` con el mismo `session_id`: el segundo debe recordar el primero.
3. Mensaje violento → `blocked: true`.
4. `DELETE` → 204. `curl localhost:5173/api/health` con Vite arriba → el proxy funciona.
5. `npm run build` sin errores.

## Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| `'BetaAgentsOperations' object has no attribute 'create_session'` | Snippet del portal desactualizado | `pc.agents.create_session(...)` sin `isolation_key` |
| `output_text` vacío | `status == failed` (rate limit u otro) | Leer `r.error.message`; subir capacidad del modelo |
| El agente no recuerda el turno anterior | Falta `conversation=` | Crear conversación y pasarla en cada turno |
| `zsh: echo` rompe el JSON al probar con curl | `echo` interpreta `\n` | Probar con Python `urllib` o `printf '%s'` |
| Sesiones IDLE acumuladas en Foundry | No se borran | `pc.agents.list_sessions` / `delete_session` |
| Cambias `AGENT_VERSION` en `.env` y el backend sigue en la versión anterior | `--reload` solo vigila `.py` | Reiniciar uvicorn |
