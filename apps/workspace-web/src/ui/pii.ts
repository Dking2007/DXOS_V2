// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// The warning shown when a file's text looks like it holds personal identifiers.
const LABELS: Record<string, string> = {
  CCCD: 'số CCCD',
  CMND: 'số CMND',
  PHONE: 'số điện thoại',
  BANK_ACCOUNT: 'số tài khoản',
  TAX_CODE: 'mã số thuế',
  EMAIL: 'địa chỉ e-mail',
}

/** "2 số CCCD, 1 số điện thoại", or an empty string when nothing was found. */
export function piiSummary(counts: Record<string, number>): string {
  return Object.entries(counts)
    .filter(([, n]) => n > 0)
    .map(([kind, n]) => `${n} ${LABELS[kind] ?? kind}`)
    .join(', ')
}
