// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { historyFor } from './state'

describe('assistant history', () => {
  it('drops item references from earlier answers, since each answer numbers them afresh', () => {
    const sent = historyFor([
      { role: 'user', content: 'Việc của tôi?' },
      { role: 'assistant', content: 'Có “Báo cáo quý” @1 và “Kiểm kê” @2.' },
      { role: 'user', content: 'Mail a@3.vn là gì?' },
    ])
    expect(sent[1].content).toBe('Có “Báo cáo quý” và “Kiểm kê” .')
    expect(sent[2].content).toBe('Mail a@3.vn là gì?')
  })
})
