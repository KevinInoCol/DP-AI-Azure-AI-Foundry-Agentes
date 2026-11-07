#!/usr/bin/env python3
"""
Hook PreToolUse (Bash) que hace cumplir el ADR 0001: bloquea operaciones que crean
o cambian recursos de Microsoft Foundry si el destino (recurso + proyecto) es
inconsistente entre azure.yaml, el entorno azd, los .env y los scripts auxiliares.

Intercepta:
  - azd up | provision | deploy
  - scripts auxiliares del agente: crear_base_conocimiento.py, crear_memory_store.py,
    crear_guardrail.sh

Para cada uno localiza la carpeta con azure.yaml (subiendo desde la carpeta efectiva
del comando) y ejecuta .claude/skills/azure-foundry-hosted-agent-deploy/scripts/
verificar_destino.sh. Si falla, sale con código 2: Claude Code cancela el comando y
le muestra a Claude el motivo (stderr). Cualquier otro comando pasa sin coste.

Variables:
  FOUNDRY_HOOK_DESACTIVADO=1  -> deja pasar todo (escape consciente, p. ej. sin red).
Ver docs/adr/0003.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

PATRON = re.compile(
    r"\bazd\s+(?:(?:-C|--cwd)\s+\S+\s+|-{1,2}\S+\s+)*(?:up|provision|deploy)\b"
    r"|crear_base_conocimiento\.py|crear_memory_store\.py|crear_guardrail\.sh"
)
VERIFICADOR = Path(".claude/skills/azure-foundry-hosted-agent-deploy/scripts/verificar_destino.sh")
TIMEOUT_SEGUNDOS = 150
LINEAS_MAX = 25


def carpeta_efectiva(comando: str, cwd: Path) -> Path:
    """Carpeta donde correrá la operación: cwd + el último `cd` previo + `--cwd/-C` de azd."""
    carpeta = cwd
    for tramo in re.split(r"&&|;|\|\|", comando):
        try:
            partes = shlex.split(tramo)
        except ValueError:
            partes = tramo.split()
        if not partes:
            continue
        if partes[0] == "cd" and len(partes) > 1:
            carpeta = (carpeta / os.path.expanduser(partes[1])).resolve()
        elif PATRON.search(tramo):
            for i, p in enumerate(partes):
                if p in ("--cwd", "-C") and i + 1 < len(partes):
                    return (carpeta / os.path.expanduser(partes[i + 1])).resolve()
                if p.startswith("--cwd="):
                    return (carpeta / os.path.expanduser(p.split("=", 1)[1])).resolve()
                # Script auxiliar invocado por ruta: su carpeta manda.
                if re.search(r"crear_\w+\.(py|sh)$", p):
                    return (carpeta / os.path.expanduser(p)).resolve().parent
            return carpeta
    return carpeta


def buscar_azure_yaml(desde: Path) -> Path | None:
    for d in [desde, *desde.parents]:
        if (d / "azure.yaml").is_file():
            return d
    return None


def main() -> int:
    if os.getenv("FOUNDRY_HOOK_DESACTIVADO") == "1":
        return 0
    try:
        entrada = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if entrada.get("tool_name") != "Bash":
        return 0
    comando = (entrada.get("tool_input") or {}).get("command", "")
    if not PATRON.search(comando):
        return 0

    proyecto_claude = Path(os.getenv("CLAUDE_PROJECT_DIR") or entrada.get("cwd") or ".").resolve()
    cwd = Path(entrada.get("cwd") or proyecto_claude).resolve()
    carpeta = carpeta_efectiva(comando, cwd)
    raiz_azd = buscar_azure_yaml(carpeta)
    if raiz_azd is None:
        return 0  # sin azure.yaml no hay destino que verificar; azd fallará por su cuenta

    verificador = proyecto_claude / VERIFICADOR
    if not verificador.is_file():
        print(f"[hook destino Foundry] No encontré {VERIFICADOR}; no puedo verificar el destino. "
              "Sincroniza las skills (bash .claude/scripts/sync-skills.sh) o desactiva el hook con "
              "FOUNDRY_HOOK_DESACTIVADO=1 si es intencional.", file=sys.stderr)
        return 2

    try:
        r = subprocess.run(["bash", str(verificador)], cwd=raiz_azd, capture_output=True,
                           text=True, timeout=TIMEOUT_SEGUNDOS)
    except subprocess.TimeoutExpired:
        print(f"[hook destino Foundry] La verificación superó {TIMEOUT_SEGUNDOS}s (¿sin red o sin sesión de az?). "
              "Comando bloqueado.", file=sys.stderr)
        return 2

    salida = [l for l in (r.stdout + r.stderr).splitlines() if "Update available" not in l and "To update" not in l]
    if r.returncode == 0:
        resumen = next((l for l in reversed(salida) if l.startswith("Destino coherente")), "Destino coherente.")
        print(json.dumps({"systemMessage": f"[hook destino Foundry] {raiz_azd.name}: {resumen}"}))
        return 0

    relevantes = [l for l in salida if "❌" in l or "⚠️" in l or "DESTINO" in l or "recurso '" in l] or salida[-LINEAS_MAX:]
    print(
        f"[hook destino Foundry] Bloqueado: `{comando.strip()[:120]}`\n"
        f"Destino inconsistente en {raiz_azd} (ADR 0001):\n" + "\n".join(relevantes[:LINEAS_MAX]) +
        "\nCorrige lo marcado con ❌ y confirma con el usuario el recurso y el proyecto antes de reintentar.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
