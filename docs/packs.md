<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# Gói giao diện (`desktiny-pack/1`)

Gói giao diện đóng gói **nghiệp vụ** (quy trình, biểu mẫu, mẫu quy trình, luồng tự động, bài kiến thức cho trợ lý
AI) và **giao diện** (tên, logo, màu, phông, trang đăng nhập, từ ngữ, menu, trang chủ) của một ngành hay một cơ
quan. Gói **không chứa mã**. Cài, nâng cấp, gỡ ở **Quản trị › Gói giao diện** (quyền `organization.manage`); gỡ gói thì
Desktiny về đúng giao diện và nghiệp vụ mặc định. Đây là tầng 1 của hướng mở rộng; plugin có mã chạy ở máy chủ
riêng (tầng 2) xem [`plugins.md`](plugins.md).

## Cấu trúc

```
packs/truong-hoc/
├── desktiny-pack.json          # bắt buộc
├── processes/*.json            # quy trình: biểu mẫu + đồ thị luồng
├── forms/*.json                # biểu mẫu đứng riêng (thân POST /forms)
├── templates/*.json            # mẫu quy trình cho hộp “Tạo quy trình”
├── automations/*.json          # luồng tự động, cài ở trạng thái tắt
├── knowledge/*.md              # bài kiến thức cho trợ lý AI
└── assets/                     # logo, favicon, ảnh nền đăng nhập
```

Tải lên dạng `.zip` của thư mục (có hoặc không có thư mục gốc). Giới hạn: 10 MB nén, 25 MB giải nén, 300 tệp,
mỗi tệp văn bản 2 MB. Đường dẫn tuyệt đối hoặc có `..` bị từ chối.

## `desktiny-pack.json`

```json
{
  "schema": "desktiny-pack/1",
  "id": "vn.truong-hoc",
  "name": "Trường học",
  "version": "0.2.0",
  "license": "Apache-2.0",
  "authors": ["Desktiny contributors"],
  "description": "…",
  "requires": { "desktiny": ">=0.2.0" },
  "appearance": { "…": "xem dưới" },
  "processes": ["processes/xin-nghi-phep-giao-vien.json"],
  "forms": [],
  "templates": ["templates/to-chuyen-mon-gop-y.json"],
  "automations": [],
  "knowledge": ["knowledge/quy-che-nghi-phep.md"]
}
```

- `id`: chữ thường, có ít nhất một dấu chấm (`vn.truong-hoc`). `desktiny.core` dành cho gói mặc định; `local.*`
  dành cho gói do cơ quan tạo trên trình tạo gói.
- `version`: `x.y.z`. Cài lại cùng `id` là **nâng cấp**.
- `requires.desktiny`: chỉ nhận `>=x.y.z` hoặc `*`; bản Desktiny cũ hơn thì từ chối cài.
- Mọi trường khác bị từ chối (không có trường "tự do").

### Phần giao diện (`appearance`)

| Khoá | Nhận | Ghi chú |
|---|---|---|
| `app_name`, `org_name` | chữ, ≤ 60 / 120 ký tự | Hiện ở thanh bên, tab trình duyệt, trang đăng nhập. |
| `logo`, `favicon` | đường dẫn tới PNG, WebP hoặc SVG trong gói | Logo ≤ 512 KB, favicon ≤ 256 KB. SVG được **lọc**: bỏ `script`, `foreignObject`, thuộc tính `on*`, liên kết ra ngoài, `@import`; có `DOCTYPE`/`ENTITY` thì từ chối. |
| `colors.light`, `colors.dark` | `{ "teal": "#1d5c96", … }` | Chỉ các biến màu có sẵn trong `apps/shared/src/style.css` (`navy`, `muted`, `canvas`, `surface`, `teal`, `teal-strong`, `teal-soft`, `teal-ink`, `red`, `green-ink`…), giá trị `#rrggbb`. |
| `font` | `source-sans-3` (mặc định), `be-vietnam-pro` | Phông đã đóng gói sẵn, không nhận URL. |
| `density` | `comfortable`, `compact` | |
| `radius` | `small`, `medium`, `large` | |
| `login` | `{ "style": "framed" \| "flat" \| "image", "title", "subtitle", "background", "ground", "ground_to", "button_label", "note", "effects" }` | `image` cần `background` (PNG/JPEG/WebP ≤ 2 MB). `ground`/`ground_to`: màu nền `#rrggbb` (trên → dưới; với `image` là lớp phủ lên ảnh), chữ trắng trên nền phải đạt tương phản ≥ 4,5:1. `button_label` (≤ 40), `note` (≤ 200): chữ trên nút và dòng dưới nút. `effects: false` tắt chuyển động của kiểu `framed`. Bỏ trống thì giữ như mặc định. |
| `terminology` | `{ "Hồ sơ": "Hồ sơ học vụ" }`, ≤ 60 cặp | Đổi chữ hiển thị ở menu, tiêu đề trang, trang chủ (cả dạng viết hoa đầu và thường). Không đổi dữ liệu, đường dẫn, API. |
| `menu.hide` | `tasks`, `cases`, `chat`, `feed`, `drive`, `reports` | Không ẩn được trang chủ, phê duyệt, phần quản trị. |
| `menu.order` | khoá trong `home, tasks, approvals, cases, chat, feed, drive, reports, processes, assistant, plugins, packs, settings` | Phân hệ không nêu giữ chỗ sau các phân hệ được nêu. |
| `home` | `tasks.today`, `quick.start`, `cases.recent`, `ai.digest`, `plugins.widgets` (khối của plugin kết nối) | Khối không nêu thì ẩn; ở cột phải theo thứ tự nêu. |

