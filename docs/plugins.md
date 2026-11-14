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
                │ Quy trình ◄── sự kiện của plugin (token) ── Máy chủ plugin │
                └──────────────────────────────────────────────────┘
```

## Bật cho một triển khai

| Biến | Dùng ở | Ý nghĩa |
|---|---|---|
| `PLUGIN_ALLOWED_HOSTS` | Workspace API, worker | Tên máy chủ plugin được phép, cách nhau bằng dấu phẩy. Trống = không cài được plugin nào. Plugin chỉ gọi tới, và chỉ được gọi từ, các máy chủ này. |
| `PLUGIN_FRAME_SOURCES` | gateway (CSP) | Origin (`https://host[:port]`) của trang plugin, cách nhau bằng dấu cách; thêm vào `frame-src`. Cũng ngăn khung plugin chuyển sang trang khác. |
| `PLUGIN_READS_PER_MINUTE`, `PLUGIN_WRITES_PER_MINUTE`, `PLUGIN_NOTIFICATIONS_PER_MINUTE`, `PLUGIN_EVENTS_PER_MINUTE` | Workspace API | Giới hạn mỗi plugin mỗi phút theo kênh (mặc định 600, 120, 30, 60). |
| `PLUGIN_UPLOAD_MAX_BYTES`, `PLUGIN_UPLOAD_DAILY_BYTES` | Workspace API | Tệp plugin gắn vào hồ sơ: mỗi tệp, và tổng 24 giờ mỗi plugin (mặc định 25 MB, 200 MB). |
| `OVERDUE_SWEEP_SECONDS` | worker | Chu kỳ quét hồ sơ, công việc vừa quá hạn để phát `case.overdue`, `task.overdue` (mặc định 300). |

`infra/gateway/nginx.conf` được gắn làm template của image nginx; `${PLUGIN_FRAME_SOURCES}` được điền khi container
khởi động (chỉ biến `PLUGIN_*` được thay).

## Vòng đời

1. **Cài**: **Quản trị › Plugin** (quyền `organization.manage`) → tải `desktiny-plugin.json` (hoặc `.zip` chứa nó) →
   xem plugin xin gì → cài. Plugin ở trạng thái **chờ duyệt**, chưa nhận gì.
2. **Duyệt quyền**: chọn phạm vi, sự kiện, trường được ghi, quy trình được liệt kê, quyền thiết bị và công cụ trợ lý
   cấp cho plugin (chỉ trong số nó xin). Plugin chuyển **đang bật**; Desktiny cấp **khoá ký** (HMAC) và **token cài
   đặt**, hiện **một lần**. Plugin có `settings_schema` thì điền **Cấu hình** cho cơ quan.
3. **Tắt / bật**: tắt thì ngừng gửi sự kiện, khung biến mất, token cài đặt và token phiên hết hiệu lực ngay.
4. **Đổi khoá**: cấp khoá ký và token mới; cái cũ hết hiệu lực.
5. **Nâng cấp**: cài lại manifest cùng `id`. Xin thêm quyền/sự kiện thì plugin quay về chờ duyệt.
6. **Gỡ**: token hết hiệu lực; bước quy trình của plugin báo lỗi có lý do thay vì chạy sai âm thầm.

Mọi thao tác ghi Nhật ký hoạt động. **Nhật ký** của từng plugin liệt kê sự kiện đã gửi, bước đã gọi, dữ liệu plugin
đã đọc hay ghi qua API, sự kiện plugin gửi vào, công cụ trợ lý đã hỏi và lần kiểm tra sức khoẻ, có nút **gửi lại** sự
kiện lỗi.

## Manifest

```json
{
  "schema": "desktiny-plugin/1",
  "id": "vn.vi-du.tra-cuu-mst",
  "name": "Tra cứu mã số thuế",
  "version": "1.0.0",
  "license": "Apache-2.0",
  "base_url": "https://mst.noi-bo.gov.vn",
  "requires": { "desktiny": ">=2" },
  "permissions": ["cases.read", "cases.comment", "cases.fields.write"],
  "writes": { "fields": ["ten_doanh_nghiep"] },
  "events": ["case.submitted"],
  "events_endpoint": "/events",
  "health_endpoint": "/health",
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

Mọi trường mới đều **tuỳ chọn**; manifest dùng chúng nên khai `requires.desktiny` (`">=2"`) để bản Desktiny cũ từ
chối cài thay vì hiểu sai. `GET /plugin/v1/me` trả `api_version` hiện tại (2).

- `base_url`: `http(s)://máy-chủ[:cổng][/tiền-tố]`, máy chủ phải có trong `PLUGIN_ALLOWED_HOSTS`. Mọi `endpoint`,
  `url`, `events_endpoint`, `health_endpoint` là đường dẫn trên máy chủ đó (bắt đầu bằng một `/`, không được `//`).
