// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { caseTone } from './caseFolder'

describe('case folder tone', () => {
  it('follows the status', () => {
    expect(caseTone('processing')).toBe('moving')
    expect(caseTone('needs_revision')).toBe('attention')
    expect(caseTone('approved')).toBe('done')
    expect(caseTone('rejected')).toBe('stopped')
    expect(caseTone('something_new')).toBe('draft')
  })
  it('puts archived dossiers on the archive shelf whatever their result', () => {
    expect(caseTone('approved', '2026-11-01T00:00:00Z')).toBe('archived')
  })
})
