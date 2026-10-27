// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
//
// Sinh THIRD_PARTY.md từ package-lock.json (giấy phép đọc từ node_modules đã cài bằng
// `npm ci`) cộng bảng Python/dịch vụ khai báo dưới đây.
//
//   npm ci && node scripts/gen_third_party.mjs
//
// Bảng Python lấy từ requirements.lock; giấy phép Python ghi theo metadata upstream và
// PHẢI được đối chiếu bằng `pip-licenses` (xem CI `licenses` và BUILD.md) trước mỗi release.
import { existsSync, readFileSync, writeFileSync } from 'node:fs'

const OSI_HINT = /^(MIT|ISC|BSD-[23]-Clause|Apache-2\.0|0BSD|BlueOak-1\.0\.0|MPL-2\.0|Python-2\.0|PSF-2\.0|CC0-1\.0|Unlicense|OFL-1.1|LGPL-3\.0-only|AGPL-3\.0-only|GPL-3\.0-only)$/

const lock = JSON.parse(readFileSync('package-lock.json', 'utf8'))
const npmRows = []
for (const [path, meta] of Object.entries(lock.packages)) {
  if (!path.includes('node_modules/') || meta.link) continue
  const name = path.split('node_modules/').pop()
  let license = meta.license
  const manifest = `${path}/package.json`
  if (!license && existsSync(manifest)) {
    const m = JSON.parse(readFileSync(manifest, 'utf8'))
    license = typeof m.license === 'string' ? m.license : m.license?.type
  }
  npmRows.push({ name, version: meta.version, license: license ?? 'UNKNOWN', dev: Boolean(meta.dev) })
}
npmRows.sort((a, b) => a.name.localeCompare(b.name))

const flag = (spdx) => {
  const parts = spdx.replace(/[()]/g, '').split(/ OR | AND /)
  return parts.some((p) => OSI_HINT.test(p.trim())) ? '' : ' ⚠️ kiểm tra'
}

const py = (name, version, license) => ({ name, version, license })
const pyRows = [
  py('alembic', '1.16.5', 'MIT'), py('annotated-types', '0.8.0', 'MIT'), py('anyio', '4.15.1', 'MIT'),
  py('attrs', '26.1.0', 'MIT'), py('boto3', '1.40.44', 'Apache-2.0'), py('botocore', '1.40.76', 'Apache-2.0'),
  py('certifi', '2026.7.22', 'MPL-2.0'), py('cffi', '2.1.1', 'MIT'), py('click', '8.5.0', 'BSD-3-Clause'),
  py('colorama', '0.4.6', 'BSD-3-Clause'), py('cryptography', '46.0.2', 'Apache-2.0 OR BSD-3-Clause'),
  py('fastapi', '0.118.0', 'MIT'), py('greenlet', '3.5.6', 'MIT AND PSF-2.0'), py('h11', '0.16.0', 'MIT'),
  py('httpcore', '1.0.9', 'BSD-3-Clause'), py('httptools', '0.9.0', 'MIT'), py('httpx', '0.28.1', 'BSD-3-Clause'),
  py('idna', '3.20', 'BSD-3-Clause'), py('iniconfig', '2.3.1', 'MIT'), py('jmespath', '1.1.0', 'MIT'),
  py('jsonschema', '4.25.1', 'MIT'), py('jsonschema-specifications', '2025.9.1', 'MIT'),
  py('Mako', '1.4.3', 'MIT'), py('MarkupSafe', '3.0.4', 'BSD-3-Clause'),
  py('packaging', '26.3', 'Apache-2.0 OR BSD-2-Clause'), py('pluggy', '1.7.0', 'MIT'),
  py('psycopg', '3.2.10', 'LGPL-3.0-only'),
  py('pycparser', '3.11', 'BSD-3-Clause'), py('pydantic', '2.14.1', 'MIT'),
  py('pydantic-settings', '2.11.0', 'MIT'), py('pydantic_core', '2.50.1', 'MIT'),
  py('Pygments', '2.21.0', 'BSD-2-Clause'), py('PyJWT', '2.10.1', 'MIT'), py('pytest', '8.4.2', 'MIT'),
  py('pytest-cov', '7.0.0', 'MIT'), py('python-dateutil', '2.9.0.post0', 'Apache-2.0 OR BSD-3-Clause'),
  py('python-dotenv', '1.2.4', 'BSD-3-Clause'), py('python-multipart', '0.0.20', 'Apache-2.0'),
  py('PyYAML', '6.0.3', 'MIT'), py('referencing', '0.37.0', 'MIT'), py('rpds-py', '2026.9.1', 'MIT'),
  py('ruff', '0.13.3', 'MIT'), py('s3transfer', '0.14.0', 'Apache-2.0'), py('six', '1.17.0', 'MIT'),
  py('SQLAlchemy', '2.0.43', 'MIT'), py('starlette', '0.48.0', 'BSD-3-Clause'),
  py('typing-inspection', '0.4.4', 'MIT'), py('typing_extensions', '4.16.0', 'PSF-2.0'),
  py('tzdata', '2026.5', 'Apache-2.0'), py('urllib3', '2.8.0', 'MIT'), py('uvicorn', '0.37.0', 'BSD-3-Clause'),
  py('uvloop (Linux)', '0.21.0', 'MIT OR Apache-2.0'), py('watchfiles', '1.3.0', 'MIT'),
  py('websockets', '17.2', 'BSD-3-Clause'),
]

