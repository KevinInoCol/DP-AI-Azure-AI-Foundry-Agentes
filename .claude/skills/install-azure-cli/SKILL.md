---
name: install-azure-cli
description: Instala la Azure CLI (az, la línea de comandos oficial de Microsoft Azure) detectando automáticamente el sistema operativo — macOS (Homebrew), Linux (Debian/Ubuntu, RHEL/Fedora, WSL) o Windows (winget / MSI) — y la deja verificada con az version, con sesión iniciada (az login) en el tenant y la suscripción correctos, comprobado con az account show. Úsala cuando el usuario pida instalar la CLI de Azure, cuando un comando falle con "az - command not found" / "az no se reconoce", o cuando mencione "instalar azure cli", "no tengo az", "azure-cli", "az login", "configurar mi suscripción de Azure", "elegir el tenant", o escriba /install-azure-cli. Es el prerequisito de install-azure-mcp y azure-foundry-hosted-agent-deploy.
---

Instala y configura la **Azure CLI (`az`)** en la máquina del usuario. Sigue estos pasos **en orden** y no los saltes.

> La Azure CLI se instala **una vez por computadora**, no por proyecto. No la instales con `pip install azure-cli` dentro de un venv: queda atada a ese entorno y se rompe al cambiar de proyecto.

## Paso 1 — ¿Ya está instalada?

```bash
az version
```

- **Si responde un JSON con `"azure-cli": "2.x.x"`**: ya está instalada. Muestra la versión y la ruta (`which az`, o `where az` en Windows). Si es vieja (menor a 2.60), actualízala con `az upgrade` y **salta al Paso 5** (login).
- **Si dice `command not found` / `no se reconoce como un comando`**: continúa al Paso 2.

## Paso 2 — Detectar el sistema operativo

```bash
uname -s; uname -m
```

| `uname -s` | Sistema | Método de instalación |
|---|---|---|
| `Darwin` | macOS (Intel o Apple Silicon) | Homebrew |
| `Linux` + `/etc/os-release` con `ID=ubuntu` / `debian` | Debian, Ubuntu, WSL Ubuntu | Script `InstallAzureCLIDeb` |
| `Linux` + `ID=rhel` / `fedora` / `centos` / `rocky` / `almalinux` | Familia Red Hat | Repositorio RPM de Microsoft + `dnf` |
| `MINGW*`, `MSYS*`, `CYGWIN*` | Windows (Git Bash) | winget o MSI |
| el comando falla | Windows (PowerShell/CMD nativo) | winget o MSI |

En Linux, identifica la distribución con:

```bash
cat /etc/os-release | grep -E '^(ID|VERSION_ID)='
```

## Paso 3 — Instalar

> Los instaladores piden **contraseña de administrador** (`sudo` o UAC). Claude no puede escribirla: pídele al usuario que ejecute el comando él mismo con el prefijo `!` en el prompt (ej. `! curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash`) o en su propia terminal.

### macOS

Microsoft distribuye la Azure CLI para macOS **solo por Homebrew**. Comprueba que esté con `which brew`.

```bash
brew update && brew install azure-cli
```

Si no tiene Homebrew, instálalo primero (pide contraseña):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

En Apple Silicon, al terminar Homebrew indica dos líneas para añadir `/opt/homebrew/bin` al PATH (`eval "$(/opt/homebrew/bin/brew shellenv)"`); que el usuario las ejecute antes de seguir.

Actualizar más adelante: `brew upgrade azure-cli` (con brew, `az upgrade` delega en brew).

### Linux — Debian / Ubuntu (incluye WSL)

Un solo comando que agrega el repositorio de Microsoft e instala el paquete:

```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

Si el usuario prefiere ver cada paso (o la empresa no permite `curl | bash`), la instalación manual es:

```bash
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
sudo mkdir -p /etc/apt/keyrings
curl -sLS https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor | sudo tee /etc/apt/keyrings/microsoft.gpg > /dev/null
sudo chmod go+r /etc/apt/keyrings/microsoft.gpg
AZ_DIST=$(lsb_release -cs)
echo "Types: deb
URIs: https://packages.microsoft.com/repos/azure-cli/
Suites: ${AZ_DIST}
Components: main
Architectures: $(dpkg --print-architecture)
Signed-by: /etc/apt/keyrings/microsoft.gpg" | sudo tee /etc/apt/sources.list.d/azure-cli.sources
sudo apt-get update
sudo apt-get install -y azure-cli
```

### Linux — RHEL / Fedora / Rocky / AlmaLinux

```bash
sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
# RHEL 9 / Rocky 9 / Alma 9 (para RHEL 8 cambia 9.0 por 8)
sudo dnf install -y https://packages.microsoft.com/config/rhel/9.0/packages-microsoft-prod.rpm
sudo dnf install -y azure-cli
```

### Linux — otras distribuciones o sin sudo

Script genérico que instala en el home del usuario (necesita Python 3 en el sistema):

```bash
curl -L https://aka.ms/InstallAzureCli | bash
exec -l $SHELL
```

Pregunta la carpeta de instalación y si modificar el PATH; acepta los valores por defecto.

> **WSL:** instala la versión de Linux **dentro** de WSL. No uses el `az.exe` de Windows desde WSL (`which az` no debe apuntar a `/mnt/c/...`): es lento y falla con rutas de Linux.

### Windows

**Opción A — winget (recomendado, PowerShell en Windows 10/11):**

```powershell
winget install --exact --id Microsoft.AzureCLI
```

**Opción B — MSI de 64 bits** (PowerShell **como administrador**):

```powershell
$ProgressPreference = 'SilentlyContinue'
Invoke-WebRequest -Uri https://aka.ms/installazurecliwindowsx64 -OutFile .\AzureCLI.msi
Start-Process msiexec.exe -Wait -ArgumentList '/I AzureCLI.msi /quiet'
Remove-Item .\AzureCLI.msi
```

También se puede descargar `https://aka.ms/installazurecliwindowsx64` desde el navegador y hacer doble clic en el `.msi`.

