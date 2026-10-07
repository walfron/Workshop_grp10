import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:3000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': BACKEND,
      '/ws': { target: BACKEND, ws: true },
    },
  },
})
