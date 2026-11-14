<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# desktiny-plugin

Thư viện nhỏ (chỉ dùng thư viện chuẩn Python) để viết **plugin kết nối** cho Desktiny:

- `verify(secret, timestamp, body, signature)` / `read_delivery(secret, headers, body)`: kiểm chữ ký
  `X-Desktiny-Signature` (HMAC-SHA256 trên `"<timestamp>.<body>"`) và độ mới (mặc định 5 phút) của sự kiện hoặc lời
  gọi bước quy trình.
- `Client(base_url, token)`: gọi API plugin (`/workspace/v1/plugin/v1/me`, `/cases/{id}`, `/tasks/{id}`,
  `/people/{id}`) bằng token cài đặt hoặc token phiên của khung giao diện.

Xem `docs/plugins.md` và ví dụ `examples/plugins/tra-cuu-mst`.
