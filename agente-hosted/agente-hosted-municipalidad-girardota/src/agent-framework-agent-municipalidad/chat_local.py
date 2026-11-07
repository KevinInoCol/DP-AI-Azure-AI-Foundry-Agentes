"""
Consola interactiva para probar el asistente municipal sin levantar el servidor.

El historial de la charla vive en una `AgentSession` en memoria (se pierde al
cerrar). La memoria de largo plazo entre conversaciones es Memoria de Foundry:
el agente recuerda al ciudadano identificado por MEMORY_SCOPE aunque reinicies.

Ejecutar (con el venv del servicio activado y sesión `az login` vigente):
    python chat_local.py
Escribe `salir` (o Ctrl+D) para terminar. También acepta entrada por tubería:
    printf '¿Qué necesito para un certificado de residencia?\n' | python chat_local.py
"""

import asyncio
import os

from dotenv import load_dotenv

from agente import BOT_NAME, crear_agente

load_dotenv()

# Identificador del ciudadano para la memoria de Foundry en local (en Foundry lo
# resuelve el host con la identidad de quien llama). Cambia el valor para simular
# ciudadanos distintos: MEMORY_SCOPE=ciudadano-marta python chat_local.py
MEMORY_SCOPE = os.getenv("MEMORY_SCOPE", "ciudadano-local")

COMANDOS_SALIDA = {"salir", "exit", "quit"}


async def chat() -> None:
    agent = crear_agente(scope_memoria=MEMORY_SCOPE)
    session = agent.create_session()  # historial en memoria para toda la charla

    print(f"Chat con {BOT_NAME} (memoria de Foundry, ciudadano '{MEMORY_SCOPE}'). Escribe 'salir' para terminar.\n")
    while True:
        try:
            mensaje = input("Tú: ").strip()
        except EOFError:
            print()
            break
        if not mensaje:
            continue
        if mensaje.lower() in COMANDOS_SALIDA:
            break

        respuesta = await agent.run(mensaje, session=session)
        print(f"{BOT_NAME}: {respuesta.text}\n")

    print(f"Fin de la conversación ({contar_mensajes(session)} mensajes en memoria).")


def contar_mensajes(session) -> int:
    """Cuenta los mensajes guardados por el InMemoryHistoryProvider (state["in_memory"]["messages"])."""
    estado = session.to_dict().get("state", {})
    return sum(len(v.get("messages", [])) for v in estado.values() if isinstance(v, dict))


if __name__ == "__main__":
    asyncio.run(chat())
