<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# Lộ trình

Chỉ ghi việc có thật trong kho hoặc trong bug tracker. Thứ tự trong mỗi mục không phải cam kết ngày. Theo dõi chi tiết:
[Milestones](https://github.com/Dking2007/DXOS_Desktiny/milestones), [CHANGELOG](CHANGELOG.md).

## Đã xong

**Đã phát hành (đến 3.1.0)**
- Core headless `/core/v1/`: principal/ACL, schema/record có phiên bản, tệp có phiên bản kèm SHA-256, workflow,
  nhật ký kiểm toán nối chuỗi băm.
- Workspace: giao việc, hồ sơ và phê duyệt, quy trình vẽ trên canvas, kho tài liệu, nhắn tin, bảng tin, báo cáo,
  19 tính năng AI mặc định tắt.
- Gói giao diện `desktiny-pack/1`, plugin kết nối `desktiny-plugin/1` (3.0.0), plugin đóng gói `desktiny-plugin/2` (3.1.0).

**Đã vào mã, chờ phát hành 3.2.0** (mục `[Unreleased]` của CHANGELOG)
- Quét mã độc tệp tải lên bằng ClamAV (tùy chọn, profile `security`).
- Cảnh báo và che dữ liệu cá nhân trong tệp (`dx-piivn`).
- Sao lưu, khôi phục kèm manifest SHA-256 (`scripts/backup.py`, `scripts/restore.py`).
- TOTP bắt buộc cho tài khoản demo `lanh-dao-mfa`.
- `scripts/seed_demo.py` nạp nội dung minh họa.
- Workflow phát hành kiểm số phiên bản theo SemVer và đính kèm SBOM CycloneDX.
- Nâng cấp trải nghiệm: Cài đặt cá nhân, canvas có sao chép/dán và hoàn tác, sơ đồ cơ cấu tổ chức, bộ chọn người.

## Đang làm

- **Quy trình có nhánh không tới bước *Kết thúc*:** hiện vẫn phát hành được và hồ sơ có thể kẹt ở *Đang xử lý* sau
  khi duyệt. Hướng sửa: engine tự hoàn tất hồ sơ khi một nhánh tới bước không còn bước tiếp (tương thích với gói đã có),
  và cho người tạo thu hồi hồ sơ đã kẹt.
- **Xóa biểu mẫu** trên giao diện.
- **Nút của plugin** chỉ hiện trên hồ sơ thuộc phạm vi plugin; hiện nút của mọi plugin hiện trên mọi hồ sơ.
- **Hai bản mở rộng minh họa nguyên lý dữ liệu** (repo Expansion Pack, nhánh `tich-hop/olp-2026-11-28`): plugin
  `luu-tru-lich-su` (vòng đời, truy nguồn) và `cam-bien` (dữ liệu thiết bị); chờ đưa vào bản phát hành.

## Dự kiến

- Cảm biến qua MQTT, OPC-UA và CSDL chuỗi thời gian (hiện plugin `cam-bien` chỉ nhận HTTP).
- Hồ dữ liệu thật cho dữ liệu lịch sử, chính sách lưu giữ tự động theo thời hạn.
- Đồ thị phả hệ giữa các tập dữ liệu và chỉ số chất lượng dữ liệu.
- MFA bắt buộc theo vai trò, mTLS giữa dịch vụ, triển khai GitOps.
- Quét lại tệp đã lưu khi ClamAV có chữ ký mới.
- Nhắn tin qua WebSocket; Gantt và lịch tháng cho công việc; node vòng lặp và connector OAuth2 trong luồng tự động.
- Plugin đóng gói có mã máy chủ ([thiết kế](docs/design/Plugin_dong_goi_tu_chay.md)); ô biểu mẫu do plugin vẽ; ký số
  manifest plugin.

## Không nằm trong kế hoạch

- **Chữ ký số có giá trị pháp lý.** Plugin Ký số trong bản mở rộng Một cửa là mô phỏng; chữ ký thật cần dịch vụ chứng
  thư số được cấp phép và nằm ngoài phạm vi dự án.
