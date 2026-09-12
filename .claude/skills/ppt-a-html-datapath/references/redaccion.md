# Estructura, redacción y cuestionario

## De las láminas a las secciones

No hay correspondencia uno a uno entre lámina y sección. Las de portada, agenda, reglas de clase, presentación del instructor y despedida no son temas: se descartan o se funden en la portada del HTML. Las láminas que desarrollan una misma idea en varias partes —«Embeddings (1)» hasta «Embeddings (12)»— se funden en una sola sección.

Entre 12 y 18 secciones por sesión, agrupadas en 4 a 6 grupos de temario que marquen el arco: fundamentos primero, aplicación después, cierre con el puente al módulo siguiente, el stack y los recursos. Los nombres de grupo son cortos y descriptivos, no numerados.

Cada sección declara `data-grp` (grupo del temario) y `data-nav` (nombre corto, tres o cuatro palabras). Ese nombre corto es lo que el alumno lee para orientarse, así que debe decir el tema, no ser gracioso.

## Anatomía de una sección

1. `<p class="eyebrow">NN · Etiqueta</p>` — número correlativo y una etiqueta de una o dos palabras.
2. `<h3>` — un titular que **afirma algo**, no un rótulo. Mal: «Tokens». Bien: «La unidad con la que el modelo piensa y cobra».
3. `<p class="lead">` — la idea central en dos o tres frases.
4. Cuerpo: párrafos, y cuando aporten, tarjetas `.tile` en `.duo` o `.trio`, tablas, `.formula`, figuras y llamadas `.note`.

Las llamadas tienen tres tonos y conviene no abusar: `.note` normal para una regla o un dato que merece destacarse, `.note.warn` para una advertencia de costo o de diseño, `.note.stop` para un error que hay que evitar. Una o dos por sección como mucho.

## Tono

Instructor con experiencia hablando a desarrolladores. Frases directas, sin relleno, sin entusiasmo publicitario y sin emojis en el cuerpo del texto.

El criterio para decidir qué se cuenta: **por qué esto le importa a quien va a construir el sistema**. Cada tema debería aterrizar en una consecuencia práctica —costo, latencia, un error típico en producción, un criterio de decisión— y no quedarse en la definición.

Amplía lo telegráfico. Una lámina con tres viñetas se convierte en dos o tres párrafos que las expliquen de verdad, con un ejemplo del dominio cuando ayude. Conserva las cifras, fórmulas, nombres de papers y ejemplos concretos de las láminas: son lo que hace que el material valga más que un resumen genérico.

Evita el gerundio de arranque, las listas de tres adjetivos y las frases que anuncian lo que se va a decir en vez de decirlo. Prefiere el punto seguido a la subordinación larga.

## Cuestionario final

Seis preguntas de opción múltiple, cuatro alternativas cada una, en el array `Q` del segundo bloque de `<script>`:

```js
{tag:"Tema al que pertenece",
 q:"Pregunta",
 o:["Alternativa A","Alternativa B","Alternativa C","Alternativa D"],
 ok:1,                       // índice de la correcta, empezando en 0
 why:"Explicación de dos o tres frases."}
```

Las preguntas evalúan **criterio aplicado, no memoria**. Comparación:

- Flojo: «¿Cuántos tokens tiene el vocabulario de GPT-4?»
- Bueno: «¿Por qué el mismo contenido cuesta más en español que en inglés?»
- Flojo: «¿Qué significa la sigla KV cache?»
- Bueno: «¿Por qué conviene poner el system prompt al inicio del prompt?»

Reparte las seis preguntas entre los temas centrales de la sesión, sin repetir tema. Los distractores tienen que ser plausibles: alternativas que alguien que entendió a medias elegiría de verdad, nunca absurdos de relleno.

La explicación `why` se muestra tanto si se acierta como si no, así que además de justificar la correcta conviene decir por qué falla la que suele elegirse. Cuando haya un matiz importante, es buen lugar para meterlo: «reproducible no significa correcto; el modelo puede equivocarse siempre de la misma manera».

## Cierre

Las tres últimas piezas, en este orden:

1. **Stack y preparación** para la clase siguiente: enlaces de instalación en `.links` y la tabla del programa completo con el módulo actual en negrita. La tabla se construye con los datos del programa que dio el usuario, no con los de otro curso.
2. **Recursos y materiales**: enlaces de Drive y scripts embebidos. Ver `recursos.md`.
3. **Cuestionario**, y después una `.note` final que resuma la sesión en una sola cadena de ideas encadenadas, más el pie con la marca, el módulo y el título de la sesión.
