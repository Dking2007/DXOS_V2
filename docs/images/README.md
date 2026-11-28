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
| `dien-thoai.png` | Desktiny trên màn hình điện thoại | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `mot-cua-trang-chu.png` | Trang chủ sau khi cài bản mở rộng Một cửa cấp xã | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `goi-giao-dien.png` | Quản trị › Gói giao diện | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `../media/gif-trinh-duyet.gif` | Trình hồ sơ, duyệt, xem lịch sử | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `../media/gif-thiet-ke-quy-trinh.gif` | Vẽ quy trình và chạy thử | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `../media/gif-doi-nghiep-vu.gif` | Cài bản mở rộng, giao diện và quy trình đổi | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `../media/gif-cong-dan-nop.gif` | Nộp hồ sơ trực tuyến, bộ phận một cửa tiếp nhận | README, README_EN | Chụp bằng Playwright từ bản demo với dữ liệu mẫu giả, 28/11/2026 |
| `ban-mo-rong.png`, `dang-nhap-dien-thoai.png` | Ảnh của bản 3.1.0 | Không còn dùng trong README | Ảnh chụp màn hình cũ, giữ lại cho lịch sử |
