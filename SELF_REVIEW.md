# Tự rà soát PoF – Nhóm Desktiny (DXOS V3) – OLP PMNM 2026

Ngày rà soát: 26/10/2026 (lần 1, bản nháp; cập nhật 01/11/2026); rà lại cho V3 ngày 15/11/2026 · Người thực hiện: Claude (hỗ trợ) — **chưa có thành viên ký** ·
Commit được rà: commit mang tag `v3.0.0` (bản V3; so sánh với V2 ở [docs/V3_CHANGES.md](docs/V3_CHANGES.md)). Các dòng có ngày trước 15/11 là kết quả của V2 (`v0.2.2`), giữ làm lịch sử.

> Đây là bản nháp trung thực để thành viên nhóm kiểm lại, **không** phải xác nhận cuối. Mỗi dòng "Đã kiểm" nêu lệnh
> đã chạy; dòng "Chưa kiểm" cần người chạy trước 23–29/11 và 03/12.

## 1. Giấy phép dự án
- Giấy phép: **Apache-2.0** ([LICENSE](LICENSE), [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt)). Lý do: xem README, mục Giấy phép.
- Đã kiểm: `node scripts/add_spdx_headers.mjs --check` → mọi tệp mã/cấu hình có header SPDX (180 tệp được thêm ở V2).
- Đã kiểm 15/11 (V3): `add_spdx_headers --check` đạt; `reuse lint` trên bản clone trong container: 434/434 tệp có bản quyền và giấy phép, đạt REUSE 3.3.
- **Chưa kiểm**: ScanCode.

## 2. Thành phần bên ngoài
Danh sách đầy đủ trong [THIRD_PARTY.md](THIRD_PARTY.md) (V3: 310 npm, 63 Python, 9 dịch vụ). Điểm cần chú ý:

