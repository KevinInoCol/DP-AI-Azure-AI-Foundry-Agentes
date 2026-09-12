# Consumo del agente inmobiliario Alpha State

Aplicación web de chat que consume el agente hospedado `agente-hosted-inmobiliaria` desplegado en Microsoft Foundry.

```
Agente-de-Inmobiliaria-Alpha-State/
├── Backend/    # FastAPI: sesiones del agente + Responses API (tiene las credenciales de Azure)
└── Frontend/   # React + Vite: interfaz de chat (habla solo con el backend)
```

```
Navegador ──/api/chat──▶ Backend (FastAPI, :8000) ──Responses API──▶ Foundry ──▶ agente hospedado v9
                                                                       │
                                                                       └─ conversación de Foundry (hilo) + sesión del agente (sandbox)
```

## Arrancar en local

Terminal 1, backend (requiere `az login` en el tenant del proyecto):

```bash
cd Backend
/opt/homebrew/bin/python3.13 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
cp .env.example .env            # endpoint del proyecto, agente y versión
.venv/bin/uvicorn main:app --reload --port 8000
```

Terminal 2, frontend:

```bash
cd Frontend
npm install
npm run dev                      # http://localhost:5173 (proxy /api → :8000)
```

Abre `http://localhost:5173`, escribe tu teléfono o correo como identificador y chatea.

## Cómo funciona

1. El frontend pide un identificador del cliente (teléfono o correo) y lo guarda en el navegador.
2. Cada mensaje va a `POST /api/chat` con `user_id`, `message` y, desde el segundo turno, el `session_id` que devolvió el backend.
3. El backend, en el primer mensaje, crea una **sesión del agente** (`project_client.agents.create_session`, fijada a la versión configurada) y una **conversación de Foundry** (`openai_client.conversations.create()`), y las asocia. En cada turno llama a `responses.create(input, conversation=..., extra_body={"agent_session_id": ...})`. La conversación guarda el hilo: el backend no almacena historial.
4. Si el guardrail del agente bloquea el mensaje (HTTP 400 `content_filter`), el backend responde con `blocked: true` y un texto amable; el frontend lo marca en ámbar.
5. Si el modelo devuelve una respuesta fallida (por ejemplo rate limit), el backend responde 503 con un motivo legible.
6. "Nueva conversación" borra la sesión del agente (`DELETE /api/sessions/{id}`) y empieza de cero.

## Limitación conocida: memoria por cliente

El agente guarda recuerdos por ámbito usando la identidad de quien llama (`x-agent-user-id`). Desde este backend, quien llama es siempre la misma identidad (tu `az login` en local, la identidad administrada en Azure), así que **todos los usuarios de la web comparten un mismo ámbito de memoria**. El backend ya envía el identificador del cliente en la cabecera `x-client-user-id`, que Foundry reenvía al contenedor; falta que el agente la lea en `memoria/proveedor.py` (siguiente iteración) para que cada cliente web tenga su propia memoria.

## Producción (siguiente paso)

- Servir `Frontend/dist` (`npm run build`) desde el mismo host que el backend o desde un Static Web App con el proxy `/api`.
- Backend en Azure Container Apps o App Service con identidad administrada y rol Foundry User en el recurso de Foundry.
- Sesiones en Redis en vez de memoria del proceso; autenticación de usuarios en el frontend.
