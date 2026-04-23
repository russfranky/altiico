import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  base: process.env.BASE_PATH || "/",
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    allowedHosts: ['.ngrok-free.dev', '.ngrok.io', '.trycloudflare.com', '.hubzz.xyz'],
    proxy: {
      '/avatar-api': {
        target: 'http://localhost:1233',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/avatar-api/, ''),
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 500,
    cssCodeSplit: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          // Vendor: React core (shared across all routes)
          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/')) {
            return 'react-vendor';
          }
          // Router: only needed once shell loads
          if (id.includes('node_modules/react-router')) {
            return 'router';
          }
          // Three.js: heavy 3D engine, only needed for viewer/hero
          if (id.includes('node_modules/three/')) {
            return 'three';
          }
          // VRM: 3D avatar format, only needed for avatar preview
          if (id.includes('node_modules/@pixiv/three-vrm')) {
            return 'vrm';
          }
          // UI libs: radix, lucide icons, CVA, tailwind-merge
          if (
            id.includes('node_modules/radix-ui') ||
            id.includes('node_modules/@base-ui') ||
            id.includes('node_modules/lucide-react') ||
            id.includes('node_modules/class-variance-authority') ||
            id.includes('node_modules/clsx') ||
            id.includes('node_modules/tailwind-merge')
          ) {
            return 'ui-vendor';
          }
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
