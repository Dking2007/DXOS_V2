// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { piiSummary } from './pii'

describe('personal data warning', () => {
  it('names each kind with its count and skips empty ones', () => {
    expect(piiSummary({ CCCD: 2, PHONE: 1, EMAIL: 0 })).toBe('2 số CCCD, 1 số điện thoại')
    expect(piiSummary({})).toBe('')
  })
})
