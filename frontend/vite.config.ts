import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Vendor: React + router (~150KB)
          'vendor': ['react', 'react-dom', 'react-router-dom'],
          // Markdown: Heavy parsing libs (~120KB)
          'markdown': ['react-markdown', 'remark-gfm'],
          // Utils: JSZip + other heavy deps (~80KB)
          'utils': ['jszip'],
        },
      },
    },
    chunkSizeWarningLimit: 500,
  },
})
