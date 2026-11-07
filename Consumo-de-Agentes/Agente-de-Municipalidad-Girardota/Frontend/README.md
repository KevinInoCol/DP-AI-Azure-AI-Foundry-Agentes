# Frontend · asistente virtual de la Alcaldía de Girardota

React + Vite. Chat que habla con el backend FastAPI (`:8001`) a través del proxy
`/api` de Vite; nunca con Foundry directamente.

```bash
npm install
npm run dev      # http://localhost:5174
npm run build    # dist/
```

| Archivo | Qué hace |
|---|---|
| `vite.config.js` | Puerto 5174 y proxy `/api` → `http://localhost:8001` |
| `src/App.jsx` | Pantalla de entrada (nombre opcional + id opaco) y chat |
| `src/api.js` | `enviarMensaje`, `cerrarSesion`, `estadoBackend` |
| `src/components/Mensaje.jsx` | Burbuja de mensaje, indicador "escribiendo", estados bloqueado/error |
| `src/index.css` | Tema institucional claro (verde municipal), responsive |

**Identificación sin datos personales.** La app genera un identificador opaco
(`ciudadano-<aleatorio>`) y lo guarda en `localStorage`; es el que viaja como
`user_id` y sirve de ámbito de memoria del agente. El nombre de pila es opcional
y solo se usa para el saludo. La pantalla de entrada advierte de que no se deben
escribir cédula, teléfono, dirección ni datos bancarios, y el botón "Olvidar mis
datos" borra el identificador y cierra la sesión.
