---
name: azure-foundry-memory
description: Da memoria persistente entre conversaciones a un agente hospedado de Microsoft Foundry construido con Microsoft Agent Framework, usando Memoria de Foundry (memory store, preview) y FoundryMemoryProvider con ámbito (scope) por cliente resuelto en cada petición. Cubre creación del memory store (modelos, user_profile_details, chat summary), roles RBAC que necesitan la identidad del proyecto y la del agente (Foundry User + Cognitive Services OpenAI User), el proveedor MemoriaPorCliente (MEMORY_SCOPE en local, cabecera x-agent-user-id en Foundry, ámbito por defecto), cómo probar de verdad con conversaciones nuevas, cómo ver los recuerdos en el portal y los errores reales (401 de embeddings, update que no cambia la definición). Use when the user asks to "persistir la memoria", "que el agente recuerde al usuario entre conversaciones", "memoria de Foundry", "memory store", "FoundryMemoryProvider", "la memoria es volátil", "no aparecen memorias en el portal", or types /azure-foundry-memory.
---

# Memoria de Foundry para un agente hospedado (Agent Framework)

Flujo probado el 2026-09-04 en el agente `agente-hosted-inmobiliaria` (proyecto `datapath-inofuente`). Las plantillas de `templates/` son el código real que quedó funcionando.

## Conceptos en 30 segundos

| Nivel | Qué es | Dónde vive |
|---|---|---|
| Historial de la conversación | Los mensajes del chat actual | Lo pasa el host de Foundry en cada petición (protocolo Responses) o una `AgentSession` en memoria en local. Volátil por diseño. |
| **Memoria de Foundry** (preview) | Hechos estables del cliente extraídos por un LLM (perfil de usuario, resumen de charlas, memoria procedimental) | Un **memory store** del proyecto. Se consulta y actualiza por **scope** (ámbito): un identificador por cliente. |

`FoundryMemoryProvider` (paquete `agent-framework-foundry`) es un `ContextProvider`: antes de cada respuesta busca recuerdos (estáticos + contextuales) y los inyecta en el contexto; después de cada turno envía la conversación al store con `update_delay` segundos de debounce.

## Prerequisitos

- Proyecto de Foundry con un chat model (gpt-5-mini / gpt-5.4-mini) y un embedding (`text-embedding-3-small`).
- `azure-ai-projects >= 2.3.0`, `agent-framework-foundry` (ya incluidos en un hosted agent de Agent Framework).
- Roles en el **recurso** de Foundry (account scope) para **tres identidades**: tu usuario, la identidad administrada del **proyecto** y la identidad de instancia del **agente hospedado** (`azd ai agent show` → Instance Identity Principal ID):

```bash
ACC=$(az cognitiveservices account show -n <recurso> -g <rg> --query id -o tsv)
for P in <oid-usuario> <principal-proyecto> <principal-agente>; do
  for ROLE in "Foundry User" "Cognitive Services OpenAI User"; do
    az role assignment create --assignee-object-id $P --assignee-principal-type $([ "$P" = "<oid-usuario>" ] && echo User || echo ServicePrincipal) --role "$ROLE" --scope "$ACC"
  done
done
```

El rol "Azure AI User" ya no existe con ese nombre: es **Foundry User**. La propagación tarda varios minutos; mientras, la búsqueda de recuerdos falla con `Memory search failed ... 401 Authentication to the Azure OpenAI resource failed` (el servicio de memoria no puede llamar al modelo de embeddings) aunque las escrituras funcionen.

## Paso 1: Configuración en model_config.yaml

Añade una sección `memory` (ver `templates/model_config_memory.yaml`): `enabled`, `store_name`, `chat_model`, `embedding_model`, `chat_summary_enabled`, `user_profile_details` (qué recordar, qué NO guardar y "redacta cada recuerdo en español"), `scope_por_defecto`, `update_delay`, `context_prompt`. El system prompt solo necesita una sección `<Memoria_Del_Cliente>` que explique cómo usar el bloque de recuerdos (saludar por nombre, retomar la búsqueda, no citar "según mi memoria", no inventar recuerdos, honrar "olvida esto").

## Paso 2: Crear el memory store

Copia `templates/crear_memory_store.py` a `memoria/` y ejecútalo con el venv del agente (lee la sección `memory` del YAML; idempotente):

```bash
.venv/bin/python memoria/crear_memory_store.py
```

Usa `AIProjectClient(endpoint, credential, allow_preview=True).beta.memory_stores.create(name, definition=MemoryStoreDefaultDefinition(chat_model, embedding_model, options=MemoryStoreDefaultOptions(user_profile_enabled=True, chat_summary_enabled=..., user_profile_details=...)))`.

**Limitación real:** `memory_stores.update` solo cambia `description`/`metadata`; la `definition` (modelos, `user_profile_details`) no se actualiza. Para cambiarla hay que **borrar y recrear** el store (se pierden los recuerdos). Define bien `user_profile_details` desde el principio.

## Paso 3: Proveedor con ámbito por cliente

No uses `scope="{{$userId}}"` con `FoundryMemoryProvider` en un hosted agent aunque el sample oficial lo haga: el servicio lo resuelve a un ámbito **opaco** que no coincide con el OID, ni con el literal, ni con la identidad del agente, así que no puedes verlo en el portal ni consultarlo con `list_memories`.