- `permissions` (phạm vi API):

  | Phạm vi | Cho phép | Token cài đặt? |
  |---|---|---|
  | `cases.read`, `tasks.read`, `people.read` | Đọc một hồ sơ / công việc / người | Có (bản ghi đã được báo) |
  | `cases.list` | Liệt kê hồ sơ của các quy trình chọn lúc duyệt | Có |
  | `departments.read`, `people.list` | Cây phòng ban, danh bạ (phân trang) | Có |
  | `files.read` | Danh sách và nội dung tài liệu của hồ sơ | Có (hồ sơ đã được báo) |
  | `cases.comment` | Ghi ý kiến vào hồ sơ | Có |
  | `cases.attach` | Gắn tệp vào hồ sơ | Có |
  | `notifications.send` | Gửi thông báo trong ứng dụng | Có |
  | `cases.fields.write` | Ghi các trường khai trong `writes.fields` và được duyệt | **Chỉ token phiên** |
  | `tasks.write` | Tạo việc, bình luận, chuyển trạng thái việc | **Chỉ token phiên** |

- `events`: `case.submitted`, `case.approved`, `case.rejected`, `case.needs_revision`, `case.step_entered`,
  `case.file_added`, `case.overdue`, `case.closed`, `task.created`, `task.assigned`, `task.submitted`,
  `task.completed`, `task.returned`, `task.blocked`, `task.overdue`, `post.created`.
- `nodes[].config_schema`: tối đa 20 ô, kiểu `string` / `number` / `boolean`, có thể kèm `enum`, `default`,
  `description`; trình thiết kế quy trình tự dựng ô cấu hình từ đây. `outputs`: các giá trị đơn plugin trả về.
  `mode: "async"` kèm `timeout_days` (1–90, bắt buộc) cho bước chạy lâu.
- `ui[].slot`: `case.side`, `case.tab`, `case.action`, `task.side`, `task.action`, `home.widget` (gói ngành bật/tắt
  bằng khối `plugins.widgets`), `page` (mục trong nhóm **Ứng dụng** của thanh bên), `admin.page`. `height` 80–1200.
- `frame_permissions`: `geolocation`, `camera`, `clipboard-write` (duyệt từng quyền).
- `emits`: sự kiện của chính plugin (mục “Kênh 5”). `assistant_tools`: công cụ cho trợ lý AI (mục “Trợ lý AI”).
- `settings_schema`: cấu hình theo cơ quan, cùng dạng `config_schema`, ô có `"secret": true` được mã hoá.
- `list_scope`: `{"forms": "ask"}` (mặc định) — quy trình được liệt kê do quản trị viên chọn lúc duyệt.

Nâng cấp mà xin thêm phạm vi, sự kiện, trường ghi, quyền thiết bị hay công cụ trợ lý thì plugin về **chờ duyệt**; phần
đã duyệt và vẫn còn trong manifest được giữ nguyên.

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

Sự kiện lõi mới: `case.step_entered` (hồ sơ tới một bước phải chờ; kèm `node_id`, `step`), `case.file_added`,
`case.closed` (duyệt, từ chối hoặc huỷ), `case.overdue` và `task.overdue` (worker quét mỗi `OVERDUE_SWEEP_SECONDS`,
mặc định 5 phút; mỗi hạn chỉ báo một lần). Ngoài sự kiện đã duyệt, plugin luôn nhận sự kiện về chính nó:
`plugin.settings.changed`, `plugin.call.cancelled` (`subject: {"type": "call", "id": "<call_id>"}`).

## Kênh 2 — API cho plugin

`/workspace/v1/plugin/v1` với `Authorization: Bearer <token>` (cho phép gọi từ mọi origin, không dùng cookie).
Contract riêng: [`contracts/plugin.openapi.json`](../contracts/plugin.openapi.json) (sinh cùng các contract khác bằng
`scripts/export_contracts.py`, CI kiểm khớp).

