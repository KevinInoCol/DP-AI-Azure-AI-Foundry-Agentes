# Agentes hospedados (Foundry) — estado y bitácora

Skill para desplegar: `azure-foundry-hosted-agent-deploy`. Plan desde cero: `PLAN-B-DESPLIEGUE.md`.

## Recursos de Azure (Suscripción de Azure 1)

- Suscripción: `57ff11aa-f7e9-4f80-a643-565666f00aed` · Tenant: `6d444148-296b-4727-8e8d-b45cb3d0da14`
- Usuario: `kevin.inofuente@hotmail.com` (Owner + Foundry User a nivel de suscripción). azd reutiliza la sesión de az (`auth.useAzCliAuth true`).

| Recurso Foundry | RG | Región | Proyecto | Despliegues |
|---|---|---|---|---|
| **Datapath-AI-Engineer-KAIC** (DESTINO ACTUAL) | `Datapath-ai-engineer-ka-ic` | eastus | `proj-ai-engineer-foundry` | gpt-5, gpt-6.1-sol, text-embedding-3-small, **gpt-5.4-mini** (DataZoneStandard 50) |
| datapath-inofuente-resource (anterior) | `rg-kevin.inofuente-7619` | eastus2 | `datapath-inofuente` | gpt-5-mini, gpt-5.4-mini, text-embedding-3-small |

- Endpoint del proyecto KAIC: `https://datapath-ai-engineer-kaic.services.ai.azure.com/api/projects/proj-ai-engineer-foundry`
- Identidad del proyecto KAIC (principalId): `6fa0b5d6-accb-4f5d-a425-a53309fbed60`
- AI Search compartido (base de conocimiento): `srch-alphastate-datapath` en `rg-kevin.inofuente-7619` (brazilsouth, Free). Ahí vive `girardota-kb`; es independiente del recurso Foundry, se reutiliza desde KAIC.

## Agente Municipalidad Girardota — despliegue en KAIC (2026-11-06)

Carpeta: `agente-hosted-municipalidad-girardota/` · servicio azd: `agent-framework-agent-municipalidad`

Hecho:
1. Primero se redesplegó (sin cambios, v5) en `datapath-inofuente`; luego el usuario pidió moverlo a **Datapath-AI-Engineer-KAIC**.
2. `azure.yaml`: endpoint → proyecto KAIC; ruta del guardrail (comentado/desactivado) → KAIC.
3. Nuevo entorno azd **`girardota-kaic`** (ahora el default). El viejo `agente-hosted-municipalidad-girardota-dev` sigue apuntando a datapath-inofuente.
   Cambiar entre ellos: `azd env select <nombre>` (ojo: `azure.yaml` ahora tiene el endpoint de KAIC).
4. `azd provision` creó `gpt-5.4-mini` en KAIC.
5. `gpt-5-mini` NO se pudo crear (GlobalStandard y DataZoneStandard): error Azure **`715-123420` "unusual activity for your account"** → requiere ticket de soporte. Se quitó de `azure.yaml`.
6. Memory store `municipalidad_girardota_memory` creado en KAIC con **chat_model = gpt-5** (no gpt-5-mini):
   `MEMORY_CHAT_MODEL=gpt-5 FOUNDRY_PROJECT_ENDPOINT=<KAIC> .venv/bin/python memoria/crear_memory_store.py`
   (se añadió la variable `MEMORY_CHAT_MODEL` al script).
7. Venv Python 3.13 creado en `src/agent-framework-agent-municipalidad/.venv`; `.env` local apunta a KAIC.
8. `azd deploy` → agente **`agente-hosted-municipalidad-girardota` v1, active** en KAIC.
   - Identidad del agente (principalId): `99051aba-d814-4d93-9687-40b8f51778a6`
   - Responses: `https://datapath-ai-engineer-kaic.services.ai.azure.com/api/projects/proj-ai-engineer-foundry/agents/agente-hosted-municipalidad-girardota/endpoint/protocols/openai/responses?api-version=v1`

### PENDIENTE

- [x] **Roles RBAC** (2026-11-06, ejecutado por el usuario: el modo auto bloquea `az role assignment create`): Foundry User + Cognitive Services OpenAI User en KAIC y Search Index Data Reader en `srch-alphastate-datapath` para el agente (`99051aba…`) y el proyecto KAIC (`6fa0b5d6…`). Verificado: `azd ai agent invoke … "¿Cómo pago el impuesto predial en Girardota?"` responde con Bancolombia, Banco Agrario, Banco de Bogotá, CFA y Cotrafa.
- [x] **Base de conocimiento en KAIC** (2026-11-06): `girardota-kb` ahora usa la fuente nueva `girardota-tramites-kaic-ks` (147 fragmentos, embeddings de KAIC; el embedding de una fuente es inmutable, por eso no se pudo actualizar la anterior), modelo `gpt-5.4-mini` de KAIC y conexión `CognitiveSearch` `srch-alphastate-datapath` en `proj-ai-engineer-foundry`.
- [x] (Limpieza, 2026-11-06) Borrada la fuente huérfana `girardota-tramites-ks` y sus objetos generados; el AI Search Free vuelve a 2/3 índices.
- `guardrails/crear_guardrail.sh` repuntado a KAIC (2026-11-06; la política aún no existe en KAIC y sigue desactivada).
- Antes de cualquier deploy o script auxiliar: `bash ~/.claude/skills/azure-foundry-hosted-agent-deploy/scripts/verificar_destino.sh Datapath-AI-Engineer-KAIC proj-ai-engineer-foundry`.
- [x] App `Consumo-de-Agentes/Agente-de-Municipalidad-Girardota`: `Backend/.env` → `FOUNDRY_PROJECT_ENDPOINT` de KAIC (2026-11-06). Verificado con `call_ai_azure_agent.py` (conversations + responses 200, agente v1). El backend no tiene `.venv` propio: crearlo con `requirements.txt` antes de `uvicorn main:app --port 8001`.
- [ ] Commit de los cambios (`azure.yaml`, `memoria/crear_memory_store.py`, este archivo).
- [ ] (Opcional) Actualizar azd a ≥1.37 para extensiones 1.0.0 estables: `brew trust azure/azd && brew uninstall azd && brew install --cask azure/azd/azd`. Con azd 1.33 funcionan las betas (`azure.ai.agents` 1.0.0-beta.17) aunque `azd extension list` diga "Incompatible".

## Avisos

- No usar `azd down` en ningún entorno: borraría despliegues de modelo compartidos con otros agentes del taller.
- Guardrail propio desactivado desde 2026-09-11 (bloqueaba ~40% de consultas legítimas); ver comentario en `azure.yaml`.
