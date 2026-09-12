# Diagramas y movimiento

Todo gráfico es SVG escrito a mano dentro del HTML. Las clases ya están definidas en el `<style>` de la plantilla: aquí está qué hace cada una y cómo componer una figura que se lea bien proyectada.

## Contenido

- [Anatomía de una figura](#anatomía-de-una-figura)
- [Clases disponibles](#clases-disponibles)
- [Geometría y espaciado](#geometría-y-espaciado)
- [Movimiento](#movimiento)
- [Patrones que ya funcionan](#patrones-que-ya-funcionan)

## Anatomía de una figura

```html
<figure>
  <div class="canvas">
    <svg viewBox="0 0 940 300" role="img" aria-label="[qué muestra el diagrama]">
      …
    </svg>
  </div>
  <figcaption><b>Figura N.</b> [Lectura de la figura.]</figcaption>
</figure>
```

El `figcaption` no describe lo que ya se ve: aporta la conclusión, el matiz o el dato que el dibujo no puede decir. Mal: «Diagrama del proceso de inferencia». Bien: «Sin cache, generar el token 500 obligaría a recalcular los 499 anteriores. Es la diferencia entre viable y prohibitivo».

Entre 8 y 14 figuras por sesión. Una figura por idea que se entienda mejor viéndola; ninguna decorativa.

## Clases disponibles

**Cajas** — `class="box"` normal, `class="box hi"` destacada en coral, `class="box mute"` apagada. Siempre `rx` entre 10 y 16.

**Líneas y conectores** — `class="ln"` gris, `class="ln on"` coral, `.dash` para punteado. Las flechas se dibujan como `<polygon points="x-12,y-6 x,y x-12,y+6" fill="#FF7A50"/>` al final de la línea.

**Textos** — `.dt` título dentro de una caja (14 px, semibold), `.ds` contenido (12,5 px), `.dm` etiqueta monoespaciada en mayúsculas (10 px, para rótulos de sección y unidades), `.dc` cifra o porcentaje en coral (11 px).

**Colores fuera de la paleta base**, solo dentro de diagramas y con sentido semántico: menta `#6FD3C7` para lo correcto o el grupo A, ámbar `#F0B85C` para advertencia, rosa `#F0776E` para el error, violeta `#8E7CC3` para categorías neutras.

## Geometría y espaciado

`viewBox="0 0 940 H"` con H entre 250 y 330. El ancho útil termina en 920.

Estima el ancho del texto antes de colocarlo: unos 6,3 px por carácter en `.ds`, 7,5 px en `.dm` por el espaciado entre letras. Un rótulo de 30 caracteres en `.dm` ocupa unos 225 px. Si empieza en `x=762`, termina en 987 y se sale: hay que acortarlo o moverlo.

Cajas de nodo: 110 a 200 px de ancho, 48 a 64 de alto. Separación mínima entre nodos de una fila: 34 px, que es lo que necesita la flecha. Filas: una en `y≈60` y otra en `y≈220` si el diagrama tiene dos carriles (ingesta y consulta, prefill y decode).

Para texto centrado en una caja, `text-anchor="middle"` con `x` en el centro de la caja y `y` en el centro vertical más 5.

## Movimiento

**Al entrar en pantalla.** El JavaScript de la plantilla añade la clase `in` a cada `<figure>` cuando aparece, y reparte el retardo entre los elementos `.rise` de esa figura. Basta con marcar los elementos:

- `.rise` — sube y aparece. Va en cajas y grupos. La plantilla ya lo aplica a `.box`, `.box hi` y `.box mute` si los escribes como `class="box rise"`.
- `.grow` — crece desde la izquierda. Para barras de gráficos: `<rect class="grow" x=… rx="5" fill="#FF7A50"/>`.
- `.draw` — se dibuja sola. Para líneas largas: rectas de regresión, ejes, líneas de tiempo.

**Continuo, y con moderación.**

- `.flow` — dash animado en los conectores coral, marca la dirección del proceso. Es el que más vida da y se puede usar en todos los conectores de una figura.
- `.pulse` — parpadeo suave. Un solo elemento por figura, el que quieres que el ojo encuentre primero.
- `.bob` — flotación mínima. Para hitos de una línea de tiempo o nodos sueltos.

No combines `.rise` con `.pulse` en el mismo elemento: ambas animan la opacidad y se pelean. Tampoco pongas `.rise` dentro de un grupo `data-s`, por la misma razón.

`prefers-reduced-motion` ya desactiva todo en el CSS de la plantilla; no hay que hacer nada más.

## Patrones que ya funcionan

**Cadena de proceso.** Nodos en una fila, conectores `.ln on flow` con flecha, rótulo `.dm` encima de cada conector con el nombre de la transformación (`chunking`, `embedding`, `insert`). El último nodo en `.box hi`.

**Círculos concéntricos.** Rectángulos anidados con `rx` decreciente, cada uno con su `.dt` arriba a la izquierda, y a la derecha una columna de descripciones conectadas con `.ln dash`. Sirve para taxonomías: IA ⊃ ML ⊃ redes ⊃ deep learning.

**Barras de probabilidad.** Etiqueta `.ds` a la izquierda, `<rect class="grow" rx="5">` de ancho proporcional, cifra `.dc` a la derecha. Ancho máximo de barra 300 px. Ideal para distribuciones de tokens, comparaciones y resultados de un modelo.

**Dos carriles.** Rótulo `.dm` de cada carril, una fila de nodos arriba y otra abajo, y un conector vertical entre ambos con `.ln on dash flow`. Sirve para ingesta/consulta, entrenamiento/inferencia, antes/después.

**Comparación lado a lado.** Dos rectángulos grandes de 430 px separados por una línea vertical, uno en `.box` y otro en `.box hi` cuando hay un ganador claro. Para «modelo bien entrenado vs mal entrenado» o «con cache vs sin cache».

**Línea de tiempo.** Una recta con `.draw`, hitos alternando arriba y abajo, cada uno con círculo, línea corta, año en `.dm` y nombre en `.ds`. Leyenda de categorías abajo con cuadraditos de color.