Copia `templates/proveedor.py` a `memoria/proveedor.py`. `MemoriaPorCliente` (subclase de `FoundryMemoryProvider`) resuelve el scope en cada `before_run`/`after_run`:

1. `scope_fijo` (local: `chat_local.py` pasa `MEMORY_SCOPE`).
2. `get_request_context().user_id` de `azure.ai.agentserver.core`: la cabecera `x-agent-user-id` que inyecta la plataforma. En Foundry trae el **object ID de Entra del usuario que llama** (playground, `azd ai agent invoke`); en local `azd ai agent invoke --local --user-identity <id>` la envía; un canal propio (WhatsApp, web) debe enviar el id del cliente en esa cabecera.
3. `scope_por_defecto` (`cliente-sin-identificar`) para que nada quede en un ámbito desconocido.

Registra en el log `Memoria de Foundry: scope=... store=...` y normaliza el valor (solo letras, dígitos y `_ - . % + @ /`).

En `agente.py`:

```python
client = FoundryChatClient(project_endpoint=..., model=..., credential=DefaultAzureCredential(), allow_preview=True)  # allow_preview obligatorio
agent = Agent(client=client, instructions=..., tools=[...],
              context_providers=[MemoriaPorCliente(project_client=client.project_client, memory_store_name=cfg["store_name"],
                                                    scope_fijo=scope_memoria, scope_por_defecto=cfg["scope_por_defecto"],
                                                    context_prompt=cfg["context_prompt"], update_delay=cfg["update_delay"])],
              default_options={"store": False})
```

`crear_agente(scope_memoria=None)`: en Foundry se deja `None`; `chat_local.py` pasa `os.getenv("MEMORY_SCOPE", "cliente-local")`.

`azure.yaml`: añade `MEMORY_STORE_NAME: <store>` en `services.<svc>.env` (el código lo lee como override del YAML).

## Paso 4: Probar de verdad

**Trampa:** `azd ai agent invoke --new-session` **reutiliza la conversación guardada**; el agente "recuerda" por el historial, no por la memoria. Usa siempre `--new-conversation --new-session` y espera más de `update_delay` entre llamadas.

Local (con `azd ai agent run --no-client` en otra terminal):

```bash
azd ai agent invoke --local --new-conversation --new-session --user-identity cliente-mariana "Hola, soy Mariana. Busco kitnet en Barão Geraldo hasta 1500 reales, tengo un gato."
sleep 70
azd ai agent invoke --local --new-conversation --new-session --user-identity cliente-mariana "¿Recuerdas quién soy y qué buscaba?"
```

Remoto: igual sin `--local` y sin `--user-identity` (en remoto da `Caller is not authorized to delegate to another user via the x-ms-user-identity header`; el ámbito será tu OID).

Inspección directa:

```python
pc = AIProjectClient(endpoint=EP, credential=DefaultAzureCredential(), allow_preview=True)
list(pc.beta.memory_stores.list_memories(name="<store>", scope="cliente-mariana"))
pc.beta.memory_stores.delete_scope(name="<store>", scope="cliente-mariana")   # limpiar pruebas
```

## Paso 5: Ver los recuerdos en el portal

Compilación → Memoria → `<store>` → Memorias. El filtro **Ámbito** trae el texto `{{$userId}}`: es un marcador, no un ámbito real; por eso sale "Aún no hay memorias". Escribe el ámbito exacto: el id del cliente (`cliente-mariana`), o tu OID (`az ad signed-in-user show --query id -o tsv`) para lo que hablaste tú en el playground.

## Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| `Memory search failed ... 401 Authentication to the Azure OpenAI resource failed` | Faltan Foundry User + Cognitive Services OpenAI User a la identidad del proyecto/agente, o no propagó | Prerequisitos; esperar hasta 10 min |
| El agente recuerda "en la misma sesión" pero no en una nueva | Prueba con `--new-session` sin `--new-conversation` | Paso 4 |
| Portal: "Aún no hay memorias" | Filtro Ámbito con el marcador literal | Paso 5 |
| `list_memories` da 0 con OID, literal, identidad del agente | Scope `{{$userId}}` resuelto de forma opaca (v≤5) | Paso 3: scope explícito |
| `memory_stores.update(..., definition=...)` → TypeError / no cambia nada | update solo acepta description/metadata | Borrar y recrear el store |
| Recuerdos en inglés | Falta pedirlo en `user_profile_details` | "Redacta cada recuerdo en español" (recrear store) |
| `FoundryMemoryProvider` no inyecta ni los recuerdos estáticos | Si la búsqueda contextual falla, el base descarta todo (mismo try) | Arreglar el 401; no es configurable |
| `azd ai agent monitor` no muestra logs | Solo streaming en vivo | `--follow` mientras invocas, o leer el log local de `azd ai agent run` |

## Referencias

- Quickstart hosted agent con memoria: https://learn.microsoft.com/azure/foundry/agents/quickstarts/quickstart-memory-hosted-agent
- Crear y usar memoria: https://learn.microsoft.com/azure/foundry/agents/how-to/memory-usage
- Sample oficial: https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/agent-framework/responses/13-foundry-memory
