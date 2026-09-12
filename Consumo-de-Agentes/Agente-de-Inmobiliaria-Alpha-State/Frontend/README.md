# Frontend · chat con el agente Alpha State

React 19 + Vite. Interfaz de chat que consume el backend FastAPI (`../Backend`) mediante `/api/*`; en desarrollo Vite hace proxy a `http://localhost:8000` (ver `vite.config.js`).

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # genera dist/
```

Archivos: `src/App.jsx` (estado del chat, identificación del cliente, sesión), `src/components/Mensaje.jsx` (burbujas y "escribiendo"), `src/api.js` (llamadas al backend), `src/index.css` (estilos, paleta Datapath).
