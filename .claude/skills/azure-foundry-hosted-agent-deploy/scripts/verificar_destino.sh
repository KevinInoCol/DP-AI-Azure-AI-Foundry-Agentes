#!/usr/bin/env bash
# Verifica que TODAS las fuentes que definen el destino de un agente hospedado de
# Foundry apuntan al mismo recurso + proyecto antes de `azd provision` / `azd deploy`
# o de ejecutar scripts auxiliares (memoria, guardrail, base de conocimiento).
#
# Motivo: con dos o más recursos de Foundry en la suscripción, azure.yaml, el entorno
# azd por defecto, el .env local y las constantes de los scripts pueden quedar
# apuntando a recursos distintos; el deploy "sale bien" pero en el recurso equivocado.
#
# Uso (desde la raíz del proyecto azd, donde está azure.yaml):
#   bash <carpeta-de-la-skill>/scripts/verificar_destino.sh [recurso esperado] [proyecto esperado]
#   (repo del taller: .claude/skills/azure-foundry-hosted-agent-deploy · global: ~/.claude/skills/azure-foundry-hosted-agent-deploy)
# Sale con código 1 si algo no coincide. No imprime secretos.

set -uo pipefail

ESPERADO_RECURSO="${1:-}"
ESPERADO_PROYECTO="${2:-}"
ERRORES=0
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
mal() { echo "  ❌ $*"; ERRORES=$((ERRORES + 1)); }
bien() { echo "  ✅ $*"; }

[ -f azure.yaml ] || { echo "Ejecuta el script desde la carpeta que contiene azure.yaml."; exit 1; }

RE='https://([A-Za-z0-9-]+)\.services\.ai\.azure\.com/api/projects/([A-Za-z0-9_-]+)'
extraer() { grep -oE "$RE" | head -1 | sed -E "s#$RE#\1 \2#"; }

echo "== 1. Sesión de Azure =="
az account show --query "{suscripcion:name, id:id, tenant:tenantId, usuario:user.name}" -o table || { echo "Sin sesión de az."; exit 1; }
SUB=$(az account show --query id -o tsv)

echo; echo "== 2. Recursos de Foundry (AIServices) en la suscripción =="
az cognitiveservices account list --query "[?kind=='AIServices'].{recurso:name, rg:resourceGroup, region:location}" -o table
N_RECURSOS=$(az cognitiveservices account list --query "length([?kind=='AIServices'])" -o tsv)
[ "${N_RECURSOS:-0}" -gt 1 ] && echo "  ⚠️  Hay $N_RECURSOS recursos de Foundry: confirma con el usuario cuál es el destino."

echo; echo "== 3. Destino según azure.yaml =="
read -r Y_REC Y_PROY <<<"$(extraer < azure.yaml)"
if [ -z "${Y_REC:-}" ]; then
  mal "azure.yaml no tiene services.<proyecto>.endpoint (https://<recurso>.services.ai.azure.com/api/projects/<proyecto>)"
else
  echo "  azure.yaml → recurso '$Y_REC' / proyecto '$Y_PROY'"
fi
REF_REC=$(lower "${ESPERADO_RECURSO:-${Y_REC:-}}"); REF_PROY="${ESPERADO_PROYECTO:-${Y_PROY:-}}"
if [ -n "$ESPERADO_RECURSO" ]; then
  [ "$(lower "${Y_REC:-}")" = "$REF_REC" ] && [ "${Y_PROY:-}" = "$REF_PROY" ] \
    && bien "azure.yaml coincide con lo indicado por el usuario" \
    || mal "azure.yaml apunta a '${Y_REC:-?}/${Y_PROY:-?}' y el usuario indicó '$ESPERADO_RECURSO/$ESPERADO_PROYECTO'"
fi

comparar() {  # $1 = etiqueta, $2 = texto con un endpoint
  read -r R P <<<"$(printf '%s' "$2" | extraer)"
  if [ -z "${R:-}" ]; then echo "  ·  $1: sin endpoint de proyecto"; return; fi
  if [ "$(lower "$R")" = "$REF_REC" ] && [ "$P" = "$REF_PROY" ]; then bien "$1 → $R / $P"
  else mal "$1 → $R / $P (esperado $REF_REC / $REF_PROY)"; fi
}

