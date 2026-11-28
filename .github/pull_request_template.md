## Liên kết issue

Fixes #

## Loại thay đổi

- [ ] Sửa lỗi
- [ ] Tính năng mới
- [ ] Phá tương thích (API, định dạng gói hoặc migration; xem CONTRIBUTING mục 6)
- [ ] Tài liệu, CI, dọn mã

## Thay đổi gì

## Cách kiểm

<!-- Lệnh đã chạy, tài khoản demo và các bước bấm để người duyệt làm lại được. -->

## Ảnh trước/sau (nếu đổi giao diện)

<!-- Dùng dữ liệu mẫu giả. -->

## Checklist

- [ ] Commit theo Conventional Commits, dùng tài khoản của tôi
- [ ] Có test cho logic mới hoặc lỗi vừa sửa; `make lint test` đạt
- [ ] Đã cập nhật `CHANGELOG.md` (mục `[Unreleased]`)
- [ ] Tệp mới có header SPDX (`node scripts/add_spdx_headers.mjs --check`), `reuse lint` đạt
- [ ] Phụ thuộc mới đã vào lockfile và `THIRD_PARTY.md`, giấy phép thuộc OSI
- [ ] Không có mật khẩu, token, `.env` hay dữ liệu thật trong thay đổi
