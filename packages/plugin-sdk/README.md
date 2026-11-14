<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# Desktiny plugin SDK (khung giao diện)

`desktiny-plugin-sdk.js` là phía trang plugin của giao thức `desktiny: 1` giữa Desktiny và khung (iframe) của
plugin. Không phụ thuộc thư viện nào; nhúng dạng module hoặc thẻ `<script>` (đặt `window.DesktinyPlugin`).

```html
<script type="module">
  import { connect } from './desktiny-plugin-sdk.js'
  const desktiny = connect({ desktinyOrigin: 'https://desktiny.example.org' })
  const context = await desktiny.context
  const dossier = await desktiny.api(`/cases/${context.record.case_id}`)
</script>
```

- `context`: vị trí khung, mã hồ sơ/công việc, người đang xem, sáng/tối, màu của gói giao diện đang dùng
  (đặt thành biến CSS `--dk-<tên>`), tên ứng dụng.
- `api(path)`: gọi API plugin với token phiên ngắn hạn (tự xin lại khi sắp hết hạn), đọc theo quyền của người đang xem.
- `api(path, { method, body })`: lệnh ghi tự kèm `Idempotency-Key` (truyền sẵn khoá của bạn trong `headers` nếu
  cần gửi lại an toàn), `body` là đối tượng thì gửi dạng JSON.
- `resize()`: báo chiều cao (mặc định tự theo dõi bằng `ResizeObserver`).
- Lệnh: `toast(text, tone)`, `navigate('/cases/…')` (chỉ đường dẫn nội bộ), `refresh()` (tải lại sau khi ghi),
  `close(result)` (đóng hộp thoại của `case.action`/`task.action`), `await confirm(text)` (Desktiny hỏi bằng hộp
  thoại của chính nó, trả `true`/`false`).

Trang chạy trong iframe `sandbox` (không có `allow-same-origin`): không đọc được cookie hay DOM của Desktiny. Xem
`docs/plugins.md`.
