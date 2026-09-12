# Tarjetas que avanzan

Una figura por pasos: el alumno avanza con tarjetas y el diagrama de arriba se va construyendo. Sirve igual para explicar en clase —el instructor avanza mientras habla— que para estudiar solo.

## Cuándo usarlas

Entre 3 y 5 secciones por sesión, no más: si todo es un recorrido, deja de destacar y cansa.

Se justifican cuando la idea es:

- **una secuencia** — un pipeline, un flujo de datos, el ciclo de una petición;
- **una construcción** — algo que se arma por capas y cuyo estado final no se entiende sin ver cómo se llegó;
- **una progresión temporal** — generaciones, versiones, fases de un proyecto.

No se justifican en una enumeración de conceptos paralelos, en una comparación de dos alternativas —eso es una tabla o una figura lado a lado— ni cuando los pasos son tan obvios que la tarjeta repetiría el rótulo del nodo.

Entre 3 y 5 pasos por recorrido. Con dos, no hace falta el mecanismo; con seis, conviene partir el tema en dos secciones.

## Marcado

```html
<figure class="stepfig">
  <div class="canvas">
    <svg viewBox="0 0 940 300" role="img" aria-label="…">
      <!-- lo que se ve siempre va fuera de los grupos: ejes, líneas base -->
      <g data-s="0"> … </g>
      <g data-s="1"> … </g>
      <g data-s="2"> … </g>
    </svg>
  </div>
  <div class="deck">
    <div class="cards">
      <article class="card on"><span class="step">Paso 1 de 3</span><h5>…</h5><p>…</p></article>
      <article class="card"><span class="step">Paso 2 de 3</span><h5>…</h5><p>…</p></article>
      <article class="card"><span class="step">Paso 3 de 3</span><h5>…</h5><p>…</p></article>
    </div>
    <div class="ctrls">
      <div class="dots"></div>
      <button class="btn ghost sm prev" type="button">Anterior</button>
      <button class="btn sm next" type="button">Siguiente</button>
    </div>
  </div>
</figure>
```

Requisitos para que el JavaScript de la plantilla lo tome:

- La figura lleva `class="stepfig"` y contiene tanto el SVG como el `.deck`.
- Tantos grupos `data-s` como tarjetas, numerados desde `0` y en orden.
- `.dots` vacío: los puntos se generan solos.
- La primera tarjeta lleva `class="card on"`.
- Sin `figcaption`: la explicación vive en las tarjetas.
- Los elementos dentro de un grupo `data-s` **no llevan `.rise`**, porque ambas cosas animan la opacidad.

## Comportamiento que produce

Al cambiar de paso, los grupos con `data-s` menor o igual al paso actual reciben `on` y quedan visibles; el grupo del paso actual recibe además `now` y se resalta en coral; el resto queda atenuado al 13%. El diagrama se construye en vez de reemplazarse, así que al final se ve completo.

`Anterior` se deshabilita en el primer paso y `Siguiente` pasa a decir `Fin` en el último. Los puntos permiten saltar a cualquier paso, hacia adelante o hacia atrás.

## Cómo repartir el diagrama en grupos

El corte lo manda la narración, no el dibujo. Escribe primero las tarjetas y después decide qué entra en cada grupo: cada tarjeta debe tener algo nuevo que mirar.

Reglas prácticas:

- El conector que lleva de la etapa A a la B pertenece al grupo de B, no al de A. Así la flecha aparece con el nodo al que apunta.
- Los rótulos de carril (`INGESTA`, `CONSULTA`) entran con el primer grupo de su carril.
- Los contenedores grandes —el panel de un cache, un marco que agrupa varios nodos— entran en el paso donde se explican, no antes.
- Si un elemento tiene que verse desde el principio, déjalo fuera de los grupos: ejes, la recta de una línea de tiempo, un título permanente.

## Cómo escribir las tarjetas

Título corto y afirmativo: «K y V se guardan en el cache», no «El cache». El cuerpo, entre dos y cuatro frases, explica qué ocurre y por qué importa. La última tarjeta cierra el recorrido con la consecuencia práctica, no con un resumen de lo dicho.

Las tarjetas sustituyen al `figcaption` y a parte del cuerpo de la sección: si el párrafo de arriba ya explicó los pasos, sobra uno de los dos.
