import type { FormField } from './types'

export function initialPayload(fields: FormField[]): Record<string, unknown> {
  return Object.fromEntries(
    fields.map((field) => [
      field.key,
      field.type === 'checkbox' ? false : field.type === 'number' ? null : '',
    ]),
  )
}

export function validatePayload(
  fields: FormField[],
  payload: Record<string, unknown>,
): Record<string, string> {
  const errors: Record<string, string> = {}
  for (const field of fields) {
    const value = payload[field.key]
    if (
      field.required &&
      (value === undefined ||
        value === null ||
        value === '' ||
        (field.type === 'checkbox' && value !== true))
    ) {
      errors[field.key] = `Nhập ${field.label.toLocaleLowerCase('vi-VN')}.`
      continue
    }
    if (value === undefined || value === null || value === '') continue
    if (
      field.type === 'number' &&
      (typeof value !== 'number' || !Number.isFinite(value))
    )
      errors[field.key] = 'Nhập một số hợp lệ.'
    if (field.type === 'select' && !field.options?.includes(String(value)))
      errors[field.key] = 'Chọn một giá trị trong danh sách.'
    if (
      field.type === 'date' &&
      (typeof value !== 'string' ||
        !/^\d{4}-\d{2}-\d{2}$/.test(value) ||
        Number.isNaN(Date.parse(value)))
    )
      errors[field.key] = 'Nhập ngày hợp lệ.'
  }
  return errors
}

export function fieldKey(label: string): string {
  return label
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
}
