# ADR 0001 — Verificar el recurso y el proyecto de Foundry antes de desplegar o crear recursos

- **Estado:** Aceptado
- **Fecha:** 2026-11-06
- **Ámbito:** agentes hospedados de Microsoft Foundry (`agente-hosted/`) y el harness que los despliega: skills de Claude Code `azure-foundry-hosted-agent-deploy` y `azure-foundry-knowledge-base`
- **Agente donde se detectó:** Municipalidad de Girardota (`agente-hosted/agente-hosted-municipalidad-girardota`)

## 1. Contexto

La suscripción del taller (`57ff11aa-…`) tiene **dos recursos de Microsoft Foundry**:

| Recurso | Resource group | Proyecto | Rol |
|---|---|---|---|
| `Datapath-AI-Engineer-KAIC` | `Datapath-ai-engineer-ka-ic` | `proj-ai-engineer-foundry` | Destino actual |
| `datapath-inofuente-resource` | `rg-kevin.inofuente-7619` | `datapath-inofuente` | Anterior |

El AI Search compartido (`srch-alphastate-datapath`, nivel Free, uno por suscripción) está en el RG del recurso anterior, no en el de KAIC.

El destino de un agente se define en **varias fuentes independientes**, y ninguna herramienta comprueba que coincidan:

1. `azure.yaml`: endpoint del proyecto y ruta de la política RAI.
2. El entorno azd por defecto (`.azure/<env>/.env`): `AZURE_AI_PROJECT_ID`, `FOUNDRY_PROJECT_ENDPOINT`, `AZURE_RESOURCE_GROUP`.
3. El `.env` local del agente.
4. Constantes en el código de los scripts auxiliares: `rag/crear_base_conocimiento.py`, `guardrails/crear_guardrail.sh` y `memoria/crear_memory_store.py`.

`azd deploy` despliega donde digan el entorno y `azure.yaml`, sin preguntar. Los scripts crean recursos donde digan sus constantes.

**Fallas observadas el 2026-11-06:**

- **Deploy en el recurso equivocado.** El agente se redesplegó (v5) en `datapath-inofuente` y se informó como hecho, cuando el usuario lo quería en KAIC. Hubo que crear un entorno azd nuevo y desplegar de nuevo.
- **Base de conocimiento conectada al proyecto equivocado.** `crear_base_conocimiento.py` conservaba las constantes del recurso anterior. La KB `girardota-kb` existía, pero la conexión `CognitiveSearch` quedó en `datapath-inofuente`. En KAIC, Compilación → Conocimiento mostraba "Conexión a un recurso de AI Search para empezar". La KB además planificaba con `gpt-5-mini` y la clave del recurso anterior.
- **Un resource group para todo.** El script usaba una sola constante `RESOURCE_GROUP` para Foundry, Storage y AI Search. En KAIC esos recursos están en RGs distintos.
- **Script de guardrail desalineado.** `crear_guardrail.sh` seguía apuntando al recurso anterior. Nadie lo notó hasta que se escribió el verificador.
- **El harness no lo prevenía.** Ninguna de las dos skills tenía un paso que confirmara el destino con el usuario. El "Paso 2" de la skill de deploy listaba los recursos, pero no obligaba a elegir uno ni a comparar. El agente de código (Claude Code) tomó como verdad un despliegue anterior y unas constantes viejas.

## 2. Decisión

**El destino (recurso + proyecto de Foundry) es una decisión explícita del usuario y se verifica de forma automática antes de cualquier operación que cree o cambie recursos.** Se aplica en tres capas:

### 2.1 Proceso (skills)

- **Paso 0 obligatorio** en `azure-foundry-hosted-agent-deploy` y en `azure-foundry-knowledge-base`:
  1. Preguntar al usuario el recurso y el proyecto, salvo que los haya indicado explícitamente en la conversación. Un despliegue anterior, una bitácora o las constantes de un script **no** son evidencia del destino actual.
  2. Ejecutar el verificador y corregir todo lo que marque antes de continuar.
- **Paso 10 (deploy):** el verificador se ejecuta otra vez justo antes de `azd deploy`. Después del deploy se comprueba con `azd ai agent show` que el agente quedó en `<recurso>.services.ai.azure.com/api/projects/<proyecto>`. Si no es así, no se informa "desplegado".
- El **resumen final** de un deploy incluye el recurso, el RG y el proyecto, comprobados y no supuestos.
- **Mover un agente de recurso** implica una lista explícita: modelos, memory store, guardrail, KB y su conexión, permisos RBAC de las identidades nuevas y el `.env` de la app de consumo.

### 2.2 Verificación automática (código)

- **`scripts/verificar_destino.sh <recurso> <proyecto>`** (skill de deploy). Compara `azure.yaml`, el entorno azd por defecto, los `.env` y las constantes `FOUNDRY_ACCOUNT` / `FOUNDRY_PROJECT` / `RESOURCE_GROUP` de los scripts. También lista los recursos de Foundry de la suscripción y los modelos desplegados en el destino. Sale con código 1 si algo no coincide.
- **`verificar_destino()` en `crear_base_conocimiento.py`** (plantilla y proyecto). Antes de crear nada:
  - aborta con `DESTINO DISTINTO` si sus constantes no coinciden con `azure.yaml`;
  - comprueba que el recurso, los despliegues de modelo y el AI Search existen;
  - imprime el destino y pide confirmación (`--yes` la omite cuando el usuario ya confirmó).

### 2.3 Configuración

