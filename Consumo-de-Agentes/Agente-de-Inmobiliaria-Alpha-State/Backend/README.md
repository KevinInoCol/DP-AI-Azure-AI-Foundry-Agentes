# Backend · consumo del agente hospedado

Tres módulos con responsabilidades separadas:

| Archivo | Qué hace |
|---|---|
| `call_ai_azure_agent.py` | Invocación del agente de Foundry (a partir del snippet "Call agent" del playground): clase `AgenteFoundry` con `abrir_sesion()`, `enviar()` y `cerrar_sesion()`. Sin nada de HTTP. Se puede probar solo: `.venv/bin/python call_ai_azure_agent.py "Hola"`. |
| `session_store.py` | Registro en memoria de qué sesión del agente y qué conversación corresponden a cada cliente web. |
| `main.py` | Solo la API FastAPI: `GET /api/health`, `POST /api/chat`, `DELETE /api/sessions/{id}`. |

```bash
.venv/bin/uvicorn main:app --reload --port 8000
curl -X POST localhost:8000/api/chat -H "Content-Type: application/json" \
  -d '{"user_id":"cliente-demo","message":"Busco kitnet en Barão Geraldo hasta 1500 reales"}'
```

Variables (`.env`): `FOUNDRY_PROJECT_ENDPOINT`, `AGENT_NAME`, `AGENT_VERSION` (vacío = última), `CORS_ORIGINS`. Si cambias `AGENT_VERSION`, reinicia uvicorn: `--reload` solo vigila archivos `.py`.
