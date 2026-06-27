/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { fileURLToPath } from 'url'
import { VitePWA } from 'vite-plugin-pwa'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  base: mode === 'production' ? '/app/' : '/',
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      registerType: 'autoUpdate',
      manifest: false, // Use existing public/manifest.json
      includeAssets: ['offline.html', 'icons/*.png'],
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
      },
      devOptions: {
        enabled: false,
        type: 'module',
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: '../static/app',
    emptyOutDir: true,
  },
  server: {
    host: true,
    port: parseInt(process.env.PORT || '5175'),
    hmr: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/socket.io': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      // Report stays broad so untested modules (pwa.ts, offlineQueue.ts,
      // status.ts, categories.ts — all 0% today) remain VISIBLE as future work,
      // not hidden by a narrow include.
      include: ['src/lib/**', 'src/store/**'],
      thresholds: {
        // Soft floor set just under current actuals (Phase A): fails CI only on
        // a real regression. Ratchet these up as Phases B/C add coverage.
        statements: 40,
        branches: 60,
        functions: 20,
        lines: 40,
      },
    },
  },
  optimizeDeps: {
    exclude: ['@dnd-kit/core', '@dnd-kit/sortable', '@dnd-kit/utilities']
  }
}))
