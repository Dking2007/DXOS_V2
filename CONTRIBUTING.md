# Đóng góp cho Desktiny

Cảm ơn bạn đã quan tâm. Tài liệu này mô tả cách báo lỗi, đề xuất và gửi mã.

## Quy trình

1. Tìm hoặc tạo **issue** (mẫu bug / tính năng) trước khi làm; nhận việc bằng cách tự gán (assign).
2. Tạo nhánh từ `main`: `feat/<mô-tả>`, `fix/<mô-tả>`, `docs/<mô-tả>`.
3. Commit nhỏ, theo [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `chore:`.
   Tham chiếu issue: `Fixes #12`. **Dùng tài khoản và email của chính bạn** để lịch sử phản ánh đúng người làm.
4. Cập nhật [CHANGELOG.md](CHANGELOG.md) mục `[Unreleased]` trong **cùng PR** với thay đổi.
5. Mở Pull Request; CI phải xanh (lint, test, build, `compliance`). Cần ít nhất một người duyệt.

## Môi trường và kiểm tra cục bộ

Xem [BUILD.md](BUILD.md). Trước khi gửi PR:

```bash
make lint test
node scripts/add_spdx_headers.mjs --check   # mọi tệp mới phải có header SPDX
reuse lint                                  # pipx install reuse
```

## Quy tắc giấy phép (bắt buộc)

- Mã mới dùng **Apache-2.0**: chạy `node scripts/add_spdx_headers.mjs` để thêm header
  (`SPDX-License-Identifier: Apache-2.0`, `SPDX-FileCopyrightText: 2026 Desktiny contributors`).
- **Không** sao chép mã từ web, từ đầu ra AI hay từ dự án khác khi chưa kiểm tra nguồn và giấy phép.
- **Không** commit thư viện (`node_modules/`, `vendor/`, `.jar`, `.so`…). Thêm phụ thuộc qua manifest + lockfile,
  rồi chạy `make licenses` và commit `THIRD_PARTY.md`. Chỉ nhận giấy phép OSI; không dùng SSPL, BSL, Elastic, RSAL…
- Cần sửa thư viện ngoài: gửi bản vá lên upstream hoặc fork công khai và ghi trong THIRD_PARTY.md.

## Báo lỗi bảo mật

Không mở issue công khai; xem [SECURITY.md](SECURITY.md).

Tham gia cộng đồng theo [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
