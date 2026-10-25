// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it, vi } from 'vitest'
import { badgeText, visibleGroups } from './nav'
import { PERMISSION_GROUPS, PERMISSIONS, permissionLabel, roleLabel } from './labels'
import { stepsFor } from './tour'
// The backend's role templates are the source of truth for which permission codes exist.
import policies from '../../../../services/workspace-api/src/dx_workspace/policies.py?raw'

describe('navigation', () => {
  it('hides admin screens from people without the capability', () => {
    const staff = visibleGroups(() => false).flatMap((group) => group.links.map((link) => link.to))
    expect(staff).toContain('/tasks')
    expect(staff).toContain('/settings')
    expect(staff).not.toContain('/automations')
    expect(staff).not.toContain('/packages')
    const admin = visibleGroups(() => true).flatMap((group) => group.links.map((link) => link.to))
    expect(admin).toContain('/automations')
  })

  it('counts badges from the overview and caps the text', () => {
    const tasks = visibleGroups(() => true)
      .flatMap((group) => group.links)
      .find((link) => link.to === '/tasks')!
    expect(tasks.badge!({ tasks: 2, tasks_to_review: 3, approvals: 0, notifications: 0, chat: 0 })).toBe(5)
    expect(badgeText(0)).toBe('')
    expect(badgeText(7)).toBe('7')
    expect(badgeText(250)).toBe('99+')
  })
})

describe('plain-language labels', () => {
  it('names every permission the Workspace API can grant', () => {
    const templates = policies.slice(policies.indexOf('ROLE_TEMPLATES'), policies.indexOf('ALLOWED_PERMISSIONS'))
    const codes = new Set((templates.match(/"[a-z_]+\.[a-z_.]+"/g) ?? []).map((code: string) => code.slice(1, -1)))
    expect(codes.size).toBeGreaterThan(5)
    for (const code of codes) expect(PERMISSIONS[code], code).toBeDefined()
    for (const info of Object.values(PERMISSIONS)) expect(PERMISSION_GROUPS).toContain(info.group)
  })

  it('falls back to the raw code or the staff role for unknown values', () => {
    expect(permissionLabel('cases.create')).toBe('Tạo và trình hồ sơ')
    expect(permissionLabel('future.thing')).toBe('future.thing')
    expect(roleLabel('director')).toBe('Ban giám đốc')
    expect(roleLabel(undefined)).toBe('Cán bộ / nhân viên')
  })
})

describe('onboarding tour', () => {
  it('adds role-specific steps after the shared introduction', () => {
    const staff = stepsFor('staff')
    const admin = stepsFor('technical_admin')
    expect(staff[0].title).toBe(admin[0].title)
    expect(staff.at(-1)!.target).toBe('agenda')
    expect(admin.at(-1)!.target).toBe('nav-admin')
    expect(stepsFor('unknown')).toEqual(staff)
  })
})

describe('toasts', () => {
  it('keeps at most four and dismisses them after a while', async () => {
    vi.useFakeTimers()
    const { toast, toasts } = await import('./toast')
    for (let i = 0; i < 6; i++) toast.success(`Việc ${i}`)
    expect(toasts.map((item) => item.text)).toEqual(['Việc 2', 'Việc 3', 'Việc 4', 'Việc 5'])
    toast.error('Lỗi')
    vi.advanceTimersByTime(4100)
    expect(toasts.map((item) => item.kind)).toEqual(['error'])
    vi.advanceTimersByTime(4000)
    expect(toasts).toHaveLength(0)
    vi.useRealTimers()
  })
})
