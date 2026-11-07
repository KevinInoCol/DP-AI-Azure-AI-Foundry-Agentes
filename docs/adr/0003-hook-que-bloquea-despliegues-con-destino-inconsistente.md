# ADR 0003 — Hook PreToolUse que bloquea despliegues y scripts de Foundry con destino inconsistente

- **Estado:** Aceptado
- **Fecha:** 2026-11-06
- **Ámbito:** harness de Claude Code del repo (`.claude/settings.json`, `.claude/hooks/`)
- **Origen:** pendientes del [ADR 0001](0001-verificar-destino-foundry-antes-de-desplegar.md) y del [ADR 0002](0002-fuente-de-verdad-de-las-skills-del-harness.md)

## 1. Contexto

El ADR 0001 introdujo un Paso 0 en las skills y el verificador `verificar_destino.sh`. Pero esa protección **depende de que el agente de código siga el procedimiento**:

- Una skill es una instrucción, no un control. Si la skill no se activa (por ejemplo, un `azd deploy` pedido de pasada), si el agente la resume o la salta, o si el contexto se compacta, el verificador no se ejecuta.
- La falla original fue precisamente esa: el agente de código actuó con datos que creía correctos (un despliegue anterior, constantes viejas) y no verificó nada.
- Algunos scripts auxiliares (`crear_memory_store.py`, `crear_guardrail.sh`) **no tienen verificación propia**. Solo `crear_base_conocimiento.py` incorpora `verificar_destino()`.
- El usuario quiere que el harness evite el error **en los siguientes despliegues**, no que el agente "se acuerde".

Claude Code ofrece hooks `PreToolUse`: se ejecutan antes de cada llamada a una herramienta, y un código de salida 2 cancela la llamada y le devuelve el motivo al agente.

## 2. Decisión

**Registrar en `.claude/settings.json` (versionado) un hook `PreToolUse` para la herramienta Bash que ejecute el verificador y bloquee la operación si el destino es inconsistente.**

- **Script:** `.claude/hooks/verificar_destino_foundry.py`.
- **Qué intercepta:**
  - `azd up`, `azd provision` y `azd deploy`, también con variables antes (`AZURE_DEV_USER_AGENT=… azd deploy`) y con flags antes del subcomando;
  - `crear_base_conocimiento.py`, `crear_memory_store.py` y `crear_guardrail.sh`.
- **Qué no intercepta:** `azd ai agent invoke/show`, `azd env …` ni ningún otro comando. Un comando ajeno pasa en unos 50 ms sin llamar a Azure. El patrón exige que `up|provision|deploy` sea el subcomando de azd, así que `azd ai agent invoke "cómo hago deploy"` no lo activa.
- **Cómo decide la carpeta:** parte del `cwd` del comando, aplica el último `cd …` previo, `--cwd`/`-C` de azd o la ruta del script auxiliar, y sube hasta encontrar `azure.yaml`. Sin `azure.yaml` deja pasar el comando (no hay destino que verificar y azd fallará por su cuenta).
- **Qué ejecuta:** `.claude/skills/azure-foundry-hosted-agent-deploy/scripts/verificar_destino.sh`, la **copia del repo**, no la global. Así el hook funciona en la máquina de un alumno (ADR 0002). Si la copia no existe, bloquea y pide sincronizar las skills.
- **Resultado:**
  - si el destino es coherente, deja pasar y muestra `Destino coherente: recurso … / proyecto …`;
  - si es inconsistente, sale con código 2 y le devuelve al agente solo las líneas relevantes (❌, ⚠️, el destino de `azure.yaml`) más la instrucción de corregir y confirmar con el usuario;
  - si la verificación supera 150 s (sin red o sin sesión de `az`), bloquea.
- **Escape consciente:** `FOUNDRY_HOOK_DESACTIVADO=1` deja pasar todo, para trabajar sin red o en una emergencia. Debe usarse a propósito y no como costumbre.

Verificado antes de registrarlo:

| Caso | Resultado |
|---|---|
| `ls -la` | pasa, ~50 ms |
| `cd agente-hosted-municipalidad-girardota && azd deploy` | pasa: "Destino coherente … datapath-ai-engineer-kaic / proj-ai-engineer-foundry" |
| `python src/svc/crear_memory_store.py` en un proyecto cuyo `azure.yaml` apunta al recurso anterior y sin entorno azd | **bloqueado** (exit 2) con el detalle de lo que no coincide |
| `azd ai agent invoke "cómo hago deploy"`, `azd env get-values`, `git commit -m "deploy"` | no se interceptan |

### Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Quedarse solo con el Paso 0 de las skills | Es lo que falló: depende de que el agente lo siga. |
| Hook en `~/.claude/settings.json` (global) | Solo protegería la máquina del autor. Los alumnos que clonan el taller no lo tendrían. |
| Hook que además pregunte al usuario el destino | Un hook no puede conversar. Comprueba que las fuentes sean coherentes; la intención del usuario la sigue cubriendo el Paso 0 de la skill (pregunta + verificador con `<recurso> <proyecto>`). |
| Envolver `azd` en un alias o función de shell | No aplica a las llamadas que hace el agente desde la herramienta Bash, se puede saltar fácilmente y no queda versionado. |
| Verificar en `azure.yaml` con hooks propios de azd (`preprovision`/`predeploy`) | Es una buena capa adicional (ver Pendientes), pero no cubre los scripts auxiliares que se ejecutan fuera de azd. |

## 3. Consecuencias

### Qué se gana

- **La regla del ADR 0001 se cumple aunque el agente se la salte:** ningún `azd provision/deploy/up` ni script auxiliar se ejecuta con un destino inconsistente desde Claude Code.
- **Cubre los scripts sin verificación propia** (memoria, guardrail).
- **Viaja con el repo:** cualquiera que abra el taller en Claude Code tiene la misma protección.
- **Mensajes accionables:** el agente recibe qué fuente difiere y hacia dónde apunta, no un error genérico.

### Qué se pierde / costo

- **Unos 20–40 s más** por cada `azd provision/deploy/up` o script auxiliar (llamadas a `az`).
- **Comprueba coherencia, no intención.** Si las cuatro fuentes apuntan, coherentemente, al recurso equivocado, el hook deja pasar. Ese caso solo lo cubre el Paso 0 (preguntar al usuario y pasar `<recurso> <proyecto>` al verificador).
- **Solo protege lo que pasa por Claude Code.** Un `azd deploy` ejecutado a mano en una terminal no pasa por el hook.
- **Análisis del comando basado en patrones:** construcciones de shell inusuales (subshells, `eval`, scripts que llaman a azd por dentro) pueden escaparse. También puede bloquear un comando legítimo si no hay red o sesión de `az`.
- **Dependencia de `python3`** en la máquina (disponible en macOS y en el entorno del taller).
- Los hooks nuevos o modificados en `settings.json` pueden requerir revisarlos en `/hooks` o reiniciar la sesión de Claude Code para que se activen.

### Qué queda pendiente

- [ ] **Activar y verificar en vivo:** revisar el hook en `/hooks` (o reiniciar Claude Code) y comprobar que `azd deploy --help` dentro del proyecto de Girardota muestra el aviso "Destino coherente".
- [ ] **Hook `SessionStart`** que ejecute `bash .claude/scripts/sync-skills.sh --check` y avise de skills desalineadas (pendiente del ADR 0002).
- [ ] **Capa en azd:** hooks `preprovision`/`predeploy` en cada `azure.yaml` que llamen al verificador, para proteger también los despliegues hechos a mano fuera de Claude Code.
- [ ] Pasar la **intención** al verificador de forma automática: guardar el destino confirmado (por ejemplo `AZURE_AI_PROJECT_ID` del entorno azd elegido explícitamente, o un archivo `.foundry-destino`) para comparar contra él y no solo comprobar coherencia.
- [ ] Añadir verificación propia a `crear_memory_store.py` y `crear_guardrail.sh`, igual que `crear_base_conocimiento.py`, para quien los ejecute fuera de Claude Code.

## Referencias

- Hook: `.claude/hooks/verificar_destino_foundry.py`
- Registro: `.claude/settings.json` (`hooks.PreToolUse`, matcher `Bash`, timeout 180 s)
- Verificador: `.claude/skills/azure-foundry-hosted-agent-deploy/scripts/verificar_destino.sh`
- Hooks de Claude Code: https://docs.claude.com/en/docs/claude-code/hooks
