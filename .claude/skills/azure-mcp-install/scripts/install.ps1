# Instala el Azure MCP Server globalmente y lo registra en Claude Code (scope user).
# Uso: powershell -ExecutionPolicy Bypass -File install.ps1
$ErrorActionPreference = "Stop"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }
function Need($cmd, $hint) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Fail "$cmd no está instalado. $hint" } }

Step "Comprobando prerequisitos"
Need node   "Descárgalo en https://nodejs.org"
Need npm    ""
Need az     "https://learn.microsoft.com/cli/azure/install-azure-cli"
Need claude "Claude Code no está en el PATH."
Write-Host "node $(node -v) | npm $(npm -v) | $(claude --version)"

Step "Comprobando sesión de Azure"
az account show -o none 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "No hay sesión de Azure. Abriendo 'az login'..."
  az login -o none
  if ($LASTEXITCODE -ne 0) { Fail "No se pudo iniciar sesión en Azure." }
}
az account show --query "{suscripcion:name, usuario:user.name}" -o tsv

Step "Instalando @azure/mcp globalmente"
npm install -g @azure/mcp@latest
if ($LASTEXITCODE -ne 0) { Fail "npm install falló." }

$azmcp = Join-Path (npm prefix -g) "azmcp.cmd"
if (-not (Test-Path $azmcp)) { Fail "No se encontró el binario en $azmcp" }
Write-Host "Binario: $azmcp"

Step "Registrando el servidor en Claude Code (scope user)"
claude mcp remove azure -s user 2>$null
claude mcp add --scope user azure -- cmd /c azmcp server start
if ($LASTEXITCODE -ne 0) { Fail "claude mcp add falló." }

Step "Verificando"
claude mcp get azure

Write-Host "`nListo. Reinicia Claude Code para que carguen las tools mcp__azure__*." -ForegroundColor Green
