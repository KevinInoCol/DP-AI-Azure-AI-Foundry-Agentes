---
name: ppt-a-html-datapath
description: Convierte presentaciones de clase (.pptx o su PDF) en un archivo .html único, oscuro, animado, con tarjetas que avanzan, sección de recursos descargables y cuestionario final, siguiendo la identidad visual de Datapath. Sirve para cualquier programa o curso, no solo para uno. Úsala siempre que el usuario comparta un PPT, un PDF de láminas, notas de clase o material de una sesión y pida convertirlo, pasarlo a HTML, crear material interactivo, material de estudio, un recurso para alumnos o "lo mismo que la sesión anterior" — aunque no diga las palabras "HTML" ni "convertir". Actívala también cuando pida animar diagramas de clase, agregar tarjetas paso a paso, añadir scripts descargables o enlaces de Drive a un material existente, o retomar la conversión de otra sesión de un curso.
---

# Convertir láminas de clase a HTML animado (Datapath)

Convierte el material de una sesión —hoy en PowerPoint— en **un solo archivo `.html` autocontenido** que el alumno usa antes, durante y después de la clase: lectura larga con temario lateral, diagramas SVG animados, algunas secciones en formato paso a paso, una sección de recursos con enlaces y scripts copiables, y un cuestionario final autoevaluable.

El diseño no se reinventa en cada sesión. Todo el sistema visual y todo el JavaScript ya están resueltos en `assets/plantilla.html`; el trabajo real es leer las láminas, decidir la estructura, redactar y dibujar los diagramas.

## Flujo de trabajo

### 1. Preguntar los datos de cabecera

Estos datos aparecen en la barra lateral, la portada y el pie, y **no se deben inventar ni asumir**: el mismo formato se usa en programas distintos, así que pregúntalos antes de construir el archivo. Si algo ya está dicho en la conversación o se deduce sin ambigüedad de las láminas, no lo vuelvas a preguntar: propónlo y pide confirmación.

- **Nombre del programa o curso** — va en la barra lateral y en el pie. Ejemplos de formato: `AI Engineer for Developers`, `Data Analytics con Power BI`.
- **Título de la sesión**, tal como debe aparecer, con su numeración si la tiene.
- **Módulo y número de sesión** — `Módulo 3 · Sesión 2 de 5`.
- **Duración estimada**.
- **Enlaces a material alojado en Drive**, con el nombre con que debe mostrarse cada uno.
- **Scripts que deben quedar embebidos**, si no vinieron adjuntos.

Pregúntalo todo junto, en una sola pasada, y en lenguaje llano. Si el usuario dijo "hazlo sin preguntar", usa lo que se deduzca de las láminas y marca en el reporte final qué datos asumiste.

### 2. Leer el material de origen

Lee el PPT o su PDF completo antes de escribir nada, más cualquier nota, apunte o script adjunto. Anota tres cosas mientras lees: qué temas hay, qué láminas están telegráficas y necesitan desarrollo, y qué datos concretos (cifras, fórmulas, ejemplos, nombres de papers) deben sobrevivir a la conversión.

Si el usuario adjuntó el HTML de una sesión anterior, ábrelo: es la referencia viva del formato y puede tener mejoras posteriores a esta skill.

### 3. Acordar la estructura antes de redactar

Propón al usuario, en pocas líneas: los temas en que dividirás la sesión (entre 12 y 18), los grupos del temario (entre 4 y 6) y qué secciones serán recorridos de tarjetas. Es barato corregir el esqueleto y caro rehacer el archivo entero.

Un tema es una sección `<section>` con su entrada en el temario. Los grupos ordenan el temario lateral y marcan el arco de la sesión: de lo fundamental a lo aplicado, cerrando con los recursos y el puente al módulo siguiente.

### 4. Construir el archivo

Parte de `assets/plantilla.html`, que ya trae el bloque `<style>` completo, la barra lateral, la portada, secciones de ejemplo de los tres tipos (normal, con tarjetas y de recursos), el marcado del cuestionario y los dos bloques de `<script>`: temario y progreso de lectura; animación de figuras, recursos plegables, tarjetas y cuestionario. Copia esa plantilla al directorio de trabajo y rellénala. **No reescribas el CSS ni el JavaScript**: si algo no encaja, añade reglas nuevas al final del `<style>` en vez de tocar las existentes.

Consulta según lo que estés escribiendo:

