# ADR 0002 — Fuente de verdad de las skills del harness: autoría global, copias reales sincronizadas en el repo

- **Estado:** Aceptado
- **Fecha:** 2026-11-06
- **Ámbito:** harness de Claude Code del taller (`.claude/skills/` del repo y `~/.claude/skills/` del autor)
- **Origen:** pendiente del [ADR 0001](0001-verificar-destino-foundry-antes-de-desplegar.md)

## 1. Contexto

Las skills que guían la construcción y el despliegue de los agentes existen en **dos lugares**:

| Lugar | Quién lo usa | Cómo llegó ahí |
|---|---|---|
| `~/.claude/skills/<skill>/` (global) | El autor, en todos sus proyectos | Donde se escriben y corrigen las skills |
| `<repo>/.claude/skills/<skill>/` (proyecto) | El autor en este repo y **los alumnos que clonan el taller** | Copiadas a mano en algún momento |

Problemas observados el 2026-11-06:

- **Divergencia silenciosa.** Las correcciones del ADR 0001 (Paso 0, `verificar_destino.sh`, plantilla de KB con un RG por recurso) se hicieron solo en la carpeta global. Las copias del repo de `azure-foundry-hosted-agent-deploy` y `azure-foundry-knowledge-base` se quedaron en la versión anterior, la que causó el error. Un alumno, o el propio autor trabajando en el repo, habría seguido el procedimiento defectuoso.
- **Dos versiones con el mismo nombre.** Cuando la skill global y la del proyecto se llaman igual, no se puede garantizar cuál carga el agente de código. El comportamiento depende de qué copia lea.
- **Nada avisaba.** No había ningún mecanismo para detectar la diferencia. Se descubrió por casualidad al escribir el ADR 0001.
- **La convención existente no sirve aquí.** La skill `skill-mirror` propone **enlaces simbólicos** del proyecto hacia `~/.claude/skills/`. Eso evita la divergencia en la máquina del autor, pero este repo **se distribuye a los alumnos**: en sus máquinas los enlaces apuntarían a rutas que no existen y las skills desaparecerían. Git tampoco versionaría el contenido, solo la ruta.
- **Rutas absolutas dentro de las skills.** La skill de deploy citaba `~/.claude/skills/.../verificar_destino.sh`, una ruta que no existe para quien solo tiene el repo.

Estado al detectarlo: de 10 skills del repo, 7 iguales a la global, 2 desactualizadas y 1 (`ppt-a-html-datapath`) solo en el repo.

## 2. Decisión

**La autoría está en la carpeta global y la distribución en el repo, con copias reales y una sincronización explícita y verificable.**

1. **Fuente de autoría:** `~/.claude/skills/<skill>/`. Las skills se crean y corrigen ahí, porque las usa el autor en todos sus proyectos.
2. **El repo contiene copias reales, nunca enlaces simbólicos.** `.claude/skills/` es parte del material del taller y debe funcionar al clonar. `skill-mirror` sigue valiendo para proyectos personales que no se distribuyen; en repos de taller, no.
3. **El repo decide qué skills forman parte del taller.** La sincronización solo actualiza skills que ya existen en `.claude/skills/`; no copia toda la carpeta global. Las que solo existen en el repo (`ppt-a-html-datapath`) se conservan tal cual.
4. **Sincronización con `.claude/scripts/sync-skills.sh`:**
   - `--check`: lista las skills que difieren (archivo por archivo) y sale con código 1. Detecta también enlaces simbólicos.
   - Sin argumentos: copia de global a repo con `rsync --delete`, ignorando `__pycache__` y `.DS_Store`.
   - En una máquina sin carpeta global (un alumno), informa que el repo es la única fuente y no hace nada.
5. **Regla de trabajo:** toda corrección a una skill del taller se cierra con `bash .claude/scripts/sync-skills.sh`, se comprueba con `--check` y las copias se incluyen en el mismo commit que la corrección.
6. **Las skills no citan rutas absolutas de la máquina del autor.** Se refieren a `<carpeta-de-la-skill>/...` e indican las dos ubicaciones posibles (repo y global).

