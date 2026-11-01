# Tự rà soát PoF – Nhóm Desktiny (DXOS V2) – OLP PMNM 2026

Ngày rà soát: 26/10/2026 (lần 1, bản nháp; cập nhật trạng thái 01/11/2026) · Người thực hiện: Claude (hỗ trợ) — **chưa có thành viên ký** ·
Commit được rà: ghi bằng `git rev-parse HEAD` tại thời điểm tag `v0.2.2` (bản `v0.2.0` có `reuse lint` lỗi, giữ làm mốc lịch sử).

> Đây là bản nháp trung thực để thành viên nhóm kiểm lại, **không** phải xác nhận cuối. Mỗi dòng "Đã kiểm" nêu lệnh
> đã chạy; dòng "Chưa kiểm" cần người chạy trước 23–29/11 và 03/12.

## 1. Giấy phép dự án
- Giấy phép: **Apache-2.0** ([LICENSE](LICENSE), [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt)). Lý do: xem README, mục Giấy phép.
- Đã kiểm: `node scripts/add_spdx_headers.mjs --check` → mọi tệp mã/cấu hình có header SPDX (180 tệp được thêm ở V2).
- **Chưa kiểm**: `reuse lint` và ScanCode (máy phát triển không có Python); CI job `compliance` chạy `reuse lint` — cần xác nhận xanh.

## 2. Thành phần bên ngoài
Danh sách đầy đủ trong [THIRD_PARTY.md](THIRD_PARTY.md) (309 npm, 54 Python, 9 dịch vụ). Điểm cần chú ý:

| Thành phần | Phiên bản | Giấy phép (SPDX) | Nguồn | Cách dùng |
|---|---|---|---|---|
| psycopg | 3.2.10 | LGPL-3.0-only | PyPI | thư viện pip thuần Python, không sửa; nạp libpq5 của hệ điều hành |
| ONLYOFFICE Docs | 8.3.3 | AGPL-3.0-only | image chính thức | dịch vụ chạy riêng, mặc định tắt |
| RustFS | 1.0.3 | Apache-2.0 | image chính thức | dịch vụ S3 chạy riêng (thay MinIO) |
| Valkey | 8.1.1 | BSD-3-Clause | image chính thức | dịch vụ chạy riêng (thay Redis) |
| @fontsource/* | 5.1.1 | OFL-1.1 | npm | font gói qua npm |

- Đã kiểm: giấy phép npm đọc từ `node_modules` bằng `scripts/gen_third_party.mjs` — 0 gói ngoài danh sách OSI.
- **Chưa kiểm**: giấy phép 54 gói Python (ghi theo metadata upstream) — cần `pip-licenses`; mở LICENSE đúng phiên bản cho `certifi`, `psycopg`.
- Không có `vendor/`, `node_modules/`, tệp nhị phân của bên khác trong Git (`git ls-files | grep node_modules` → 0).

## 3. Biên dịch, phát hành, tài liệu
- Đã chạy trên Windows/Node 24: `npm run lint`, `typecheck`, `test` (45/45 đạt), `build` — đều thành công.
- Đã kiểm 27/10 (Docker Desktop trên Windows, container Linux): `ruff check` sạch; `pytest` 108 đạt với PostgreSQL 17.5 thật; `python -m unittest discover -s infra/tests` 2 đạt; `export_contracts.py` sinh ra contract trùng bản đã commit; build image `api.Dockerfile` cho `core-api` và `workspace-api`; chạy BUILD.md cách B trong `ubuntu:24.04` sạch (`make venv deps`, `build`, `test`, `install PREFIX=`, xóa mã nguồn, `desktiny-migrate core` tạo 23 bảng, `uvicorn` khởi động từ bản đã cài). Lượt chạy này tìm ra và sửa 3 lỗi của `make install` (xem CHANGELOG).
- Đã kiểm 28/10 trên stack Docker Compose đang chạy (11 container: Keycloak, RustFS, Postgres, Valkey, gateway, 2 API, 2 worker, 2 web; `identity`, `core-api`, `workspace-api`, `postgres`, `broker` báo healthy; gateway `:8080` trả 200, OIDC discovery 200). Stack này dựng từ một bản sao cục bộ khác thư mục, image dựng trước nhánh này, nên **chưa phải** lượt chạy `make up` từ chính commit của nhánh. Playwright E2E có đăng nhập (`tests/e2e`, Chromium, tài khoản demo `staff`): 3/3 đạt sau khi sửa lỗi họ trống của người dùng demo (xem CHANGELOG) và tạo một biểu mẫu đã phát hành bằng tài khoản `manager`, vì `seed` không tạo biểu mẫu. `reuse lint` trên bản clone sạch: 227/227 tệp đạt (REUSE 3.3); `add_spdx_headers --check` và đối chiếu `THIRD_PARTY.md` đạt. Đã kiểm thêm 28/10: `pip-licenses` trên image runtime (47 gói: chỉ psycopg là LGPL-3.0, không có giấy phép bị cấm; uvloop ghi Apache/MIT, khớp THIRD_PARTY.md; gói tự viết nay khai báo Apache-2.0); Core chạy độc lập khi dừng Workspace (I03, `examples/core-client`). **Chưa kiểm**: ONLYOFFICE Document Server thật, backup/restore, `make up` từ chính commit này, ScanCode, `make dist`/Release từ nhánh này.
- Release: tag `v0.1.0` (V1, hồi tố), `v0.2.0` (mốc lịch sử), `v0.2.1` và `v0.2.2`; workflow `release.yml` tạo `.tar.gz` + `SHA256SUMS`. Đã kiểm 27/10: API công khai của GitHub (không đăng nhập) liệt kê cả hai Release kèm `.tar.gz` và `SHA256SUMS`.
- Bug tracker: đã kiểm 29/10 qua API công khai của GitHub — repo có 28 issue (#1–#28, trạng thái mở/đóng theo `docs/issues-backlog.json`) và 5 milestone. Cập nhật 01/11: đã có Pull Request #30–#33 (đã đóng/merge), trong đó PR #32 gồm 3 commit của thành viên `Raphael-Fug` (tài khoản riêng) đã merge vào `main` (e236157).

## 4. Rủi ro còn lại và cách xử lý
- Tiêu chí nhiều thành viên: đã có commit của hai tài khoản (`Dking2007`, `Raphael-Fug` qua PR #32). Cần thêm bằng chứng nếu thể lệ yêu cầu từ ba thành viên. Một số commit cũ trên `main` còn trailer đồng tác giả công cụ AI — nhóm quyết định có viết lại lịch sử hay không. Người chịu trách nhiệm: nhóm trưởng.
- Giấy phép Python chưa quét tự động tại máy — người chịu trách nhiệm: thành viên phụ trách tuân thủ.
- Cập nhật README/docs nói "chưa nghiệm thu" ở nhiều nơi: giữ nguyên, không tuyên bố quá mức.

## 5. Xác nhận
Chúng tôi đã tự rà soát và khai báo trung thực theo thể lệ OLP PMNM 2026.

Người ký lần 1: ________________  Ngày: ________   ·   Người ký lần 2 (03/12): ________________  Ngày: ________