**Kiểm tương phản** (WCAG AA, 4,5:1) chạy cho cả giao diện sáng và tối, với màu của gói đè lên màu mặc định. Các
cặp: chữ chính trên nền thẻ và nền trang, chữ phụ, liên kết, chữ trên nền nhấn nhạt, chữ trên nút chính, chữ báo
lỗi, nhãn lỗi, nhãn thành công. Một cặp không đạt thì gói bị từ chối, trình tạo gói không cho lưu.

### Quy trình (`processes/*.json`)

```json
{
  "name": "Giáo viên xin nghỉ phép",
  "description": "…",
  "form": { "name": "Đơn xin nghỉ phép", "fields": [ { "key": "so_ngay", "label": "Số ngày nghỉ", "type": "number", "required": true } ] },
  "graph": { "nodes": [ … ], "edges": [ … ] },
  "allowed_roles": [],
  "required_file_count": 0,
  "publish": true
}
```

- `form.fields` dùng đúng kiểu trường của biểu mẫu (`text`, `textarea`, `number`, `date`, `select`, `checkbox`,
  `visible_when`…). Mỗi lần cài/nâng cấp có thay đổi trường thì tạo biểu mẫu mới (biểu mẫu đã phát hành là bất biến).
- `graph` là đồ thị canvas (`ApiGraph`) như trình thiết kế quy trình lưu; node kích hoạt là `case.submitted`,
  `form_id` để `null` (khi cài được gắn biểu mẫu vừa tạo). Đồ thị được kiểm như khi lưu trên canvas.
- Người duyệt nên dùng `department_manager` hoặc `role`. Quy trình có bước chỉ định người cụ thể (`user_id`,
  `user_ids`) được cài **dạng nháp** để cơ quan chọn lại người, không phát hành tự động.
- `publish: true` (mặc định): phát hành ngay nếu hợp lệ; lỗi thì để nháp và báo lại sau khi cài.

### Mẫu, luồng, kiến thức

- `templates/*.json`: `{ "key", "title", "description", "graph" }`; `key` là duy nhất giữa các gói. Hiện trong hộp
  **Tạo quy trình**, có tên gói đi kèm (trừ gói mặc định).
- `automations/*.json`: `{ "name", "description", "graph", "scope" }`, luồng phản ứng sự kiện (không gắn biểu
  mẫu); luôn cài ở trạng thái **tắt**.
- `knowledge/*.md`: tiêu đề lấy từ dòng `# …` đầu tiên (không có thì lấy tên tệp); bài được đánh dấu nguồn `pack`.

## Cài, nâng cấp, gỡ

