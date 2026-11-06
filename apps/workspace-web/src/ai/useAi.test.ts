// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { ALL_FEATURES, RECOMMENDED_FEATURES } from './useAi'
// The backend registry is the source of truth for which AI features exist.
import core from '../../../../services/workspace-api/src/dx_workspace/ai_core.py?raw'

describe('AI feature list', () => {
  it('matches the features the server knows', () => {
    const block = core.slice(core.indexOf('FEATURES = {'), core.indexOf('}  # fmt: skip'))
    const server = [...block.matchAll(/^ {4}"([a-z_]+)": \(/gm)].map((m) => m[1])
    expect(server).toEqual(ALL_FEATURES)
  })

  it('recommends only features that read what people already see', () => {
    expect(RECOMMENDED_FEATURES).toHaveLength(13)
    expect(RECOMMENDED_FEATURES).not.toContain('assistant_my_data')
    expect(RECOMMENDED_FEATURES).not.toContain('automation_ai')
  })
})
