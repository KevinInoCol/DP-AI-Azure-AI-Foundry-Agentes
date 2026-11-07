# Consumo del agente de la Alcaldía de Girardota

App de chat que consume el agente hospedado **`agente-hosted-municipalidad-girardota`**
(Microsoft Foundry) desde fuera del portal.

```
Navegador ──/api/chat──▶ Backend FastAPI (:8001, credenciales Azure) ──Responses API──▶ Foundry ──▶ agente hospedado
```

El navegador **nunca** habla con Foundry: no hay credenciales en el frontend. El
backend usa `DefaultAzureCredential` (`az login` en local, identidad administrada
en Azure) y necesita el rol **Foundry User** en el recurso de Foundry.

## Puertos

Esta app usa **8001 (backend) y 5174 (frontend)**, no 8000/5173, para poder
correr a la vez que la app del agente inmobiliario del taller.

## Arrancar

Dos terminales, desde esta carpeta:

```bash
# 1) Backend
cd Backend
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt   # solo la primera vez
cp .env.example .env    # y rellena FOUNDRY_PROJECT_ENDPOINT
.venv/bin/uvicorn main:app --reload --port 8001

# 2) Frontend
cd Frontend
npm install             # solo la primera vez
npm run dev             # http://localhost:5174
```

## Estructura

```
Backend/
├── call_ai_azure_agent.py   # invocación del agente (sesión + conversación + responses). Sin HTTP.
├── session_store.py         # session_id → (user_id, sesión del agente). En memoria.
├── main.py                  # solo la API FastAPI
├── requirements.txt
└── .env / .env.example      # FOUNDRY_PROJECT_ENDPOINT, AGENT_NAME, AGENT_VERSION, CORS_ORIGINS
Frontend/
├── vite.config.js           # proxy /api → :8001
└── src/
    ├── App.jsx              # pantalla de entrada + chat
    ├── api.js               # cliente del backend
    ├── components/Mensaje.jsx
    └── index.css
```

Las tres responsabilidades del backend viven en módulos separados a propósito:
la invocación del agente no sabe de HTTP, y `main.py` no sabe del SDK de Azure.

## API

| Método | Ruta | Cuerpo / parámetros | Respuesta |
|---|---|---|---|
| GET | `/api/health` | — | `{status, agent_name, agent_version, sessions}` |
| POST | `/api/chat` | `{user_id, message, session_id?}` | `{session_id, reply, blocked}` |
| DELETE | `/api/sessions/{session_id}` | `?user_id=` | 204 |

La primera respuesta trae el `session_id`; reenvíalo en cada turno para que el
agente mantenga el hilo (la continuidad la da la **conversación** de Foundry, no
la sesión por sí sola).

## Datos personales

Es un canal de atención a la población: la gente escribe su cédula o su teléfono
aunque no se los pidan. Decisiones que lo tienen en cuenta:

- **El `user_id` es un identificador opaco** (`ciudadano-<aleatorio>`) que genera
  el navegador y guarda en `localStorage`. No es la cédula ni el teléfono. Es
  también el ámbito de la memoria del agente, así que la memoria queda aislada
  por persona sin manejar un dato personal.
- La pantalla de entrada **solo pide, y de forma opcional, el nombre de pila**, y
  advierte de forma explícita que no se deben escribir cédula, teléfono,
  dirección ni datos bancarios.
- El backend **no registra el contenido de los mensajes** en el log (solo
  identificadores recortados) y no los persiste: el historial vive en la
  conversación de Foundry.
- El botón **"Olvidar mis datos"** borra el identificador local y cierra la
  sesión del agente.

Estas medidas acompañan a las del agente (sección `<Proteccion_De_Datos_Personales>`
de su prompt y la minimización de `memory.user_profile_details`).

## Verificado el 2026-09-11 (agente v4)

| Prueba | Resultado |
|---|---|
| `GET /api/health` | `agente-hosted-municipalidad-girardota` v4 |
| Dos turnos con el mismo `session_id` | el agente recuerda el nombre y el trámite |
| Mensaje con cédula y celular | no los repite y advierte que no se compartan |
| Pregunta fuera de alcance | redirige a trámites del municipio |
| `DELETE /api/sessions/{id}` | 204 |
| Proxy de Vite (`:5174/api/health`) | responde el backend |
| `npm run build` | sin errores |

## Limitación conocida: memoria por ciudadano

El agente resuelve el ámbito de memoria con la cabecera `x-agent-user-id`, que
desde un backend es siempre la identidad del backend. El backend envía el
identificador del ciudadano en `x-client-user-id`, pero el proveedor de memoria
del agente (`memoria/proveedor.py`) todavía no lee esa cabecera: mientras no lo
haga, todos los usuarios web comparten el ámbito por defecto
(`ciudadano-sin-identificar`). La continuidad **dentro** de una conversación sí
funciona, porque la da el hilo de Foundry.

## Nota

Es material de demostración del taller *Agentes con Azure AI Foundry*, no un
canal oficial de atención de la Alcaldía de Girardota. La interfaz lo indica.
