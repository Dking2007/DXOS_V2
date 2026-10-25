// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
//
// Tạo nhãn, milestone và issue từ docs/issues-backlog.json trên GitHub.
//   GITHUB_TOKEN=... node scripts/create_issues.mjs [--dry-run]
// Token cần quyền Issues: write (fine-grained) hoặc scope `repo`. Không lưu token vào repo.
import { readFileSync } from 'node:fs'

const REPO = process.env.GITHUB_REPOSITORY ?? 'Raphael-Fug/DXOS_V2'
const dry = process.argv.includes('--dry-run')
const token = process.env.GITHUB_TOKEN
if (!dry && !token) {
  console.error('Thiếu GITHUB_TOKEN (hoặc dùng --dry-run).')
  process.exit(1)
}
const data = JSON.parse(readFileSync('docs/issues-backlog.json', 'utf8'))

const api = async (method, path, body) => {
  if (dry) {
    console.log(method, path, body ? JSON.stringify(body).slice(0, 90) : '')
    return { number: 0, ok: true }
  }
  const res = await fetch(`https://api.github.com/repos/${REPO}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok && res.status !== 422) throw new Error(`${method} ${path}: ${res.status} ${JSON.stringify(json)}`)
  return { ...json, ok: res.ok }
}

for (const l of data.labels) await api('POST', '/labels', l)

const milestoneNumbers = []
for (const m of data.milestones) {
  const r = await api('POST', '/milestones', { title: m.title, due_on: `${m.due}T23:59:59Z` })
  milestoneNumbers.push(r.number)
}
if (!dry) {
  const all = await api('GET', '/milestones?state=all&per_page=100')
  for (const [i, m] of data.milestones.entries()) {
    milestoneNumbers[i] = (Array.isArray(all) ? all : []).find((x) => x.title === m.title)?.number ?? milestoneNumbers[i]
  }
}

for (const i of data.issues) {
  const body = i.ref ? `${i.body}\n\nCommit liên quan: ${i.ref}` : i.body
  const created = await api('POST', '/issues', {
    title: i.title, body, labels: i.labels, milestone: milestoneNumbers[i.milestone],
  })
  if (i.state === 'closed') await api('PATCH', `/issues/${created.number}`, { state: 'closed', state_reason: 'completed' })
  console.log(`${i.state === 'closed' ? 'đã đóng' : 'đang mở'}: ${i.title}`)
}
