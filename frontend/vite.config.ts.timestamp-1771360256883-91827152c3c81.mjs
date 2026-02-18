// vite.config.ts
import { defineConfig } from "file:///C:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander/frontend/node_modules/vite/dist/node/index.js";
import react from "file:///C:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander/frontend/node_modules/@vitejs/plugin-react/dist/index.js";
import tailwindcss from "file:///C:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander/frontend/node_modules/@tailwindcss/vite/dist/index.mjs";
import path from "path";
import { fileURLToPath } from "url";
var __vite_injected_original_import_meta_url = "file:///C:/Users/adam/OneDrive/Documents/Desktop/Development/projects/ebay-draft-commander/frontend/vite.config.ts";
var __dirname = path.dirname(fileURLToPath(__vite_injected_original_import_meta_url));
var vite_config_default = defineConfig({
  plugins: [
    react(),
    tailwindcss()
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
      "@": path.resolve(__dirname, "./src")
    }
  },
  build: {
    outDir: "../static/app",
    emptyOutDir: true
  },
  server: {
    host: true,
    port: 5175,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5001",
        changeOrigin: true
      }
    }
  },
  // @ts-expect-error vitest types not automatically inferred
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcudHMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCJDOlxcXFxVc2Vyc1xcXFxhZGFtXFxcXE9uZURyaXZlXFxcXERvY3VtZW50c1xcXFxEZXNrdG9wXFxcXERldmVsb3BtZW50XFxcXHByb2plY3RzXFxcXGViYXktZHJhZnQtY29tbWFuZGVyXFxcXGZyb250ZW5kXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ZpbGVuYW1lID0gXCJDOlxcXFxVc2Vyc1xcXFxhZGFtXFxcXE9uZURyaXZlXFxcXERvY3VtZW50c1xcXFxEZXNrdG9wXFxcXERldmVsb3BtZW50XFxcXHByb2plY3RzXFxcXGViYXktZHJhZnQtY29tbWFuZGVyXFxcXGZyb250ZW5kXFxcXHZpdGUuY29uZmlnLnRzXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ltcG9ydF9tZXRhX3VybCA9IFwiZmlsZTovLy9DOi9Vc2Vycy9hZGFtL09uZURyaXZlL0RvY3VtZW50cy9EZXNrdG9wL0RldmVsb3BtZW50L3Byb2plY3RzL2ViYXktZHJhZnQtY29tbWFuZGVyL2Zyb250ZW5kL3ZpdGUuY29uZmlnLnRzXCI7Ly8vIDxyZWZlcmVuY2UgdHlwZXM9XCJ2aXRlc3RcIiAvPlxuaW1wb3J0IHsgZGVmaW5lQ29uZmlnIH0gZnJvbSAndml0ZSdcbmltcG9ydCByZWFjdCBmcm9tICdAdml0ZWpzL3BsdWdpbi1yZWFjdCdcbmltcG9ydCB0YWlsd2luZGNzcyBmcm9tICdAdGFpbHdpbmRjc3Mvdml0ZSdcbmltcG9ydCBwYXRoIGZyb20gJ3BhdGgnXG5pbXBvcnQgeyBmaWxlVVJMVG9QYXRoIH0gZnJvbSAndXJsJ1xuLy8gaW1wb3J0IHsgVml0ZVBXQSB9IGZyb20gJ3ZpdGUtcGx1Z2luLXB3YScgLy8gVGVtcG9yYXJpbHkgZGlzYWJsZWQgZm9yIE1WUCBidWlsZFxuXG5jb25zdCBfX2Rpcm5hbWUgPSBwYXRoLmRpcm5hbWUoZmlsZVVSTFRvUGF0aChpbXBvcnQubWV0YS51cmwpKVxuXG4vLyBodHRwczovL3ZpdGUuZGV2L2NvbmZpZy9cbmV4cG9ydCBkZWZhdWx0IGRlZmluZUNvbmZpZyh7XG4gIHBsdWdpbnM6IFtcbiAgICByZWFjdCgpLFxuICAgIHRhaWx3aW5kY3NzKCksXG4gICAgLy8gVml0ZVBXQSBwbHVnaW4gdGVtcG9yYXJpbHkgZGlzYWJsZWQgdG8gZml4IGJ1aWxkIGVycm9yc1xuICAgIC8vIFZpdGVQV0Eoe1xuICAgIC8vICAgcmVnaXN0ZXJUeXBlOiAnYXV0b1VwZGF0ZScsXG4gICAgLy8gICBpbmNsdWRlQXNzZXRzOiBbJ29mZmxpbmUuaHRtbCcsICdpY29ucy8qLnBuZyddLFxuICAgIC8vICAgbWFuaWZlc3Q6IHtcbiAgICAvLyAgICAgc2hvcnRfbmFtZTogXCJEcmFmdENtZHJcIixcbiAgICAvLyAgICAgbmFtZTogXCJlQmF5IERyYWZ0IENvbW1hbmRlclwiLFxuICAgIC8vICAgICBkZXNjcmlwdGlvbjogXCJNYW5hZ2UgeW91ciBlQmF5IGxpc3RpbmdzIHdpdGggQUktcG93ZXJlZCBhdXRvbWF0aW9uXCIsXG4gICAgLy8gICAgIGljb25zOiBbXG4gICAgLy8gICAgICAge1xuICAgIC8vICAgICAgICAgc3JjOiBcImljb25zL2ljb24tMTkyLnBuZ1wiLFxuICAgIC8vICAgICAgICAgdHlwZTogXCJpbWFnZS9wbmdcIixcbiAgICAvLyAgICAgICAgIHNpemVzOiBcIjE5MngxOTJcIixcbiAgICAvLyAgICAgICAgIHB1cnBvc2U6IFwiYW55IG1hc2thYmxlXCJcbiAgICAvLyAgICAgICB9LFxuICAgIC8vICAgICAgIHtcbiAgICAvLyAgICAgICAgIHNyYzogXCJpY29ucy9pY29uLTUxMi5wbmdcIixcbiAgICAvLyAgICAgICAgIHR5cGU6IFwiaW1hZ2UvcG5nXCIsXG4gICAgLy8gICAgICAgICBzaXplczogXCI1MTJ4NTEyXCIsXG4gICAgLy8gICAgICAgICBwdXJwb3NlOiBcImFueSBtYXNrYWJsZVwiXG4gICAgLy8gICAgICAgfVxuICAgIC8vICAgICBdLFxuICAgIC8vICAgICBzdGFydF91cmw6IFwiL2FwcFwiLFxuICAgIC8vICAgICBiYWNrZ3JvdW5kX2NvbG9yOiBcIiMwRjE3MkFcIixcbiAgICAvLyAgICAgZGlzcGxheTogXCJzdGFuZGFsb25lXCIsXG4gICAgLy8gICAgIHNjb3BlOiBcIi9cIixcbiAgICAvLyAgICAgdGhlbWVfY29sb3I6IFwiIzNCODJGNlwiLFxuICAgIC8vICAgICBvcmllbnRhdGlvbjogXCJwb3J0cmFpdC1wcmltYXJ5XCIsXG4gICAgLy8gICAgIGNhdGVnb3JpZXM6IFtcInByb2R1Y3Rpdml0eVwiLCBcImJ1c2luZXNzXCJdLFxuICAgIC8vICAgICBwcmVmZXJfcmVsYXRlZF9hcHBsaWNhdGlvbnM6IGZhbHNlXG4gICAgLy8gICB9XG4gICAgLy8gfSlcbiAgXSxcbiAgcmVzb2x2ZToge1xuICAgIGFsaWFzOiB7XG4gICAgICAnQCc6IHBhdGgucmVzb2x2ZShfX2Rpcm5hbWUsICcuL3NyYycpLFxuICAgIH0sXG4gIH0sXG4gIGJ1aWxkOiB7XG4gICAgb3V0RGlyOiAnLi4vc3RhdGljL2FwcCcsXG4gICAgZW1wdHlPdXREaXI6IHRydWUsXG4gIH0sXG4gIHNlcnZlcjoge1xuICAgIGhvc3Q6IHRydWUsXG4gICAgcG9ydDogNTE3NSxcbiAgICBwcm94eToge1xuICAgICAgJy9hcGknOiB7XG4gICAgICAgIHRhcmdldDogJ2h0dHA6Ly8xMjcuMC4wLjE6NTAwMScsXG4gICAgICAgIGNoYW5nZU9yaWdpbjogdHJ1ZSxcbiAgICAgIH0sXG4gICAgfSxcbiAgfSxcbiAgLy8gQHRzLWV4cGVjdC1lcnJvciB2aXRlc3QgdHlwZXMgbm90IGF1dG9tYXRpY2FsbHkgaW5mZXJyZWRcbiAgdGVzdDoge1xuICAgIGdsb2JhbHM6IHRydWUsXG4gICAgZW52aXJvbm1lbnQ6ICdqc2RvbScsXG4gICAgc2V0dXBGaWxlczogJy4vc3JjL3Rlc3Qvc2V0dXAudHMnLFxuICAgIGNzczogdHJ1ZSxcbiAgfSxcbn0pXG4iXSwKICAibWFwcGluZ3MiOiAiO0FBQ0EsU0FBUyxvQkFBb0I7QUFDN0IsT0FBTyxXQUFXO0FBQ2xCLE9BQU8saUJBQWlCO0FBQ3hCLE9BQU8sVUFBVTtBQUNqQixTQUFTLHFCQUFxQjtBQUxtUixJQUFNLDJDQUEyQztBQVFsVyxJQUFNLFlBQVksS0FBSyxRQUFRLGNBQWMsd0NBQWUsQ0FBQztBQUc3RCxJQUFPLHNCQUFRLGFBQWE7QUFBQSxFQUMxQixTQUFTO0FBQUEsSUFDUCxNQUFNO0FBQUEsSUFDTixZQUFZO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBLEVBaUNkO0FBQUEsRUFDQSxTQUFTO0FBQUEsSUFDUCxPQUFPO0FBQUEsTUFDTCxLQUFLLEtBQUssUUFBUSxXQUFXLE9BQU87QUFBQSxJQUN0QztBQUFBLEVBQ0Y7QUFBQSxFQUNBLE9BQU87QUFBQSxJQUNMLFFBQVE7QUFBQSxJQUNSLGFBQWE7QUFBQSxFQUNmO0FBQUEsRUFDQSxRQUFRO0FBQUEsSUFDTixNQUFNO0FBQUEsSUFDTixNQUFNO0FBQUEsSUFDTixPQUFPO0FBQUEsTUFDTCxRQUFRO0FBQUEsUUFDTixRQUFRO0FBQUEsUUFDUixjQUFjO0FBQUEsTUFDaEI7QUFBQSxJQUNGO0FBQUEsRUFDRjtBQUFBO0FBQUEsRUFFQSxNQUFNO0FBQUEsSUFDSixTQUFTO0FBQUEsSUFDVCxhQUFhO0FBQUEsSUFDYixZQUFZO0FBQUEsSUFDWixLQUFLO0FBQUEsRUFDUDtBQUNGLENBQUM7IiwKICAibmFtZXMiOiBbXQp9Cg==