| API | Phạm vi | Trả về |
|---|---|---|
| `GET /me` | — | plugin, `api_version`, phạm vi Desktiny hỗ trợ, phạm vi của token, trường được ghi, người dùng (token phiên), ngữ cảnh |
| `GET /cases/{id}` | `cases.read` | thông tin chung, biểu mẫu, nội dung (bước chỉ xem một phần thì chỉ phần đó), người tạo, phòng ban |
| `GET /cases?form_id=&status=&updated_since=&cursor=&limit=` | `cases.list` | mã, tiêu đề, trạng thái, hạn, cập nhật lúc; ≤ 200/trang, sắp theo `updated_at` |
| `GET /tasks/{id}` | `tasks.read` | tiêu đề, trạng thái, ưu tiên, hạn, hồ sơ gắn, người làm, `revision` |
| `GET /people/{id}` | `people.read` | họ tên, chức danh, phòng ban |
| `GET /people?department_id=&cursor=` | `people.list` | danh bạ người đang hoạt động |
| `GET /departments` | `departments.read` | cây phòng ban (`parent_id`, `manager_id`) |
| `GET /settings` | — (token cài đặt) | cấu hình của cơ quan, kể cả giá trị bí mật |

- **Token cài đặt** (không gắn người): chỉ tới được hồ sơ/công việc mà plugin **đã được báo** qua một sự kiện hoặc
  một lời gọi bước quy trình, hoặc hồ sơ thuộc quy trình được chọn cho `cases.list`. Không có quyền "xem tất cả".
- **Token phiên** (khung giao diện, 10 phút; công cụ trợ lý, 2 phút): đọc và ghi **theo quyền của người đang xem**.
- Phạm vi luôn là giao của quyền đã duyệt cho plugin và phạm vi của token. Mọi lời gọi ghi vào nhật ký plugin.

### Ghi

| API | Phạm vi | Ghi chú |
|---|---|---|
| `POST /cases/{id}/comments` `{body}` | `cases.comment` | Hiện ở lịch sử hồ sơ: “Plugin X” hoặc “A qua plugin X”; người tạo hồ sơ được báo. |
| `PATCH /cases/{id}/plugin-fields` `{values}` | `cases.fields.write` | Chỉ trường trong `writes.fields` **và** được duyệt; không đổi trạng thái hồ sơ; bản đã trình giữ nguyên. |
| `POST /cases/{id}/files` (multipart `file`, `node_id`, `role`) | `cases.attach` | Mục “Tệp”. |
| `POST /tasks` | `tasks.write` | Như người xem tự giao: chỉ cho người/đơn vị họ được giao. |
| `POST /tasks/{id}/comments`, `POST /tasks/{id}/status` `{action, expected_revision, reason}` | `tasks.write` | Theo đúng luật chuyển trạng thái của công việc. |
| `POST /notifications` `{title, user_ids, department_id, case_id, link}` | `notifications.send` | Tiêu đề có tên plugin; `link` chỉ đường dẫn nội bộ; ≤ 200 người nhận. |

Mọi lệnh ghi **bắt buộc** `Idempotency-Key`: gửi lại cùng khoá và cùng nội dung trả đúng kết quả cũ; cùng khoá khác
nội dung là `409`. Mỗi lệnh ghi một dòng nhật ký plugin (`write`) và một dòng Nhật ký hoạt động `plugin.write.*`.
Không có lệnh duyệt/trả hồ sơ thay người, xoá hay sửa quyền.

### Tệp

`GET /cases/{id}/files` liệt kê tài liệu của hồ sơ (kèm `content_url`); `GET /files/{id}/content?case_id=` trả nội
dung đọc qua Core, có `Content-Type` và `X-Content-SHA256`. Bước chỉ cho xem một phần hồ sơ mà giấu tài liệu thì
token phiên của người ở bước đó không đọc được tệp. `POST /cases/{id}/files` gắn tệp (tối đa 25 MB/tệp, 200 MB mỗi
24 giờ mỗi plugin — `PLUGIN_UPLOAD_MAX_BYTES`, `PLUGIN_UPLOAD_DAILY_BYTES`); `node_id` gắn tệp với một bước để hiện
ở “Tài liệu” của bước trên sơ đồ hồ sơ; hồ sơ phát sự kiện `case.file_added`.

