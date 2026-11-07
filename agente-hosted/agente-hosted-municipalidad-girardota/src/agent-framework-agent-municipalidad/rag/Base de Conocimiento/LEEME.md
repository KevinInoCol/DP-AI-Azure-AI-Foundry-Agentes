# Base de conocimiento de la Alcaldía de Girardota

Copia aquí los documentos oficiales del municipio (PDF, DOCX, TXT, MD, HTML).
Todo lo que esté en esta carpeta se sube al contenedor de blobs y se indexa.

Sugerencia de contenido, uno o varios documentos:

- Catálogo de trámites y servicios (qué es cada uno, requisitos, costo, plazo, dependencia).
- Impuesto predial e industria y comercio: calendario, descuentos por pronto pago, medios de pago.
- Certificados: residencia, estratificación, paz y salvo.
- Licencias y permisos: construcción, uso de suelo, eventos, publicidad exterior.
- Programas sociales: SISBÉN, adulto mayor, primera infancia, discapacidad, empleo.
- PQRSD: canales de radicación y tiempos legales de respuesta.
- Directorio de dependencias, horarios y puntos de atención.
- Preguntas frecuentes de la ventanilla de atención.

## Qué NO poner aquí

Nada con datos personales de ciudadanos: bases de datos de contribuyentes,
listados de beneficiarios, expedientes, PQRSD radicadas, censos. La base de
conocimiento se consulta desde el agente y sus fragmentos llegan al modelo:
debe contener solo información pública y de procedimiento.

## Después de copiar los documentos

```bash
.venv/bin/python rag/crear_base_conocimiento.py
```

Luego concede el rol "Search Index Data Reader" (el script imprime los
comandos), pon `enabled: true` en `tools.consultar_tramites_girardota` de
`model_config/model_config.yaml` y ejecuta `azd deploy --no-prompt`.

Esta carpeta está en `.azdignore`: los documentos NO viajan al contenedor del agente.
