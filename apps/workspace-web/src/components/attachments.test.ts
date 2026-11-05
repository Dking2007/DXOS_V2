// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { mergeIds } from './attachments'

describe('attaching files', () => {
  it('keeps the existing order and ignores files attached twice', () => {
    expect(mergeIds(['a', 'b'], ['b', 'c', 'c'])).toEqual(['a', 'b', 'c'])
    expect(mergeIds([], [])).toEqual([])
  })
})
