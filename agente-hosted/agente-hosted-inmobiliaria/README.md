# Agente inmobiliario de Alpha State (Microsoft Agent Framework + Foundry)

Asesor inmobiliario virtual de **Alpha State**, construido con [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) en Python y hospedado en Microsoft Foundry con el **protocolo Responses**. Módulo del taller **Agentes con Azure AI Foundry** de DATAPATH.

| Aspecto | Estado |
|---|---|
| Tools (function calling) | `buscar_propiedades_alquiler` (catálogo de alquileres en Google Sheets) y `consultar_politicas_alpha_state` (políticas, pagos, requisitos y FAQ desde Foundry IQ) |
| Base de conocimiento (RAG) | Foundry IQ: knowledge base `alpha-state-kb` en Azure AI Search, conectada como tool `consultar_politicas_alpha_state` |
| Historial de conversación | Dentro de una conversación: `AgentSession` en local, host de Foundry en la nube. Entre conversaciones: **Memoria de Foundry** (memory store `alpha_state_memory`, un scope por cliente) |
| System prompt | `prompt/system_prompt.yaml`: solo instrucciones (YAML + tags XML, versionado) |
| Configuración del modelo | `model_config/model_config.yaml`: identidad, modelo, opciones y tools |
| Modelo | `gpt-5.4-mini` (SKU `DataZoneStandard`) en el proyecto `datapath-inofuente` |
| Identidad | Bot "Alpha", Alpha State, Campinas (Brasil), catálogo en reales (BRL) |

Para **alquileres** el agente consulta el catálogo real y presenta hasta 5 propiedades. Para **compra y venta** no tiene catálogo: entiende la necesidad y recoge los datos de contacto para que un asesor humano llame. Nunca inventa propiedades, precios ni disponibilidad.

## Estructura

```
agente-hosted-inmobiliaria/
├── azure.yaml                          # manifiesto azd (agente, modelo, runtime, env GOOGLE_SHEETS_ID)
├── AGENTS.md / CLAUDE.md               # instrucciones para agentes de código
└── src/agent-framework-agent-inmobiliaria/
    ├── agente.py                       # une model_config + prompt + tools y crea el Agent
    ├── main.py                         # entry point hosted: ResponsesHostServer en :8088
    ├── chat_local.py                   # consola interactiva con historial en memoria
    ├── model_config/model_config.yaml  # identidad (Alpha, Alpha State, Lima), modelo, opciones, tools
    ├── prompt/system_prompt.yaml       # instrucciones del asesor (placeholders {bot_name} {empresa} {ciudad})
    ├── memoria/crear_memory_store.py   # crea el memory store de Foundry (idempotente)
    ├── tools/google_sheets.py          # CatalogoAlquileres + tool buscar_propiedades_alquiler
    ├── tools/knowledge_base.py         # BaseConocimiento + tool consultar_politicas_alpha_state (retrieve de Foundry IQ)
    ├── data/propiedades_alquiler_ejemplo.csv  # plantilla de la hoja / datos de demo
    ├── rag/Base de Conocimiento/*.pdf  # PDF de políticas y FAQ (fuente de la knowledge base)
    ├── rag/crear_base_conocimiento.py  # crea knowledge source + knowledge base + conexión en Foundry
    ├── tests/test_catalogo.py          # pruebas offline de la tool
    ├── tests/demo_tool_csv_local.py    # demo end-to-end con el CSV local
    ├── requirements.txt
    ├── Dockerfile                      # no se usa con --deploy-mode code
    ├── .env.example
    └── .env                            # endpoint, modelo, GOOGLE_SHEETS_ID
```

## Cómo funciona

1. `agente.py` lee `model_config/model_config.yaml`: sección `agent` (bot, empresa, ciudad), `model` (despliegue y opciones como `store: false`) y `tools`.
2. Carga `prompt/system_prompt.yaml` y rellena los placeholders con la sección `agent`. Así el prompt solo contiene instrucciones.
3. Instancia las tools habilitadas. `buscar_propiedades_alquiler` recibe `distrito`, `precio_max`, `moneda`, `dormitorios_min`, `tipo`, `amoblado` y `mascotas`, descarga la hoja (con caché de 60 s), filtra las filas disponibles y devuelve un JSON con hasta 5 propiedades ordenadas por precio. El precio solo se compara con propiedades en la misma moneda, así no se mezclan soles con dólares.
4. `main.py` expone el agente con `ResponsesHostServer` (Foundry envía el historial en cada petición). `chat_local.py` usa una `AgentSession` en memoria.

## La hoja de Google Sheets

La hoja real de Alpha State es **"Inmuebles en Alquiler - Alpha State V2"**, pestaña `Departamentos`, con inmuebles de Campinas (Brasil) y precios en reales (BRL). Sus cabeceras son:

