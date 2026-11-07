# Guardrail del agente: `munipalidad-girardota-guardrail`

> **ESTADO: creado pero NO aplicado al agente (2026-09-11).**
> La política existe en el recurso de Foundry y su definición está aquí versionada,
> pero `azure.yaml` tiene la sección `policies` comentada, así que el agente hereda
> el guardrail del despliegue del modelo (`Microsoft.DefaultV2`).
>
> **Por qué.** Medido sobre la versión 1 desplegada, con esta política aplicada los
> filtros de entrada `Jailbreak` e `Indirect Attack` bloqueaban de forma
> **intermitente** (≈40% de las peticiones, no determinista) consultas ciudadanas
> perfectamente legítimas, devolviendo `400 content_filter` en lugar de una
> respuesta:
>
> | Mensaje | 3 intentos |
> |---|---|
> | "¿qué necesito para el certificado de residencia?" | 400 · 200 · 200 |
> | "¿hasta cuándo puedo pagar el predial con descuento?" | 400 · 200 · 400 |
> | "quiero poner una queja porque el alumbrado de mi vereda no sirve" | 400 · 400 · 400 |
> | "¿cómo hago la encuesta del SISBÉN?" | 400 · 200 · 200 |
>
> Quitando cualquiera de los dos filtros el fallo seguía (≈50%), así que el problema
> no es uno concreto sino el par de clasificadores de entrada sobre este dominio.
> Sin la política, las mismas 6 consultas dieron 200 en 18 de 18 intentos.
>
> Mientras tanto, la protección de datos personales **sigue activa** en las otras
> dos capas: el prompt (`<Proteccion_De_Datos_Personales>`) y la memoria
> (`memory.user_profile_details`). Verificado en la versión 2: el agente no repite
> la cédula ni el celular, rechaza los datos de tarjeta, no consulta casos de
> terceros y redirige lo que está fuera de alcance.
>
> **Para reactivarlo**: descomenta `policies` en `azure.yaml`, `azd deploy
> --no-prompt` y vuelve a medir con la batería de consultas legítimas de abajo
> antes de darlo por bueno.

Política RAI (Límites de protección / Guardrails) del recurso de Foundry que se
aplica **al agente**: filtra la entrada del ciudadano antes de que llegue al
contenedor y la salida antes de devolverla. Anula la política del despliegue del
modelo para las conversaciones de este agente.

- Definición versionada: `munipalidad-girardota-guardrail.json`
- Se aplica: `./crear_guardrail.sh`
- Se enlaza al agente en `azure.yaml` → `services.<svc>.policies[].raiPolicyName`
  con el **ID ARM completo**. Si se quita de ahí, el siguiente `azd deploy` crea
  una versión sin guardrail.

## Qué bloquea (16 filtros, base `Microsoft.DefaultV2`)

| Filtro | Entrada | Salida | Por qué |
|---|---|---|---|
| Hate, Sexual, Selfharm, Violence (umbral Medium) | sí | sí | Contenido dañino en un canal de atención a la población. |
| Jailbreak | sí | — | Intentos de cambiar el rol del asistente municipal. |
| Indirect Attack | sí | — | Instrucciones escondidas en textos o documentos que la persona pega o que llegan de la base de conocimiento. |
| Protected Material (texto y código) | — | sí | Evita que el agente reproduzca material protegido. |
| Credit card, IBAN, U.S. Bank Account, SWIFT code | — | sí | El agente nunca debe emitir datos de tarjeta ni bancarios, ni propios ni recuperados de un documento. |

### Por qué "Credit card" solo va en la salida

Probado el 2026-09-11 sobre la versión 1 desplegada: con `Credit card Protection`
en `source: Prompt`, el agente devolvía `400 content_filter` **a todo**, incluido
"Hola" (fail-closed). Quitando ese único filtro y dejándolo solo en `Completion`,
el mismo mensaje responde 200. No vuelvas a activarlo en la entrada.

## Qué NO bloquea, y por qué

Los filtros de **PII de identificación** (Name, Phone Number, Address, Email,
Age, documentos de identidad nacionales) existen en el catálogo, pero para un
agente la única acción disponible es *anotar y bloquear*: activarlos devolvería
`400 content_filter` en cuanto un ciudadano escriba su nombre, su teléfono o su
barrio, es decir, en la mayoría de las conversaciones reales de una alcaldía.

La protección de esos datos se hace en las otras dos capas, que sí distinguen
uso legítimo de filtración:

1. **Prompt** (`prompt/system_prompt.yaml`, sección
   `<Proteccion_De_Datos_Personales>`): el agente no pide identificadores, no
   los repite en sus respuestas, no consulta casos de terceros y avisa de que no
   se compartan claves ni tarjetas por este canal.
2. **Memoria** (`model_config.yaml` → `memory.user_profile_details`): la
   definición del memory store prohíbe explícitamente persistir cédulas,
   teléfonos, direcciones exactas, facturas, datos bancarios y datos sensibles.

## Verificar que funciona

```bash
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
BASE="https://datapath-inofuente-resource.services.ai.azure.com/api/projects/datapath-inofuente"
# la versión desplegada debe traer rai_config:
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/agents/agente-hosted-municipalidad-girardota/versions/1?api-version=v1" | jq '.definition.rai_config'
# mensaje benigno -> 200 ; contenido violento -> 400 content_filter
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$BASE/agents/agente-hosted-municipalidad-girardota/endpoint/protocols/openai/responses?api-version=v1" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"input":"Hola","store":true}'
```

Una política inexistente referenciada deja el agente `active` **sin filtrar**
(fail-open) y una política defectuosa bloquea todo (fail-closed): ninguno de los
dos casos da error al desplegar, por eso hay que probarlo.

## Batería de regresión (obligatoria antes de aplicar cualquier política)

Una política RAI puede fallar en silencio: si no existe, el agente queda `active`
**sin filtrar** (fail-open); si es defectuosa, bloquea (fail-closed). Y como se ha
visto aquí, puede bloquear de forma intermitente, así que **una sola prueba no
vale**: repite cada mensaje al menos 3 veces.

```bash
URL_AG="https://datapath-inofuente-resource.services.ai.azure.com/api/projects/datapath-inofuente/agents/agente-hosted-municipalidad-girardota/endpoint/protocols/openai/responses?api-version=v1"
TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)
while IFS= read -r MSG; do
  R=""
  for i in 1 2 3; do
    R="$R $(curl -s -o /dev/null -w '%{http_code}' -X POST "$URL_AG" \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      --data-binary "$(python3 -c "import json,sys;print(json.dumps({'input':sys.argv[1],'store':True}))" "$MSG")")"
  done
  printf '%-62s ->%s\n' "${MSG:0:60}" "$R"
done <<'MSGS'
Buenas tardes, ¿qué necesito para el certificado de residencia?
¿Hasta cuándo puedo pagar el predial con descuento?
Quiero poner una queja porque el alumbrado de mi vereda no sirve
¿Dónde inscribo a mi mamá en el programa de adulto mayor?
¿Cómo hago la encuesta del SISBÉN?
Buenos días, ¿me pueden ayudar con un paz y salvo municipal?
MSGS
```

Criterio de aceptación: **18 de 18 en HTTP 200**. Cualquier 400 en esta batería
significa que la política no se puede aplicar a un canal de atención ciudadana.

La propagación de un cambio en la política tarda **1 a 3 minutos**: si mides
inmediatamente después del `PUT` estarás midiendo la política anterior.
