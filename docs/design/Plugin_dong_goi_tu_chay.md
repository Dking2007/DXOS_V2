<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# PLUGIN ĐÓNG GÓI, DESKTINY TỰ CHẠY

**Trạng thái:** đã chốt hướng; giai đoạn 1 đã làm (nhánh `feat/plugin-dong-goi`) · **Ngày:** 14/11/2026 · **Phiên bản:** 0.2

**Đã quyết định (14/11/2026):** mã máy chủ của plugin đóng gói viết bằng **Deno (TypeScript)**; plugin **được mang
theo gói giao diện** (`pack/`). Plugin viết bằng Python vẫn chạy được ở dạng plugin kết nối (máy chủ ngoài).

## 1. Điều chỉnh cách hiểu

| | Plugin kết nối hiện tại (`desktiny-plugin/1`) | Plugin cần có |
|---|---|---|
| Tệp cài | `.zip` chỉ chứa `desktiny-plugin.json` trỏ tới `base_url` | `.zip` chứa **đủ** manifest, giao diện, mã máy chủ, dữ liệu mẫu — giống gói giao diện |
| Ai chạy mã | Cơ quan phải tự dựng và vận hành một máy chủ web | **Desktiny tự chạy**, cài là dùng |
| Dữ liệu riêng của plugin | Plugin tự có CSDL | Desktiny cấp **kho dữ liệu riêng** cho từng plugin |
| Kết quả khi cài | Thêm khung, bước quy trình, sự kiện | Thêm **tính năng mới**: menu, màn hình, bước quy trình, công cụ trợ lý, việc định kỳ — gỡ là mất sạch |

Không bỏ việc đã làm: bốn kênh hiện có (sự kiện, API có phạm vi, bước quy trình, khung giao diện) **giữ nguyên**.
Điểm khác duy nhất là "máy chủ plugin" do Desktiny dựng từ chính tệp `.zip`, thay vì một địa chỉ bên ngoài.

```
  Quản trị › Plugin ── tải .zip ──► Workspace API ── kiểm, xem trước, duyệt quyền
                                         │ giải nén vào kho plugin (volume)
                                         ▼
  Trình duyệt ── iframe ──► /plugins/<id>/ui/…   (gateway phục vụ tệp tĩnh từ .zip)
  Worker/API ── HTTP ký HMAC ──► plugin-host ── tiến trình Deno cách ly của từng plugin
  Plugin ── token có phạm vi ──► /workspace/v1/plugin/v1 (API, kho dữ liệu riêng)
```

## 2. Cấu trúc gói

```
tra-cuu-mst-1.2.0.zip
├── desktiny-plugin.json      # bắt buộc
├── ui/                       # HTML/JS/CSS tĩnh cho các khung (case.tab, page, admin.page…)
├── server/main.ts            # mã máy chủ (tuỳ chọn), chạy trên Deno
├── data/                     # dữ liệu khởi tạo cho kho riêng (tuỳ chọn)
├── pack/                     # một gói giao diện đi kèm (tuỳ chọn): biểu mẫu, quy trình, kiến thức
└── README.md, LICENSE
```

Manifest thêm khối `runtime`; `base_url` trở thành tuỳ chọn (vẫn dùng được cho plugin đặt ở máy chủ ngoài):

```json
{
  "schema": "desktiny-plugin/2",
  "id": "vn.vi-du.tra-cuu-mst",
  "version": "1.2.0",
  "runtime": { "kind": "deno", "entry": "server/main.ts", "memory_mb": 128, "outbound_hosts": ["api.thue.gov.vn"] },
  "storage": { "collections": ["tra_cuu", "cache"], "quota_mb": 50 },
  "schedules": [{ "cron": "0 7 * * 1-5", "endpoint": "/jobs/nhac-han", "title": "Nhắc hồ sơ sắp hết hạn" }],
  "permissions": ["cases.read", "cases.comment"],
  "events": ["case.submitted"],
  "nodes": [ … ], "ui": [ … ], "assistant_tools": [ … ], "settings_schema": { … }
}
```

- `ui[].url` là đường dẫn **trong gói** (`/ui/…`); `endpoint` là đường dẫn trên máy chủ của plugin (`/…`).
- Mục menu dùng lại khung `page` (nhóm **Ứng dụng** trên thanh bên), không thêm khối `menu` riêng.
- `pack/` dùng lại trình cài gói giao diện: plugin "Một cửa" mang theo biểu mẫu và quy trình của nó.

## 3. Thành phần mới

### 3.1. `plugin-host` (dịch vụ mới trong compose)

- Một container riêng, **không** có Docker socket, không có quyền gì với CSDL hay Core.
- Mỗi plugin là một tiến trình Deno với quyền khoá chặt:
  `--allow-net=workspace-api:8000,<outbound_hosts đã duyệt> --allow-read=<thư mục gói> --no-prompt`, không
  `--allow-write`, `--allow-env`, `--allow-run`, `--allow-ffi`; giới hạn bộ nhớ V8 theo `memory_mb`, CPU qua cgroup.
- Nhận lời gọi tại `http://plugin-host:8100/p/<plugin_id>/…` và chuyển tới tiến trình tương ứng. Desktiny coi đây là
  `base_url` nội bộ, nên **toàn bộ** code gửi sự kiện, gọi bước, ký HMAC, kiểm máy chủ hiện có dùng lại nguyên.
- Khởi động lười (lần gọi đầu), tắt khi rảnh 15 phút; tự khởi động lại khi lỗi, quá 5 lần/giờ thì báo quản trị viên.
- Khoá ký và token cài đặt chuyển cho tiến trình qua lời gọi khởi tạo (không qua biến môi trường, không ghi đĩa).

