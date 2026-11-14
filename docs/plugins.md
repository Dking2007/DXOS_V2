<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# Plugin kết nối (`desktiny-plugin/1`)

Plugin kết nối là một **ứng dụng web riêng**, do người viết plugin hoặc cơ quan tự chạy (thường trong mạng nội bộ).
Mã của plugin **không bao giờ chạy trong Desktiny**: Desktiny chỉ gọi HTTP tới plugin và nhận `postMessage` từ khung
giao diện cách ly. Đây là tầng 2 của hướng mở rộng, sau [gói ngành](packs.md) (tầng 1, không chứa mã).

```
                ┌──────────────────── Desktiny ────────────────────┐
  Người dùng ── │ Giao diện ── iframe sandbox ◄─postMessage─► Trang plugin │
                │ API plugin ◄── token có phạm vi ───────── Máy chủ plugin │
                │ Outbox ─────── sự kiện ký HMAC ──────────► Máy chủ plugin │
                │ Bước plugin_action ── HTTP ký HMAC ──────► Máy chủ plugin │
                └──────────────────────────────────────────────────┘
```

## Bật cho một triển khai

| Biến | Dùng ở | Ý nghĩa |
|---|---|---|
| `PLUGIN_ALLOWED_HOSTS` | Workspace API, worker | Tên máy chủ plugin được phép, cách nhau bằng dấu phẩy. Trống = không cài được plugin nào. Plugin chỉ gọi tới, và chỉ được gọi từ, các máy chủ này. |
| `PLUGIN_FRAME_SOURCES` | gateway (CSP) | Origin (`https://host[:port]`) của trang plugin, cách nhau bằng dấu cách; thêm vào `frame-src`. Cũng ngăn khung plugin chuyển sang trang khác. |

`infra/gateway/nginx.conf` được gắn làm template của image nginx; `${PLUGIN_FRAME_SOURCES}` được điền khi container
khởi động (chỉ biến `PLUGIN_*` được thay).

## Vòng đời

1. **Cài**: **Quản trị › Plugin** (quyền `organization.manage`) → tải `desktiny-plugin.json` (hoặc `.zip` chứa nó) →
   xem plugin xin gì → cài. Plugin ở trạng thái **chờ duyệt**, chưa nhận gì.
2. **Duyệt quyền**: chọn quyền và sự kiện cấp cho plugin (chỉ trong số nó xin). Plugin chuyển **đang bật**; Desktiny
   cấp **khoá ký** (HMAC) và **token cài đặt**, hiện **một lần**.
3. **Tắt / bật**: tắt thì ngừng gửi sự kiện, khung biến mất, token cài đặt và token phiên hết hiệu lực ngay.
4. **Đổi khoá**: cấp khoá ký và token mới; cái cũ hết hiệu lực.
5. **Nâng cấp**: cài lại manifest cùng `id`. Xin thêm quyền/sự kiện thì plugin quay về chờ duyệt.
6. **Gỡ**: token hết hiệu lực; bước quy trình của plugin báo lỗi có lý do thay vì chạy sai âm thầm.

Mọi thao tác ghi Nhật ký hoạt động. **Nhật ký** của từng plugin liệt kê sự kiện đã gửi, bước đã gọi và dữ liệu plugin
đã đọc qua API, có nút **gửi lại** sự kiện lỗi.

## Manifest

```json
{
  "schema": "desktiny-plugin/1",
  "id": "vn.vi-du.tra-cuu-mst",
  "name": "Tra cứu mã số thuế",
  "version": "1.0.0",
  "license": "Apache-2.0",
  "base_url": "https://mst.noi-bo.gov.vn",
  "permissions": ["cases.read"],
  "events": ["case.submitted"],
  "events_endpoint": "/events",
  "nodes": [
    {
      "kind": "tra_cuu_mst",
      "title": "Tra cứu mã số thuế",
      "endpoint": "/nodes/tra-cuu",
      "config_schema": {
        "type": "object",
        "properties": { "ma_so": { "type": "string", "title": "Mã số thuế", "default": "{form.ma_so_thue}" } },
        "required": ["ma_so"]
      },
      "outputs": { "ten_dn": "Tên doanh nghiệp", "trang_thai": "Trạng thái hoạt động" }
    }
  ],
  "ui": [{ "slot": "case.side", "title": "Thông tin doanh nghiệp", "url": "/ui/case-card.html", "height": 220 }]
}
```

