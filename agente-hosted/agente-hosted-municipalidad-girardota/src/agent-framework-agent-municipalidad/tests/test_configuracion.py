"""
Pruebas offline de la configuración del asistente municipal (sin llamar al modelo).

Comprueba lo que rompe en producción y no se ve hasta desplegar:
1. Los dos YAML parsean y tienen metadata con versión.
2. Todos los tags del system prompt abren y cierran, con una sola convención.
3. Los placeholders del prompt existen en la sección `agent` de model_config.
4. El nombre de cada tool coincide en los tres sitios: función de `tools/`,
   clave de `tools:` en model_config y `<Herramientas_Disponibles>` del prompt.
5. La memoria declara qué NO debe guardar (minimización de datos personales).
6. El guardrail declarado en model_config existe como archivo JSON.

Ejecutar desde src/agent-framework-agent-municipalidad/:
    .venv/bin/python tests/test_configuracion.py
"""

import json
import re
import sys
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
RUTA_MODEL_CONFIG = BASE_DIR / "model_config" / "model_config.yaml"
RUTA_PROMPT = BASE_DIR / "prompt" / "system_prompt.yaml"
RUTA_TOOLS = BASE_DIR / "tools"

# Datos que la memoria NUNCA debe persistir en una entidad pública.
PROHIBIDOS_EN_MEMORIA = ["cédula", "teléfono", "dirección exacta", "bancarios", "factura"]

fallos: list[str] = []


def comprobar(condicion: bool, mensaje: str) -> None:
    print(("  OK   " if condicion else "  FALLA ") + mensaje)
    if not condicion:
        fallos.append(mensaje)


def main() -> None:
    print("1) Los YAML parsean y tienen versión")
    cfg = yaml.safe_load(RUTA_MODEL_CONFIG.read_text(encoding="utf-8"))
    prompt_cfg = yaml.safe_load(RUTA_PROMPT.read_text(encoding="utf-8"))
    comprobar(bool(cfg.get("version")), f"model_config.yaml v{cfg.get('version')}")
    comprobar(bool(prompt_cfg.get("version")), f"system_prompt.yaml v{prompt_cfg.get('version')}")

    sp = prompt_cfg["system_prompt"]

    print("2) Tags del system prompt")
    abiertos = re.findall(r"^[ \t]*<([A-Za-z_]+)>[ \t]*$", sp, re.M)
    cerrados = re.findall(r"^[ \t]*</([A-Za-z_]+)>[ \t]*$", sp, re.M)
    huerfanos = set(abiertos) ^ set(cerrados)
    comprobar(not huerfanos, f"todos los tags cierran (huérfanos: {sorted(huerfanos) or 'ninguno'})")
    tags = list(dict.fromkeys(abiertos))
    mayus = [t for t in tags if t[0].isupper()]
    minus = [t for t in tags if t[0].islower()]
    comprobar(not (mayus and minus), f"una sola convención de nombres ({len(tags)} tags)")
    for obligatorio in ("Identidad", "Proteccion_De_Datos_Personales", "Herramientas_Disponibles", "IMPORTANTE"):
        comprobar(obligatorio in tags, f"existe la sección <{obligatorio}>")

    print("3) Placeholders del prompt")
    for variable in prompt_cfg.get("variables", []):
        comprobar(variable in cfg["agent"], f"agent.{variable} está en model_config")
        comprobar(f"{{{variable}}}" in sp, f"el prompt usa {{{variable}}}")
    usados = set(re.findall(r"\{([a-z_]+)\}", sp))
    comprobar(usados <= set(prompt_cfg.get("variables", [])), f"sin placeholders sin declarar ({sorted(usados)})")

    print("4) Nombres de tools en los tres sitios")
    codigo = "\n".join(p.read_text(encoding="utf-8") for p in RUTA_TOOLS.glob("*.py"))
    for nombre in cfg.get("tools", {}):
        comprobar(f"def {nombre}(" in codigo, f"'{nombre}' está definida en tools/")
        comprobar(nombre in sp, f"'{nombre}' se cita en el system prompt")

    print("5) Minimización de datos en la memoria")
    detalles = (cfg.get("memory", {}).get("user_profile_details") or "").lower()
    comprobar(bool(detalles), "memory.user_profile_details definido")
    for termino in PROHIBIDOS_EN_MEMORIA:
        comprobar(termino in detalles, f"la memoria prohíbe guardar '{termino}'")

    print("6) Guardrail")
    ruta_guardrail = BASE_DIR / cfg.get("guardrail", {}).get("definicion", "")
    comprobar(ruta_guardrail.is_file(), f"existe {ruta_guardrail.name}")
    if ruta_guardrail.is_file():
        filtros = json.loads(ruta_guardrail.read_text(encoding="utf-8"))["properties"]["contentFilters"]
        nombres = {f["name"] for f in filtros}
        comprobar("Indirect Attack" in nombres, "el guardrail filtra ataques indirectos (prompt injection)")
        comprobar("Credit card Protection" in nombres, "el guardrail bloquea datos de tarjeta")

    print()
    if fallos:
        print(f"{len(fallos)} comprobación(es) fallida(s).")
        sys.exit(1)
    print("Todas las comprobaciones pasaron.")


if __name__ == "__main__":
    main()
