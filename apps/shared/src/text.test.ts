// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { fold, textMatches } from './text'

describe('accent-insensitive matching', () => {
  it('drops accents and case, including Đ', () => {
    expect(fold('Đề xuất MUA SẮM')).toBe('de xuat mua sam')
  })

  it('finds accented text from a plain query and the other way round', () => {
    expect(textMatches('Báo cáo quý III', 'bao cao')).toBe(true)
    expect(textMatches('bao cao quy III', 'Báo cáo')).toBe(true)
    expect(textMatches('Báo cáo', 'bảo')).toBe(true)
    expect(textMatches('Kế hoạch', 'bao')).toBe(false)
  })
})