## Kênh 3 — Bước quy trình `plugin_action`

Trong trình thiết kế quy trình, bước của plugin đang bật nằm ở nhóm **Plugin**. Khi luồng tới bước, worker gửi
`POST {base_url}{endpoint}` (ký như sự kiện, `Idempotency-Key` = `run_id:node_id`):

```json
{ "call_id": "…", "run_id": "…", "node_id": "tra_cuu", "step": "tra_cuu_mst",
  "config": { "ma_so": "0101234567" }, "subject": { "type": "case", "id": "…" },
  "files": [{ "id": "…", "name": "don.pdf", "type": "application/pdf" }] }
```

`config` là đúng các ô người thiết kế đã điền, `{form.truong}` đã được thay bằng giá trị; `files` chỉ có khi người
thiết kế bật “Gửi danh sách tài liệu” (mã và tên, không có nội dung). Plugin trả
`{"branch": "success" | "error", "output": {...}, "message": "..."}`; thiếu `branch` thì 2xx là `success`, 4xx là
`error`. Bước sau đọc `{tra_cuu.ten_dn}`; chỉ giữ giá trị đơn mà manifest khai trong `outputs`. Quá 15 giây thì đi
nhánh `error` và **không gọi lại** (plugin có thể đã làm). Plugin tắt, gỡ hoặc máy chủ không còn được phép thì bước đi
nhánh `error` và ghi lý do lên sơ đồ; khi lưu luồng, trình thiết kế cũng báo lỗi ở bước đó.

### Bước chạy lâu (`mode: "async"`)

1. Plugin trả **202** ngay (`{"accepted": true}`); luồng dừng ở bước, sơ đồ hồ sơ hiện “Đang chờ plugin X”.
2. Plugin báo tiến độ (tuỳ chọn): `POST /plugin/v1/calls/{call_id}/progress` `{"message": "Đang chờ ký"}`.
3. Plugin báo xong: `POST /plugin/v1/calls/{call_id}/complete` `{"branch", "output", "message"}` bằng token cài đặt,
   **ký HMAC** như Desktiny ký (header `X-Desktiny-Timestamp`, `X-Desktiny-Signature`). Chỉ lần báo đầu được nhận;
   lần sau trả `{"accepted": false}`.
4. Quá `timeout_days` mà chưa báo thì bước đi nhánh **Hết thời gian chờ** (`timeout`).
5. Hồ sơ bị thu hồi, luồng quay lại bước trước hay kết thúc thì cuộc gọi chuyển `cancelled` và plugin nhận
   `plugin.call.cancelled`; gỡ plugin thì luồng đang chờ đi nhánh `error`.

## Kênh 4 — Khung giao diện

Trang plugin hiện trong `<iframe sandbox="allow-scripts allow-forms allow-popups">` (không có
`allow-same-origin` hay `allow-top-navigation`, `referrerpolicy="no-referrer"`): không đọc được cookie, DOM hay bộ nhớ
của Desktiny. Vị trí:

| `slot` | Hiện ở |
|---|---|
| `case.side`, `task.side` | Cột phải trang hồ sơ / công việc |
| `case.tab` | Một tab trong trang hồ sơ |
| `case.action`, `task.action` | Nút trong thanh thao tác, mở hộp thoại chứa khung |
| `home.widget` | Trang chủ |
| `page` | Trang riêng, mục trong nhóm **Ứng dụng** của thanh bên |
| `admin.page` | Trang quản trị của plugin (Quản trị › Plugin), chỉ người quản lý tổ chức |

Trao đổi qua `postMessage` với giao thức `{ "desktiny": 1, "type": … }`:

| Từ khung | Desktiny làm |
|---|---|
| `ready` / `context` | trả `context`: vị trí, mã hồ sơ/công việc, người xem, `theme`, `colors`, phông, tên ứng dụng |
| `token` (`id`) | trả `token` (`id`, `token`, `expires_at`, `api_base`) hoặc `error` |
| `resize` (`height`) | đổi chiều cao khung |
| `toast` (`text`, `tone`) | hiện thông báo ngắn có tên plugin |
| `navigate` (`path`) | chuyển trang, **chỉ** đường dẫn nội bộ (`/cases/…`) |
| `refresh` | tải lại dữ liệu đang hiện (sau khi plugin ghi) |
| `close` (`result`) | đóng hộp thoại của `case.action` / `task.action` |
| `confirm` (`id`, `text`) | hỏi bằng hộp thoại **của Desktiny**, trả `confirm_result` (`id`, `ok`) |

