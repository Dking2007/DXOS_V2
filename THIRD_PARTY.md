# THIRD_PARTY — Khai báo thành phần bên ngoài

Tệp này là bản khai báo bắt buộc theo thể lệ OLP PMNM 2026. **Sinh bởi** `scripts/gen_third_party.mjs`
(phần npm) và bảng Python/dịch vụ trong cùng script; phiên bản khớp `package-lock.json` và `requirements.lock`.
Mã gốc của dự án là Apache-2.0 (xem [LICENSE](LICENSE)). **Không có mã bên thứ ba nào được sao chép vào repo**;
mọi thư viện lấy qua trình quản lý gói (npm, pip) và mọi dịch vụ dùng image chính thức của upstream.

> Không phải tư vấn pháp lý. Giấy phép có thể đổi theo phiên bản: luôn đối chiếu `LICENSE` của đúng phiên bản.
> Cột giấy phép Python theo metadata upstream — chưa quét bằng `pip-licenses` trên máy phát triển này
> (không có Python); bước `licenses` trong CI chạy lại để kiểm chứng (xem [SELF_REVIEW.md](SELF_REVIEW.md)).

## 1. Dịch vụ chạy riêng (không liên kết vào mã Desktiny)

| Thành phần | Phiên bản | Giấy phép (SPDX) | Nguồn | Cách dùng |
|---|---|---|---|---|
| PostgreSQL | 17.5-alpine | PostgreSQL | <https://www.postgresql.org/about/licence/> | dịch vụ chạy riêng (container) |
| Keycloak | 26.2.5 | Apache-2.0 | <https://github.com/keycloak/keycloak> | dịch vụ chạy riêng — SSO/OIDC |
| Valkey | 8.1.1-alpine | BSD-3-Clause | <https://github.com/valkey-io/valkey> | dịch vụ chạy riêng — thay Redis (không thuộc OSI ở bản 7.4+) |
| RustFS | 1.0.3 | Apache-2.0 | <https://github.com/rustfs/rustfs> | dịch vụ chạy riêng — lưu trữ S3, thay MinIO (AGPL-3.0) |
| Nginx | 1.28.0-alpine | BSD-2-Clause | <https://nginx.org/LICENSE> | dịch vụ chạy riêng — API gateway/static host |
| ONLYOFFICE Docs (tùy chọn) | 8.3.3 | AGPL-3.0-only | <https://github.com/ONLYOFFICE/DocumentServer> | dịch vụ chạy riêng, mặc định TẮT; giao tiếp qua HTTP/JWT, không liên kết vào mã Desktiny |
| Python (base image) | 3.13.5-slim-bookworm | PSF-2.0 | <https://docs.python.org/3/license.html> | runtime của container API |
| Node.js (build image) | 22.17.0-alpine | MIT | <https://github.com/nodejs/node> | chỉ dùng khi build frontend |
| Alpine Linux | 3.21.3 | MIT (+ gói riêng) | <https://www.alpinelinux.org/> | helper một lần cấp quyền tệp realm |

Đã loại/không dùng các thành phần không thuộc OSI: Redis ≥ 7.4 (→ Valkey), MinIO (AGPL, → RustFS),
MongoDB, HashiCorp Vault/Terraform, Camunda 8, Elasticsearch bản SSPL. Workflow do Core tự cài đặt.

### Ghi chú giấy phép đáng chú ý

- **psycopg — LGPL-3.0-only**: cài từ PyPI (gói thuần Python, không `[binary]`), nạp libpq của hệ điều hành (`libpq5`, PostgreSQL License) qua liên kết động; không sửa, không đính kèm mã nguồn.
  Tương thích với Apache-2.0 khi dùng như thư viện; người phân phối image cần giữ thông báo LGPL.
- **ONLYOFFICE Docs — AGPL-3.0**: tùy chọn, mặc định tắt, chạy container riêng; giữ logo/thông báo của hãng.
- **certifi — MPL-2.0**: dùng nguyên bản, không sửa tệp.

