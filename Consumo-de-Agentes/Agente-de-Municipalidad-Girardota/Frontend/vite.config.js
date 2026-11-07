import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// El navegador nunca habla con Foundry directamente: todo pasa por el backend
// (FastAPI en :8001), que es quien tiene las credenciales de Azure.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/api': { target: 'http://localhost:8001', changeOrigin: true },
    },
  },
})
