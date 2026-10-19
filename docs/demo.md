# Demo Core + e-Office

Dùng dữ liệu giả được bootstrap/seed riêng. Không nhập hồ sơ thực hoặc credential
production vào buổi demo. Đăng nhập các role bằng browser profile riêng hoặc logout
đúng cách để không nhầm phiên SSO.

## Chuẩn bị

1. Bật Docker Desktop; bootstrap, `--profile workspace up --build -d`, seed demo.
2. Nếu trình diễn editor, bật thêm profile Office và chờ Document Server sẵn sàng.
3. Đọc credential local, không đưa file credential hoặc `.env` vào màn hình chiếu.
4. Tạo mẫu biểu có text/number/date/select và rule duyệt; chọn người nhận không phải
   người tạo, kiểm form published/version. Không cần dữ liệu mẫu ngầm trong source.
5. Mở `director`, `manager`, `staff` ở các browser session tách biệt. Có thêm tài
   khoản phòng B để kiểm không lộ hồ sơ/file ngoài quyền.

## Luồng 15 phút

### 0–2: Ranh giới nền tảng

Giải thích Core không biết phòng ban/hồ sơ; Workspace không đọc SQL bảng Core.
Chỉ ra DB user/database riêng và payload live ở Core, decision ở Workspace.

### 2–5: Core tái sử dụng

Dùng Core admin/client generic tạo schema `equipment_check`, record có validation,
upload file, chạy workflow chờ human task; namespace equipment không thấy workspace.
Nếu dừng Workspace để chứng minh độc lập, chỉ dừng service Workspace/web/worker,
không chạy `down -v` hoặc xóa dữ liệu. Không gọi đây là app chuyên ngành hoàn thiện.

### 5–10: Hồ sơ và phiên bản tài liệu

Staff tạo hồ sơ, điền biểu mẫu, gắn file, đặt hạn xử lý, mức độ ưu tiên và người
phụ trách. Nếu Office bật, mở tài liệu, chỉnh sửa và
chờ trạng thái lưu về hệ thống. Gửi hồ sơ sau khi version đã chốt. Manager trả lại
có lý do; staff sửa/trình lại, manager duyệt. Hiển thị snapshot, actor và phiên bản
file đúng lần trình, không chỉ toast hoặc thay trạng thái trên frontend.
Trong Drive, gán nhãn cho tài liệu và tạo bản sao; chỉ ra bản sao là tài liệu độc
lập nên sửa bản sao không đụng lịch sử version của bản gốc.

### 10–12: Lỗi và quyền

Thử gửi cùng intent/retry hoặc decision revision cũ; không tạo trùng và conflict rõ.
Đăng nhập phòng B thử tài nguyên không được chia sẻ; cả metadata và bytes phải chặn.
Nếu callback save lỗi hoặc Core tạm dừng, hiển thị pending/lỗi chứ không báo lưu
hoặc approved giả.

### 12–15: Bằng chứng và giới hạn

Chỉ trình các test/log/health thật đã chạy. Nêu phần chưa nghiệm thu: concurrency DB
thật nếu chưa chạy, Office edition/font compatibility, restore/load và module hoãn.
Không khẳng định tuân thủ đề thi/giấy phép hoặc giảm tỷ lệ thao tác khi chưa có đo.
