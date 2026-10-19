import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: '/console/',
  plugins: [vue()],
  server: { proxy: { '/core': 'http://localhost:8001' } },
  build: { sourcemap: false },
})
