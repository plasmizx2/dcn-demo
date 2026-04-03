import { defineConfig } from 'vite'
import path from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  // File types to support raw imports. Never add .css, .tsx, or .ts files to this.
  assetsInclude: ['**/*.svg', '**/*.csv'],

  // Proxy API calls to FastAPI backend during development
  server: {
    port: 3000,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/jobs': 'http://localhost:8000',
      '/monitor': 'http://localhost:8000',
      '/workers': 'http://localhost:8000',
      '/tasks': 'http://localhost:8000',
      '/stats': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/datasets': 'http://localhost:8000',
      '/bugs': 'http://localhost:8000',
      '/contact': 'http://localhost:8000',
    },
  },

  // Build output goes to dist/ — FastAPI serves this in production
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