const services = [
  ['PostgreSQL', '17.5-alpine', 'PostgreSQL', 'https://www.postgresql.org/about/licence/', 'dịch vụ chạy riêng (container)'],
  ['Keycloak', '26.2.5', 'Apache-2.0', 'https://github.com/keycloak/keycloak', 'dịch vụ chạy riêng — SSO/OIDC'],
  ['Valkey', '8.1.1-alpine', 'BSD-3-Clause', 'https://github.com/valkey-io/valkey', 'dịch vụ chạy riêng — thay Redis (không thuộc OSI ở bản 7.4+)'],
  ['RustFS', '1.0.3', 'Apache-2.0', 'https://github.com/rustfs/rustfs', 'dịch vụ chạy riêng — lưu trữ S3, thay MinIO (AGPL-3.0)'],
  ['Nginx', '1.28.0-alpine', 'BSD-2-Clause', 'https://nginx.org/LICENSE', 'dịch vụ chạy riêng — API gateway/static host'],
  ['ONLYOFFICE Docs (tùy chọn)', '8.3.3', 'AGPL-3.0-only', 'https://github.com/ONLYOFFICE/DocumentServer', 'dịch vụ chạy riêng, mặc định TẮT; giao tiếp qua HTTP/JWT, không liên kết vào mã Desktiny'],
  ['Python (base image)', '3.13.5-slim-bookworm', 'PSF-2.0', 'https://docs.python.org/3/license.html', 'runtime của container API'],
  ['Node.js (build image)', '22.17.0-alpine', 'MIT', 'https://github.com/nodejs/node', 'chỉ dùng khi build frontend'],
  ['Alpine Linux', '3.21.3', 'MIT (+ gói riêng)', 'https://www.alpinelinux.org/', 'helper một lần cấp quyền tệp realm'],
]

