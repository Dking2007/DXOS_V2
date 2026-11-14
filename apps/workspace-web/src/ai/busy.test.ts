// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { isAiCall } from '../api'

describe('slow AI notice', () => {
  it('counts calls that wait on a model, not settings or plain reads', () => {
    expect(isAiCall('/ai/cases/c1/summary', 'POST')).toBe(true)
    expect(isAiCall('/assistant/chat', 'POST')).toBe(true)
    expect(isAiCall('/assistant/providers/p1/test', 'POST')).toBe(true)
    expect(isAiCall('/ai/cases/c1/summary', 'GET')).toBe(false)
    expect(isAiCall('/ai/settings', 'PUT')).toBe(false)
    expect(isAiCall('/ai/index', 'POST')).toBe(false)
    expect(isAiCall('/tasks', 'POST')).toBe(false)
  })
})