## 2. Thư viện Python (54) — nguồn: PyPI, khóa trong `requirements.lock`

| Gói | Phiên bản | Giấy phép (SPDX) | Cách dùng |
|---|---|---|---|
| alembic | 1.16.5 | MIT | thư viện (pip) |
| annotated-types | 0.8.0 | MIT | thư viện (pip) |
| anyio | 4.15.1 | MIT | thư viện (pip) |
| attrs | 26.1.0 | MIT | thư viện (pip) |
| boto3 | 1.40.44 | Apache-2.0 | thư viện (pip) |
| botocore | 1.40.76 | Apache-2.0 | thư viện (pip) |
| certifi | 2026.7.22 | MPL-2.0 | thư viện (pip) |
| cffi | 2.1.1 | MIT | thư viện (pip) |
| click | 8.5.0 | BSD-3-Clause | thư viện (pip) |
| colorama | 0.4.6 | BSD-3-Clause | thư viện (pip) |
| cryptography | 46.0.2 | Apache-2.0 OR BSD-3-Clause | thư viện (pip) |
| fastapi | 0.118.0 | MIT | thư viện (pip) |
| greenlet | 3.5.6 | MIT AND PSF-2.0 | thư viện (pip) |
| h11 | 0.16.0 | MIT | thư viện (pip) |
| httpcore | 1.0.9 | BSD-3-Clause | thư viện (pip) |
| httptools | 0.9.0 | MIT | thư viện (pip) |
| httpx | 0.28.1 | BSD-3-Clause | thư viện (pip) |
| idna | 3.20 | BSD-3-Clause | thư viện (pip) |
| iniconfig | 2.3.1 | MIT | thư viện (pip) |
| jmespath | 1.1.0 | MIT | thư viện (pip) |
| jsonschema | 4.25.1 | MIT | thư viện (pip) |
| jsonschema-specifications | 2025.9.1 | MIT | thư viện (pip) |
| Mako | 1.4.3 | MIT | thư viện (pip) |
| MarkupSafe | 3.0.4 | BSD-3-Clause | thư viện (pip) |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | thư viện (pip) |
| pluggy | 1.7.0 | MIT | thư viện (pip) |
| psycopg | 3.2.10 | LGPL-3.0-only | thư viện (pip) |
| pycparser | 3.11 | BSD-3-Clause | thư viện (pip) |
| pydantic | 2.14.1 | MIT | thư viện (pip) |
| pydantic-settings | 2.11.0 | MIT | thư viện (pip) |
| pydantic_core | 2.50.1 | MIT | thư viện (pip) |
| Pygments | 2.21.0 | BSD-2-Clause | thư viện (pip) |
| PyJWT | 2.10.1 | MIT | thư viện (pip) |
| pytest | 8.4.2 | MIT | thư viện (pip) |
| pytest-cov | 7.0.0 | MIT | thư viện (pip) |
| python-dateutil | 2.9.0.post0 | Apache-2.0 OR BSD-3-Clause | thư viện (pip) |
| python-dotenv | 1.2.4 | BSD-3-Clause | thư viện (pip) |
| python-multipart | 0.0.20 | Apache-2.0 | thư viện (pip) |
| PyYAML | 6.0.3 | MIT | thư viện (pip) |
| referencing | 0.37.0 | MIT | thư viện (pip) |
| rpds-py | 2026.9.1 | MIT | thư viện (pip) |
| ruff | 0.13.3 | MIT | thư viện (pip) |
| s3transfer | 0.14.0 | Apache-2.0 | thư viện (pip) |
| six | 1.17.0 | MIT | thư viện (pip) |
| SQLAlchemy | 2.0.43 | MIT | thư viện (pip) |
| starlette | 0.48.0 | BSD-3-Clause | thư viện (pip) |
| typing-inspection | 0.4.4 | MIT | thư viện (pip) |
| typing_extensions | 4.16.0 | PSF-2.0 | thư viện (pip) |
| tzdata | 2026.5 | Apache-2.0 | thư viện (pip) |
| urllib3 | 2.8.0 | MIT | thư viện (pip) |
| uvicorn | 0.37.0 | BSD-3-Clause | thư viện (pip) |
| uvloop (Linux) | 0.21.0 | MIT OR Apache-2.0 | thư viện (pip) |
| watchfiles | 1.3.0 | MIT | thư viện (pip) |
| websockets | 17.2 | BSD-3-Clause | thư viện (pip) |

