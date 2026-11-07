#!/usr/bin/env bash
# Instala el Azure MCP Server globalmente y lo registra en Claude Code (scope user).
# Uso: bash install.sh
set -euo pipefail

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

step "Comprobando prerequisitos"
command -v node >/dev/null || fail "Node.js no está instalado. Descárgalo en https://nodejs.org"
command -v npm  >/dev/null || fail "npm no está instalado."
command -v az   >/dev/null || fail "Azure CLI no está instalado. https://learn.microsoft.com/cli/azure/install-azure-cli"
command -v claude >/dev/null || fail "Claude Code (claude) no está en el PATH."
echo "node $(node -v) | npm $(npm -v) | $(az version --query '"azure-cli"' -o tsv 2>/dev/null | sed 's/^/az /') | $(claude --version)"

step "Comprobando sesión de Azure"
if ! az account show -o none 2>/dev/null; then
  echo "No hay sesión de Azure. Abriendo 'az login'..."
  az login -o none || fail "No se pudo iniciar sesión en Azure."
fi
az account show --query "{suscripcion:name, usuario:user.name}" -o tsv

step "Instalando @azure/mcp globalmente"
npm install -g @azure/mcp@latest

AZMCP="$(npm prefix -g)/bin/azmcp"
[ -x "$AZMCP" ] || fail "No se encontró el binario en $AZMCP"
echo "Binario: $AZMCP"

step "Registrando el servidor en Claude Code (scope user)"
claude mcp remove azure -s user >/dev/null 2>&1 || true
claude mcp add --scope user azure -- "$AZMCP" server start

step "Verificando"
claude mcp get azure

printf '\n\033[1;32mListo. Reinicia Claude Code para que carguen las tools mcp__azure__*.\033[0m\n'