| Thành phần | Phiên bản | Giấy phép (SPDX) | Nguồn | Cách dùng |
|---|---|---|---|---|
| psycopg | 3.2.10 | LGPL-3.0-only | PyPI | thư viện pip thuần Python, không sửa; nạp libpq5 của hệ điều hành |
| ONLYOFFICE Docs | 8.3.3 | AGPL-3.0-only | image chính thức | dịch vụ chạy riêng, mặc định tắt |
| RustFS | 1.0.3 | Apache-2.0 | image chính thức | dịch vụ S3 chạy riêng (thay MinIO) |
| Valkey | 8.1.1 | BSD-3-Clause | image chính thức | dịch vụ chạy riêng (thay Redis) |
| @fontsource/* | 5.1.1 | OFL-1.1 | npm | font gói qua npm |

- Đã kiểm: giấy phép npm đọc từ `node_modules` bằng `scripts/gen_third_party.mjs` — 0 gói ngoài danh sách OSI.
- **Chưa kiểm**: giấy phép 54 gói Python (ghi theo metadata upstream) — cần `pip-licenses`; mở LICENSE đúng phiên bản cho `certifi`, `psycopg`.
- Đã kiểm 15/11 (V3): `gen_third_party.mjs` sinh lại `THIRD_PARTY.md` không khác biệt (0 gói cần duyệt); `pip-licenses` trên `requirements.lock` trong container: trong các gói của dự án chỉ `psycopg` là LGPL-3.0 (đã khai báo); `python-debian` (GPL-2.0+) chỉ xuất hiện vì cài công cụ `reuse` để kiểm, không phải phụ thuộc của Desktiny.
- Không có `vendor/`, `node_modules/`, tệp nhị phân của bên khác trong Git (`git ls-files | grep node_modules` → 0).

## 3. Biên dịch, phát hành, tài liệu
- Đã chạy trên Windows/Node 24: `npm run lint`, `typecheck`, `test` (45/45 đạt), `build` — đều thành công.
- Đã kiểm 27/10 (Docker Desktop trên Windows, container Linux): `ruff check` sạch; `pytest` 108 đạt với PostgreSQL 17.5 thật; `python -m unittest discover -s infra/tests` 2 đạt; `export_contracts.py` sinh ra contract trùng bản đã commit; build image `api.Dockerfile` cho `core-api` và `workspace-api`; chạy BUILD.md cách B trong `ubuntu:24.04` sạch (`make venv deps`, `build`, `test`, `install PREFIX=`, xóa mã nguồn, `desktiny-migrate core` tạo 23 bảng, `uvicorn` khởi động từ bản đã cài). Lượt chạy này tìm ra và sửa 3 lỗi của `make install` (xem CHANGELOG).
- Đã kiểm 28/10 trên stack Docker Compose đang chạy (11 container: Keycloak, RustFS, Postgres, Valkey, gateway, 2 API, 2 worker, 2 web; `identity`, `core-api`, `workspace-api`, `postgres`, `broker` báo healthy; gateway `:8080` trả 200, OIDC discovery 200). Stack này dựng từ một bản sao cục bộ khác thư mục, image dựng trước nhánh này, nên **chưa phải** lượt chạy `make up` từ chính commit của nhánh. Playwright E2E có đăng nhập (`tests/e2e`, Chromium, tài khoản demo `staff`): 3/3 đạt sau khi sửa lỗi họ trống của người dùng demo (xem CHANGELOG) và tạo một biểu mẫu đã phát hành bằng tài khoản `manager`, vì `seed` không tạo biểu mẫu. `reuse lint` trên bản clone sạch: 227/227 tệp đạt (REUSE 3.3); `add_spdx_headers --check` và đối chiếu `THIRD_PARTY.md` đạt. Đã kiểm thêm 28/10: `pip-licenses` trên image runtime (47 gói: chỉ psycopg là LGPL-3.0, không có giấy phép bị cấm; uvloop ghi Apache/MIT, khớp THIRD_PARTY.md; gói tự viết nay khai báo Apache-2.0); Core chạy độc lập khi dừng Workspace (I03, `examples/core-client`). **Chưa kiểm**: ONLYOFFICE Document Server thật, backup/restore, `make up` từ chính commit này, ScanCode, `make dist`/Release từ nhánh này.
- Đã kiểm 15/11 (V3, nhánh `release/v3.0.0`, Windows 11 + Docker Desktop): `npm run typecheck` sạch; vitest 83/83 đạt; `ruff check` sạch; `pytest` 351 đạt trong container `python:3.13-slim` + `postgres:17.5-alpine` theo cấu hình job `backend` của CI; `audit_repo.mjs`: kho sạch (439 tệp). Build Docker Compose từ code V3 trên CSDL đang có dữ liệu của `main` trước đó (image build thành công sau khi sửa; migration `workspace_0022`–`workspace_0027` chạy được trên CSDL đang có dữ liệu ở `workspace_0021`; `/` và `/console/` trả 200, đăng nhập chuyển hướng sang Keycloak). Lượt build đầu tìm ra lỗi thiếu `examples/plugins` trong `web.Dockerfile`, đã sửa (xem CHANGELOG).
- Release: tag `v0.1.0` (V1, hồi tố), `v0.2.0` (mốc lịch sử), `v0.2.1`, `v0.2.2` (V2), `v3.0.0` và `v3.1.0` (V3); workflow `release.yml` tạo `.tar.gz` + `SHA256SUMS`. Đã kiểm 27/11: API công khai của GitHub (không đăng nhập) liệt kê 5 Release (`v0.2.0`, `v0.2.1`, `v0.2.2`, `v3.0.0`, `v3.1.0`), mỗi bản kèm `.tar.gz` và `SHA256SUMS`; `v0.1.0` chỉ có tag.
- Đã kiểm 28/11 (nhánh `tich-hop/olp-2026-11-28`, `610f2a3`): `pytest` 399 đạt, 1 bỏ qua (test PostgreSQL cần `DX_TEST_POSTGRES_URL`); CI GitHub (backend, frontend, compliance) xanh, gồm kiểm contract OpenAPI và kiểu TypeScript sinh ra khớp mã. Kho Pack: job `cai-vao-desktiny` chạy trên GitHub với tag `v3.1.0` (6 đạt, 2 bỏ qua cho hai lỗi đã sửa sau 3.1.0), 8/8 trên máy với nhánh tích hợp. Sao lưu, khôi phục đã diễn tập 28/11 (số đo trong `docs/operations.md`). **Chưa kiểm**: chạy lại từ đầu trên Ubuntu sạch theo `BUILD.md` từ tag mới, ScanCode.
- Bug tracker: đã kiểm 29/10 qua API công khai của GitHub — repo có 28 issue (#1–#28, trạng thái mở/đóng theo `docs/issues-backlog.json`) và 5 milestone. Cập nhật 01/11: đã có Pull Request #30–#33 (đã đóng/merge), trong đó PR #32 gồm 3 commit của thành viên `Raphael-Fug` (tài khoản riêng) đã merge vào `main` (e236157).

## 4. Rủi ro còn lại và cách xử lý
- Tiêu chí nhiều thành viên: từ `v0.2.2` đến `v3.0.0` có commit của ba tài khoản (`Dking2007` 51, `Raphael-Fug` 28, `Mai1174` 17, không tính merge) và PR #34–#38 merge trên GitHub. Một số commit cũ trên `main` còn trailer đồng tác giả công cụ AI — nhóm quyết định có viết lại lịch sử hay không. Người chịu trách nhiệm: nhóm trưởng.
- Giấy phép Python: đã quét bằng `pip-licenses` trong container ngày 15/11; nên chạy lại khi đổi `requirements.lock` — người chịu trách nhiệm: thành viên phụ trách tuân thủ.
- V3 áp dụng lại gói ngành (PR #37) mà `main` đã revert ở PR #38; nhóm cần thống nhất trước khi merge `release/v3.0.0` vào `main`. Kho chưa có `.gitattributes`, máy Windows đặt `core.autocrlf=true` sẽ hỏng script khởi tạo Postgres (xem docs/V3_CHANGES.md, mục 5).
- Cập nhật README/docs nói "chưa nghiệm thu" ở nhiều nơi: giữ nguyên, không tuyên bố quá mức.

## 5. Đối chiếu yêu cầu đề thi

Nguồn đã đối chiếu ngày 21/11/2026: [Thể lệ](https://vfossa.vn/tin-tuc/the-le-olp-phan-mem-nguon-mo-nam-2026-760.html)
(09/06/2026) và [Đề thi](https://vfossa.vn/tin-tuc/de-thi-phan-mem-nguon-mo-olp-2026-798.html) (30/09/2026).

### 5.1 Tiêu chí PoF (50 điểm) và bằng chứng

| Tiêu chí (tối đa) | Lỗi bị trừ theo thể lệ | Bằng chứng trong kho |
|---|---|---|
| 1. Quản lý mã nguồn (5) | không web viewer, không truy cập mở, không thực sự dùng | Kho công khai trên GitHub; lịch sử commit của ba thành viên; PR #30–#39 |
| 2. Giấy phép OSI (10) | thiếu giấy phép trong từng tệp; không tương thích; thiếu thông báo mục đích; thiếu toàn văn | Apache-2.0; header SPDX trong mọi tệp mã (`add_spdx_headers --check`); [LICENSE](LICENSE), [LICENSES/](LICENSES/); README mục Giấy phép nêu lý do và tính tương thích |
| 3. Release (5) | không có; không theo phiên bản; định dạng không mở | [Releases](https://github.com/Dking2007/DXOS_Desktiny/releases) tag `v0.1.0`, `v0.2.0`, `v0.2.1`, `v0.2.2`, `v3.0.0`, `v3.1.0` (`git tag`), gói `.tar.gz` kèm `SHA256SUMS` (gói zip do GitHub tự thêm, không phải bản phân phối) |
| 4. Biên dịch từ mã nguồn (10) | thiếu hướng dẫn; sửa tay header; không cấu hình được; công cụ đóng; không chạy ngoài thư mục nguồn | [BUILD.md](BUILD.md): `make venv deps build test`, cấu hình qua biến môi trường/`.env`, `make install PREFIX=` rồi chạy từ bản đã cài (mục 3) |
| 5. Thư viện, gói đính kèm (10) | không dùng thư viện hệ thống; đính kèm gói dự án khác; sửa mã gói đính kèm | [THIRD_PARTY.md](THIRD_PARTY.md); phụ thuộc lấy qua npm/PyPI/image chính thức; không có `vendor/` hay mã bên thứ ba trong Git (mục 2) |
| 6. Tài liệu, giao tiếp (10) | thiếu bug tracker; thiếu changelog; thiếu README | [Issues](https://github.com/Dking2007/DXOS_Desktiny/issues); [CHANGELOG.md](CHANGELOG.md); [README.md](README.md), [docs/installation.md](docs/installation.md) |

### 5.2 Yêu cầu bắt buộc của đề

| Yêu cầu | Thành phần | Trạng thái |
|---|---|---|
| Core headless ở Tầng 1, không cung cấp giao diện | `services/core-api`, `core-worker`; chỉ có API `/core/v1/` | Có. `--profile core` không phục vụ trang nào (`/`, `/console/` trả 404). Core admin (`apps/core-admin`) là client riêng ở Tầng 2, chỉ chạy với profile `console` hoặc `workspace` |
| Identity/SSO | Keycloak, OIDC code flow + PKCE | Có |
| API Gateway | Nginx (`infra/gateway/nginx.conf`): định tuyến, giới hạn tần suất, CSP, chặn `/internal/` | Có |
| Dữ liệu có cấu trúc và phi cấu trúc | Schema/record có phiên bản (PostgreSQL); tệp có phiên bản (RustFS, S3) | Có |
| Workflow | Engine đồ thị (`packages/flowkit`), run, human task | Có |
| Ít nhất một ứng dụng giao diện trong H-P-D-I | Workspace: H (giao việc, trao đổi), P (hồ sơ, phê duyệt, quy trình), D (báo cáo, một phần) | Có. I (Trí tuệ) có ở mức tính năng hỗ trợ, nêu giới hạn ngay dưới bảng này |

Trạng thái I (Trí tuệ), đối chiếu mã trong `services/workspace-api/src/dx_workspace` và [docs/ai-features.md](docs/ai-features.md):

- Có trợ lý trả lời cách dùng phần mềm và quy trình (`assistant.py`, `POST /assistant/chat`), chỉ dựa trên bài tri thức do quản trị viên viết hoặc sinh từ gói quy trình đã phát hành. Có 19 tính năng AI khai trong `ai_core.py` (`FEATURES`), gồm hỏi đáp về hồ sơ (`POST /ai/cases/{id}/ask`), đọc tài liệu điền biểu mẫu, soạn văn bản hành chính, tóm tắt, giao việc bằng câu nói và tìm theo ý nghĩa (`POST /ai/search`). `docs/ai-features.md` liệt kê đủ 19.
- Mặc định **tắt hết**: cấu hình trợ lý có `enabled=False`, mọi tính năng cần được người giữ quyền `assistant.manage` bật riêng. Dự án **không kèm model nào**: cần quản trị viên khai một dịch vụ AI bên ngoài (Anthropic, OpenAI, Gemini, DeepSeek, Ollama, vLLM hoặc cổng tương thích). Tính năng chưa bật thì lệnh gọi trả lỗi 409 `ai_feature_disabled`.
- Giới hạn: AI chỉ đề xuất, không tự trình, duyệt hay giao việc; mặc định 50 lượt AI/người/ngày; đọc tối đa 60 trang một tệp; tìm theo ý nghĩa cần thêm dịch vụ và model tạo vector, vector lưu trong cột JSON và tính độ giống bằng Python, chưa dùng cơ sở dữ liệu vector. Dùng dịch vụ đám mây nghĩa là nội dung người dùng được xem sẽ được gửi ra dịch vụ đó.
- Mức đã kiểm: có test backend với dịch vụ AI giả (`tests/test_ai.py`, `test_assistant.py`); ngày 31/10/2026 gọi thật Ollama `gpt-oss:20b` và `bge-m3`. **Chưa thử** với Claude, OpenAI, Gemini thật, và chưa thử tài liệu scan với model có thị giác.

### 5.3 Bốn nguyên lý kỹ thuật (đề nêu nền tảng cần được xây dựng dựa trên)

Đề yêu cầu nền tảng xây dựng dựa trên bốn nguyên lý này, nên bảng dưới ghi từng nguyên lý đã có gì và còn thiếu gì, không coi là tùy chọn.

| Nguyên lý | Đã có (bằng chứng) | Còn thiếu |
|---|---|---|
| Vòng đời dữ liệu, đẩy dữ liệu lịch sử xuống hồ dữ liệu | Tệp và record có phiên bản (`services/core-api/src/dx_core`); xóa mềm tài liệu. Plugin minh họa **Lưu trữ lịch sử** (bản mở rộng `quan-tri-du-lieu`, [kho Pack](https://github.com/Dking2007/Desktiny_expansion_pack)): hồ sơ đã duyệt hoặc kết thúc được chép ra tệp JSONL theo tháng, tháng quá thời gian giữ được đánh dấu cần chuyển kho lạnh | Tệp JSONL, chưa phải hồ dữ liệu (không lưu dạng cột, không truy vấn); kho lạnh chỉ là đánh dấu. Bảng `retention_holds` có khai báo trong `models.py` của Core nhưng chưa có mã nào dùng |
| Hội tụ IT/OT, dữ liệu cảm biến | Core là API headless `/core/v1/` nhận dữ liệu có cấu trúc qua client dịch vụ (`client_credentials`). Plugin **Cảm biến thiết bị** (bản mở rộng `van-hanh`, [kho Pack](https://github.com/Dking2007/Desktiny_expansion_pack)): thiết bị gửi số đo qua HTTP với khoá riêng, vượt ngưỡng thành sự kiện (có hàng chờ gửi lại), luồng tạo hồ sơ sự cố giao người phụ trách; có script giả lập thiết bị | Chỉ HTTP(S), chưa MQTT, OPC UA; chưa có cơ sở dữ liệu chuỗi thời gian |
| Phả hệ, nguồn gốc, chất lượng dữ liệu | Phiên bản record và tệp kèm checksum SHA-256 (`storage.py`); snapshot hồ sơ khi trình; nhật ký kiểm toán có chuỗi băm (`audit_chain.py`, `verify_chain`). Plugin Lưu trữ lịch sử ghi mỗi bản lưu kèm nguồn, phiên bản, sha256 nối chuỗi, kiểm toàn vẹn và tra ngược về hồ sơ gốc; che CCCD, điện thoại, e-mail trước khi ghi | Chưa có đồ thị phả hệ giữa các tập dữ liệu, chưa có quy tắc đo chất lượng dữ liệu. Chuỗi băm chỉ phát hiện sửa trực tiếp CSDL, không chống được người ghi lại toàn bảng |
| Zero-Trust, GitOps, quét mã độc ở biên | OIDC cho mọi API, ACL theo người dùng, gateway Nginx chặn `/internal/`, giới hạn tần suất, CSP (`infra/gateway/nginx.conf`); Workspace gọi Core bằng client dịch vụ riêng; tệp tải lên qua danh sách định dạng cho phép và giới hạn ZIP (`inspect_content`); CI và phát hành chạy bằng GitHub Actions từ mã trong kho (`.github/workflows`) | Quét mã độc ClamAV là tùy chọn, mặc định tắt (profile `security`, `CLAMAV_HOST`; lỗi quét thì từ chối tệp), chưa quét lại tệp đã lưu. MFA (TOTP) mới bắt buộc cho tài khoản demo `lanh-dao-mfa`. Chưa có công cụ GitOps đồng bộ trạng thái triển khai từ kho; triển khai dùng `make up` hoặc cài thủ công. Chưa có mTLS giữa các dịch vụ |

### 5.4 Nộp bài

Email trước **17:00 06/12/2026** tới `olpvietnam@vaip.vn` và `thuky@vfossa.vn`, tiêu đề
`BÀI THI PMNM 2026 - [Tên Đội] - [Tên Trường]`, nội dung theo mẫu của BTC (thành viên, người hướng dẫn, đường dẫn kho,
xác nhận đăng ký qua trường, cam kết bản quyền). Chấm kho mã 07–09/12; chung kết 10/12, trình bày 15 phút.

## 6. Xác nhận
Chúng tôi đã tự rà soát và khai báo trung thực theo thể lệ OLP PMNM 2026.

Người ký lần 1: ________________  Ngày: ________   ·   Người ký lần 2 (03/12): ________________  Ngày: ________