echo; echo "== 4. Entorno azd por defecto =="
azd env list 2>/dev/null | grep -v "Update available\|To update"
VALORES=$(azd env get-values 2>/dev/null)
comparar "FOUNDRY_PROJECT_ENDPOINT" "$(printf '%s\n' "$VALORES" | grep '^FOUNDRY_PROJECT_ENDPOINT=')"
comparar "AZURE_AI_PROJECT_ENDPOINT" "$(printf '%s\n' "$VALORES" | grep '^AZURE_AI_PROJECT_ENDPOINT=')"
PID=$(printf '%s\n' "$VALORES" | sed -n 's/^AZURE_AI_PROJECT_ID="\{0,1\}\([^"]*\)"\{0,1\}$/\1/p')
if [ -n "$PID" ]; then
  PID_REC=$(printf '%s' "$PID" | sed -nE 's#.*/accounts/([^/]+)/projects/([^/]+)$#\1#p')
  PID_PROY=$(printf '%s' "$PID" | sed -nE 's#.*/accounts/([^/]+)/projects/([^/]+)$#\2#p')
  PID_RG=$(printf '%s' "$PID" | sed -nE 's#.*/resourceGroups/([^/]+)/.*#\1#p')
  [ "$(lower "$PID_REC")" = "$REF_REC" ] && [ "$PID_PROY" = "$REF_PROY" ] \
    && bien "AZURE_AI_PROJECT_ID → $PID_REC / $PID_PROY (RG $PID_RG)" \
    || mal "AZURE_AI_PROJECT_ID → $PID_REC / $PID_PROY (esperado $REF_REC / $REF_PROY)"
  ENV_RG=$(printf '%s\n' "$VALORES" | sed -n 's/^AZURE_RESOURCE_GROUP="\{0,1\}\([^"]*\)"\{0,1\}$/\1/p')
  [ -n "$ENV_RG" ] && { [ "$(lower "$ENV_RG")" = "$(lower "$PID_RG")" ] && bien "AZURE_RESOURCE_GROUP = $ENV_RG" || mal "AZURE_RESOURCE_GROUP = $ENV_RG pero el proyecto está en $PID_RG"; }
else
  mal "El entorno azd no tiene AZURE_AI_PROJECT_ID (¿entorno equivocado? azd env select <nombre>)"
fi

echo; echo "== 5. .env locales y scripts auxiliares (memoria, guardrail, RAG) =="
while IFS= read -r f; do
  while IFS= read -r linea; do comparar "${f#./}" "$linea"; done < <(grep -hoE "$RE" "$f" | sort -u)
  # Scripts con constantes FOUNDRY_ACCOUNT / FOUNDRY_PROJECT (p. ej. rag/crear_base_conocimiento.py)
  FA=$(sed -nE 's/^FOUNDRY_ACCOUNT *= *"([^"]+)".*/\1/p' "$f" | head -1)
  FP=$(sed -nE 's/^FOUNDRY_PROJECT *= *"([^"]+)".*/\1/p' "$f" | head -1)
  # Cada script debe usar el RG real de su recurso de Foundry (puede diferir del AI Search).
  FRG=$(sed -nE 's/^(FOUNDRY_)?RESOURCE_GROUP *= *"([^"]+)".*/\2/p' "$f" | head -1)
  if [ -n "$FA" ] && [ -n "$FRG" ] && [ -n "${PID_RG:-}" ] && [ "$(lower "$FA")" = "$REF_REC" ] && [ "$(lower "$FRG")" != "$(lower "$PID_RG")" ]; then
    mal "${f#./} usa RG '$FRG' para $FA, pero el recurso está en '$PID_RG'"
  fi
  if [ -n "$FA" ]; then
    # Scripts a nivel de recurso (guardrail) no definen proyecto: se compara solo el recurso.
    if [ "$(lower "$FA")" = "$REF_REC" ] && { [ -z "$FP" ] || [ "$FP" = "$REF_PROY" ]; }; then
      bien "${f#./} (constantes) → $FA${FP:+ / $FP}"
    else
      mal "${f#./} (constantes) → $FA${FP:+ / $FP} (esperado $REF_REC${FP:+ / $REF_PROY})"
    fi
  fi
done < <(find . \( -name .venv -o -name node_modules -o -name .git -o -name .azure \) -prune -o \
          -type f \( -name ".env" -o -name "*.py" -o -name "*.sh" -o -name "*.yaml" -o -name "*.yml" -o -name "*.json" \) \
          ! -name azure.yaml -print 2>/dev/null | xargs grep -lE "$RE|^FOUNDRY_ACCOUNT *=" 2>/dev/null)

echo; echo "== 6. El proyecto y sus despliegues existen =="
if [ -n "${PID:-}" ]; then
  if az rest --method get --url "https://management.azure.com$PID?api-version=2025-06-01" --query name -o tsv >/dev/null 2>&1; then
    bien "Proyecto existe en Azure"
    echo "  Despliegues de modelo en $PID_REC:"
    az cognitiveservices account deployment list -n "$PID_REC" -g "$PID_RG" --query "[].{nombre:name, modelo:properties.model.name, sku:sku.name}" -o table | sed 's/^/    /'
  else
    mal "No existe o no tienes acceso a $PID"
  fi
fi

echo
if [ "$ERRORES" -gt 0 ]; then
  echo "DESTINO INCONSISTENTE ($ERRORES problema(s)). No ejecutes azd provision/deploy ni scripts auxiliares hasta corregirlo."
  exit 1
fi
echo "Destino coherente: recurso '$REF_REC' / proyecto '$REF_PROY'. Confírmalo con el usuario antes de desplegar."
