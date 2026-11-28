// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// Builds PeoplePicker options from plain user / department lists.
import type { PickerOption } from './filter'

/** A "none" choice shown first (empty value). */
export function noneOption(label: string): PickerOption {
  return { value: '', label, group: '', kind: 'special' }
}

export function userOptions(users: { id: string; display_name: string }[], none?: string): PickerOption[] {
  const list = users.map<PickerOption>((u) => ({ value: u.id, label: u.display_name, group: 'Cá nhân', kind: 'user', userId: u.id }))
  return none ? [noneOption(none), ...list] : list
}

export function departmentOptions(departments: { id: string; name: string }[], none?: string): PickerOption[] {
  const list = departments.map<PickerOption>((d) => ({ value: d.id, label: d.name, group: 'Đơn vị', kind: 'dept' }))
  return none ? [noneOption(none), ...list] : list
}

/** PeoplePicker emits string | string[]; a single picker always emits a string. */
export function asText(value: string | string[]): string {
  return Array.isArray(value) ? (value[0] ?? '') : value
}
