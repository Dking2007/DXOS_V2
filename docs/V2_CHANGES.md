# DXOS V2 — Những thay đổi so với V1

**V1** = bản 0.1.0 (commit `f089bfb`, 24/10/2026): đã có nền tảng Core + Workspace chạy được
nhưng kho mã chưa đủ hồ sơ cho chấm PoF. **V2** = bản 0.2.2 (31/10/2026; 0.2.0 là bản đầu, có lỗi `reuse lint` đã sửa ở 0.2.1; 0.2.1 là bản chấm trước đó): giữ nguyên chức năng,
hoàn thiện cách quản lý giấy phép, biên dịch, phát hành và tài liệu. Không có thay đổi hành vi
của ứng dụng; mọi thay đổi mã chỉ là chú thích header và khai báo `license` trong `package.json`.

## 1. Tóm tắt

| Hạng mục | V1 (0.1.0) | V2 (0.2.2) |
|---|---|---|
| Giấy phép toàn văn | `LICENSE` Apache-2.0, `NOTICE` | + `LICENSES/Apache-2.0.txt` (chuẩn REUSE) |
| Giấy phép từng tệp | 0/180 tệp có header | 180/180 tệp mã có SPDX; còn lại trong `REUSE.toml` |
| Kiểm tuân thủ | không | `reuse lint` + kiểm header + đối chiếu THIRD_PARTY trong CI |
| Khai báo thành phần ngoài | `docs/third-party-inventory.md` (mô tả, nêu rõ chưa hoàn tất) | `THIRD_PARTY.md` đầy đủ 309 npm + 54 Python + 9 dịch vụ, sinh tự động |
| Hướng dẫn biên dịch | `docs/installation.md`, README | + `BUILD.md`, `Makefile`, `make install PREFIX=` |
| Phát hành | không có tag/release | tag `v0.1.0` (V1), `v0.2.0` (mốc lịch sử), `v0.2.1` và `v0.2.2` (bản dùng để chấm), Release `.tar.gz` + `SHA256SUMS` tự động |
| Changelog | không | `CHANGELOG.md` (Keep a Changelog, SemVer) |
| Bug tracker / cộng đồng | không có mẫu | mẫu issue, PR, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY |
| Tự rà soát | không | `SELF_REVIEW.md` (bản nháp, chờ thành viên ký) |

## 2. Đối chiếu 6 tiêu chí PoF

| # | Tiêu chí (điểm) | Trạng thái V1 | Việc đã làm ở V2 | Còn lại / cần người |
|---|---|---|---|---|
| 1 | Quản lý mã nguồn (5) | Repo GitHub, 8 commit nhưng **một tác giả duy nhất** | `.gitignore` đã đúng, không commit `.env`/`node_modules`; thêm quy ước commit | Mỗi thành viên commit bằng tài khoản riêng; bật public & kiểm ẩn danh |
| 2 | Cấp phép OSI (10) | Có LICENSE, thiếu header từng tệp, thiếu REUSE | SPDX 180 tệp, `LICENSES/`, `REUSE.toml`, mục *Giấy phép* trong README | Chạy `reuse lint` (CI sẽ chạy) và ScanCode |
| 3 | Release (5) | Chưa có | Tag SemVer + workflow tạo tar.gz/SHA256SUMS | Phát hành v0.1.x đều mỗi tuần; bản cuối trước 17:00 06/12/2026 |
| 4 | Cài đặt & biên dịch (10) | Chỉ tài liệu dài, không có điểm vào thống nhất | `BUILD.md`, `Makefile`, cài ra `PREFIX`, cấu hình qua `.env` | Chạy thử trong container Ubuntu sạch (chưa làm được trên máy hiện tại). Đã sửa: migration CSDL nay được cài kèm (`desktiny-migrate`) để chương trình chạy được ngoài thư mục mã nguồn |
| 5 | Thư viện & gói (10) | Lockfile có; inventory chưa đầy đủ | `THIRD_PARTY.md`; xác nhận không vendor, không có thành phần ngoài OSI | Đối chiếu giấy phép Python bằng `pip-licenses`; xem lưu ý psycopg (LGPL), ONLYOFFICE (AGPL) |
| 6 | Tài liệu & giao tiếp (10) | README tốt, thiếu CHANGELOG, mẫu issue | CHANGELOG, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, mẫu issue/PR | Tạo issue thật & milestone theo tuần trên GitHub |

## 3. Rủi ro đã nhận diện

- **Lịch sử commit chỉ có một tác giả** (`Raphael-Fug`). Tài liệu hướng dẫn yêu cầu cả nhóm có đóng góp
  riêng; đây là việc nhóm phải tự xử lý từ nay, không thể sửa hồi tố.
- **Tag `v0.1.0` hồi tố**: gắn vào commit V1 để có đường cơ sở so sánh; ngày tạo tag là ngày V2, không
  phải 24/10. Điều này được ghi rõ trong CHANGELOG.
- **Chưa chạy được** `reuse lint`, `pip-licenses` trên máy phát triển (không có Python cục bộ; CI chạy hai lệnh này). Từ 27/10, pytest, ruff và Docker build đã chạy được qua Docker Desktop; xem `SELF_REVIEW.md`.
  Phần frontend (lint, typecheck, test, build) đã chạy; kết quả ghi trong `SELF_REVIEW.md`.
- **Giấy phép Python** trong THIRD_PARTY.md theo metadata upstream, chưa quét tự động tại máy.
