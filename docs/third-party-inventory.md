# Third-party inventory — bản triển khai đầu

Không có mã ONLYOFFICE/Keycloak/MinIO được sao chép vào source ứng dụng. Những
service này chạy bằng image riêng. Tách process không tự miễn nghĩa vụ phân phối,
giấy phép hoặc thương hiệu. Bảng dưới là inventory kỹ thuật, **không phải tư vấn
pháp lý hoặc xác nhận đã hoàn tất license/security audit**.

## Image/service được khai báo

| Thành phần | Version/tag trong Compose/Dockerfile | Hình thức | License/nguồn tham chiếu | Việc cần rà soát khi release |
|---|---|---|---|---|
| Python | 3.13.5-slim-bookworm | Base image API | [PSF](https://docs.python.org/3/license.html), Debian packages | SBOM image/OS, advisory, notice |
| Node.js | 22.17.0-alpine | Build frontend | [MIT + notices](https://github.com/nodejs/node/blob/main/LICENSE) | Build-only dependencies, OS inventory |
| PostgreSQL | 17.5-alpine | Service DB | [PostgreSQL License](https://www.postgresql.org/about/licence/) | Exact image digest, extensions |
| Keycloak | 26.2.5 | Service SSO | [Apache-2.0](https://github.com/keycloak/keycloak/blob/main/LICENSE.txt) | Exact distribution/notice, CVEs |
| Valkey | 8.1.1-alpine | Optional broker provision | [BSD-3-Clause](https://github.com/valkey-io/valkey/blob/unstable/COPYING) | Not used as history/runtime source |
| MinIO | RELEASE.2025-04-22T22-12-26Z | S3 service | [AGPL-3.0](https://github.com/minio/minio/blob/master/LICENSE) | Distribution/source obligations, edition/terms |
| Nginx | 1.28.0-alpine | Gateway/static host | [BSD-like](https://nginx.org/LICENSE) | OS dependencies and notices |
| Alpine | 3.21.3 | One-shot realm file permissions helper | [Alpine package licenses](https://www.alpinelinux.org/about/) | Package inventory |
| ONLYOFFICE Docs | documentserver:8.3.3 | Optional separate Document Server | [License FAQ](https://www.onlyoffice.com/license-faq), [source license](https://github.com/ONLYOFFICE/DocumentServer/blob/master/LICENSE.txt) | Community AGPL-3.0, logo/legal notices, edition/concurrency, fonts |

Tags are pinned, not immutable digests. Before shipping, resolve and record image
digests, verify registry availability and platform architecture, update supported
security-patched versions after integration tests, then generate SBOM. No image
pull or end-to-end container verification is implied by this table.

## Application dependencies

Authoritative versions are the service `pyproject.toml` files, Python
`requirements.lock` constraints and root npm `package-lock.json`. API Dockerfile
installs with the Python constraints. Record transitive versions/licenses from the installed lock
before distribution; do not claim this short table exhausts transitive software.

| Nhóm | Thành phần dự kiến dùng | License reference |
|---|---|---|
| API | FastAPI, Pydantic, Uvicorn, HTTPX | MIT/BSD-3-Clause per exact package |
| Data | SQLAlchemy, Alembic, psycopg | MIT / LGPL-3.0 (psycopg), review artifacts |
| Storage/security | boto3/botocore, PyJWT, cryptography | Apache-2.0 / MIT / Apache-2.0 or BSD-3-Clause by package |
| Validation | jsonschema | MIT |
| Frontend | Vue 3, Vue Router, Pinia, Vite, TypeScript, TanStack Vue Query | MIT per exact package/version |
| Tests | pytest, Playwright, Vitest if installed | MIT/Apache-2.0 per exact package |
| Fonts/icons | Installed frontend assets only | Inspect bundled packages and retain font/icon notices |

Do not label SDK JavaScript downloaded dynamically from Document Server as original
Apache project code. If the official Vue component is bundled later, inspect that
package/tag's license independently. Keep editor vendor branding unless a valid
edition/contract explicitly grants otherwise.

## Release review record

Current status: initial inventory prepared 2026-10-18; legal compatibility, full
transitive SBOM, image vulnerability review, trademark and distribution/source
fulfillment review **not completed**. Assign a reviewer and record exact artifact,
review date, result and required notices before public release. The Apache license
at repository root covers original code, not third-party artifacts or user data.
