// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: '/console/',
  plugins: [vue()],
  server: { proxy: { '/core': 'http://localhost:8001' } },
  build: { sourcemap: false },
})
