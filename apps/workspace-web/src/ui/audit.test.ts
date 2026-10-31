// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
import { describe, expect, it } from 'vitest'
import { auditKnown, auditLabel, auditLink } from './audit'

// Every action the backend records, so a new one cannot ship with a raw code as its label.
const sources = import.meta.glob('../../../../services/workspace-api/src/dx_workspace/*.py', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

describe('audit log text', () => {
  it('names the record and what was done', () => {
    expect(auditLabel('case.submitted')).toBe('Hồ sơ: trình duyệt')
    expect(auditLabel('assistant.provider_activated')).toBe('Trợ lý AI: chọn dịch vụ AI')
  })

  it('links only to records that have a page', () => {
    expect(auditLink('case.created', 'c1')).toBe('/cases/c1')
    expect(auditLink('role.updated', 'staff')).toBeNull()
  })

  it('has a label for every action the backend records', () => {
    const actions = new Set<string>()
    for (const text of Object.values(sources)) {
      for (const match of text.matchAll(/audit\(\s*db,\s*\w+,\s*"([a-z_]+\.[a-z_]+)"/g)) actions.add(match[1])
    }
    // Task transitions are recorded as "task." + action.
    for (const action of ['accept', 'start', 'submit', 'complete', 'return', 'block', 'unblock', 'cancel'])
      actions.add('task.' + action)
    expect(actions.size).toBeGreaterThan(20)
    expect([...actions].filter((action) => !auditKnown(action))).toEqual([])
  })
})