**Quyền thiết bị:** chỉ quyền trong `frame_permissions` **được duyệt** mới được đặt vào thuộc tính `allow` của iframe
(ví dụ `allow="geolocation"`); quyền không duyệt thì trình duyệt chặn. Desktiny chỉ nhận tin đến từ chính cửa sổ của
khung. SDK `packages/plugin-sdk/desktiny-plugin-sdk.js` lo phần này:

```js
import { connect } from './desktiny-plugin-sdk.js'
const desktiny = connect({ desktinyOrigin: 'https://desktiny.example.org' })
const context = await desktiny.context            // màu đã gán thành biến CSS --dk-<tên>
const dossier = await desktiny.api(`/cases/${context.record.case_id}`)
if (await desktiny.confirm('Ghi kết quả vào hồ sơ?')) {
  await desktiny.api(`/cases/${context.record.case_id}/comments`, { method: 'POST', body: { body: 'Đã ký' } })
  desktiny.refresh()
  desktiny.close({ signed: true })
}
```

## Kênh 5 — Sự kiện của plugin (gọi vào)

```json
"emits": [{ "type": "di_muon", "title": "Đi muộn quá 3 lần/tháng",
            "fields": { "nhan_vien": "person", "so_lan": "number" } }]
```

Plugin gửi `POST /plugin/v1/events` `{"type": "di_muon", "data": {...}}` (token cài đặt, `Idempotency-Key`, mặc định
60 sự kiện/phút — `PLUGIN_EVENTS_PER_MINUTE`). Desktiny kiểm dữ liệu theo khai báo (kiểu `string`, `number`, `date`
ISO 8601, `person` và `case` phải tồn tại) rồi phát sự kiện `plugin.<plugin id>.<type>`. Trình thiết kế quy trình có
nhóm điểm bắt đầu **Sự kiện của plugin**; dữ liệu đọc như `{so_lan}` hoặc `{trigger.so_lan}`. Không có webhook “mở”:
hệ thống ngoài (máy chấm công, cổng dịch vụ công) luôn đi qua máy chủ plugin, plugin tự xác thực phía nó.

## Trợ lý AI

```json
"assistant_tools": [{ "name": "so_lan_di_muon", "description": "Số lần đi muộn của người hỏi trong một tháng",
                      "endpoint": "/tools/di-muon",
                      "parameters": { "type": "object", "properties": { "thang": { "type": "string", "title": "Tháng" } } } }]
```

Quản trị viên duyệt từng công cụ; trợ lý chỉ dùng khi tính năng AI **Trợ lý dùng công cụ của plugin**
(`assistant_plugins`) bật. Với mỗi câu hỏi, trợ lý chọn tối đa một công cụ, gửi `POST {endpoint}` (ký HMAC, 10 giây)
`{"call_id", "tool", "arguments", "user", "token", "api_base"}` — `token` là token phiên 2 phút **của người đang hỏi**,
chỉ mang các phạm vi đọc. Plugin trả `{"result": …}` (≤ 8 KB). Câu trả lời ghi “theo plugin X”; kết quả không đưa vào
chỉ mục tri thức chung.

## Cấu hình theo cơ quan

`settings_schema` khai các ô (ô `"secret": true` được mã hoá khi lưu, không hiện lại). Quản trị viên điền ở
**Quản trị › Plugin › Cấu hình**; để trống ô bí mật là giữ giá trị cũ. Plugin đọc bằng `GET /plugin/v1/settings`
(token cài đặt) và nhận `plugin.settings.changed` (không kèm giá trị) khi cấu hình đổi. Gỡ plugin thì cấu hình bị xoá.

## Vận hành

- **Giới hạn tần suất** theo plugin và kênh: đọc `PLUGIN_READS_PER_MINUTE` (600), ghi `PLUGIN_WRITES_PER_MINUTE`
  (120), thông báo `PLUGIN_NOTIFICATIONS_PER_MINUTE` (30), sự kiện vào `PLUGIN_EVENTS_PER_MINUTE` (60). Vượt thì
  `429` kèm `Retry-After`.
