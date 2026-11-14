<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# desktiny-plugin

Thư viện nhỏ (chỉ dùng thư viện chuẩn Python) để viết **plugin kết nối** cho Desktiny:

- `verify(secret, timestamp, body, signature)` / `read_delivery(secret, headers, body)`: kiểm chữ ký
  `X-Desktiny-Signature` (HMAC-SHA256 trên `"<timestamp>.<body>"`) và độ mới (mặc định 5 phút) của sự kiện hoặc lời
  gọi bước quy trình.
- `Client(base_url, token, secret=...)`: gọi API plugin (`/workspace/v1/plugin/v1`) bằng token cài đặt hoặc token
  phiên: đọc (`case`, `cases`, `task`, `person`, `people`, `departments`, `settings`, `case_files`, `file_content`),
  ghi kèm `Idempotency-Key` (`comment_case`, `write_fields`, `attach`, `create_task`, `comment_task`,
  `task_status`, `notify`), gửi sự kiện của plugin (`send_event`), báo kết quả bước chạy lâu có ký
  (`complete_call`, `call_progress`), kiểm phiên bản API (`require(2)`).
- CLI `desktiny-plugin`:

  ```sh
  desktiny-plugin init thu-nghiem --id vn.co-quan.thu-nghiem      # khung dự án
  desktiny-plugin check thu-nghiem                                # kiểm manifest
  desktiny-plugin pack thu-nghiem -o thu-nghiem.zip               # đóng gói để cài
  desktiny-plugin dev step vi_du --config noi_dung=abc --secret … --manifest thu-nghiem/desktiny-plugin.json
  ```

  `dev` đóng vai Desktiny: gửi sự kiện (`event`), gọi bước (`step`) hoặc công cụ trợ lý (`tool`), có ký, tới máy chủ
  plugin đang chạy.

Xem `docs/plugins.md` và ví dụ `examples/plugins/tra-cuu-mst`.
