// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { afterEach, describe, expect, it } from 'vitest'
import { answerConfirm, confirmDialog, pendingConfirm } from './confirm'

afterEach(() => answerConfirm(false))

describe('confirmDialog', () => {
  it('resolves true on confirm and false on cancel, then clears the question', async () => {
    const yes = confirmDialog({ message: 'Xóa?', danger: true })
    expect(pendingConfirm.value?.message).toBe('Xóa?')
    answerConfirm(true)
    await expect(yes).resolves.toBe(true)
    expect(pendingConfirm.value).toBeNull()

    const no = confirmDialog('Xóa?')
    answerConfirm(false)
    await expect(no).resolves.toBe(false)
  })

  it('treats a newer question as "no" to the older one', async () => {
    const first = confirmDialog('một')
    const second = confirmDialog('hai')
    await expect(first).resolves.toBe(false)
    expect(pendingConfirm.value?.message).toBe('hai')
    answerConfirm(true)
    await expect(second).resolves.toBe(true)
  })

  it('answering with nothing open is harmless', () => {
    expect(() => answerConfirm(true)).not.toThrow()
  })
})
