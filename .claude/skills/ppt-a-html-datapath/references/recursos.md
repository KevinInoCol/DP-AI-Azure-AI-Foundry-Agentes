# Recursos y materiales

Penúltima sección del archivo, antes del cuestionario. Reúne en un solo sitio todo lo que se usó en clase, con dos tipos de tarjeta dentro de un contenedor `.res`. La lógica de plegado y copiado ya está en el JavaScript de la plantilla: aquí está el marcado y el criterio.

## Qué tipo de tarjeta usar

**Enlace externo** para lo que vive fuera: documentos, notas escaneadas, cuadernos de Colab, carpetas de Drive, repositorios, grabaciones. También para código que cambia a menudo, porque el que se embebe queda congelado en el archivo.

**Script embebido** para el código estable de la sesión: los scripts que el alumno va a ejecutar tal cual o a adaptar. Va dentro del HTML, así que sigue disponible sin conexión y sin permisos de Drive.

Una tarjeta por recurso, con nombre real y una línea que diga qué es, para que el alumno no tenga que abrirlos todos para encontrar el que busca. Primero los enlaces, después los scripts.

## Enlace externo

```html
<a class="rescard" href="[URL]" target="_blank" rel="noopener">
  <span class="ic">📄</span>
  <span class="bd"><b>[Nombre del recurso]</b><span>[Qué contiene y dónde está alojado]</span></span>
  <span class="go">Abrir ↗</span>
</a>
```

`target="_blank"` y `rel="noopener"` siempre. El icono es un emoji dentro de `.ic`: documento para notas y PDF, carpeta para carpetas, cuaderno para Colab, gato para repositorios de GitHub. Es el único lugar del archivo donde se usan emojis.

## Script embebido

```html
<div class="rescard code">
  <button class="reshead" type="button" aria-expanded="false">
    <span class="ic">🐍</span>
    <span class="bd"><b>[nombre_del_archivo.py]</b><span>[Lenguaje · qué hace el script]</span></span>
    <span class="chev">Ver código</span>
  </button>
  <div class="resbody">
    <div class="codetop"><span class="lang">python</span><button class="copy" type="button">Copiar</button></div>
    <pre><code>[código escapado]</code></pre>
  </div>
</div>
```

Requisitos para que el JavaScript de la plantilla lo tome:

- La tarjeta lleva `class="rescard code"` y contiene `.reshead`, `.chev`, `.resbody`, `.copy` y un `<code>`.
- `aria-expanded="false"` en la cabecera: el JavaScript lo mantiene sincronizado.
- El texto del indicador arranca en `Ver código`; al abrir pasa a `Ocultar`.

**Escapa el código antes de insertarlo.** `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`. Sin esto, cualquier comparación `if x < 10` o cualquier genérico `List<str>` rompe el HTML, a veces de forma silenciosa: el archivo abre pero se pierde parte del contenido. Si generas el archivo con un script, usa la función de escape del lenguaje en lugar de reemplazos a mano.

El bloque de código hace scroll a partir de 440 px de alto, así que un script largo no estira la página. No hay resaltado de sintaxis, y no conviene añadirlo: obligaría a una dependencia externa y rompería la regla del archivo único.

## Comportamiento que produce

Al pulsar la cabecera, la tarjeta alterna la clase `open` y el código aparece con una transición corta. El botón de copiar usa `navigator.clipboard.writeText`, con respaldo en un `textarea` temporal y `document.execCommand("copy")` para navegadores antiguos o para cuando el archivo se abre desde el sistema de archivos sin HTTPS. Al copiar, el botón confirma con `Copiado` en verde y vuelve a su estado a los dos segundos. El clic en copiar detiene su propagación, así que no cierra la tarjeta.

En `jsdom` el copiado no funciona porque no hay portapapeles ni `execCommand`: el botón mostrará el texto de respaldo. Es esperado y no indica un fallo.

## Cierre de la sección

Termina con una `.note` que explique cómo ejecutar lo que hay: entorno o gestor de paquetes, dependencias que hay que instalar y qué conviene cambiar para probarlo con datos propios. Cuando el script se relacione con temas concretos de la sesión, remite a ellos por número: es lo que convierte el recurso en ejercicio.
