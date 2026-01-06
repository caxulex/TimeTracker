import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api/ws': {
        target: 'ws://localhost:8000',
        changeOrigin: true,
        ws: true,
        rewriteWsOrigin: true,
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    // Chunk splitting for optimal caching
    rollupOptions: {
      output: {
        manualChunks: {
          // Core React libraries (rarely changes)
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          // Data fetching (rarely changes)
          'vendor-query': ['@tanstack/react-query', 'axios'],
          // UI utilities
          'vendor-utils': ['date-fns', 'zod', 'zustand'],
          // Charts (large, lazy loaded when needed)
          'vendor-charts': ['recharts'],
          // Icons (loaded on demand)
          'vendor-icons': ['lucide-react'],
        },
      },
    },
    // Increase chunk size warning limit slightly
    chunkSizeWarningLimit: 600,
  },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
})