- **Un resource group por recurso:** `FOUNDRY_RESOURCE_GROUP`, `SEARCH_RESOURCE_GROUP` y `STORAGE_RESOURCE_GROUP`. Nunca se asume que comparten RG.
- Los scripts del agente de Girardota apuntan a KAIC: el script de KB usa `gpt-5.4-mini`, porque `gpt-5-mini` no se pudo crear en KAIC (error de Azure `715-123420`).

### Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Confiar en la bitácora (`CLAUDE.md`) como fuente del destino | Se desactualiza. Fue justo lo que falló: había información correcta y aun así se usaron constantes viejas. |
| Eliminar las constantes y leerlo todo de `azure.yaml` | Es lo ideal a medio plazo (ver Pendientes). Pero los scripts también necesitan los RGs de AI Search y Storage, que `azure.yaml` no conoce. Se adopta primero la verificación, que no rompe nada. |
| Borrar el recurso anterior para que no haya ambigüedad | Otros agentes y despliegues del taller lo usan, y el AI Search compartido vive en su RG. |
| Solo un aviso en la documentación de la skill | Un aviso no detiene la ejecución. Se necesita un control que falle (código 1 / `sys.exit`). |

## 3. Consecuencias

### Qué se gana

- **Fallar antes de desplegar, no después.** Un destino inconsistente detiene el proceso con un mensaje que dice qué fuente difiere y hacia dónde apunta.
- **Detecta desalineaciones que nadie veía.** La primera ejecución encontró `crear_guardrail.sh` apuntando al recurso anterior.
- **El usuario es la fuente de verdad del destino**, y el agente de código tiene un procedimiento concreto en lugar de inferirlo.
- **La KB se puede repuntar sin reindexar.** Volver a correr el script (todo `PUT` idempotente) actualiza el modelo y crea la conexión en el proyecto correcto.
- Queda registrado (bitácora, memoria del agente de código y este ADR) para los siguientes despliegues.

### Qué se pierde / costo

- **Un poco más de fricción:** una pregunta al usuario y unos 20–40 s de llamadas a `az` por verificación.
- **El verificador busca patrones, no entiende el código:** busca endpoints `*.services.ai.azure.com` y constantes con nombres fijos (`FOUNDRY_ACCOUNT`, `FOUNDRY_PROJECT`, `RESOURCE_GROUP`). Un script que nombre sus variables de otra forma no se verifica.
- **Compara el nombre del recurso en minúsculas contra el subdominio del endpoint.** Funciona porque Foundry usa el nombre del recurso como subdominio, pero un dominio personalizado no se detectaría.
- **La confirmación interactiva** del script de KB obliga a usar `--yes` en ejecuciones automáticas, y alguien puede usarlo sin pensar.

### Qué queda pendiente

- [x] **Sincronizar las skills versionadas en el repo** → resuelto en [ADR 0002](0002-fuente-de-verdad-de-las-skills-del-harness.md). `.claude/skills/azure-foundry-hosted-agent-deploy` y `.claude/skills/azure-foundry-knowledge-base` son **copias** desactualizadas: no tienen el Paso 0, ni `verificar_destino.sh`, ni la plantilla nueva. Las correcciones solo están en `~/.claude/skills/`. Hay que decidir si el repo usa enlaces simbólicos (skill `skill-mirror`) o copias sincronizadas. Es candidato al ADR 0002: fuente de verdad de las skills del harness.
- [x] **Hacer cumplir la regla desde el harness, no solo describirla** → resuelto en [ADR 0003](0003-hook-que-bloquea-despliegues-con-destino-inconsistente.md): un hook `PreToolUse` en `.claude/settings.json` que ejecute `verificar_destino.sh` antes de cualquier `azd deploy` / `azd provision` y bloquee si falla.
- [ ] **Una sola fuente del destino:** que los scripts auxiliares lean el recurso y el proyecto de `azd env get-values` en lugar de constantes, y dejar en constantes solo lo que azd no conoce (AI Search, Storage).
- [ ] Aplicar el mismo Paso 0 a `azure-foundry-memory`, `azure-foundry-guardrails` y `azure-foundry-consume-agent`, que también crean o consumen recursos de un proyecto concreto.
- [ ] Completar la migración de Girardota a KAIC:
  - ejecutar `rag/crear_base_conocimiento.py` (conexión de la KB);
  - asignar los roles RBAC a las identidades del agente y del proyecto en KAIC;
  - repuntar el `.env` de `Consumo-de-Agentes/Agente-de-Municipalidad-Girardota`.
- [ ] Decidir el destino del agente inmobiliario (`agente-hosted-inmobiliaria`). Hoy apunta de forma coherente al recurso **anterior** en las tres fuentes que lo definen: `azure.yaml`, el `.env` y `rag/crear_base_conocimiento.py`. Si se mueve a KAIC, hacerlo con el Paso 0 y `verificar_destino.sh`.

## Referencias

- Bitácora del despliegue: `agente-hosted/CLAUDE.md`
- Skills: `~/.claude/skills/azure-foundry-hosted-agent-deploy/SKILL.md` (Paso 0, Paso 10, `scripts/verificar_destino.sh`) y `~/.claude/skills/azure-foundry-knowledge-base/SKILL.md` (Paso 0, `templates/crear_base_conocimiento.py`)
- Código del agente: `agente-hosted/agente-hosted-municipalidad-girardota/src/agent-framework-agent-municipalidad/rag/crear_base_conocimiento.py` y `guardrails/crear_guardrail.sh`
