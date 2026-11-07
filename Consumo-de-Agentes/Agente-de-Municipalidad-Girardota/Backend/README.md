# Backend · consumo del agente de la Alcaldía de Girardota

FastAPI que invoca el agente hospedado `agente-hosted-municipalidad-girardota`.
Ver el [README de la app](../README.md) para la arquitectura completa.

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # rellena FOUNDRY_PROJECT_ENDPOINT
.venv/bin/uvicorn main:app --reload --port 8001
```

Requiere `az login` con una cuenta que tenga el rol **Foundry User** en el
recurso de Foundry.

| Módulo | Responsabilidad |
|---|---|
| `call_ai_azure_agent.py` | Clase `AgenteFoundry`: `abrir_sesion` / `enviar` / `cerrar_sesion`. Excepciones `MensajeBloqueado` y `RespuestaFallida`. No sabe nada de HTTP. |
| `session_store.py` | Mapa en memoria `session_id → (user_id, SesionAgente)`. En producción, Redis. |
| `main.py` | Solo la API HTTP: valida, traduce errores y responde. |

Prueba directa del módulo del agente, sin levantar la API:

```bash
.venv/bin/python call_ai_azure_agent.py "¿Qué necesito para un certificado de residencia?"
```

| Variable | Para qué |
|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | Endpoint del proyecto de Foundry |
| `AGENT_NAME` | `agente-hosted-municipalidad-girardota` |
| `AGENT_VERSION` | Vacío = última versión al arrancar (se fija al arranque; reinicia uvicorn para cambiarla) |
| `CORS_ORIGINS` | `http://localhost:5174` en desarrollo |

El log no incluye el texto de los mensajes: pueden contener datos personales que
el ciudadano escribió por su cuenta.