| Thao tác | Hành vi |
|---|---|
| Xem trước | `POST /workspace/v1/packs/preview` (tệp `.zip` hoặc `builtin=<id>`): sẽ thêm gì, đổi giao diện gì, trùng tên gì, cảnh báo gì. Không ghi gì. |
| Cài | `POST /workspace/v1/packs` (`activate=true` để dùng ngay giao diện của gói). Một giao dịch; ghi lại id mọi thứ đã tạo vào `installed_packs.created`. Cần thêm `forms.manage`, `automations.manage`, `assistant.manage` nếu gói có phần tương ứng. |
| Nâng cấp | Cài lại cùng `id`: cập nhật đúng các đối tượng cũ (quy trình phát hành phiên bản mới), thêm cái mới, gỡ cái bản mới bỏ đi. |
| Gỡ | `DELETE /workspace/v1/packs/{id}`: xoá mẫu, bài kiến thức, luồng/quy trình **chưa từng dùng**; quy trình đã có hồ sơ hoặc luồng đã chạy chỉ **ngừng sử dụng**, biểu mẫu đã có hồ sơ được giữ. Giao diện đang dùng thì về mặc định. |
| Giao diện | `GET /workspace/v1/appearance` (công khai, trang đăng nhập dùng) · `PUT /workspace/v1/appearance` chọn gói hoặc `null` (mặc định). Một gói giao diện có hiệu lực tại một thời điểm. |
| Xuất | `GET /workspace/v1/packs/{id}/export` → `.zip` cài được ở cơ quan khác. |

Tài nguyên (logo, favicon, ảnh nền) được lưu trong cơ sở dữ liệu Workspace (bảng `pack_assets`) thay vì Core như ảnh
đại diện, vì Core không nhận SVG và trang đăng nhập cần hiển thị logo trước khi có phiên. Chúng được phục vụ ở
`/workspace/v1/appearance/assets/{id}` với `Content-Security-Policy: default-src 'none'` và `nosniff`.

## Gói của cơ quan (trình tạo gói)

Nút **Tạo gói của cơ quan** mở trình tạo gói: tab **Giao diện** chỉnh trực quan với **xem trước** (thanh bên, thẻ,
nút, trang đăng nhập; sáng/tối), kiểm tương phản ngay khi chọn màu; tab **Nghiệp vụ** chọn quy trình, luồng, bài
kiến thức đang có. Lưu tạo/cập nhật gói `local.*` (`PUT /workspace/v1/packs/{id}`, tài nguyên qua
`POST /workspace/v1/packs/{id}/assets`); muốn áp dụng thì bấm **Dùng giao diện này**. Gói `local.*` chỉ **trỏ tới**
những thứ đã có: gỡ không xoá chúng; khi xuất, chúng được ghi thành tệp trong `.zip`.

## Gói đi kèm bản phát hành

| Gói | Nội dung |
|---|---|
| `packs/desktiny.core` | 17 mẫu quy trình của hộp **Tạo quy trình**. Luôn được cài và cập nhật theo bản phát hành; không gỡ được. |
| `packs/truong-hoc` | Gói mẫu: giao diện xanh dương, từ ngữ của nhà trường, ẩn Bảng tin, quy trình giáo viên xin nghỉ phép, mẫu góp ý của tổ chuyên môn, quy định nghỉ phép cho trợ lý AI. Tên trường là tên giả. |

Thư mục gói được tìm ở `PACKS_DIR` (biến môi trường), thư mục `packs/` cạnh mã nguồn, rồi `/app/packs` (image API).
`make install` chép `packs/` vào `share/desktiny/packs`.

## Viết và thử một gói

1. Chép `packs/truong-hoc` thành thư mục mới, đổi `id`, `name`, `version`.
2. Vẽ quy trình trên canvas, rồi dùng trình tạo gói chọn nó và **Xuất** để có tệp `processes/*.json` đúng định dạng.
3. Nén thư mục thành `.zip`, tải lên ở **Gói giao diện**, đọc kỹ phần xem trước rồi cài.
4. Gói trong repo phải qua `reuse lint` (thư mục `packs/` được khai trong `REUSE.toml`), không dùng tên, logo, con dấu
   của cơ quan thật, không chứa phông hay ảnh tải từ ngoài.

## Giới hạn hiện tại

- Từ ngữ chỉ đổi ở menu, tiêu đề trang, trang chủ và một số tiêu đề; nội dung các màn hình khác vẫn dùng chữ gốc.
- Mật độ và bo góc tác động lên thẻ, nút, ô nhập, bảng và danh sách; một số thành phần riêng giữ kích thước gốc.
- Chưa có danh mục gói dùng chung giữa các cơ quan và chưa ký số gói; cài từ tệp hoặc từ `packs/` của bản phát hành.