```
ID Inmueble, Tipo, Barrio, Dirección, Metros Cuadrados, Habitaciones, Baños, Cocheras,
Alquiler Mensual (BRL), IPTU Mensual (BRL), Agua / SANASA, Estado Amoblado
```

La tool trabaja con campos canónicos (`id, titulo, tipo, distrito, direccion, dormitorios, banos, area_m2, precio, moneda, amoblado, mascotas, estacionamiento, estado, descripcion, link`) y la correspondencia con las cabeceras reales se declara en `columnas:` de `model_config.yaml`. Las columnas que no se mapean (IPTU, agua) se devuelven igualmente al modelo. Si la hoja no tiene columna de `estado`, todas las filas se consideran disponibles; si no tiene `moneda`, se usa `moneda_por_defecto` (BRL). Si el cliente pide un criterio que la hoja no registra (por ejemplo mascotas), la tool lo avisa y el agente lo deriva al asesor en lugar de afirmarlo.

Acceso a la hoja:

- **Hoja privada** (configuración actual): cuenta de servicio de Google Cloud con la API de Sheets y Drive habilitadas; la hoja está compartida con su email. El contenido del JSON de la cuenta va en `GOOGLE_SERVICE_ACCOUNT_JSON` y el ID de la hoja (en la URL, entre `/d/` y `/edit`) en `GOOGLE_SHEETS_ID`. Se lee con `gspread` la pestaña `worksheet` de `model_config.yaml`.
- **Hoja pública**: si se comparte como "cualquier persona con el enlace", basta `GOOGLE_SHEETS_ID` y el `gid` de la pestaña; se descarga el CSV exportado sin credenciales.
- **Sin Google**: `origen: csv_local` lee `data/propiedades_alquiler_ejemplo.csv` (esquema canónico, Lima/PEN) para demos.

## Base de conocimiento (Foundry IQ)

El PDF `rag/Base de Conocimiento/Base de Conocimiento - Alpha State V2.pdf` (políticas de alquiler, composición del boleto, multas, garantías y FAQ) está indexado en Foundry IQ:

| Recurso | Nombre |
|---|---|
| Storage (blob) | `stalphastatea144be` / contenedor `base-conocimiento` (East US 2) |
| Azure AI Search | `srch-alphastate-datapath`, nivel Free, Brazil South |
| Knowledge source | `alpha-state-politicas-ks` (azureBlob, embeddings `text-embedding-3-small`) |
| Knowledge base | `alpha-state-kb` (planificación de consultas con `gpt-5-mini`) |
| Conexión en el proyecto | `srch-alphastate-datapath` (Azure AI Search, clave de API) |

Se creó con `rag/crear_base_conocimiento.py`, que es idempotente: si cambias el PDF, vuelve a subirlo al contenedor y ejecuta el script (o el indexador `alpha-state-politicas-ks-indexer`). Las claves se leen con Azure CLI en tiempo de ejecución y no se guardan.

La base se ve en el portal en Compilación → Conocimiento. El agente la consulta con la tool `consultar_politicas_alpha_state` (`tools/knowledge_base.py`), que llama a la acción REST `/knowledgebases/alpha-state-kb/retrieve` con un token de Entra obtenido con `DefaultAzureCredential`: en local usa tu sesión de `az login`; en Foundry usa la identidad administrada del agente hospedado. Ambas identidades, y la del proyecto, tienen el rol Search Index Data Reader en el servicio de búsqueda. El parámetro `maxOutputSize` debe ser mayor que 5000 (el servicio lo exige). Para prompt agents existe la alternativa MCP: `https://srch-alphastate-datapath.search.windows.net/knowledgebases/alpha-state-kb/mcp?api-version=2026-08-01-preview` con la tool `knowledge_base_retrieve`.

## Memoria entre conversaciones (Memoria de Foundry)

El agente recuerda a cada cliente entre conversaciones con **Memoria de Foundry** (preview): un memory store llamado `alpha_state_memory` en el proyecto, creado con `memoria/crear_memory_store.py` y configurado en la sección `memory` de `model_config.yaml`.

