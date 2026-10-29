# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/), đánh phiên bản theo
[SemVer](https://semver.org/lang/vi/). Mỗi mục trỏ tới commit thật trong lịch sử Git; từ
0.2.0 trở đi mỗi thay đổi đi kèm issue/PR. So sánh chi tiết V1 → V2: [docs/V2_CHANGES.md](docs/V2_CHANGES.md).

## [Unreleased]

### Added
- `scripts/desktiny-migrate.sh` (cài thành `$PREFIX/bin/desktiny-migrate`): chạy migration CSDL từ bản đã cài, không cần thư mục mã nguồn.

### Fixed
- Sửa chữ `WorkMMODIARY` (lỗi thay chuỗi) thành `Workspace` trong chú thích mã và `docs/acceptance.md`.
- Tạo hồ sơ với trường số không bắt buộc để trống bị từ chối (`amount: None is not of type number`): form web gửi `null`, nay `validate_payload` coi giá trị `null` là chưa nhập. Có test hồi quy.
- Người dùng demo do `scripts/bootstrap.py` sinh có họ (`lastName`) trống; Keycloak 26 buộc điền họ ở bước `VERIFY_PROFILE`, nên lần đăng nhập đầu của mọi tài khoản demo bị chặn và Playwright E2E có đăng nhập không qua được. Nay `lastName` là `Demo`.
- `make install` không cài `alembic.ini` và `migrations/`, nên bản cài ra `PREFIX` không thể khởi tạo CSDL khi xóa thư mục mã nguồn (tiêu chí PoF 4, mục "chạy được ngoài thư mục mã nguồn"). Nay cài vào `$PREFIX/share/desktiny/<service>-api/`.

### Changed
- Cấu trúc Workspace API: bỏ hai vòng phụ thuộc bị che bằng import trong hàm (`tasks` ↔ `messaging`, `routers` ↔ `packages`). `validate_payload` và `step_evidence` chuyển vào `schemas.py`; `membership` và `message_readable` chuyển vào `policies.py`; các import cục bộ giữa `automations`, `messaging` và `tasks` đưa lên đầu tệp. Không đổi hành vi hay API (contract OpenAPI không đổi; 105 test dịch vụ + 4 test ranh giới đạt). `tests/test_boundaries.py` có thêm test chặn vòng phụ thuộc mới.
- Thêm `.gitattributes` và `.editorconfig` (LF thống nhất giữa Windows/Linux/macOS).
- `npm run generate:api` giữ header SPDX của hai tệp sinh ra (trước đây xóa mất, làm job `compliance` đỏ). CI so sánh `contracts/` và `apps/shared/src/generated/` với bản đã commit.
- Chuyển hai tài liệu thiết kế vào `docs/design/`; `docs/third-party-inventory.md` ghi rõ phạm vi so với `THIRD_PARTY.md`.
- Ba `pyproject.toml` khai báo `license = "Apache-2.0"` (trước đây `pip-licenses` báo UNKNOWN cho gói tự viết). Quét `pip-licenses` trên image runtime ngày 28/10/2026: 47 gói, không có GPL/SSPL/BUSL/Elastic; chỉ psycopg là LGPL-3.0 (đúng khai báo, nạp libpq của hệ điều hành).
- Cập nhật `docs/architecture.md`, `docs/installation.md`, `docs/acceptance.md` theo trạng thái thật (chat, bảng tin, canvas đã có; Docker/E2E đã chạy ngày 28/10/2026; ghi rõ mục chưa kiểm). `docs/issues-backlog.json` bổ sung các việc đã xong và việc còn mở.
- Thống nhất số phiên bản 0.2.2 ở `package.json` (gốc và 3 workspace), `package-lock.json`, 3 `pyproject.toml` (kèm ràng buộc `dx-platform-kit==`), tiêu đề OpenAPI của hai dịch vụ và `contracts/*.openapi.json` (trước đây còn ghi 0.1.0).
- Thêm `.mailmap` gộp tên hiển thị "unknown" của các commit cũ về `Dking2007` (cùng email; không viết lại lịch sử); CONTRIBUTING.md hướng dẫn cấu hình `user.name`/`user.email` trước khi commit.
- `make install` dùng pip của `.venv` (cần `make venv` trước) thay vì `python3 -m pip` của hệ thống (kèm `--ignore-installed` để mọi phụ thuộc thật sự nằm trong `PREFIX`, không bị bỏ qua vì đã có trong `.venv`): Python 3.13 từ deadsnakes trên Ubuntu 24.04 không có pip, nên lệnh cũ thất bại. `desktiny-migrate` tự chọn đúng `python3.X` đã cài gói thay vì `python3` mặc định. BUILD.md gọi `make venv deps PYTHON=python3.13`. Cả ba lỗi tìm ra khi chạy BUILD.md từng dòng trong Ubuntu 24.04 sạch (27/10/2026).
- Phụ thuộc `psycopg[binary]` đổi thành `psycopg` thuần Python: không còn đóng gói sẵn libpq trong wheel; hệ điều hành cung cấp `libpq5` (đã thêm vào `api.Dockerfile`, bước CI backend và BUILD.md). `psycopg-binary` bị loại khỏi `requirements.lock` và `THIRD_PARTY.md` (54 gói Python).
- BUILD.md: thêm mục Thư viện hệ thống và `libpq5` vào bảng yêu cầu.
- Tài liệu (`V2_CHANGES.md`, `SELF_REVIEW.md`) trỏ tới v0.2.1 là bản dùng để chấm.

## [0.2.1] - 2026-10-26

### Fixed
- `reuse lint` lỗi do `scripts/add_spdx_headers.mjs` và `CONTRIBUTING.md` chứa mẫu header SPDX bị đọc nhầm; bỏ khóa không hợp lệ trong `REUSE.toml` — `d31d057`, `fdc0e7c`. CI toàn bộ xanh từ bản này; `v0.2.0` giữ nguyên làm mốc lịch sử. **Lưu ý:** `v0.2.0` được build từ commit `633b9ec` khi `reuse lint` còn lỗi, vì vậy bản dùng để chấm/cài đặt là `v0.2.1` trở lên, không phải `v0.2.0`.

## [0.2.0] - 2026-10-26 — DXOS V2: sẵn sàng đối chiếu tiêu chí PoF

Bản V2 giữ nguyên chức năng của V1 (0.1.0) và hoàn thiện phần kho mã nguồn: giấy phép, khai
báo thành phần ngoài, hướng dẫn biên dịch, phát hành và tài liệu cộng đồng.

### Added
- Header `SPDX-License-Identifier` + `SPDX-FileCopyrightText` cho 180 tệp mã/cấu hình; công cụ
  `scripts/add_spdx_headers.mjs` (idempotent, có `--check`).
- `LICENSES/Apache-2.0.txt` và `REUSE.toml` (khai báo tập trung cho JSON/Markdown/lockfile/HTML) — chuẩn REUSE.
- `THIRD_PARTY.md` sinh bởi `scripts/gen_third_party.mjs`: 309 gói npm, 55 gói Python, 9 dịch vụ/image với SPDX, nguồn, cách dùng.
- `Makefile` (venv, deps, build, test, lint, `install PREFIX=`, dist, up/down, reuse, licenses) và `BUILD.md`.
- `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SELF_REVIEW.md`.
- Mẫu issue (bug, tính năng), mẫu pull request, nhãn & quy ước commit.
- CI: job `compliance` (reuse lint, kiểm header, đối chiếu THIRD_PARTY.md, quét giấy phép), job build sạch.
- Workflow `release.yml`: đẩy tag `v*` tự tạo Release có `.tar.gz` + `SHA256SUMS`.
- `docs/V2_CHANGES.md`: bảng so sánh V1 → V2 và ánh xạ 6 tiêu chí PoF.
- README: mục *Giấy phép* (lý do chọn Apache-2.0, trỏ LICENSE/THIRD_PARTY) và *Đóng góp*.

### Changed
- `package.json` (gốc và 3 workspace) khai báo `"license": "Apache-2.0"`.
- README/docs trỏ về BUILD.md làm điểm vào cài đặt.

## [0.1.0] - 2026-10-24 — DXOS V1 (đường cơ sở)

Trạng thái kho trước khi bước vào V2, tag hồi tố tại `f089bfb`.

### Added
- Khung dự án, nền tảng Core + Workspace (FastAPI/Vue 3), SSO Keycloak, Docker Compose — `ded2d88`, `e29fa17`.
- Cập nhật nghiệp vụ Drive, hồ sơ, workflow, giao việc — `0fd1ef0`.
- Giao diện mới: banner chào, 4 ô số liệu, khối thời gian chờ theo bước — `15725c5`.
- Gói nghiệp vụ trực quan, tự động hóa theo công việc (canvas luồng), chat đa phương tiện, khung làm việc dễ dùng — `abab487`.
- Bảng tin có ảnh/video; xem PDF, ảnh, video, âm thanh ngay trong ứng dụng — `f949ab9`.

### Changed
- Đổi tên sản phẩm thành Desktiny — `f089bfb`.

### Fixed
- Thứ tự import trong `auth.py` để CI backend qua ruff — `d495abb`.

[Unreleased]: https://github.com/Raphael-Fug/DXOS_V2/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/Raphael-Fug/DXOS_V2/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Raphael-Fug/DXOS_V2/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Raphael-Fug/DXOS_V2/releases/tag/v0.1.0
