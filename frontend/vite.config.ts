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
    rollupOptions: {
      output: {
        // Split the always-eager framework vendors into stable chunks so
        // returning users cache them across deploys instead of re-downloading
        // the whole bundle. Only vendors that are PROVABLY eager belong here —
        // manually chunking an async-only dep (recharts, zxing) would promote
        // it into the initial graph and defeat its lazy load. recharts rides
        // its lazy Analytics chunk; zxing self-splits via dynamic import().
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('framer-motion')) return 'vendor-motion'      // App.tsx top-level
          if (id.includes('socket.io') || id.includes('engine.io')) return 'vendor-socket'  // useJobSync
          if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('/scheduler/')) return 'vendor-react'
        },
      },
    },
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