- **Qué guarda**: hechos estables del cliente (nombre, forma y horario de contacto, operación, barrios, presupuesto, dormitorios, mascotas, propiedades que le interesaron o descartó). La sección `user_profile_details` le dice a Foundry qué extraer y qué no guardar (documentos, datos bancarios, ingresos, direcciones personales). Los recuerdos se consolidan tras `update_delay` segundos de inactividad.
- **Cómo se usa**: `agente.py` añade un `FoundryMemoryProvider` (Agent Framework) como `context_provider`. Antes de cada respuesta busca recuerdos relevantes y los inyecta en el contexto con el texto de `context_prompt`; después de cada turno envía la conversación al store. El `FoundryChatClient` se crea con `allow_preview=True` para compartir su `AIProjectClient`.
- **Aislamiento por cliente**: el `scope` es `{{$userId}}`. En Foundry, el host lo sustituye por la identidad del usuario que llama (o por la cabecera `x-memory-user-id` si tu canal la envía). En local, `chat_local.py` usa la variable `MEMORY_SCOPE` (por defecto `cliente-local`); cambia su valor para simular clientes distintos.
- **Permisos**: la identidad administrada del proyecto, la identidad del agente hospedado y tu usuario necesitan **Foundry User** y **Cognitive Services OpenAI User** en el recurso de Foundry (el servicio de memoria usa los modelos `gpt-5-mini` y `text-embedding-3-small`). Sin ellos, las escrituras o búsquedas fallan con 401.
- **Prueba**: en local, ejecuta `chat_local.py`, preséntate y cierra; vuelve a abrirlo con el mismo `MEMORY_SCOPE` y pregunta "¿recuerdas qué buscaba?". En Foundry, `azd ai agent invoke --new-session "..."` dos veces.

## Prerequisitos

- Azure CLI con sesión (`az login --tenant <tenant-id>`) y `azd` ≥ 1.27 con la extensión `microsoft.foundry`.
- Python 3.13.
- Proyecto de Foundry con el despliegue `gpt-5.4-mini` (ya existe en `datapath-inofuente`).

```bash
azd config set auth.useAzCliAuth true      # azd reutiliza la sesión de Azure CLI
azd auth login --check-status
```

## Ejecutar en local

```bash
cd src/agent-framework-agent-inmobiliaria
/opt/homebrew/bin/python3.13 -m venv .venv          # Windows: py -3.13 -m venv .venv
.venv/bin/python -m pip install uv
.venv/bin/python -m uv pip install -r requirements.txt --python .venv/bin/python
cp .env.example .env                                 # endpoint, modelo, GOOGLE_SHEETS_ID y GOOGLE_SERVICE_ACCOUNT_JSON
```

Pruebas y demos:

```bash
.venv/bin/python tests/test_catalogo.py            # pruebas offline de la tool de Google Sheets
.venv/bin/python tests/test_base_conocimiento.py   # pruebas offline de la tool de la base de conocimiento
.venv/bin/python tests/demo_tool_csv_local.py      # conversación de 3 turnos con la tool (CSV local)
MEMORY_SCOPE=cliente-demo .venv/bin/python chat_local.py   # consola interactiva con memoria de Foundry
```

Servidor con protocolo Responses, como en Foundry:

```bash
cd ../..
source src/agent-framework-agent-inmobiliaria/.venv/bin/activate
azd ai agent run --no-client                         # espera "Running on http://0.0.0.0:8088"
azd ai agent invoke --local "Busco un departamento en alquiler en Miraflores hasta 2500 soles"
```

## Desplegar en Foundry

```bash
export AZURE_DEV_USER_AGENT=microsoft_foundry_skill
azd env set GOOGLE_SHEETS_ID "<id-de-la-hoja>"                       # se inyectan al contenedor vía azure.yaml
azd env set GOOGLE_SERVICE_ACCOUNT_JSON "$(cat cuenta-servicio.json)"  # solo si la hoja es privada
azd deploy --no-prompt                           # nueva versión, ~1-3 min
azd ai agent show                                # status active + URL del playground
azd ai agent invoke "Busco alquiler en Barranco, acepto mascotas"
```

> El despliegue `gpt-5.4-mini` lo comparten `agente-hosted-basico` y este agente. `azd down` en cualquiera de los dos proyectos intentaría eliminar ese despliegue de modelo.

## Personalizar

- **Nombre del bot, empresa, ciudad, moneda**: sección `agent` de `model_config.yaml`.
- **Otra hoja con otras cabeceras**: ajusta `columnas:` y `worksheet` en `tools.buscar_propiedades_alquiler` de `model_config.yaml`.
- **Modelo y opciones**: sección `model`. Si cambias a un modelo que lo admita (gpt-4o-mini), puedes añadir `temperature` o `max_tokens` en `options`.
- **Comportamiento y tono**: `prompt/system_prompt.yaml`. Sube `version` y vuelve a desplegar. Mantén todas las secciones en tags abiertos y cerrados y cita las tools con su nombre exacto.
- **Nueva tool**: impleméntala en `tools/`, regístrala en `crear_tools()` de `agente.py`, añade su bloque en `tools:` de `model_config.yaml` y descríbela en `<Herramientas_Disponibles>` del prompt.

## Referencias

- [Hosted agents](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents)
- [Quickstart: hosted agent con azd](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent)
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
