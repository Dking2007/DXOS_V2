# Một cửa (mẫu) — plugin đóng gói

Plugin mẫu dạng `desktiny-plugin/2` **không có máy chủ riêng**: cài tệp `.zip` là dùng được. Desktiny tự phục vụ các
trang trong `ui/` (luôn trong khung cách ly) và cài gói giao diện trong `pack/` cùng plugin.

| Thành phần | Nội dung |
|---|---|
| `ui/tinh-han.html` | Trang **Tính hạn xử lý** (nhóm Ứng dụng trên thanh bên): hạn theo ngày làm việc, bỏ cuối tuần và ngày lễ. |
| `ui/phieu-tiep-nhan.html` | Khung **Phiếu tiếp nhận** ở cột phải trang hồ sơ: đọc hồ sơ theo quyền người đang xem. |
| `ui/desktiny-plugin-sdk.js` | Bản sao của `packages/plugin-sdk/desktiny-plugin-sdk.js` (test kiểm hai bản giống nhau). |
| `pack/` | Gói giao diện đi kèm: quy trình "Tiếp nhận hồ sơ một cửa" và bài hướng dẫn cho trợ lý AI. |

## Cài thử

```sh
pip install -e packages/desktiny-plugin
desktiny-plugin check examples/plugins/mot-cua-mau
desktiny-plugin pack examples/plugins/mot-cua-mau -o mot-cua-mau.zip
```

Tải `mot-cua-mau.zip` lên ở **Quản trị › Plugin**, xem trước (quyền, khung, gói giao diện đi kèm), cài, rồi **Duyệt quyền**.
Gỡ plugin thì gói giao diện đi kèm cũng được gỡ.