- `base_url`: `http(s)://máy-chủ[:cổng][/tiền-tố]`, máy chủ phải có trong `PLUGIN_ALLOWED_HOSTS`. Mọi `endpoint`,
  `url`, `events_endpoint` là đường dẫn trên máy chủ đó (bắt đầu bằng một `/`, không được `//`).
- `permissions` (phạm vi API): `cases.read`, `tasks.read`, `people.read`.
- `events`: `case.submitted`, `case.approved`, `case.rejected`, `case.needs_revision`, `task.created`,
  `task.assigned`, `task.submitted`, `task.completed`, `task.returned`, `task.blocked`, `post.created`.
- `nodes[].config_schema`: tối đa 20 ô, kiểu `string` / `number` / `boolean`, có thể kèm `enum`, `default`,
  `description`; trình thiết kế quy trình tự dựng ô cấu hình từ đây. `outputs`: các giá trị đơn plugin trả về.
- `ui[].slot`: `case.side` (cột phải trang hồ sơ), `task.side` (cột phải trang công việc), `home.widget` (trang
  chủ, gói ngành bật/tắt bằng khối `plugins.widgets`), `page` (trang riêng, có mục trong nhóm **Ứng dụng** của thanh
  bên). `height` 80–1200.

## Kênh 1 — Sự kiện

Worker gửi `POST {base_url}{events_endpoint}` cho mỗi sự kiện đã duyệt:

```json
{ "delivery_id": "…", "event_id": "…", "type": "case.submitted", "occurred_at": "…",
  "subject": { "type": "case", "id": "…" } }
```

Chỉ có mã, không có nội dung: plugin cần chi tiết thì gọi API (theo quyền đã duyệt). Header: `X-Desktiny-Event`,
`X-Desktiny-Delivery`, `X-Desktiny-Timestamp`, `X-Desktiny-Signature: sha256=<hex>` với
`HMAC-SHA256(khoá ký, "<timestamp>.<body>")`, `Idempotency-Key` = `delivery_id`. Trả 2xx là thành công; 4xx là
từ chối (không gửi lại); 5xx, 429 hoặc không kết nối được thì gửi lại theo hàng đợi, giãn cách tăng dần. Plugin nên
bỏ qua `delivery_id` đã nhận.

## Kênh 2 — API cho plugin

`/workspace/v1/plugin/v1` với `Authorization: Bearer <token>` (cho phép gọi từ mọi origin, không dùng cookie):

| API | Phạm vi | Trả về |
|---|---|---|
| `GET /me` | — | plugin, phạm vi, loại token, người dùng (nếu là token phiên), ngữ cảnh |
| `GET /cases/{id}` | `cases.read` | thông tin chung, biểu mẫu, nội dung (bước chỉ xem một phần thì chỉ phần đó), người tạo, phòng ban |
| `GET /tasks/{id}` | `tasks.read` | tiêu đề, trạng thái, ưu tiên, hạn, hồ sơ gắn, người làm |
| `GET /people/{id}` | `people.read` | họ tên, chức danh, phòng ban |

- **Token cài đặt** (không gắn người): chỉ đọc được hồ sơ/công việc mà plugin **đã được báo** qua một sự kiện hoặc
  một lời gọi bước quy trình. Không có quyền "xem tất cả".
- **Token phiên** (khung giao diện, 10 phút): đọc **theo quyền của người đang xem**, trong ngữ cảnh của khung.
- Phạm vi luôn là giao của quyền đã duyệt cho plugin và phạm vi của token. Mọi lời gọi ghi vào nhật ký plugin.

## Kênh 3 — Bước quy trình `plugin_action`

Trong trình thiết kế quy trình, bước của plugin đang bật nằm ở nhóm **Plugin**. Khi luồng tới bước, worker gửi
`POST {base_url}{endpoint}` (ký như sự kiện, `Idempotency-Key` = `run_id:node_id`):

```json
{ "call_id": "…", "run_id": "…", "node_id": "tra_cuu", "step": "tra_cuu_mst",
  "config": { "ma_so": "0101234567" }, "subject": { "type": "case", "id": "…" } }
```

