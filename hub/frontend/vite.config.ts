import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// Output goes into Flask's static/ folder so /static/dist/* is served
// without any extra route. The Vue SPA itself is served by /v2/* in app.py.
export default defineConfig({
  plugins: [vue()],
  base: '/static/dist/',          // asset URLs in built index.html
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    outDir: '../static/dist',     // relative to frontend/
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 600,
  },
  server: {
    port: 5173,
    proxy: {
      // During `npm run dev`, proxy API calls to the running Flask Hub
      '/api': 'http://localhost:8080',
    },
  },
})
