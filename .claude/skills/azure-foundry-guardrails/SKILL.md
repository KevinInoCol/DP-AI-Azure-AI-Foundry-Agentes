---
name: azure-foundry-guardrails
description: Aplica Límites de protección (Guardrails, políticas RAI) a un agente hospedado de Microsoft Foundry: diferencia entre el guardrail del modelo y el del agente, cómo se declara en azure.yaml (policies → rai_policy) para que persista en cada azd deploy, cómo se verifica (rai_config en la versión, prueba de bloqueo HTTP 400 content_filter) y el problema real de una política creada desde el asistente del portal que bloqueaba todo (fail-closed), resuelto creando la política por REST. Use when the user asks about "guardrails", "límites de protección", "content safety en el agente", "política RAI", "el agente bloquea todo", "cómo pongo filtros de contenido al agente hospedado", or types /azure-foundry-guardrails.
---

# Guardrails (Límites de protección) en un agente hospedado

Probado el 2026-09-11 en `agente-hosted-inmobiliaria` (versiones 7 a 9). Preview: verificar siempre con una prueba real, no con el estado "active".

## Modelo vs agente en 30 segundos

| Dónde se aplica | Qué revisa | Cómo se asigna |
|---|---|---|
| **Despliegue del modelo** | Lo que entra y sale del modelo, venga de donde venga. Por defecto `Microsoft.DefaultV2`. | `raiPolicyName` del deployment (portal o ARM). |
| **Agente** | La entrada del usuario antes de ejecutar el contenedor y la salida final; en preview también llamadas y respuestas de tools; egress de red solo en hosted. **Anula** al del modelo para esa conversación. | `rai_config.rai_policy_name` en la versión del agente = **ID ARM completo** de la política. |

Si el agente no tiene `rai_config`, hereda el guardrail del modelo. El portal muestra la asignación en la columna "Aplicado a".

## Paso 1: crear la política por REST (no por el asistente del portal)

Copia `templates/rai_policy_basica.json` (odio, sexual, autolesión y violencia en umbral Medium bloqueando entrada y salida; ataques al prompt e indirectos; material protegido) y créala:

```bash
ACC="https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<recurso>"
az rest --method put --url "$ACC/raiPolicies/<nombre>?api-version=2025-06-01" --headers "Content-Type=application/json" --body @rai_policy_basica.json
```

**Problema real:** la política creada con el asistente del portal (198 controles: los básicos + ~190 de PII y secretos en bloqueo en los 4 puntos de intervención + una blocklist vacía) hizo que el agente devolviera `400 content_filter` a **todo**, incluido "Hola", y siguió bloqueando aunque se recortara a los 8 filtros básicos. La misma política mínima creada por REST funcionó a la primera. Además, el paso "Seleccionar agentes" del asistente no creó la versión nueva del agente hospedado ("Aplicado a" quedó vacío).

Para agentes, la acción **Anotar** no existe (solo "Anotar y bloquear"): los controles de PII (nombre, teléfono, dirección, email) bloquearían el flujo normal de una inmobiliaria. No los añadas al agente; si hacen falta, van en el modelo.

## Paso 2: declararla en azure.yaml y desplegar

```yaml
services:
  <servicio>:
    host: azure.ai.agent
    kind: hosted
    policies:
      - type: rai_policy
        raiPolicyName: /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<recurso>/raiPolicies/<nombre>
```

`azd deploy --no-prompt` crea una versión nueva con `rai_config`; el endpoint enruta a `@latest`. Declararlo en el YAML evita que el siguiente despliegue pierda el guardrail.

## Paso 3: verificar de verdad

```bash
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
BASE="https://<recurso>.services.ai.azure.com/api/projects/<proyecto>"
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/agents/<agente>/versions/<N>?api-version=v1" | jq '.definition.rai_config'
# benigno → 200; violento → 400 {"code":"content_filter", ... "at input stage"}
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$BASE/agents/<agente>/endpoint/protocols/openai/responses?api-version=v1" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"input":"Hola","store":true}'
```

Si una política inexistente se referencia, el agente queda `active` **sin filtrar** (fail-open). Si la política es defectuosa, bloquea todo (fail-closed). Ninguno de los dos casos da error al desplegar.

## Diagnóstico rápido cuando "bloquea todo"

1. Despliega apuntando a `.../raiPolicies/Microsoft.DefaultV2`: si "Hola" pasa, el problema es tu política, no el runtime.
2. Recrea la política por REST con la plantilla; añade controles de a uno.
3. Guarda un backup del JSON (`az rest --method get`) antes de tocar una política del portal.

## Referencias

- https://learn.microsoft.com/azure/foundry/agents/how-to/add-hosted-agent-guardrails
- https://learn.microsoft.com/azure/foundry/guardrails/guardrails-overview
- https://learn.microsoft.com/azure/foundry/guardrails/how-to-create-guardrails
