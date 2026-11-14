<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# Plugin mẫu: Tra cứu mã số thuế (giả lập)

Ví dụ đủ 4 kênh của plugin kết nối: nhận sự kiện `case.submitted` (có chữ ký), đọc hồ sơ bằng token, bước quy trình
`tra_cuu_mst` (nhánh Thành công/Lỗi, trả `ten_dn`, `trang_thai`), khung “Thông tin doanh nghiệp” trên trang hồ sơ.
Dữ liệu doanh nghiệp là **giả lập**. Chỉ dùng thư viện chuẩn Python và `packages/desktiny-plugin`.

## Chạy thử với Desktiny trên máy

1. Cho phép máy chủ plugin trong `.env` của Desktiny rồi khởi động lại `workspace-api`, `workspace-worker`, `gateway`:
   ```
   PLUGIN_ALLOWED_HOSTS=host.docker.internal
   PLUGIN_FRAME_SOURCES=http://localhost:9100
   ```
   Container Desktiny gọi plugin qua `host.docker.internal`; trình duyệt mở khung qua `localhost`. Với cách chạy này,
   sửa `base_url` trong `desktiny-plugin.json` thành `http://host.docker.internal:9100` và dùng URL khung tương ứng,
   hoặc chạy plugin như một service trong cùng mạng Docker.
2. **Quản trị › Plugin** → **Cài plugin** → chọn `desktiny-plugin.json` → **Duyệt quyền** → sao chép khoá ký và token.
3. Chạy plugin:
   ```
   pip install -e packages/desktiny-plugin
   cd examples/plugins/tra-cuu-mst
   DESKTINY_SECRET=<khoá ký> DESKTINY_TOKEN=<token> DESKTINY_URL=http://localhost:8080 python server.py
   ```
4. Tạo biểu mẫu có trường `ma_so_thue`, thêm bước **Plugin › Tra cứu mã số thuế** vào quy trình, trình hồ sơ với
   mã `0101234567` hoặc `0309876543`.

Test: `pytest examples/plugins/tra-cuu-mst`.
