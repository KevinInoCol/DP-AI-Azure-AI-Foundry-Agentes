# Prerequisitos para desplegar agentes hospedados en Microsoft Foundry con azd (Windows).
# Uso: powershell -ExecutionPolicy Bypass -File install-prereqs.ps1
$ErrorActionPreference = "Stop"
function Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Fail($m) { Write-Host "ERROR: $m" -ForegroundColor Red; exit 1 }
function Has($c) { [bool](Get-Command $c -ErrorAction SilentlyContinue) }

Step "Azure CLI"
if (-not (Has az)) { Fail "Instala Azure CLI: https://learn.microsoft.com/cli/azure/install-azure-cli" }
az account show -o none 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "Sin sesión. Abriendo 'az login'..."; az login -o none; if ($LASTEXITCODE -ne 0) { Fail "az login falló" } }
az account show --query "{suscripcion:name, tenant:tenantId, usuario:user.name}" -o tsv

Step "Azure Developer CLI (azd)"
if (-not (Has azd)) { winget install --id Microsoft.Azd -e --accept-source-agreements --accept-package-agreements; $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User") }
azd version

Step "azd reutiliza las credenciales de Azure CLI"
azd config set auth.useAzCliAuth true
azd auth login --check-status

Step "Extensión microsoft.foundry de azd"
$ext = azd extension list 2>$null
if (-not ($ext -match "microsoft.foundry")) { azd extension install microsoft.foundry }
azd extension list 2>$null | Select-String "microsoft.foundry|azure.ai.agents|azure.ai.projects"

Step "Python 3.13"
py -3.13 --version 2>$null
if ($LASTEXITCODE -ne 0) { winget install --id Python.Python.3.13 -e --accept-source-agreements --accept-package-agreements }
py -3.13 --version

Step "Proyectos de Foundry visibles en la suscripción"
az cognitiveservices account list --query "[?kind=='AIServices'].{recurso:name, rg:resourceGroup, region:location}" -o table

Write-Host "`nPrerequisitos listos. Continúa con el paso 2 de la skill (ARM ID del proyecto)." -ForegroundColor Green