Vì sao Deno: chặn quyền mạng/tệp/tiến trình ở mức runtime, chạy được TypeScript trực tiếp, không cần build, không cần
cài gói lúc chạy (phụ thuộc phải đóng sẵn vào gói). Python không cô lập được ở mức này; plugin Python để ở dạng plugin
máy chủ ngoài (`base_url`) như hiện tại.

### 3.2. Phục vụ giao diện

- Workspace API giải nén `ui/` vào volume `plugin-files`; gateway phục vụ `/plugins/<id>/<version>/ui/…` với
  `Content-Security-Policy` riêng (`default-src 'self'`, `connect-src` chỉ tới API plugin), `nosniff`.
- Khung vẫn là iframe `sandbox` **không** `allow-same-origin`, nên dù cùng tên miền vẫn là origin riêng, không đọc được
  cookie/DOM của Desktiny. Không cần `PLUGIN_FRAME_SOURCES` cho plugin đóng gói.
- Đường dẫn có phiên bản để nâng cấp không lẫn bộ nhớ đệm.

### 3.3. Kho dữ liệu riêng

- API mới `/plugin/v1/storage/{collection}`: thêm, sửa, xoá, lấy theo mã, truy vấn đơn giản (bằng, khoảng, sắp xếp
  theo tối đa 3 trường khai trong manifest), phân trang. Tài liệu JSON ≤ 256 KB.
- Một bảng `plugin_records` (plugin_id, collection, id, data JSON, cập nhật lúc) + chỉ mục theo trường khai báo; hạn
  mức theo `quota_mb`. Plugin chỉ thấy dữ liệu của chính nó.
- Gỡ plugin: giữ dữ liệu 30 ngày (khôi phục được khi cài lại), có nút **xuất** `.zip`; sau đó xoá hẳn.

### 3.4. Việc định kỳ

Worker đọc `schedules` của plugin đang bật, đến giờ thì gọi `endpoint` (ký HMAC, `Idempotency-Key` = mã lần chạy).
Quản trị viên xem lịch, lần chạy gần nhất và tắt từng việc.

### 3.5. Menu và màn hình

Khung `page` thêm mục vào nhóm **Ứng dụng** của thanh bên, mở trang `ui/…` toàn màn hình; `admin.page` thêm trang ở
Quản trị › Plugin.

## 4. Vòng đời

| Bước | Hành vi |
|---|---|
| Xem trước | Kiểm `.zip` (giới hạn dung lượng, đường dẫn, manifest), liệt kê: menu, màn hình, bước, sự kiện, quyền, máy chủ ngoài muốn gọi, dung lượng kho, việc định kỳ, gói giao diện đi kèm. |
| Cài | Lưu gói, cài `pack/` nếu có, trạng thái **chờ duyệt**. |
| Duyệt | Quản trị viên chọn quyền, sự kiện, `outbound_hosts`, quyền thiết bị; bật thì `plugin-host` sẵn sàng chạy. |
| Nâng cấp | Tải bản mới cùng `id`: giữ dữ liệu kho, chạy `server/migrate` nếu có, đổi sang bản mới khi kiểm sức khoẻ đạt; xin thêm quyền thì chờ duyệt phần thêm. Lỗi thì giữ bản cũ. |
| Tắt | Dừng tiến trình, ẩn menu/khung, thu hồi token. |
| Gỡ | Như tắt + gỡ gói giao diện đi kèm (theo luật gỡ gói giao diện), giữ dữ liệu 30 ngày. |

## 5. An toàn

| Mối lo | Biện pháp |
|---|---|
| Mã lạ đọc dữ liệu | Không có đường tới CSDL/Core; chỉ API có phạm vi đã duyệt; kho riêng theo plugin |
| Mã lạ gọi ra ngoài, dò mạng nội bộ | Deno `--allow-net` chỉ API Desktiny và máy chủ ngoài đã duyệt; `plugin-host` ở mạng Docker riêng |
| Ăn hết tài nguyên | Giới hạn bộ nhớ, CPU, số tiến trình, thời gian mỗi lời gọi; hạn mức kho |
| Gói bị sửa | Lưu SHA-256 của gói; về sau ký số gói (cùng cơ chế với gói giao diện) |
| Thoát sandbox Deno | `plugin-host` không đặc quyền, chỉ đọc, `no-new-privileges`, bỏ mọi capability; cập nhật Deno theo bản vá |

## 6. Lộ trình

| Giai đoạn | Nội dung | Ước lượng |
|---|---|---|
| 1 ✅ | Định dạng `.zip`/manifest `/2`, cài, phục vụ `ui/` (CSP `sandbox`), gói giao diện đi kèm — plugin chỉ có giao diện | 1,5 tuần |
| 2 | `plugin-host` + Deno, `runtime`, dùng lại 4 kênh hiện có | 2 tuần |
| 3 | Kho dữ liệu riêng + việc định kỳ | 1,5 tuần |
| 4 | Nâng cấp có migrate, xuất dữ liệu; CLI `desktiny-plugin init/dev/pack` cho Deno | 1 tuần |
| 5 | Chuyển plugin mẫu `tra-cuu-mst` sang dạng đóng gói; thêm một plugin mẫu "Sổ văn bản" có kho dữ liệu | 1 tuần |

## 7. Câu hỏi để nhóm quyết định

1. ~~Ngôn ngữ máy chủ~~: đã chốt Deno (TypeScript).
2. ~~Kèm gói giao diện~~: đã chốt có; gói cài, nâng cấp, gỡ cùng plugin.
3. Kho dữ liệu riêng có cần tìm kiếm toàn văn không, hay truy vấn theo trường là đủ?
4. Có cần ký số gói trước khi cho cơ quan tự tải lên `.zip` không?
