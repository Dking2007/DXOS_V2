// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
//
// Thêm header SPDX vào mọi tệp mã nguồn/cấu hình đã được Git theo dõi.
// Tệp không ghi chú được (JSON, Markdown, lockfile, HTML) khai báo trong REUSE.toml.
// Chạy lại nhiều lần vẫn an toàn (bỏ qua tệp đã có header).
//
//   node scripts/add_spdx_headers.mjs          # ghi header
//   node scripts/add_spdx_headers.mjs --check  # chỉ liệt kê tệp còn thiếu
import { execFileSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'

const LICENSE_ID = 'Apache-2.0'
const COPYRIGHT = '2026 Desktiny contributors'
const check = process.argv.includes('--check')

const hash = (t) => `# ${t}`
const slash = (t) => `// ${t}`
const html = (t) => `<!-- ${t} -->`
const block = (t) => `/* ${t} */`

const byExt = {
  py: hash, sh: hash, yml: hash, yaml: hash, toml: hash, ini: hash, conf: hash,
  ts: slash, mjs: slash, vue: html, css: block,
}
const byName = {
  '.gitignore': hash, '.dockerignore': hash, '.prettierignore': hash,
  'api.Dockerfile': hash, 'web.Dockerfile': hash,
}

const files = execFileSync('git', ['ls-files'], { encoding: 'utf8' }).split('\n').filter(Boolean)
const missing = []
let written = 0

for (const file of files) {
  const base = file.split('/').pop()
  const ext = base.includes('.') ? base.split('.').pop() : ''
  const comment = byName[base] ?? byExt[ext]
  if (!comment) continue
  const raw = readFileSync(file, 'utf8')
  if (raw.includes('SPDX-License-Identifier')) continue
  if (check) {
    missing.push(file)
    continue
  }
  const eol = raw.includes('\r\n') ? '\r\n' : '\n'
  const header = [
    comment(`SPDX-License-Identifier: ${LICENSE_ID}`),
    comment(`SPDX-FileCopyrightText: ${COPYRIGHT}`),
  ].join(eol)
  let out
  if (raw.startsWith('#!')) {
    const nl = raw.indexOf('\n')
    out = raw.slice(0, nl + 1) + header + eol + raw.slice(nl + 1)
  } else {
    out = header + eol + raw
  }
  writeFileSync(file, out)
  written += 1
}

if (check) {
  console.log(missing.length ? `Thiếu header:\n${missing.join('\n')}` : 'Mọi tệp đã có header SPDX.')
  process.exit(missing.length ? 1 : 0)
}
console.log(`Đã ghi header cho ${written} tệp.`)
