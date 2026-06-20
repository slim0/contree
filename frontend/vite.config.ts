import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendHttp = process.env.BACKEND_URL ?? 'http://localhost:8000'
const backendWs = backendHttp.replace(/^http/, 'ws')

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,   // bind 0.0.0.0 pour Docker
    proxy: {
      '/api': backendHttp,
      '/ws': { target: backendWs, ws: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
})