Se instala en `C:\Program Files\Microsoft SDKs\Azure\CLI2\`. Para actualizar: `az upgrade`, o repetir winget/MSI.

## Paso 4 — Verificar la instalación

```bash
az version
```

Debe responder un JSON con `"azure-cli": "2.x.x"`.

- **macOS / Linux:** si dice `command not found` justo después de instalar, ejecuta `hash -r` o abre una terminal nueva.
- **Windows:** **cierra y vuelve a abrir** la terminal (PowerShell, CMD, Git Bash o la de VS Code; en VS Code, reinicia el editor completo). El PATH nuevo no se aplica a las ventanas ya abiertas.

## Paso 5 — Iniciar sesión

> `az login` abre el navegador para autenticarse. Claude no puede completar ese flujo: pídele al usuario que lo ejecute con el prefijo `!` (ej. `! az login`). Nunca pidas contraseñas ni tokens en el chat.

```bash
az login
```

Desde la versión 2.61, al terminar muestra la lista de suscripciones y pide elegir una. Si el usuario no está seguro, que elija la que usará en el curso o el proyecto (se puede cambiar después).

Casos especiales:

| Situación | Comando |
|---|---|
| La cuenta pertenece a varios tenants (invitado en la empresa + cuenta personal) | `az login --tenant <tenant-id o dominio.onmicrosoft.com>` |
| Máquina sin navegador (SSH, contenedor, Codespaces) | `az login --use-device-code` |
| En Windows aparece la ventana de WAM y falla o elige otra cuenta | `az config set core.enable_broker_on_windows=false` y repetir `az login` |

## Paso 6 — Elegir y verificar la suscripción

```bash
az account show --query "{suscripcion:name, id:id, tenant:tenantId, usuario:user.name}" -o table
```

Confirma con el usuario que la **suscripción** y el **tenant** son los que espera (muy común: quedó activa la suscripción de la empresa en vez de la personal, o al revés).

Si no es la correcta:

```bash
az account list --query "[].{nombre:name, id:id, tenant:tenantId, activa:isDefault}" -o table
az account set --subscription "<nombre o id>"
```

Si una suscripción esperada no aparece en la lista, está en otro tenant: `az login --tenant <tenant-id>`.

## Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| `az: command not found` tras instalar | PATH no recargado | Terminal nueva / `hash -r` (Windows: cerrar y abrir) |
| Dos `az` distintos según la terminal | brew + pip, o el `az.exe` de Windows dentro de WSL | `which -a az` y desinstalar el sobrante (`pip uninstall azure-cli`) |
| `No subscriptions found` | La cuenta no tiene suscripción en ese tenant | `az login --tenant <id>` o crear una suscripción (Azure for Students / pago por uso) |
| `AADSTS50076` / `AADSTS50079` (MFA requerida) | El tenant exige MFA para ese recurso | `az login --tenant <tenant-id>` y completar el MFA |
| `AADSTS700082` / token expirado | Sesión vieja | `az logout` y `az login` |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Proxy corporativo que inspecciona TLS | Exportar `REQUESTS_CA_BUNDLE=<ruta al certificado de la empresa>` |
| `az upgrade` falla en macOS | Instalada con brew | `brew upgrade azure-cli` |
| Error de reloj / tokens "not yet valid" en WSL | Hora del sistema desfasada | `sudo hwclock -s` |

## Notas

- La sesión vive en `~/.azure/` (`%USERPROFILE%\.azure\` en Windows) y la comparten todos los proyectos. No leas ni imprimas `~/.azure/msal_token_cache.*`: contiene tokens.
- Otras herramientas reutilizan esta sesión: el **Azure MCP Server** (skill `install-azure-mcp`) y **azd** (skill `azure-foundry-hosted-agent-deploy`, con `azd config set auth.useAzCliAuth true`).
- Desinstalar: `brew uninstall azure-cli` (macOS), `sudo apt-get remove -y azure-cli` / `sudo dnf remove -y azure-cli` (Linux), `winget uninstall --id Microsoft.AzureCLI` (Windows).
- Documentación oficial: https://learn.microsoft.com/cli/azure/install-azure-cli
