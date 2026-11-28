<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# Nguồn gốc hình ảnh

Mọi ảnh chụp màn hình và ảnh động dùng **dữ liệu mẫu giả** (tên người, cơ quan, hồ sơ đều là giả), không chứa mật
khẩu hay dữ liệu thật. Giấy phép theo [REUSE.toml](../../REUSE.toml) (mục `docs/**`). Các sơ đồ `*-dong.svg`
chuyển động bằng CSS và SMIL, không có script, phông hay ảnh ngoài; khi người xem bật giảm chuyển động thì chỉ còn sơ
đồ tĩnh.

| Tệp | Nội dung | Dùng ở | Nguồn |
|---|---|---|---|
| `banner.svg` | Tên sản phẩm, câu giới thiệu, sơ đồ Core với ứng dụng, gói và plugin cắm vào | README, README_EN | Vẽ tay SVG |
| `kien-truc-dong.svg` | Sơ đồ kiến trúc động: cổng, Tầng 2, Tầng 1, lưu trữ, Keycloak, máy chủ plugin; 6 bước khớp danh sách trong mục Kiến trúc | README, README_EN mục Kiến trúc | Vẽ tay SVG, 2026 |
| `luong-du-lieu-dong.svg` | Dữ liệu đi đâu: thao tác của người dùng, dịch vụ ghi, nơi dữ liệu nằm | README, README_EN mục Kiến trúc › Dữ liệu nằm ở đâu | Vẽ tay SVG, 2026 |
| `luong-ho-so-dong.svg` | Một hồ sơ trình duyệt qua bốn làn, 10 bước, nơi ghi dữ liệu của từng bước | README, README_EN mục Luồng nghiệp vụ | Vẽ tay SVG, 2026 |
| `trang-chu.png` | Trang chủ *Việc cần làm hôm nay* | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `ho-so.png` | Trang hồ sơ với nút duyệt, trả lại và tab Quy trình | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `quy-trinh-canvas.png` | Trình thiết kế quy trình dạng canvas | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `cong-viec.png` | Màn công việc | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `bao-cao.png` | Trang báo cáo | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `tai-lieu.png` | Kho tài liệu | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `bang-tin.png` | Bảng tin | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `dang-nhap.png` | Trang đăng nhập | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `../media/gif-trinh-duyet.gif` | Trình hồ sơ, duyệt, xem lịch sử | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `../media/gif-thiet-ke-quy-trinh.gif` | Vẽ quy trình và chạy thử | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `../media/gif-doi-nghiep-vu.gif` | Đổi gói giao diện: cả ứng dụng đổi sang Một cửa rồi Nhân sự | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `../media/gif-cong-dan-nop.gif` | Nộp hồ sơ trực tuyến, bộ phận một cửa tiếp nhận | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `hero-ghep.png` | Ảnh ghép đầu trang: danh sách hồ sơ, trang chủ, canvas, điện thoại | README, README_EN | Ghép bằng Pillow từ ảnh chụp Playwright, dữ liệu mẫu giả |
| `ho-so-chi-tiet.png` | Chi tiết hồ sơ, chế độ sáng | README, README_EN | Chụp bằng Playwright từ bản demo (mã nhánh tích hợp ngày 28/11/2026), dữ liệu mẫu giả |
| `toi-ho-so.png` | Chi tiết hồ sơ, chế độ tối | README, README_EN | Chụp bằng Playwright từ bản demo (mã nhánh tích hợp ngày 28/11/2026), dữ liệu mẫu giả |
| `dt-trang-chu.png` | Trang chủ trên điện thoại (390 px) | README, README_EN | Chụp bằng Playwright từ bản demo (mã nhánh tích hợp ngày 28/11/2026), dữ liệu mẫu giả |
| `dt-ho-so.png` | Hồ sơ trên điện thoại | README, README_EN | Chụp bằng Playwright từ bản demo (mã nhánh tích hợp ngày 28/11/2026), dữ liệu mẫu giả |
| `dt-cong-viec.png` | Công việc trên điện thoại | README, README_EN | Chụp bằng Playwright từ bản demo (mã nhánh tích hợp ngày 28/11/2026), dữ liệu mẫu giả |
| `dt-dang-nhap.png` | Trang đăng nhập trên điện thoại | README, README_EN | Chụp bằng Playwright từ bản demo (mã nhánh tích hợp ngày 28/11/2026), dữ liệu mẫu giả |
| `goi-truoc-sau.png` | Trước và sau khi cài gói Một cửa | README, README_EN | Ghép bằng Pillow từ ảnh chụp Playwright, dữ liệu mẫu giả |
| `goi-mot-cua.png` | Trang chủ với gói Một cửa cấp xã | README, README_EN | Chụp bằng Playwright từ bản demo (mã nhánh tích hợp ngày 28/11/2026), dữ liệu mẫu giả |
| `goi-nhan-su.png` | Trang chủ với gói Nhân sự doanh nghiệp | README, README_EN | Chụp bằng Playwright từ bản demo (mã nhánh tích hợp ngày 28/11/2026), dữ liệu mẫu giả |
| `goi-van-thu.png` | Trang chủ với gói Văn thư – điều hành | README, README_EN | Chụp bằng Playwright từ bản demo (mã nhánh tích hợp ngày 28/11/2026), dữ liệu mẫu giả |
| `../media/gif-canh-bao-cam-bien.gif` | Cảm biến vượt ngưỡng tạo hồ sơ sự cố | README, README_EN | Chụp bằng Playwright từ bản demo (mã nhánh tích hợp ngày 28/11/2026), dữ liệu mẫu giả |
| `../media/gif-dien-thoai.gif` | Cập nhật công việc trên điện thoại | README, README_EN | Chụp bằng Playwright từ bản demo (mã nhánh tích hợp ngày 28/11/2026), dữ liệu mẫu giả |
