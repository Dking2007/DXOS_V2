// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { defineConfig } from 'vitest/config'
export default defineConfig({
  test: {
    include: ['apps/shared/src/**/*.test.ts', 'apps/workspace-web/src/**/*.test.ts'],
    environment: 'node',
  },
})
