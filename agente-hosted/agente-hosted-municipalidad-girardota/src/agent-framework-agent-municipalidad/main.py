"""
Punto de entrada del asistente virtual de la Alcaldía de Girardota hospedado en Microsoft Foundry.

Expone el agente definido en `agente.py` mediante `ResponsesHostServer`, que
implementa el protocolo Responses (compatible con OpenAI) en el puerto 8088.
El historial multi-turno lo gestiona la infraestructura de hosting: el host
envía en cada petición la conversación completa, por eso el agente usa
`store: False`.

Ejecutar en local:
    azd ai agent run --no-client          # o: python main.py
    azd ai agent invoke --local "Hola, ¿qué necesito para un certificado de residencia?"

Desplegar:
    azd deploy --no-prompt
"""

from agent_framework_foundry_hosting import ResponsesHostServer

from agente import crear_agente


def main() -> None:
    agent = crear_agente()
    server = ResponsesHostServer(agent)
    server.run()


if __name__ == "__main__":
    main()
