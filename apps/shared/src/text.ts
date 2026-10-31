// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Text matching that ignores case and Vietnamese accents, the same rule the server's search uses.

/** Lower case without accents: "Đề xuất" becomes "de xuat". */
export function fold(value: string): string {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd')
}

/** Whether `needle` occurs in `text`; "bao cao" finds "Báo cáo". */
export function textMatches(text: string, needle: string): boolean {
  return fold(text).includes(fold(needle.trim()))
}
