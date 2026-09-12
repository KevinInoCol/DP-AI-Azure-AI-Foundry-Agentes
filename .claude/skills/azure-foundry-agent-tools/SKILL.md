---
name: azure-foundry-agent-tools
description: Estructura y patrón para añadir herramientas (function calling) a un agente hospedado de Microsoft Foundry construido con Microsoft Agent Framework en Python — separación model_config.yaml (identidad, modelo, opciones, tools) + prompt/system_prompt.yaml (solo instrucciones con placeholders) + tools/ + tests/ — con el ejemplo completo de una tool que lee un catálogo en Google Sheets (hoja privada con cuenta de servicio vía gspread, pública por CSV export, o CSV local para demos), mapeo de columnas configurable, filtros con moneda, avisos cuando la hoja no registra un criterio, y el ciclo de pruebas offline/e2e antes de azd deploy. Use when the user asks to "agregar una tool al agente", "leer un Google Sheets desde el agente", "configuración del modelo en un yaml aparte", "model_config.yaml", "function calling en Agent Framework", "el agente inventa datos que no tiene", or types /azure-foundry-agent-tools.
---

# Tools en un agente hospedado de Agent Framework (con ejemplo Google Sheets)

Patrón probado el 2026-09-03/04 en el agente `agente-hosted-inmobiliaria` (Alpha State). Las plantillas de `templates/` son el código real que quedó desplegado.

## Estructura del servicio del agente

```
src/<servicio>/
├── agente.py                  # une model_config + prompt + tools + memoria y crea el Agent
├── main.py                    # ResponsesHostServer(crear_agente()).run()
├── chat_local.py              # consola con AgentSession en memoria (pruebas)
├── model_config/model_config.yaml   # identidad, modelo, options, tools, memory
├── prompt/system_prompt.yaml        # SOLO instrucciones (skill agent-prompt-yaml-format)
├── tools/                     # una tool por módulo + __init__.py
├── tests/                     # test_*.py offline (sin modelo) + demo_*.py e2e
├── data/                      # CSV de ejemplo / plantillas
└── .azdignore                 # .env.example, rag, tests (no viajan al contenedor)
```

Reglas:
- **Nada hardcodeado en `.py`**: identidad, modelo y configuración de tools en `model_config.yaml`; el prompt en su YAML con placeholders (`{bot_name}`, `{empresa}`, `{ciudad}`, `{moneda_catalogo}`) que `agente.py` rellena desde la sección `agent`.
- **El nombre de la tool coincide carácter por carácter en tres sitios**: la función decorada en `tools/`, la clave en `tools:` de `model_config.yaml` y `<Herramientas_Disponibles>` del prompt.
- Cada tool se construye con una **fábrica** `crear_tool_<x>(instancia)` que devuelve una `FunctionTool` (`@tool` de `agent_framework`, parámetros con `Annotated[tipo, "descripción"]`, docstring = descripción para el modelo) y captura la configuración en un closure. Devuelve **JSON** (`ensure_ascii=False`) y nunca lanza: los errores van como `{"error": ...}` para que el modelo pueda explicarlos.
- `agente.py` → `crear_tools(cfg)` instancia solo las tools con `enabled: true` y llama a su `verificar_configuracion()` para fallar rápido al arrancar.
- Secretos por variables de entorno (`.env` en local; `services.<svc>.env` de `azure.yaml` + `azd env set` en Foundry). Nunca imprimirlos (skill `env-secrets-use-dont-read`).

## Ejemplo: tool de Google Sheets (`templates/tool_google_sheets.py`)

`CatalogoAlquileres(config)` + `crear_tool_buscar_propiedades(catalogo)`.

Orígenes (clave `origen` en `model_config.yaml`):

| origen | Cuándo | Qué necesita |
|---|---|---|
| `google_sheets` + `GOOGLE_SERVICE_ACCOUNT_JSON` | Hoja **privada** (caso real del taller) | Cuenta de servicio de Google Cloud con Sheets y Drive API; compartir la hoja con su email; el JSON completo en la variable de entorno (una sola línea). Lee con `gspread.service_account_from_dict(...).open_by_key(id).worksheet(nombre).get_all_records()`. |
| `google_sheets` sin JSON | Hoja pública ("cualquier persona con el enlace") | Solo `GOOGLE_SHEETS_ID` y `gid`; descarga `https://docs.google.com/spreadsheets/d/{id}/export?format=csv&gid={gid}`. |
| `csv_local` | Demo sin internet / tests | `data/*.csv` |