Aplicado hoy: sincronizadas `azure-foundry-hosted-agent-deploy` (con `scripts/verificar_destino.sh`) y `azure-foundry-knowledge-base` (Paso 0 y plantilla nueva). Antes se comprobó que las copias del repo eran idénticas a las versiones globales anteriores, así que no se perdió ningún cambio local. `--check` termina sin diferencias.

### Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| Enlaces simbólicos repo → global (`skill-mirror`) | Se rompen en las máquinas de los alumnos y git no versiona el contenido. |
| Enlaces simbólicos global → repo (el repo como fuente) | Las skills globales dependerían de la ruta de un clon de un taller concreto. Si se mueve o se borra el repo, el autor pierde las skills en todos sus proyectos. |
| Solo copias del repo, sin skills globales | El autor perdería las skills en el resto de sus proyectos (otros talleres, clientes). |
| Submódulo git con un repo de skills | Agrega una herramienta más a un taller cuyo público está aprendiendo Azure, no git. Se puede reconsiderar si las skills se comparten entre varios repos de taller. |
| Sincronización automática en cada sesión | Copiar sin revisar puede meter en el material del taller cambios globales a medio terminar. Se prefiere `--check` automático y sincronización manual (ver Pendientes). |

## 3. Consecuencias

### Qué se gana

- **La divergencia se detecta con un comando** (`--check`), con detalle de qué archivo difiere.
- **El repo es autosuficiente:** un alumno que clona tiene las skills completas, incluido el verificador, sin depender de la máquina del autor.
- **Una sola dirección de cambios** (global → repo): no hay que decidir cuál de las dos versiones es la buena.
- **El script protege la intención del repo:** solo actualiza las skills del taller y respeta las que solo existen en el repo.

### Qué se pierde / costo

- **La sincronización depende de que el autor la ejecute.** Sin un control automático, la divergencia puede volver (ver Pendientes).
- **`rsync --delete` pisa cualquier edición hecha directamente en el repo.** Un cambio a una skill hecho en `.claude/skills/` del repo se pierde en la siguiente sincronización. Regla: no editar skills en el repo; editarlas en la carpeta global y sincronizar.
- **Contenido duplicado en disco** en la máquina del autor (poco relevante: son archivos de texto).
- **Mientras no se sincronice, en este repo hay dos copias con el mismo nombre.** El riesgo de cargar la desactualizada no desaparece; solo se puede detectar.

### Qué queda pendiente

- [ ] **Detección automática:** un hook `SessionStart` (o un paso de CI) que ejecute `sync-skills.sh --check` y avise de la divergencia al abrir el repo.
- [x] **Hacer cumplir el ADR 0001 desde el harness** con un hook `PreToolUse` que bloquee `azd provision/deploy/up` y los scripts auxiliares si el destino es inconsistente → [ADR 0003](0003-hook-que-bloquea-despliegues-con-destino-inconsistente.md).
- [ ] Revisar las demás skills del taller en busca de rutas absolutas o constantes de la máquina del autor (suscripción, recursos, RGs) que se presenten como si fueran genéricas.
- [ ] Decidir si `ppt-a-html-datapath` debe tener fuente global o quedarse solo en el repo.
- [ ] Actualizar la tabla de skills del `README.md`: menciona `azure-mcp-install`, pero la carpeta es `install-azure-mcp`, y falta `install-azure-cli`.
- [ ] Documentar en la propia skill `skill-mirror` la excepción "repos que se distribuyen → copias, no enlaces".

## Referencias

- Script: `.claude/scripts/sync-skills.sh`
- Skills sincronizadas: `.claude/skills/azure-foundry-hosted-agent-deploy/`, `.claude/skills/azure-foundry-knowledge-base/`
- Convención anterior: `~/.claude/skills/skill-mirror/SKILL.md`
