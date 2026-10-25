# Chính sách bảo mật

## Phiên bản được hỗ trợ

Chỉ bản phát hành mới nhất (`v0.x`) nhận bản vá bảo mật. Dự án ở giai đoạn pilot/phát triển; cấu hình
Compose trong repo là cấu hình **dev**, không phải production (xem [docs/security.md](docs/security.md)).

## Báo lỗ hổng

Vui lòng **không** mở issue công khai. Dùng *Security → Report a vulnerability* (GitHub private advisory)
của repo `Raphael-Fug/DXOS_V2`, hoặc email người duy trì: nduy34540@gmail.com. Hãy nêu phiên bản, các bước tái hiện
và ảnh hưởng. Chúng tôi phản hồi trong vòng 7 ngày và công bố bản vá cùng ghi nhận người báo (nếu bạn đồng ý).

## Không commit bí mật

`.env` và `infra/identity/generated/` bị `.gitignore` loại trừ. Nếu lỡ commit khóa/mật khẩu, hãy xoay (rotate) ngay.
