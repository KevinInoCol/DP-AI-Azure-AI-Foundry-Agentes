import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// El frontend nunca habla con Foundry directamente: todo pasa por el backend
// (FastAPI en :8000), que es quien tiene las credenciales de Azure.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
