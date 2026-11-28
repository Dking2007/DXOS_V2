# Chính sách bảo mật

Desktiny giữ tài khoản, hồ sơ, tệp và lịch sử phê duyệt của một tổ chức, nên một lỗ hổng có thể làm lộ hoặc làm sai
dữ liệu nghiệp vụ. Vui lòng **không** mở issue công khai cho lỗ hổng; báo riêng theo hướng dẫn dưới đây.

## Phiên bản được hỗ trợ

Chính sách của nhóm: chỉ dòng phiên bản mới nhất và dòng sắp phát hành nhận bản vá bảo mật.

| Phiên bản | Nhận bản vá |
|---|---|
| 3.2.x (sắp phát hành) | Có |
| 3.1.x | Có |
| < 3.1 | Không; hãy nâng cấp |

Compose trong kho là cấu hình **phát triển**, không phải production ([docs/security.md](docs/security.md)).

## Cách báo

Dùng báo cáo lỗ hổng riêng tư của GitHub:
<https://github.com/Dking2007/DXOS_Desktiny/security/advisories/new> (tab *Security › Report a vulnerability*). Chỉ
người báo và người duy trì thấy nội dung.

Nên gửi kèm:
- phiên bản (tag) hoặc commit;
- các bước tái hiện, tốt nhất trên cài đặt mới bằng `scripts/bootstrap.py`;
- ảnh hưởng: ai làm được gì mà lẽ ra không được;
- đề xuất sửa, nếu có.

Không gửi mật khẩu, token hay dữ liệu thật; dùng tài khoản demo và dữ liệu giả.

## Thời gian phản hồi (mục tiêu)

| Bước | Mục tiêu |
|---|---|
| Xác nhận đã nhận | Trong 3 ngày |
| Đánh giá mức độ và phạm vi | Trong 7 ngày |
| Bản vá cho lỗi nghiêm trọng | Trong 30 ngày |

Đây là mục tiêu của một nhóm nhỏ, không phải cam kết dịch vụ. Nếu cần lâu hơn, chúng tôi báo lại trong advisory.

## Phạm vi

**Trong phạm vi:** mã trong kho này: Core (`services/core-api`), Workspace (`services/workspace-api`,
`apps/workspace-web`), Core admin (`apps/core-admin`), cấu hình cổng `infra/gateway/nginx.conf`, các gói trong
`packages/` (kể cả SDK plugin), các script `scripts/bootstrap.py`, `backup.py`, `restore.py`.

**Ngoài phạm vi:**
- Lỗi của chính Keycloak, ONLYOFFICE, PostgreSQL, RustFS, ClamAV…: báo cho dự án đó. Nếu Desktiny cấu hình sai thành
  phần đó, đó vẫn là lỗi của chúng tôi.
- Rủi ro đã ghi của cấu hình dev: HTTP không TLS, Keycloak `start-dev`, `COOKIE_SECURE=false`.
- Plugin mẫu và máy chủ plugin của repo
  [Desktiny Expansion Pack](https://github.com/Dking2007/Desktiny_expansion_pack): báo ở repo đó.

## Công bố

Chúng tôi sửa trong advisory riêng, phát hành bản vá, rồi công bố advisory và ghi vào [CHANGELOG.md](CHANGELOG.md).
Người báo được ghi công nếu đồng ý.

## Chuỗi cung ứng

- Phụ thuộc ghim phiên bản trong `requirements.lock` và `package-lock.json`; image dịch vụ ghim tag, không dùng
  `latest`.
- CI ([`ci.yml`](.github/workflows/ci.yml)) chạy test, kiểm header SPDX, `reuse lint`, kiểm `THIRD_PARTY.md` khớp
  lockfile và quét kho tìm secret (`scripts/audit_repo.mjs`).
- Release kèm `SHA256SUMS`; từ bản 3.2.0 kèm SBOM CycloneDX (`sbom-*.cdx.json`). Kiểm bằng `sha256sum -c SHA256SUMS`.

## Cơ chế bảo vệ và giới hạn đã biết

Xác thực hai lớp (TOTP), quét mã độc ClamAV (tùy chọn), cảnh báo dữ liệu cá nhân trong tệp, kiểm quyền và nhật ký
kiểm toán chuỗi băm: [docs/security.md](docs/security.md).

Giới hạn đã biết: chưa có mTLS giữa các dịch vụ; MFA mới bắt buộc cho một tài khoản demo; ClamAV mặc định tắt và không
quét lại tệp đã lưu; chuỗi băm không chống được người ghi lại toàn bộ bảng; token đã phát sống tới khi hết hạn. Xem
thêm mục Giới hạn trong [README](README.md#giới-hạn).

## Không commit bí mật

`.env` và `infra/identity/generated/` bị `.gitignore` loại trừ. Nếu lỡ commit khóa hay mật khẩu, hãy đổi (rotate)
ngay rồi báo theo mục *Cách báo*.
