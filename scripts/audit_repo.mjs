// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
//
// Kiểm vệ sinh kho: không để secret, bản dump hay image không ghim phiên bản vào Git.
//
//   node scripts/audit_repo.mjs
//
// Thoát 1 nếu có vi phạm. Chỉ kiểm tệp Git đang theo dõi.
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'

const tracked = execFileSync('git', ['ls-files', '-z'], { encoding: 'utf8' }).split('\0').filter(Boolean)
const problems = []

const forbidden = [
  [/(^|\/)\.env(\..+)?$/, 'tệp môi trường', /\.example$/],
  [/\.(pem|key|p12|pfx)$/i, 'khóa hoặc chứng chỉ riêng'],
  [/\.(dump|bak)$/i, 'bản dump hoặc sao lưu'],
  [/\.sql\.gz$/i, 'bản dump nén'],
  [/^infra\/identity\/generated\//, 'cấu hình định danh sinh tự động (chứa credential)'],
]
for (const file of tracked) {
  for (const [pattern, label, allow] of forbidden) {
    if (pattern.test(file) && !(allow && allow.test(file))) problems.push(`${file}: ${label} không được theo dõi bởi Git`)
  }
}

const composeFiles = tracked.filter((f) => /(^|\/)(docker-)?compose[^/]*\.ya?ml$/.test(f))
for (const file of composeFiles) {
  readFileSync(file, 'utf8')
    .split('\n')
    .forEach((line, index) => {
      const match = line.match(/^\s*image:\s*["']?([^\s"'#]+)/)
      if (!match) return
      const ref = match[1]
      if (ref.includes('${')) return
      const tag = ref.split('@')[0].split('/').pop().split(':')[1]
      if (!tag || tag === 'latest') problems.push(`${file}:${index + 1}: image "${ref}" không ghim phiên bản`)
    })
}

if (problems.length) {
  console.error(problems.join('\n'))
  console.error(`\n${problems.length} vi phạm.`)
  process.exit(1)
}
console.log(`Kho sạch: ${tracked.length} tệp, ${composeFiles.length} tệp compose được kiểm.`)