const out = []
out.push('# THIRD_PARTY — Khai báo thành phần bên ngoài')
out.push('')
out.push('Tệp này là bản khai báo bắt buộc theo thể lệ OLP PMNM 2026. **Sinh bởi** `scripts/gen_third_party.mjs`')
out.push('(phần npm) và bảng Python/dịch vụ trong cùng script; phiên bản khớp `package-lock.json` và `requirements.lock`.')
out.push('Mã gốc của dự án là Apache-2.0 (xem [LICENSE](LICENSE)). **Không có mã bên thứ ba nào được sao chép vào repo**;')
out.push('mọi thư viện lấy qua trình quản lý gói (npm, pip) và mọi dịch vụ dùng image chính thức của upstream.')
out.push('')
out.push('> Không phải tư vấn pháp lý. Giấy phép có thể đổi theo phiên bản: luôn đối chiếu `LICENSE` của đúng phiên bản.')
out.push('> Cột giấy phép Python theo metadata upstream — chưa quét bằng `pip-licenses` trên máy phát triển này')
out.push('> (không có Python); bước `licenses` trong CI chạy lại để kiểm chứng (xem [SELF_REVIEW.md](SELF_REVIEW.md)).')
out.push('')
out.push('## 1. Dịch vụ chạy riêng (không liên kết vào mã Desktiny)')
out.push('')
out.push('| Thành phần | Phiên bản | Giấy phép (SPDX) | Nguồn | Cách dùng |')
out.push('|---|---|---|---|---|')
for (const s of services) out.push(`| ${s[0]} | ${s[1]} | ${s[2]} | <${s[3]}> | ${s[4]} |`)
out.push('')
out.push('Đã loại/không dùng các thành phần không thuộc OSI: Redis ≥ 7.4 (→ Valkey), MinIO (AGPL, → RustFS),')
out.push('MongoDB, HashiCorp Vault/Terraform, Camunda 8, Elasticsearch bản SSPL. Workflow do Core tự cài đặt.')
out.push('')
out.push('### Ghi chú giấy phép đáng chú ý')
out.push('')
out.push('- **psycopg — LGPL-3.0-only**: cài từ PyPI (gói thuần Python, không `[binary]`), nạp libpq của hệ điều hành (`libpq5`, PostgreSQL License) qua liên kết động; không sửa, không đính kèm mã nguồn.')
out.push('  Tương thích với Apache-2.0 khi dùng như thư viện; người phân phối image cần giữ thông báo LGPL.')
out.push('- **ONLYOFFICE Docs — AGPL-3.0**: tùy chọn, mặc định tắt, chạy container riêng; giữ logo/thông báo của hãng.')
out.push('- **certifi — MPL-2.0**: dùng nguyên bản, không sửa tệp.')
out.push('')
out.push(`## 2. Thư viện Python (${pyRows.length}) — nguồn: PyPI, khóa trong \`requirements.lock\``)
out.push('')
out.push('| Gói | Phiên bản | Giấy phép (SPDX) | Cách dùng |')
out.push('|---|---|---|---|')
for (const r of pyRows) out.push(`| ${r.name} | ${r.version} | ${r.license}${flag(r.license)} | thư viện (pip) |`)
out.push('')
const prod = npmRows.filter((r) => !r.dev)
const dev = npmRows.filter((r) => r.dev)
for (const [title, rows] of [[`3. Thư viện npm chạy trong sản phẩm (${prod.length})`, prod], [`4. Thư viện npm chỉ dùng khi phát triển/build/test (${dev.length})`, dev]]) {
  out.push(`## ${title}`)
  out.push('')
  out.push('| Gói | Phiên bản | Giấy phép (SPDX) | Cách dùng |')
  out.push('|---|---|---|---|')
  for (const r of rows) out.push(`| ${r.name} | ${r.version} | ${r.license}${flag(r.license)} | thư viện (npm) |`)
  out.push('')
}
const odd = npmRows.filter((r) => flag(r.license))
out.push('## 5. Mục cần người duyệt')
out.push('')
out.push(odd.length ? odd.map((r) => `- ${r.name}@${r.version}: ${r.license}`).join('\n') : '- Không có gói npm nào ngoài danh sách giấy phép OSI thông dụng.')
out.push('')
writeFileSync('THIRD_PARTY.md', out.join('\n'))
console.log(`npm: ${npmRows.length} (${prod.length} prod / ${dev.length} dev), python: ${pyRows.length}, cần duyệt: ${odd.length}`)
