/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { fileURLToPath } from 'url'
// import { VitePWA } from 'vite-plugin-pwa' // Temporarily disabled for MVP build

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  base: '/app/',
  plugins: [
    react(),
    tailwindcss(),
    // VitePWA plugin temporarily disabled to fix build errors
    // VitePWA({
    //   registerType: 'autoUpdate',
    //   includeAssets: ['offline.html', 'icons/*.png'],
    //   manifest: {
    //     short_name: "DraftCmdr",
    //     name: "eBay Draft Commander",
    //     description: "Manage your eBay listings with AI-powered automation",
    //     icons: [
    //       {
    //         src: "icons/icon-192.png",
    //         type: "image/png",
    //         sizes: "192x192",
    //         purpose: "any maskable"
    //       },
    //       {
    //         src: "icons/icon-512.png",
    //         type: "image/png",
    //         sizes: "512x512",
    //         purpose: "any maskable"
    //       }
    //     ],
    //     start_url: "/app",
    //     background_color: "#0F172A",
    //     display: "standalone",
    //     scope: "/",
    //     theme_color: "#3B82F6",
    //     orientation: "portrait-primary",
    //     categories: ["productivity", "business"],
    //     prefer_related_applications: false
    //   }
    // })
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
    port: 5175,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
    },
  },
  // @ts-expect-error vitest types not automatically inferred
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
  },
})