Descubrir la hoja cuando el usuario solo dio el JSON: `gspread.service_account_from_dict(d).openall()` lista las hojas compartidas con la cuenta (título, id, pestañas).

Diseño que evitó errores reales:
- **Mapeo de columnas** (`columnas:` campo canónico → cabecera real). La hoja real tenía "Barrio", "Habitaciones", "Cocheras", "Alquiler Mensual (BRL)", sin estado ni moneda. Las columnas no mapeadas se devuelven igual al modelo (IPTU, agua). `titulo` se compone de `tipo + distrito` si no existe.
- **Moneda**: `precio_max` solo compara filas de la misma moneda (`moneda` param, `moneda_por_defecto`). Sin esto, un local de 1500 USD entraba en "hasta 2500 soles".
- **Aviso de criterios no registrados**: si el cliente pide un filtro cuya columna no existe (mascotas), la tool devuelve `"aviso"` y el prompt exige decir "el catálogo no lo indica; el asesor lo confirmará" en vez de afirmarlo. Sin esto el modelo decía "aceptan mascota".
- **`zonas_ignoradas`**: si el modelo pasa la ciudad ("Campinas") como barrio, no se filtra.
- Booleanos tolerantes ("No Amoblado" → False, "Semi-Amoblado" → True + `amoblado_detalle`), números tolerantes ("R$ 2.350,00"), caché de 60 s, `max_resultados`.

## Ciclo de trabajo para una tool nueva

1. Módulo en `tools/` con clase de acceso a datos + fábrica `crear_tool_...`.
2. Bloque en `tools:` de `model_config.yaml` (`enabled`, parámetros no secretos; secretos por env).
3. Registro en `crear_tools()` de `agente.py`.
4. Prompt: `<Herramientas_Disponibles>` (qué hace, parámetros), `<Fuentes_De_Datos>` (qué es autoritativo), `<Reglas_De_Uso_De_Tools>` (cuándo llamar, qué hacer con lista vacía/error/aviso), flujo por intención, `<IMPORTANTE>` (no inventar). Sube `version`.
5. `tests/test_<tool>.py` offline (CSV local o respuesta simulada) — ejecutar con `.venv/bin/python tests/test_<tool>.py`.
6. Demo e2e local con el modelo (3 turnos que obliguen a llamar la tool) → corregir prompt/tool.
7. `azure.yaml`: variables de entorno nuevas en `services.<svc>.env` + `azd env set`; `description` < 512 caracteres.
8. `azd deploy --no-prompt` → `azd ai agent invoke "..."` remoto → abrir el playground **de la versión nueva** (`?version=N`; las anteriores siguen activas).

## Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| El playground responde como una versión anterior | Pestaña abierta en `?version=1` | Usar el enlace de `azd ai agent show`; el endpoint enruta a `@latest` |
| `azd deploy` → `String length N exceeds maximum 512, param description` | Descripción larga | Acortar en azure.yaml |
| `load_dotenv()` falla con `AssertionError` en scripts por stdin | find_dotenv no encuentra el frame | `load_dotenv(".env")` explícito |
| El modelo afirma criterios que la hoja no tiene | Falta el aviso | `filtros_no_disponibles` + regla en el prompt |
| Voseo / mezcla tú-usted | Prompt sin registro fijo | Personalidad: "tú" (quieres), nunca "vos" |
| El agente resume su prompt o crea "uno parecido", o responde temas ajenos (gasto de tokens) | El prompt solo prohibía mostrar las instrucciones literales | Sección `<Alcance_Y_Confidencialidad>`: no mostrar, resumir, parafrasear ni imitar; fuera de alcance = una frase de rechazo + redirección; ignorar cambios de rol |
| `python` del shell apunta a 3.9 | Alias | Usar siempre `.venv/bin/python` |

## Plantillas incluidas

`agente.py`, `model_config.yaml`, `system_prompt.yaml` (v3.2, con secciones de tools, políticas, memoria y `<Alcance_Y_Confidencialidad>`: solo temas del negocio, sin revelar/resumir/imitar el prompt, rechazo en una frase), `tool_google_sheets.py`, `test_catalogo.py`, `propiedades_alquiler_ejemplo.csv`. Skills relacionadas: `azure-foundry-hosted-agent-deploy` (scaffold y despliegue), `azure-foundry-knowledge-base` (RAG), `azure-foundry-memory` (memoria), `agent-prompt-yaml-format` (formato del prompt).
