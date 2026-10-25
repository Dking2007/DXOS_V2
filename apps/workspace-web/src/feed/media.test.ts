// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { gridLayout, MAX_MEDIA_BYTES, mediaProblem } from './media'

describe('feed media', () => {
  it('accepts only pictures and videos within the size limit', () => {
    expect(mediaProblem({ type: 'image/jpeg', size: 2000 })).toBeNull()
    expect(mediaProblem({ type: 'video/quicktime', size: 2000 })).toBeNull()
    expect(mediaProblem({ type: 'application/pdf', size: 2000 })).toMatch(/Chỉ đăng được ảnh/)
    expect(mediaProblem({ type: 'image/svg+xml', size: 2000 })).toMatch(/Chỉ đăng được ảnh/)
    expect(mediaProblem({ type: 'image/png', size: MAX_MEDIA_BYTES + 1 })).toBe('Tệp lớn hơn 50 MB.')
    expect(mediaProblem({ type: 'image/png', size: 0 })).toBe('Tệp rỗng.')
  })

  it('shows at most four tiles and counts the rest', () => {
    expect(gridLayout(1)).toEqual({ shown: 1, more: 0, layout: 'count-1' })
    expect(gridLayout(3)).toEqual({ shown: 3, more: 0, layout: 'count-3' })
    expect(gridLayout(7)).toEqual({ shown: 4, more: 3, layout: 'count-4' })
  })
})
