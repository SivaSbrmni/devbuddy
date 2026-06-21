import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiUrl = env.VITE_API_URL || ''
  return {
    plugins: [react()],
    define: {
      'import.meta.env.VITE_API_URL': JSON.stringify(apiUrl),
    },
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
  }
})