`config` là đúng các ô người thiết kế đã điền, `{form.truong}` đã được thay bằng giá trị; **không gửi thêm dữ liệu
nào khác**. Plugin trả `{"branch": "success" | "error", "output": {...}, "message": "..."}`; thiếu `branch` thì 2xx là
`success`, 4xx là `error`. Bước sau đọc `{tra_cuu.ten_dn}`; chỉ giữ giá trị đơn mà manifest khai trong `outputs`.
Quá 15 giây thì đi nhánh `error` và **không gọi lại** (plugin có thể đã làm). Plugin tắt, gỡ hoặc máy chủ không còn
được phép thì bước đi nhánh `error` và ghi lý do lên sơ đồ; khi lưu luồng, trình thiết kế cũng báo lỗi ở bước đó.

## Kênh 4 — Khung giao diện

Trang plugin hiện trong `<iframe sandbox="allow-scripts allow-forms allow-popups">` (không có
`allow-same-origin`, `referrerpolicy="no-referrer"`): không đọc được cookie, DOM hay bộ nhớ của Desktiny. Trao đổi
qua `postMessage` với giao thức `{ "desktiny": 1, "type": … }`:

| Từ khung | Desktiny trả |
|---|---|
| `ready` / `context` | `context`: vị trí, mã hồ sơ/công việc, người xem, `theme` sáng/tối, `colors` (biến màu của gói giao diện đang dùng), phông, tên ứng dụng |
| `token` (`id`) | `token` (`id`, `token`, `expires_at`, `api_base`) hoặc `error` |
| `resize` (`height`) | — (đổi chiều cao khung) |

Desktiny chỉ nhận tin đến từ chính cửa sổ của khung. SDK `packages/plugin-sdk/desktiny-plugin-sdk.js` lo phần này:

```js
import { connect } from './desktiny-plugin-sdk.js'
const desktiny = connect({ desktinyOrigin: 'https://desktiny.example.org' })
const context = await desktiny.context            // màu đã gán thành biến CSS --dk-<tên>
const dossier = await desktiny.api(`/cases/${context.record.case_id}`)
```

## Bộ công cụ

- `packages/desktiny-plugin` (Python, chỉ thư viện chuẩn): `read_delivery`/`verify` kiểm chữ ký và độ mới (5 phút),
  `Client` gọi API plugin.
- `packages/plugin-sdk` (JavaScript, không phụ thuộc): phía khung của giao thức.
- `examples/plugins/tra-cuu-mst`: plugin mẫu đủ 4 kênh (dữ liệu giả lập), có test; cách chạy trong README của nó.

## An toàn

| Mối lo | Biện pháp |
|---|---|
| Plugin đọc dữ liệu không được phép | Quyền theo plugin giao với quyền token; token cài đặt chỉ đọc bản ghi đã được báo; token phiên kiểm theo quyền người xem; Core vẫn kiểm ACL nội dung. |
| Plugin bị giả mạo | Ký HMAC mọi sự kiện và lời gọi bước, kèm mốc thời gian; khoá mã hoá khi lưu, đổi được; token chỉ lưu bản băm. |
| Khung đánh cắp phiên | Iframe sandbox, origin riêng, không cookie; token phiên 10 phút, gắn ngữ cảnh; CSP `frame-src` theo danh sách. |
| Gọi ra máy chủ nội bộ (SSRF) | Chỉ máy chủ trong `PLUGIN_ALLOWED_HOSTS`, kiểm lại trước mỗi lần gọi; không theo chuyển hướng. |
| Plugin lỗi làm treo quy trình | Hạn 15 giây, phản hồi tối đa 20 KB, nhánh `error`; tắt plugin là dừng ngay. |

## Giới hạn hiện tại

- API cho plugin mới có các lệnh đọc; chưa có lệnh ghi (thêm ý kiến, tạo việc) — plugin tác động qua bước quy trình.
- Chưa giới hạn tần suất theo từng plugin (gateway vẫn giới hạn chung); chưa có kênh nhận webhook từ ngoài vào.
- Chưa có CLI `desktiny-plugin init | dev | check | pack` và danh mục plugin dùng chung; plugin trong tiến trình
  (tầng 3) chưa làm.