- **Sức khoẻ**: `health_endpoint` trả 2xx khi ổn; nút **Kiểm tra** ở trang Plugin. Trang hiện lần kiểm tra gần nhất,
  tỉ lệ lỗi và thời gian trả lời trung bình 24 giờ. Lỗi 5 lần liên tiếp thì người duyệt plugin nhận thông báo (mỗi
  ngày một lần); plugin **không** tự tắt.

## Bộ công cụ

- `packages/desktiny-plugin` (Python, chỉ thư viện chuẩn): `read_delivery`/`verify` kiểm chữ ký và độ mới (5 phút);
  `Client` gọi API plugin (đọc, ghi kèm `Idempotency-Key`, tệp, sự kiện vào, báo kết quả bước chạy lâu có ký);
  CLI `desktiny-plugin`:
  - `init <thư mục>`: khung dự án (manifest, máy chủ tối thiểu, trang khung);
  - `check [manifest]`: kiểm manifest theo quy tắc của Desktiny;
  - `pack [thư mục] -o goi.zip`: kiểm rồi đóng gói;
  - `dev event|step|tool <tên> --secret … --manifest …`: đóng vai Desktiny, gửi sự kiện / gọi bước / gọi công cụ
    có ký tới máy chủ plugin đang chạy.
- `packages/plugin-sdk` (JavaScript, không phụ thuộc): phía khung của giao thức, kể cả các lệnh mới.
- `examples/plugins/tra-cuu-mst`: plugin mẫu (dữ liệu giả lập), có test; cách chạy trong README của nó.

## An toàn

| Mối lo | Biện pháp |
|---|---|
| Plugin đọc dữ liệu không được phép | Quyền theo plugin giao với quyền token; token cài đặt chỉ tới bản ghi đã được báo hoặc quy trình được chọn để liệt kê; token phiên kiểm theo quyền người xem; Core vẫn kiểm ACL nội dung. |
| Plugin ghi đè dữ liệu | Chỉ trường khai trước và được duyệt; không đổi trạng thái hồ sơ; ghi trường và công việc cần người; lịch sử ghi tên plugin; `Idempotency-Key` bắt buộc; tắt plugin là thu hồi ngay. |
| Plugin bị giả mạo | Ký HMAC mọi sự kiện, lời gọi bước, công cụ, và lời báo kết quả của plugin, kèm mốc thời gian; khoá mã hoá khi lưu, đổi được; token chỉ lưu bản băm. |
| Khung đánh cắp phiên hay lừa người dùng | Iframe sandbox, origin riêng, không cookie; token phiên ngắn, gắn ngữ cảnh; CSP `frame-src` theo danh sách; `navigate` chỉ đường dẫn nội bộ; `confirm` do Desktiny vẽ; quyền thiết bị chỉ khi được duyệt. |
| Gọi ra máy chủ nội bộ (SSRF) | Chỉ máy chủ trong `PLUGIN_ALLOWED_HOSTS`, kiểm lại trước mỗi lần gọi; không theo chuyển hướng. |
| Plugin lỗi làm treo quy trình | Hạn 15 giây, phản hồi tối đa 20 KB, nhánh `error`; bước chạy lâu bắt buộc `timeout_days`; tắt plugin là dừng ngay. |
| Trợ lý lộ dữ liệu qua công cụ | Gọi bằng token phiên của người hỏi, chỉ phạm vi đọc; duyệt từng công cụ; tính năng mặc định tắt. |
| Tải lên làm đầy kho | 25 MB/tệp, 200 MB/24 giờ mỗi plugin. |

## Giới hạn hiện tại

- Ô biểu mẫu do plugin vẽ (`form.field`), kho khoá–giá trị gắn hồ sơ cho plugin, chế độ “thử” chỉ chạy với hồ sơ
  có nhãn thử, danh mục plugin dùng chung và ký số manifest chưa làm.
- Giới hạn tần suất đếm trong từng tiến trình API (nhiều bản sao thì mỗi bản đếm riêng).
- Gateway chưa đặt `Permissions-Policy`; quyền thiết bị của khung dựa vào thuộc tính `allow` (mặc định trình duyệt
  chỉ cho trang chính và khung được trao quyền). Khung sandbox có origin ẩn danh: hãy thử `geolocation`/`camera` trên
  trình duyệt đích trước khi dựa vào.
- Plugin trong tiến trình (tầng 3) chưa làm.
