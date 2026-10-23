import { describe, expect, it } from 'vitest'
import {
  choicesFrom,
  conditionText,
  decisionsFor,
  pathStops,
  readiness,
  resolverText,
} from './model'
import type { PackageVersion, Report, Suite } from './model'

const fields = [{ key: 'amount', label: 'Kinh phí', type: 'number' as const }]

describe('package labels', () => {
  it('reads conditions with field labels and Vietnamese numbers', () => {
    expect(conditionText({ field: 'amount', operator: 'gt', value: 50000000 }, fields)).toBe(
      'Kinh phí > 50.000.000',
    )
    expect(conditionText({ field: 'urgent', operator: 'eq', value: true }, fields)).toBe('urgent = Có')
  })

  it('names who approves a step', () => {
    const name = (id: string) => (id === 'u1' ? 'An' : id)
    expect(resolverText({ label: 'A', resolver: 'department_manager' }, name)).toBe(
      'Lãnh đạo phòng của người trình',
    )
    expect(resolverText({ label: 'B', resolver: 'user', user_id: 'u1' }, name)).toBe('An')
  })

  it('turns engine node ids into the steps people configured, skipping gates', () => {
    const stops = pathStops(['start', 'review_0', 'continue_0', 'review_1', 'end'], ['Trưởng phòng', 'Giám đốc'])
    expect(stops.map((s) => s.label)).toEqual(['Bắt đầu', 'Trưởng phòng', 'Giám đốc', 'Hoàn tất'])
  })

  it('keys simulated decisions by approval position and reads them back', () => {
    const decisions = decisionsFor(['approve', 'reject'])
    expect(decisions).toEqual({ review_0: { decision: 'approve' }, review_1: { decision: 'reject' } })
    expect(choicesFrom(decisions, 3)).toEqual(['approve', 'reject', 'approve'])
  })
})

describe('publish readiness', () => {
  const version = { state: 'validated', config_hash: 'h2' } as PackageVersion
  const suite = (id: string, hash = 'h2') => ({ id, config_hash: hash, cases: [], created_at: '' }) as Suite
  const report = (suite_id: string, passed: boolean, created_at: string, hash = 'h2') =>
    ({ id: suite_id + created_at, suite_id, passed, created_at, config_hash: hash, results: [] }) as Report

  it('needs every current suite to pass on its latest run', () => {
    expect(readiness(version, [], []).blocker).toMatch(/bộ kịch bản/)
    const suites = [suite('a'), suite('b')]
    expect(readiness(version, suites, [report('a', true, '1')]).canPublish).toBe(false)
    const passing = [report('a', true, '1'), report('b', false, '1'), report('b', true, '2')]
    expect(readiness(version, suites, passing).canPublish).toBe(true)
    // A later failing run outweighs an earlier pass.
    expect(readiness(version, suites, [...passing, report('a', false, '3')]).canPublish).toBe(false)
  })

  it('ignores suites and reports made for another configuration', () => {
    const result = readiness(version, [suite('old', 'h1')], [report('old', true, '1', 'h1')])
    expect(result.hasSuites).toBe(false)
    expect(readiness({ ...version, state: 'draft' }, [], []).blocker).toBe('Kiểm tra cấu hình trước.')
  })
})
