---
name: install-azure-mcp
description: Instala el Azure MCP Server (@azure/mcp) de forma global con npm y lo registra en Claude Code con alcance de usuario (--scope user), para que las tools mcp__azure__* estén disponibles en cualquier proyecto y sesión sin timeouts de arranque. Incluye verificación de prerequisitos (Node, npm, Azure CLI, az login), scripts para macOS/Linux y Windows, y solución de problemas. Use when the user asks to "instalar el MCP de Azure", "configurar Azure MCP", "conectar Claude Code con Azure", "no aparecen las tools de Azure", "el MCP de Azure da timeout", "azmcp", or types /install-azure-mcp.
---

# Instalar el Azure MCP Server en Claude Code (global)

Objetivo: dejar el **Azure MCP Server** disponible en **todas** las sesiones y proyectos de Claude Code del usuario, arrancando rápido y autenticado con su cuenta de Azure.

## Por qué instalar global y no con `npx`

La forma "rápida" (`npx -y @azure/mcp@latest server start`) descarga el paquete en cada arranque frío. Eso suele superar los **30 segundos** que Claude Code espera para conectar un servidor MCP y el servidor aparece como *failed / timeout*. Instalando el paquete con `npm install -g` el binario `azmcp` queda en disco y arranca en ~2 segundos.

## Prerequisitos

| Requisito | Cómo comprobarlo | Si falta |
|---|---|---|
| Node.js 20+ y npm | `node -v` y `npm -v` | Instalar desde https://nodejs.org (LTS) |
| Azure CLI | `az --version` | https://learn.microsoft.com/cli/azure/install-azure-cli |
| Sesión de Azure | `az account show` | Ejecutar `az login` |
| Claude Code | `claude --version` | https://docs.anthropic.com/claude-code |

El servidor usa las credenciales de la máquina (Azure CLI, Azure Developer CLI o variables de entorno) vía Azure Identity. **Sin `az login` el servidor arranca pero todas las tools fallan con errores de autenticación.**

## Procedimiento (ejecútalo paso a paso)

### Paso 0: Comprobar prerequisitos

```bash
node -v && npm -v && az --version | head -1 && claude --version
az account show --query "{suscripcion:name, usuario:user.name}" -o tsv
```

Si `az account show` falla, pide al usuario que corra `az login` en su terminal (en Claude Code puede escribir `! az login`). No continúes hasta que haya sesión.

### Paso 1: Instalar el paquete globalmente

```bash
npm install -g @azure/mcp@latest
```

Es normal ver un aviso `npm warn allow-scripts ... post-install-script.js`. El servidor funciona igual; se puede ignorar.

### Paso 2: Localizar el binario

macOS / Linux:
```bash
AZMCP="$(npm prefix -g)/bin/azmcp"; ls -la "$AZMCP"
```

Windows (PowerShell):
```powershell
$AZMCP = Join-Path (npm prefix -g) "azmcp.cmd"; Get-Item $AZMCP
```

### Paso 3: Registrar el servidor en Claude Code con alcance de usuario

`--scope user` lo guarda en `~/.claude.json`, por lo que aplica a **todos los proyectos** del usuario.

macOS / Linux:
```bash
claude mcp remove azure -s user 2>/dev/null   # limpia un registro previo si existe
claude mcp add --scope user azure -- "$AZMCP" server start
```

Windows (PowerShell). Los `.cmd` de npm deben lanzarse a través de `cmd /c`:
```powershell
claude mcp remove azure -s user 2>$null
claude mcp add --scope user azure -- cmd /c azmcp server start
```

### Paso 4: Verificar

```bash
claude mcp get azure
```

Salida esperada: `Scope: User config (available in all your projects)` y `Status: ✔ Connected`.

Prueba de handshake MCP manual (opcional, macOS/Linux):
```bash
(printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}\n'; sleep 3) | "$AZMCP" server start | head -c 300
```
Debe devolver un JSON con `"serverInfo":{"name":"Azure MCP Server", ...}`.

### Paso 5: Reiniciar Claude Code

Las tools de un servidor nuevo se cargan al iniciar la sesión. Pide al usuario que cierre y vuelva a abrir `claude`. Después, las herramientas aparecen como `mcp__azure__*` y `/mcp` muestra `azure` conectado.

## Scripts automáticos

En `scripts/` de esta skill hay dos scripts que hacen los pasos 0 a 4:

- `scripts/install.sh` — macOS / Linux: `bash scripts/install.sh`
- `scripts/install.ps1` — Windows: `powershell -ExecutionPolicy Bypass -File scripts/install.ps1`

Si el usuario prefiere, ejecútalos en lugar de los pasos manuales y muéstrale la salida final.

## Solución de problemas

| Síntoma | Causa | Solución |
|---|---|---|
| `Status: ✗ Failed to connect` con timeout | Se registró con `npx` o el binario no está en la ruta indicada | Repetir pasos 1 a 3 usando la ruta absoluta del binario |
| Las tools devuelven errores de autenticación / tenant | No hay sesión de Azure | `az login` (o `az login --tenant <id>`) y reintentar |
| Aparecen tools duplicadas de Azure | Además de este servidor está activo el del plugin oficial `azure` (`plugin:azure:azure`, vía `npx`) | Desactivar el del plugin desde `/mcp`; las skills del plugin siguen funcionando |
| `command not found: azmcp` | El directorio global de npm no está en el PATH | Usar la ruta absoluta de `npm prefix -g` como en el paso 2 |
| Windows: el servidor no arranca | Se registró el `.cmd` sin `cmd /c` | Volver a registrar con `cmd /c azmcp server start` |
| Quiero actualizar el servidor | — | `npm install -g @azure/mcp@latest` (el registro en Claude Code no cambia) |

## Desinstalar

```bash
claude mcp remove azure -s user
npm uninstall -g @azure/mcp
```

## Referencias

- Documentación oficial: https://learn.microsoft.com/azure/developer/azure-mcp-server/overview
- Repositorio y paquete: https://github.com/microsoft/mcp — `@azure/mcp` en npm
- Skills de Azure para Claude Code (complementan al servidor): https://github.com/microsoft/azure-skills
