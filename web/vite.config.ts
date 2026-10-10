/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Everything binds to localhost only. The API runs on 8765 (`uv run vd serve`).
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5273, // unusual ports, with strictPort, so this never collides with other local projects
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8765' },
  },
  test: { environment: 'node' },
})
