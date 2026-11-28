<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# Đối chiếu yêu cầu đề thi

Đề: OLP Phần mềm nguồn mở 2026 (VFOSSA), nền tảng văn phòng số mã nguồn mở. Bảng dưới nối từng yêu cầu với chỗ
đáp ứng trong mã, cách kiểm nhanh trên bản cài local và giới hạn. Mục nào chưa làm thì ghi **chưa**.

Chuẩn bị một lần (xem [installation.md](installation.md)): `python scripts/bootstrap.py`, chạy compose profile `workspace`,
rồi `python scripts/seed.py --confirm-demo`. Địa chỉ gốc: <http://localhost:8080>. Tài khoản demo nằm trong file
credential do bootstrap sinh (đừng đưa lên màn hình chiếu). API Core cần token OIDC; không có token thì kiểm qua
giao diện hoặc chạy test bằng `make test`.

## 1. Core headless (`/core/v1/`)

Core không có giao diện nghiệp vụ; mọi thứ qua API ([contracts/core.openapi.json](../contracts/core.openapi.json)) và
console quản trị `/console/`. Core thực tế chia 4 nhóm đúng đề, thêm nhật ký kiểm toán.

| Yêu cầu | Đáp ứng ở đâu | Cách kiểm trong 1 phút | Giới hạn |
|---|---|---|---|
| Danh tính, phân quyền | OIDC qua Keycloak: `/core/v1/auth/login`, `/auth/callback`, `/principals/me`; `/applications` (mỗi ứng dụng một namespace); `/authorization/check`, `/authorization/explain`, `/resources/{id}/grants` (ACL theo tài nguyên). Mã: `services/core-api/src/dx_core/policy.py`, `main.py` | Mở <http://localhost:8080/>, đăng nhập `staff`, rồi `manager` ở cửa sổ ẩn danh; người phòng khác không thấy hồ sơ không được chia sẻ. Console: <http://localhost:8080/console/> | MFA (TOTP) mới bắt buộc cho tài khoản demo `lanh-dao-mfa` (required action `CONFIGURE_TOTP` do `scripts/bootstrap.py` đặt khi cài mới); các tài khoản demo khác chưa có yếu tố thứ hai để seed, e2e chạy được ([security.md](security.md)). Chưa mTLS giữa các dịch vụ. |
| Dữ liệu có cấu trúc (record) | `/schemas` (tạo, `publish`), `/records` (tạo, `PATCH`), `/records/{id}/versions`. Mỗi lần sửa thêm một dòng `record_versions` kèm tác giả | Console `/console/`: tạo schema, ghi record, sửa, xem lịch sử phiên bản | Phiên bản record lưu `revision` và `author`, **không** có hash nội dung riêng. |
| Tệp, tài liệu | `/storage/uploads` (tạo, `PUT content`, `complete`), `/storage/files/{id}/versions`, `download-tickets`, `holds`. Mỗi phiên bản có `checksum` SHA-256 (`storage.py`), kiểm lại khi hoàn tất (`checksum_mismatch`) | Workspace › Kho tài liệu (<http://localhost:8080/drive>): tải tệp lên, tải bản mới, xem lịch sử phiên bản | Chỉ nhận đuôi tệp trong danh sách cho phép (mục 3). Kho local hoặc S3. |
| Quy trình | `/workflows` (tạo, `validate`, `publish`, `runs`), `/workflow-simulations`, `/workflow-runs`, `/human-tasks/{id}/complete`, `/workflow-runs/{id}/decision-traces`. Mã: `workflow.py`, `worker.py` | Workspace › Quy trình (<http://localhost:8080/processes>): chạy thử một quy trình; hoặc tạo hồ sơ ở `/cases` rồi duyệt ở `/approvals` | Bộ node là tập cố định (`/node-types`), không phải BPMN. |
| (Thêm) Nhật ký kiểm toán | `/audit-logs`, `/audit-logs/verify`; chuỗi băm SHA-256, mỗi dòng nối dòng trước (`audit_chain.py`, `verify_chain`) | Console › **Nhật ký hệ thống** (<http://localhost:8080/console/>). Kiểm chuỗi: `GET /core/v1/audit-logs/verify` bằng token quản trị, hoặc test `services/core-api/tests/test_audit_chain.py` | Chỉ phát hiện sửa trực tiếp bằng SQL; ai ghi lại được cả bảng thì tính lại được hash (ghi rõ đầu `audit_chain.py`). Dòng cũ trước migration `core_0003` báo `unchained`. |

## 2. Ứng dụng giao diện: Workspace (H-P-D-I)

Mã: `apps/workspace-web`, `services/workspace-api`. Workspace chỉ gọi Core qua API, không đọc DB của Core.

| Yêu cầu | Đáp ứng ở đâu | Cách kiểm trong 1 phút | Giới hạn |
|---|---|---|---|
| H, cộng tác người | Nhắn tin `/chat`, bảng tin `/feed`, công việc `/tasks` | Đăng nhập `staff`: <http://localhost:8080/chat>, <http://localhost:8080/feed>, <http://localhost:8080/tasks> | Chưa đo tải nhiều người dùng đồng thời. |
| P, quy trình | Hồ sơ `/cases`, duyệt `/approvals`, thiết kế quy trình và tự động hóa `/processes`; chạy trên workflow của Core | Tạo hồ sơ ở `/cases`, đăng nhập `manager`, duyệt hoặc trả lại ở `/approvals`; xem lịch sử bước trong trang hồ sơ | Luồng gửi, trả lại, duyệt kiểm bằng pytest; E2E trình duyệt mới phủ một phần (`docs/acceptance.md`). |
| D, dữ liệu, báo cáo | Kho tài liệu `/drive` (soạn thảo ONLYOFFICE khi bật profile `office`), tìm kiếm `/search`, báo cáo `/reports` | <http://localhost:8080/reports> sau khi seed; <http://localhost:8080/search> | ONLYOFFICE là tùy chọn, bật riêng. |
| I, trí tuệ (AI) | 19 tính năng, **mặc định tắt**, tắt thì không hiện nút (`ai_core.py` `FEATURES`, `assistant.py`); AI chỉ đề xuất, chỉ nhận dữ liệu người dùng được xem. Xem [ai-features.md](ai-features.md) | Đăng nhập quản trị: <http://localhost:8080/assistant> › Tính năng AI, mọi công tắc đang tắt | Phải tự khai dịch vụ AI (khóa API hoặc Ollama). Mới thử thật với Ollama; **chưa** thử Claude, OpenAI, Gemini. |
| Mở rộng | Plugin ([plugins.md](plugins.md)): iframe sandbox, lời gọi ký HMAC, token theo phạm vi. Gói mở rộng `.zip` ([packs.md](packs.md)); kho gói: <https://github.com/Dking2007/Desktiny_expansion_pack> | <http://localhost:8080/plugins> và <http://localhost:8080/packs>: cài thử một `.zip`, đọc phần xem trước | Plugin kết nối chạy ở máy chủ riêng do người cài lo. |

## 3. Bốn nguyên tắc kỹ thuật

| Nguyên tắc | Đáp ứng ở đâu | Cách kiểm trong 1 phút | Giới hạn |
|---|---|---|---|
| (i) Vòng đời dữ liệu, đẩy dữ liệu lịch sử vào data lake | Phần nền: phiên bản tệp và record, `holds` giữ tệp (`/storage/versions/{id}/holds`). Plugin **Lưu trữ lịch sử** (bản mở rộng `quan-tri-du-lieu`, [kho Pack](https://github.com/Dking2007/Desktiny_expansion_pack)): hồ sơ đã duyệt hoặc kết thúc được chép ra tệp JSONL theo tháng; tháng quá thời gian giữ (`giu_thang`) được đánh dấu cần chuyển kho lạnh | Cài plugin, duyệt một hồ sơ, mở trang quản trị của plugin thấy bản lưu trong tháng; test `tests/test_luu_tru_lich_su.py` của kho Pack | Là bản minh họa: tệp JSONL, **không** phải data lake, không lưu dạng cột, không có công cụ truy vấn. Kho lạnh chỉ là đánh dấu, chuyển tệp là việc của quản trị. Chưa có chính sách xóa tự động. |
| (ii) Hội tụ IT/OT, dữ liệu cảm biến | Plugin **Cảm biến thiết bị** (bản mở rộng `van-hanh`, [kho Pack](https://github.com/Dking2007/Desktiny_expansion_pack)): thiết bị gửi số đo `POST /api/so-do` với khoá riêng; vượt ngưỡng thành sự kiện (có hàng chờ gửi lại khi Desktiny lỗi); luồng tự động tạo hồ sơ sự cố, quy trình giao người phụ trách | `scripts/gia_lap_cam_bien.py` của kho Pack giả lập một thiết bị; test `tests/test_cam_bien.py` và test cài thật `tests/desktiny` | Chỉ HTTP(S); **chưa** MQTT, OPC UA, Modbus, **chưa** cơ sở dữ liệu chuỗi thời gian. Luồng tạo hồ sơ sự cố là mẫu luồng, quản trị bật một lần sau khi cài. |
| (iii) Nguồn gốc, lineage, chất lượng dữ liệu | Phiên bản tệp có SHA-256 và tác giả; phiên bản record có tác giả; vết quyết định từng lần chạy quy trình (`/workflow-runs/{id}/decision-traces`); chuỗi băm nhật ký. Plugin **Lưu trữ lịch sử** ghi mỗi bản lưu kèm nguồn, phiên bản, sha256 nối chuỗi; kiểm toàn vẹn và tra ngược theo mã hồ sơ về hồ sơ gốc | Trang hồ sơ hiện snapshot, người quyết định, phiên bản tệp đúng lần trình; Console › Nhật ký hệ thống; trang quản trị của plugin Lưu trữ lịch sử › Kiểm toàn vẹn | **Chưa** có đồ thị lineage giữa các bộ dữ liệu, **chưa** có chỉ số chất lượng dữ liệu. Chuỗi băm phát hiện sửa đổi, không ngăn được. |
| (iv) Zero-Trust, GitOps, quét mã độc ở biên | Zero-Trust một phần: lời gọi Core qua OIDC và kiểm quyền theo tài nguyên; gateway chỉ bind `127.0.0.1:8080`, trả 404 cho `/internal/` (`infra/gateway/nginx.conf`); CSP chặt (`default-src 'self'`, `object-src 'none'`); tệp tải lên theo danh sách cho phép, kiểm chữ ký media và zip (`inspect_content` trong `storage.py`, test `test_storage_inspection.py`); plugin cô lập (mục 2). CI và release: `.github/workflows/ci.yml`, `release.yml` | `curl -i http://localhost:8080/internal/x` trả 404; `curl -sI http://localhost:8080/` thấy header `Content-Security-Policy`; tải tệp `.exe` lên Kho tài liệu bị từ chối `unsupported_file_type` | Quét mã độc ClamAV **tùy chọn**, mặc định tắt (profile `security`, `CLAMAV_HOST`; lỗi quét thì từ chối tệp, test `services/core-api/tests/test_malware_scan.py`); chỉ quét lúc tải lên, không quét lại tệp đã lưu. MFA mới bắt buộc cho `lanh-dao-mfa` (mục 1). GitOps mới ở mức CI và release có `SHA256SUMS`; chưa có bộ điều phối triển khai theo Git (Argo CD, Flux). |

## Việc chưa làm (tóm tắt)

- Data lake thật (lưu dạng cột, truy vấn) thay cho tệp JSONL minh họa (nguyên tắc i, iii).
- Giao thức OT (MQTT, OPC UA), cơ sở dữ liệu chuỗi thời gian (nguyên tắc ii).
- MFA bắt buộc cho mọi tài khoản lãnh đạo, quản trị; quét lại tệp đã lưu khi có chữ ký mã độc mới (nguyên tắc iv).
- GitOps triển khai tự động, mTLS giữa dịch vụ, lineage giữa bộ dữ liệu, chỉ số chất lượng dữ liệu.

Kiểm ngày 27/11/2026 trên `main` (`c4ccb9f`): `pytest` 356 passed, 1 skipped (test PostgreSQL cần `DX_TEST_POSTGRES_URL`).
Kiểm ngày 28/11/2026 trên nhánh `tich-hop/olp-2026-11-28` (`610f2a3`): `pytest` 399 passed, 1 skipped; CI GitHub
(backend, frontend, compliance) xanh. Kho Pack: job `cai-vao-desktiny` trên GitHub với Desktiny `v3.1.0` 6 đạt, 2 bỏ qua
(hai lỗi đã sửa sau 3.1.0); với nhánh tích hợp 8/8 trên máy.
Đường dẫn mã và route đã đối chiếu với nguồn và `contracts/core.openapi.json` (phiên bản 3.1.0).