## 3. Thư viện npm chạy trong sản phẩm (66)

| Gói | Phiên bản | Giấy phép (SPDX) | Cách dùng |
|---|---|---|---|
| @babel/helper-string-parser | 7.29.7 | MIT | thư viện (npm) |
| @babel/helper-validator-identifier | 7.29.7 | MIT | thư viện (npm) |
| @babel/parser | 7.29.9 | MIT | thư viện (npm) |
| @babel/types | 7.29.8 | MIT | thư viện (npm) |
| @fontsource/be-vietnam-pro | 5.1.1 | OFL-1.1 | thư viện (npm) |
| @fontsource/source-sans-3 | 5.1.1 | OFL-1.1 | thư viện (npm) |
| @jridgewell/sourcemap-codec | 1.6.0 | MIT | thư viện (npm) |
| @napi-rs/canvas | 0.1.100 | MIT | thư viện (npm) |
| @napi-rs/canvas-android-arm64 | 0.1.100 | MIT | thư viện (npm) |
| @napi-rs/canvas-darwin-arm64 | 0.1.100 | MIT | thư viện (npm) |
| @napi-rs/canvas-darwin-x64 | 0.1.100 | MIT | thư viện (npm) |
| @napi-rs/canvas-linux-arm-gnueabihf | 0.1.100 | MIT | thư viện (npm) |
| @napi-rs/canvas-linux-arm64-gnu | 0.1.100 | MIT | thư viện (npm) |
| @napi-rs/canvas-linux-arm64-musl | 0.1.100 | MIT | thư viện (npm) |
| @napi-rs/canvas-linux-riscv64-gnu | 0.1.100 | MIT | thư viện (npm) |
| @napi-rs/canvas-linux-x64-gnu | 0.1.100 | MIT | thư viện (npm) |
| @napi-rs/canvas-linux-x64-musl | 0.1.100 | MIT | thư viện (npm) |
| @napi-rs/canvas-win32-arm64-msvc | 0.1.100 | MIT | thư viện (npm) |
| @napi-rs/canvas-win32-x64-msvc | 0.1.100 | MIT | thư viện (npm) |
| @tanstack/match-sorter-utils | 8.19.4 | MIT | thư viện (npm) |
| @tanstack/query-core | 5.66.0 | MIT | thư viện (npm) |
| @tanstack/vue-query | 5.66.0 | MIT | thư viện (npm) |
| @types/web-bluetooth | 0.0.20 | MIT | thư viện (npm) |
| @vue-flow/background | 1.3.2 | MIT | thư viện (npm) |
| @vue-flow/controls | 1.1.3 | MIT | thư viện (npm) |
| @vue-flow/core | 1.48.2 | MIT | thư viện (npm) |
| @vue-flow/minimap | 1.5.4 | MIT | thư viện (npm) |
| @vue/compiler-core | 3.5.44 | MIT | thư viện (npm) |
| @vue/compiler-dom | 3.5.44 | MIT | thư viện (npm) |
| @vue/compiler-sfc | 3.5.44 | MIT | thư viện (npm) |
| @vue/compiler-ssr | 3.5.44 | MIT | thư viện (npm) |
| @vue/devtools-api | 6.6.4 | MIT | thư viện (npm) |
| @vue/reactivity | 3.5.44 | MIT | thư viện (npm) |
| @vue/runtime-core | 3.5.44 | MIT | thư viện (npm) |
| @vue/runtime-dom | 3.5.44 | MIT | thư viện (npm) |
| @vue/server-renderer | 3.5.44 | MIT | thư viện (npm) |
| @vue/shared | 3.5.44 | MIT | thư viện (npm) |
| @vueuse/core | 10.11.1 | MIT | thư viện (npm) |
| @vueuse/metadata | 10.11.1 | MIT | thư viện (npm) |
| @vueuse/shared | 10.11.1 | MIT | thư viện (npm) |
| csstype | 3.2.3 | MIT | thư viện (npm) |
| d3-color | 3.1.0 | ISC | thư viện (npm) |
| d3-dispatch | 3.0.1 | ISC | thư viện (npm) |
| d3-drag | 3.0.0 | ISC | thư viện (npm) |
| d3-ease | 3.0.1 | BSD-3-Clause | thư viện (npm) |
| d3-interpolate | 3.0.1 | ISC | thư viện (npm) |
| d3-selection | 3.0.0 | ISC | thư viện (npm) |
| d3-timer | 3.0.1 | ISC | thư viện (npm) |
| d3-transition | 3.0.1 | ISC | thư viện (npm) |
| d3-zoom | 3.0.0 | ISC | thư viện (npm) |
| entities | 7.0.1 | BSD-2-Clause | thư viện (npm) |
| estree-walker | 2.0.2 | MIT | thư viện (npm) |
| estree-walker | 2.0.2 | MIT | thư viện (npm) |
| lucide-vue-next | 0.468.0 | ISC | thư viện (npm) |
| magic-string | 0.30.21 | MIT | thư viện (npm) |
| nanoid | 3.3.20 | MIT | thư viện (npm) |
| pdfjs-dist | 4.10.38 | Apache-2.0 | thư viện (npm) |
| picocolors | 1.1.1 | ISC | thư viện (npm) |
| pinia | 2.3.1 | MIT | thư viện (npm) |
| postcss | 8.5.30 | MIT | thư viện (npm) |
| remove-accents | 0.5.0 | MIT | thư viện (npm) |
| source-map-js | 1.2.2 | BSD-3-Clause | thư viện (npm) |
| typescript | 5.7.3 | Apache-2.0 | thư viện (npm) |
| vue | 3.5.44 | MIT | thư viện (npm) |
| vue-demi | 0.14.10 | MIT | thư viện (npm) |
| vue-router | 4.5.0 | MIT | thư viện (npm) |