| Cuando vayas a… | Lee |
|---|---|
| dibujar cualquier figura o animarla | `references/diagramas.md` |
| convertir una sección en recorrido de tarjetas | `references/tarjetas.md` |
| montar la sección de recursos y materiales | `references/recursos.md` |
| redactar el texto y las preguntas del cuestionario | `references/redaccion.md` |

Numera las secciones de forma correlativa en el `eyebrow` (`01 ·`, `02 ·`…) y los `id` (`s1`, `s2`…), y las figuras también. La sección del cuestionario conserva el `id="s-quiz"` de la plantilla: es estable a propósito, para que insertar secciones nuevas no rompa el botón de la barra superior. Las figuras con tarjetas no llevan `figcaption`, así que no consumen número de figura.

### 5. Verificar antes de entregar

Escribe el archivo en el directorio de salida y compruébalo de verdad, no de vista. Si tienes un entorno con Node, `jsdom` sirve para cargar el archivo, ejecutar sus scripts y recorrer los controles mediante clics simulados. Comprueba:

- El HTML parsea y el JavaScript no lanza excepciones.
- El temario se genera con una entrada por sección y los grupos correctos.
- Cada recorrido de tarjetas llega del primer al último paso, los puntos permiten saltar y el diagrama se enciende de forma acumulativa.
- Cada script se despliega y se repliega, el código está escapado y completo, y el botón de copiar existe. En `jsdom` el copiado no funciona por falta de portapapeles: eso es esperado y no es un fallo.
- Los enlaces externos llevan `target="_blank"` y `rel="noopener"`.
- El cuestionario se completa, muestra resultado con el repaso de lo fallado y se puede repetir.
- Ningún texto se sale del `viewBox` de su figura: estima el ancho del texto a unos 6,3 px por carácter en `.ds` y 7,5 px en `.dm`, y verifica que `x + ancho` no pase de 920.
- Los datos de cabecera —programa, sesión, módulo— aparecen correctos en la barra lateral, la portada y el pie, sin marcadores entre corchetes sin rellenar.
- Numeración de secciones y figuras correlativa, sin huecos.

Presenta el archivo con la herramienta de entrega de archivos si la tienes.

### 6. Reportar

En el mensaje final, breve: los temas en que dividiste la sesión, qué secciones quedaron como recorrido de tarjetas y por qué, qué recursos incluiste, y **cualquier error, dato desactualizado o inconsistencia que hayas encontrado en las láminas originales**, con la corrección que aplicaste. No corrijas en silencio: el usuario también mantiene el PPT y necesita saberlo.

## Reglas que no se negocian

**Un solo archivo.** Sin frameworks, sin build, sin `localStorage`, sin imágenes externas. La única dependencia externa son las tipografías de Google Fonts. Debe funcionar con doble clic.

**Nada de capturas de las láminas.** Todos los gráficos se redibujan como SVG escrito a mano dentro del HTML. Una captura se ve borrosa al proyectar, no se anima y no se puede recorrer por pasos.

**El contenido de las láminas se conserva y se amplía.** Las cifras, fórmulas, ejemplos y fuentes citadas deben estar. Una lámina con tres viñetas se convierte en párrafos que las expliquen; nunca en tres viñetas iguales sobre fondo oscuro.

**Nada de código inventado.** Los scripts embebidos son los que el usuario entregó. Si no adjuntó ninguno, deja solo las tarjetas de enlace y dilo en el reporte.

**Español neutro** en todo el archivo, incluidos los `aria-label` y los comentarios.

**Coral como único acento.** `#FF7A50` sobre fondo oscuro. Los colores menta, ámbar y rosa solo aparecen dentro de diagramas y en el feedback del cuestionario.

## Errores frecuentes

- Asumir el nombre del programa por lo que se hizo en una sesión anterior. Cambia entre cursos: se pregunta.
- Convertir cada lámina en una sección. Las láminas de portada, agenda, reglas de clase y despedida no son temas; se funden o se descartan.
- Poner tarjetas paso a paso en una sección que es una simple enumeración. Solo se justifican en secuencias, construcciones y comparaciones por etapas.
- Insertar el código de un script sin escapar `&`, `<` y `>`: rompe el HTML y a veces de forma silenciosa.
- Rellenar de figuras decorativas. Cada figura existe porque hay algo que se entiende mejor viéndolo.
- Escribir preguntas de cuestionario que se responden recordando una definición. Deben exigir criterio aplicado.
- Dejar animaciones continuas en muchos elementos a la vez: el `.flow` de los conectores basta para dar vida; `.pulse` se reserva para un elemento por figura.
