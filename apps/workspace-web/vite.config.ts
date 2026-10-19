import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/workspace': 'http://localhost:8002',
      '/core': 'http://localhost:8001',
    },
  },
  build: { sourcemap: false },
})
