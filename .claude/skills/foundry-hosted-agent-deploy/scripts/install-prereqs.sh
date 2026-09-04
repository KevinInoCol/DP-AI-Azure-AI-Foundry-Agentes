#!/usr/bin/env bash
# Prerequisitos para desplegar agentes hospedados en Microsoft Foundry con azd.
# Uso: bash install-prereqs.sh
set -euo pipefail
step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }
OS="$(uname -s)"

step "Azure CLI"
command -v az >/dev/null || fail "Instala Azure CLI: https://learn.microsoft.com/cli/azure/install-azure-cli"
az account show -o none 2>/dev/null || { echo "Sin sesión. Abriendo 'az login'..."; az login -o none || fail "az login falló"; }
az account show --query "{suscripcion:name, tenant:tenantId, usuario:user.name}" -o tsv

step "Azure Developer CLI (azd)"
if ! command -v azd >/dev/null; then
  if [ "$OS" = "Darwin" ] && command -v brew >/dev/null; then brew install azd
  else curl -fsSL https://aka.ms/install-azd.sh | bash; fi
fi
azd version

step "azd reutiliza las credenciales de Azure CLI (evita azd auth login)"
azd config set auth.useAzCliAuth true
azd auth login --check-status

step "Extensión microsoft.foundry de azd"
azd extension list 2>/dev/null | grep -q "microsoft.foundry" || azd extension install microsoft.foundry
azd extension list 2>/dev/null | grep -E "microsoft.foundry|azure.ai.agents|azure.ai.projects" || true

step "Python 3.13"
if ! command -v python3.13 >/dev/null; then
  if [ "$OS" = "Darwin" ] && command -v brew >/dev/null; then brew install python@3.13
  else echo "Instala Python 3.13 con tu gestor de paquetes (apt, dnf, pyenv...)"; fi
fi
PY=$(command -v python3.13 || true); [ -n "$PY" ] && echo "python3.13: $PY ($($PY --version))" || echo "AVISO: python3.13 no disponible"
type python 2>/dev/null | grep -q alias && echo "AVISO: 'python' es un alias en tu shell; usa rutas explícitas al crear el venv."

step "Proyectos de Foundry visibles en la suscripción"
az cognitiveservices account list --query "[?kind=='AIServices'].{recurso:name, rg:resourceGroup, region:location}" -o table

printf '\n\033[1;32mPrerequisitos listos. Continúa con el paso 2 de la skill (ARM ID del proyecto).\033[0m\n'
