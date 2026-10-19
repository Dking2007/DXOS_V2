import { describe, expect, it } from 'vitest'
import { fieldKey, initialPayload, validatePayload } from './forms'
import type { FormField } from './types'
const fields: FormField[] = [
  { key: 'title', label: 'Tiêu đề', type: 'text', required: true },
  { key: 'amount', label: 'Số tiền', type: 'number', required: true },
  { key: 'date', label: 'Ngày', type: 'date' },
  { key: 'kind', label: 'Loại', type: 'select', options: ['A', 'B'] },
  { key: 'confirm', label: 'Xác nhận', type: 'checkbox', required: true },
]
describe('schema renderer data validation', () => {
  it('creates typed defaults without shared state', () => {
    expect(initialPayload(fields)).toEqual({
      title: '',
      amount: null,
      date: '',
      kind: '',
      confirm: false,
    })
    const first = initialPayload(fields)
    first.title = 'changed'
    expect(initialPayload(fields).title).toBe('')
  })
  it('accepts zero and rejects unchecked required confirmation', () => {
    const errors = validatePayload(fields, {
      title: 'Đề nghị',
      amount: 0,
      confirm: false,
    })
    expect(errors.amount).toBeUndefined()
    expect(errors.confirm).toBeDefined()
  })
  it('rejects invalid number, select and date values', () => {
    const errors = validatePayload(fields, {
      title: 'Đề nghị',
      amount: '100',
      date: 'not-date',
      kind: 'C',
      confirm: true,
    })
    expect(Object.keys(errors).sort()).toEqual(['amount', 'date', 'kind'])
  })
  it('accepts a complete valid payload', () => {
    expect(
      validatePayload(fields, {
        title: 'Đề nghị',
        amount: 100,
        date: '2026-10-18',
        kind: 'B',
        confirm: true,
      }),
    ).toEqual({})
  })
  it('creates stable ASCII keys for Vietnamese labels', () => {
    expect(fieldKey('Đề nghị phê duyệt')).toBe('de_nghi_phe_duyet')
    expect(fieldKey('  Số tiền (VNĐ)  ')).toBe('so_tien_vnd')
  })
})
