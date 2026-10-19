import { defineConfig } from 'vitest/config'
export default defineConfig({
  test: { include: ['apps/shared/src/**/*.test.ts'], environment: 'node' },
})