## 4. Thư viện npm chỉ dùng khi phát triển/build/test (243)

| Gói | Phiên bản | Giấy phép (SPDX) | Cách dùng |
|---|---|---|---|
| @babel/code-frame | 7.29.7 | MIT | thư viện (npm) |
| @esbuild/aix-ppc64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/android-arm | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/android-arm64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/android-x64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/darwin-arm64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/darwin-x64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/freebsd-arm64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/freebsd-x64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/linux-arm | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/linux-arm64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/linux-ia32 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/linux-loong64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/linux-mips64el | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/linux-ppc64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/linux-riscv64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/linux-s390x | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/linux-x64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/netbsd-arm64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/netbsd-x64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/openbsd-arm64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/openbsd-x64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/openharmony-arm64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/sunos-x64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/win32-arm64 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/win32-ia32 | 0.25.12 | MIT | thư viện (npm) |
| @esbuild/win32-x64 | 0.25.12 | MIT | thư viện (npm) |
| @eslint-community/eslint-utils | 4.10.1 | MIT | thư viện (npm) |
| @eslint-community/regexpp | 4.12.2 | MIT | thư viện (npm) |
| @eslint/config-array | 0.21.2 | Apache-2.0 | thư viện (npm) |
| @eslint/config-helpers | 0.4.2 | Apache-2.0 | thư viện (npm) |
| @eslint/core | 0.17.0 | Apache-2.0 | thư viện (npm) |
| @eslint/eslintrc | 3.3.7 | MIT | thư viện (npm) |
| @eslint/js | 9.39.5 | MIT | thư viện (npm) |
| @eslint/object-schema | 2.1.7 | Apache-2.0 | thư viện (npm) |
| @eslint/plugin-kit | 0.4.1 | Apache-2.0 | thư viện (npm) |
| @humanfs/core | 0.19.2 | Apache-2.0 | thư viện (npm) |
| @humanfs/node | 0.16.8 | Apache-2.0 | thư viện (npm) |
| @humanfs/types | 0.15.0 | Apache-2.0 | thư viện (npm) |
| @humanwhocodes/module-importer | 1.0.1 | Apache-2.0 | thư viện (npm) |
| @humanwhocodes/retry | 0.4.3 | Apache-2.0 | thư viện (npm) |
| @napi-rs/lzma-linux-x64-gnu | 1.5.1 | MIT | thư viện (npm) |
| @playwright/test | 1.64.1 | Apache-2.0 | thư viện (npm) |
| @redocly/ajv | 8.11.2 | MIT | thư viện (npm) |
| @redocly/config | 0.22.0 | MIT | thư viện (npm) |
| @redocly/openapi-core | 1.34.21 | MIT | thư viện (npm) |
| @rollup/rollup-android-arm-eabi | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-android-arm64 | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-darwin-arm64 | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-darwin-x64 | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-freebsd-arm64 | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-freebsd-x64 | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-linux-arm-gnueabihf | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-linux-arm-musleabihf | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-linux-arm64-gnu | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-linux-arm64-musl | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-linux-loong64-gnu | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-linux-loong64-musl | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-linux-ppc64-gnu | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-linux-ppc64-musl | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-linux-riscv64-gnu | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-linux-riscv64-musl | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-linux-s390x-gnu | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-linux-x64-gnu | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-linux-x64-musl | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-openbsd-x64 | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-openharmony-arm64 | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-win32-arm64-msvc | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-win32-ia32-msvc | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-win32-x64-gnu | 4.64.10 | MIT | thư viện (npm) |
| @rollup/rollup-win32-x64-msvc | 4.64.10 | MIT | thư viện (npm) |
| @standard-schema/spec | 1.1.0 | MIT | thư viện (npm) |
| @types/chai | 5.2.3 | MIT | thư viện (npm) |
| @types/deep-eql | 4.0.2 | MIT | thư viện (npm) |
| @types/estree | 1.0.9 | MIT | thư viện (npm) |
| @types/json-schema | 7.0.15 | MIT | thư viện (npm) |
| @typescript-eslint/eslint-plugin | 8.71.2 | MIT | thư viện (npm) |
| @typescript-eslint/parser | 8.71.2 | MIT | thư viện (npm) |
| @typescript-eslint/project-service | 8.71.2 | MIT | thư viện (npm) |
| @typescript-eslint/scope-manager | 8.71.2 | MIT | thư viện (npm) |
| @typescript-eslint/tsconfig-utils | 8.71.2 | MIT | thư viện (npm) |
| @typescript-eslint/type-utils | 8.71.2 | MIT | thư viện (npm) |
| @typescript-eslint/types | 8.71.2 | MIT | thư viện (npm) |
| @typescript-eslint/typescript-estree | 8.71.2 | MIT | thư viện (npm) |
| @typescript-eslint/utils | 8.71.2 | MIT | thư viện (npm) |
| @typescript-eslint/visitor-keys | 8.71.2 | MIT | thư viện (npm) |
| @vitejs/plugin-vue | 5.2.4 | MIT | thư viện (npm) |
| @vitest/expect | 4.1.11 | MIT | thư viện (npm) |
| @vitest/mocker | 4.1.11 | MIT | thư viện (npm) |
| @vitest/pretty-format | 4.1.11 | MIT | thư viện (npm) |
| @vitest/runner | 4.1.11 | MIT | thư viện (npm) |
| @vitest/snapshot | 4.1.11 | MIT | thư viện (npm) |
| @vitest/spy | 4.1.11 | MIT | thư viện (npm) |
| @vitest/utils | 4.1.11 | MIT | thư viện (npm) |
| @volar/language-core | 2.4.28 | MIT | thư viện (npm) |
| @volar/source-map | 2.4.28 | MIT | thư viện (npm) |
| @volar/typescript | 2.4.28 | MIT | thư viện (npm) |
| @vue/compiler-vue2 | 2.7.16 | MIT | thư viện (npm) |
| @vue/language-core | 2.2.0 | MIT | thư viện (npm) |
| acorn | 8.19.0 | MIT | thư viện (npm) |
| acorn-jsx | 5.3.2 | MIT | thư viện (npm) |
| agent-base | 7.1.4 | MIT | thư viện (npm) |
| ajv | 6.15.0 | MIT | thư viện (npm) |
| alien-signals | 0.4.14 | MIT | thư viện (npm) |
| ansi-colors | 4.1.3 | MIT | thư viện (npm) |
| ansi-styles | 4.3.0 | MIT | thư viện (npm) |
| argparse | 2.0.1 | Python-2.0 | thư viện (npm) |
| assertion-error | 2.0.1 | MIT | thư viện (npm) |
| balanced-match | 4.0.4 | MIT | thư viện (npm) |
| balanced-match | 1.0.2 | MIT | thư viện (npm) |
| boolbase | 1.0.0 | ISC | thư viện (npm) |
| brace-expansion | 2.1.7 | MIT | thư viện (npm) |
| brace-expansion | 5.0.12 | MIT | thư viện (npm) |
| brace-expansion | 2.1.7 | MIT | thư viện (npm) |
| brace-expansion | 1.1.21 | MIT | thư viện (npm) |
| callsites | 3.1.0 | MIT | thư viện (npm) |
| chai | 6.3.0 | MIT | thư viện (npm) |
| chalk | 4.1.2 | MIT | thư viện (npm) |
| change-case | 5.4.4 | MIT | thư viện (npm) |
| color-convert | 2.0.1 | MIT | thư viện (npm) |
| color-name | 1.1.4 | MIT | thư viện (npm) |
| colorette | 1.4.0 | MIT | thư viện (npm) |
| concat-map | 0.0.1 | MIT | thư viện (npm) |
| convert-source-map | 2.0.0 | MIT | thư viện (npm) |
| cross-spawn | 7.0.6 | MIT | thư viện (npm) |
| cssesc | 3.0.0 | MIT | thư viện (npm) |
| de-indent | 1.0.2 | MIT | thư viện (npm) |
| debug | 4.4.3 | MIT | thư viện (npm) |
| deep-is | 0.1.4 | MIT | thư viện (npm) |
| es-module-lexer | 2.3.2 | MIT | thư viện (npm) |
| esbuild | 0.25.12 | MIT | thư viện (npm) |
| escape-string-regexp | 4.0.0 | MIT | thư viện (npm) |
| eslint | 9.39.5 | MIT | thư viện (npm) |
| eslint-plugin-vue | 10.11.1 | MIT | thư viện (npm) |
| eslint-scope | 8.4.0 | BSD-2-Clause | thư viện (npm) |
| eslint-visitor-keys | 3.4.3 | Apache-2.0 | thư viện (npm) |
| eslint-visitor-keys | 5.0.1 | Apache-2.0 | thư viện (npm) |
| eslint-visitor-keys | 4.2.1 | Apache-2.0 | thư viện (npm) |
| espree | 10.4.0 | BSD-2-Clause | thư viện (npm) |
| esquery | 1.7.0 | BSD-3-Clause | thư viện (npm) |
| esrecurse | 4.3.0 | BSD-2-Clause | thư viện (npm) |
| estraverse | 5.3.0 | BSD-2-Clause | thư viện (npm) |
| estree-walker | 3.0.3 | MIT | thư viện (npm) |
| esutils | 2.0.3 | BSD-2-Clause | thư viện (npm) |
| expect-type | 1.4.0 | Apache-2.0 | thư viện (npm) |
| fast-deep-equal | 3.1.3 | MIT | thư viện (npm) |
| fast-json-stable-stringify | 2.1.0 | MIT | thư viện (npm) |
| fast-levenshtein | 2.0.6 | MIT | thư viện (npm) |
| fdir | 6.5.0 | MIT | thư viện (npm) |
| fdir | 6.5.0 | MIT | thư viện (npm) |
| file-entry-cache | 8.0.0 | MIT | thư viện (npm) |
| find-up | 5.0.0 | MIT | thư viện (npm) |
| flat-cache | 4.0.1 | MIT | thư viện (npm) |
| flatted | 3.4.4 | ISC | thư viện (npm) |
| fsevents | 2.3.2 | MIT | thư viện (npm) |
| fsevents | 2.3.3 | MIT | thư viện (npm) |
| glob-parent | 6.0.2 | ISC | thư viện (npm) |
| globals | 14.0.0 | MIT | thư viện (npm) |
| globals | 15.14.0 | MIT | thư viện (npm) |
| has-flag | 4.0.0 | MIT | thư viện (npm) |
| he | 1.2.0 | MIT | thư viện (npm) |
| https-proxy-agent | 7.0.6 | MIT | thư viện (npm) |
| ignore | 7.0.12 | MIT | thư viện (npm) |
| ignore | 5.3.2 | MIT | thư viện (npm) |
| import-fresh | 3.3.1 | MIT | thư viện (npm) |
| imurmurhash | 0.1.4 | MIT | thư viện (npm) |
| index-to-position | 1.2.0 | MIT | thư viện (npm) |
| is-extglob | 2.1.1 | MIT | thư viện (npm) |
| is-glob | 4.0.3 | MIT | thư viện (npm) |
| isexe | 2.0.0 | ISC | thư viện (npm) |
| js-levenshtein | 1.1.6 | MIT | thư viện (npm) |
| js-tokens | 4.0.0 | MIT | thư viện (npm) |
| js-yaml | 4.3.2 | MIT | thư viện (npm) |
| json-buffer | 3.0.1 | MIT | thư viện (npm) |
| json-schema-traverse | 1.0.0 | MIT | thư viện (npm) |
| json-schema-traverse | 0.4.1 | MIT | thư viện (npm) |
| json-stable-stringify-without-jsonify | 1.0.1 | MIT | thư viện (npm) |
| keyv | 4.5.4 | MIT | thư viện (npm) |
| levn | 0.4.1 | MIT | thư viện (npm) |
| locate-path | 6.0.0 | MIT | thư viện (npm) |
| lodash.merge | 4.6.2 | MIT | thư viện (npm) |
| minimatch | 5.1.9 | ISC | thư viện (npm) |
| minimatch | 10.2.6 | BlueOak-1.0.0 | thư viện (npm) |
| minimatch | 9.0.9 | ISC | thư viện (npm) |
| minimatch | 3.1.5 | ISC | thư viện (npm) |
| ms | 2.1.3 | MIT | thư viện (npm) |
| muggle-string | 0.4.1 | MIT | thư viện (npm) |
| natural-compare | 1.4.0 | MIT | thư viện (npm) |
| nth-check | 2.1.1 | BSD-2-Clause | thư viện (npm) |
| obug | 2.2.1 | MIT | thư viện (npm) |
| openapi-typescript | 7.13.0 | MIT | thư viện (npm) |
| optionator | 0.9.4 | MIT | thư viện (npm) |
| p-limit | 3.1.0 | MIT | thư viện (npm) |
| p-locate | 5.0.0 | MIT | thư viện (npm) |
| parent-module | 1.0.1 | MIT | thư viện (npm) |
| parse-json | 8.3.0 | MIT | thư viện (npm) |
| path-browserify | 1.0.1 | MIT | thư viện (npm) |
| path-exists | 4.0.0 | MIT | thư viện (npm) |
| path-key | 3.1.1 | MIT | thư viện (npm) |
| pathe | 2.0.3 | MIT | thư viện (npm) |
| picomatch | 4.0.7 | MIT | thư viện (npm) |
| playwright | 1.64.1 | Apache-2.0 | thư viện (npm) |
| playwright-core | 1.64.1 | Apache-2.0 | thư viện (npm) |
| pluralize | 8.0.0 | MIT | thư viện (npm) |
| postcss-selector-parser | 7.1.6 | MIT | thư viện (npm) |
| prelude-ls | 1.2.1 | MIT | thư viện (npm) |
| prettier | 3.9.10 | MIT | thư viện (npm) |
| punycode | 2.3.1 | MIT | thư viện (npm) |
| require-from-string | 2.0.2 | MIT | thư viện (npm) |
| resolve-from | 4.0.0 | MIT | thư viện (npm) |
| rollup | 4.64.10 | MIT | thư viện (npm) |
| semver | 7.8.5 | ISC | thư viện (npm) |
| shebang-command | 2.0.0 | MIT | thư viện (npm) |
| shebang-regex | 3.0.0 | MIT | thư viện (npm) |
| siginfo | 2.0.0 | ISC | thư viện (npm) |
| stackback | 0.0.2 | MIT | thư viện (npm) |
| std-env | 4.3.0 | MIT | thư viện (npm) |
| strip-json-comments | 3.1.1 | MIT | thư viện (npm) |
| supports-color | 10.2.2 | MIT | thư viện (npm) |
| supports-color | 7.2.0 | MIT | thư viện (npm) |
| tinybench | 2.9.0 | MIT | thư viện (npm) |
| tinyexec | 1.3.1 | MIT | thư viện (npm) |
| tinyglobby | 0.2.17 | MIT | thư viện (npm) |
| tinyrainbow | 3.2.0 | MIT | thư viện (npm) |
| ts-api-utils | 2.5.0 | MIT | thư viện (npm) |
| type-check | 0.4.0 | MIT | thư viện (npm) |
| type-fest | 4.41.0 | (MIT OR CC0-1.0) | thư viện (npm) |
| typescript-eslint | 8.71.2 | MIT | thư viện (npm) |
| uri-js | 4.4.1 | BSD-2-Clause | thư viện (npm) |
| uri-js-replace | 1.0.1 | MIT | thư viện (npm) |
| util-deprecate | 1.0.2 | MIT | thư viện (npm) |
| vite | 6.4.4 | MIT | thư viện (npm) |
| vitest | 4.1.11 | MIT | thư viện (npm) |
| vscode-uri | 3.2.0 | MIT | thư viện (npm) |
| vue-eslint-parser | 10.4.1 | MIT | thư viện (npm) |
| vue-tsc | 2.2.0 | MIT | thư viện (npm) |
| which | 2.0.2 | ISC | thư viện (npm) |
| why-is-node-running | 2.3.0 | MIT | thư viện (npm) |
| word-wrap | 1.2.5 | MIT | thư viện (npm) |
| xml-name-validator | 5.0.0 | Apache-2.0 | thư viện (npm) |
| yaml-ast-parser | 0.0.43 | Apache-2.0 | thư viện (npm) |
| yargs-parser | 21.1.1 | ISC | thư viện (npm) |
| yocto-queue | 0.1.0 | MIT | thư viện (npm) |

## 5. Mục cần người duyệt

- Không có gói npm nào ngoài danh sách giấy phép OSI thông dụng.
