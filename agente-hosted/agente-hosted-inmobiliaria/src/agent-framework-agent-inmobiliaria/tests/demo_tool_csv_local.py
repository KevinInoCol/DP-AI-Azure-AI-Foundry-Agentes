"""
Demo end-to-end del agente con la tool usando el CSV local en lugar de Google Sheets.

Sirve para comprobar que el modelo llama a buscar_propiedades_alquiler y
presenta resultados reales, sin depender de la hoja de Google (útil en el
taller si no hay internet hacia Google o aún no existe la hoja).

Ejecutar desde src/agent-framework-agent-inmobiliaria/ (requiere az login):
    .venv/bin/python tests/demo_tool_csv_local.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agente

MENSAJES = [
    "Hola, busco un departamento en alquiler en Miraflores, máximo 2500 soles.",
    "Acepto hasta 3000 soles si está amoblado.",
    "¿Y tienen algo con 3 dormitorios que acepte mascotas, en cualquier distrito?",
]


def cargar_model_config_csv_local():
    cfg = _cargar_original()
    cfg["tools"]["buscar_propiedades_alquiler"]["origen"] = "csv_local"
    return cfg


_cargar_original = agente.cargar_model_config
agente.cargar_model_config = cargar_model_config_csv_local


async def main() -> None:
    agent = agente.crear_agente()
    session = agent.create_session()
    for mensaje in MENSAJES:
        print(f"\nTú: {mensaje}")
        respuesta = await agent.run(mensaje, session=session)
        print(f"{agente.BOT_NAME}: {respuesta.text}")


if __name__ == "__main__":
    asyncio.run(main())
