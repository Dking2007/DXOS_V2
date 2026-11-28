# Bảo mật và giới hạn triển khai

## Cấu hình dev không phải production

Compose chỉ bind gateway vào `127.0.0.1`. Các service, DB, RustFS và broker không có
host port; không mở chúng bằng cách thêm `ports` tùy tiện. Profile dev dùng HTTP,
Keycloak `start-dev` và `COOKIE_SECURE=false`; chỉ dùng trên máy cá nhân/lab.

Trước pilot/prod: TLS và cookie Secure, Keycloak production mode/MFA, giới hạn console,
credential riêng từng môi trường, network/egress policy, tài nguyên CPU/RAM, backup
có mã hóa, kiểm tra dependency/image và threat model. Không đưa Compose dev lên
Internet rồi coi là hardening đầy đủ.

## Xác thực hai lớp (MFA)

Bootstrap đặt required action `CONFIGURE_TOTP` cho đúng một tài khoản demo,
`lanh-dao-mfa` (Phó giám đốc, vai trò `director`). Lần đăng nhập đầu Keycloak bắt quét
mã QR bằng ứng dụng TOTP (6 chữ số, 30 giây — mặc định của Keycloak). Các tài khoản
khác, kể cả `director` mà seed và e2e dùng, không bị bắt MFA để tự động hóa không vỡ.
Chỉ áp dụng cho cài đặt mới; realm đã import không đổi.

Bật OTP cho người khác: Keycloak admin console, realm `dx`, Users, chọn người dùng,
thêm required action "Configure OTP". Muốn bắt mọi người dùng: Authentication,
Required actions, bật "Set as default action" cho "Configure OTP" (chỉ ảnh hưởng người
mới), hoặc thêm điều kiện OTP vào browser flow. Production: bắt MFA cho vai trò lãnh
đạo và quản trị, lưu mã khôi phục, và không dùng tài khoản demo.

## Secret và bootstrap

`python scripts/bootstrap.py` dùng CSPRNG cho mật khẩu/client secret/session/Office
JWT, Fernet key; không dùng mật khẩu demo cố định. Nó chỉ nhận public localhost HTTP
origin và từ chối overwrite. Các file `.env`, `infra/identity/generated/*` chứa
secret, được git-ignore; không đính kèm issue hoặc log. Trên Windows cần bảo vệ
NTFS ACL vì POSIX chmod không đảm bảo quyền đọc tương đương.

Đổi `.env` **không** tự đổi password trong DB volume hoặc realm đã import. Rotation
phải đổi đồng bộ secret ở dịch vụ nguồn, consumer và secret store; kiểm tra trước
khi thu hồi khóa cũ. Realm import không phải configuration reconciliation.

## Kiểm quyền

- Server kiểm issuer/audience/expiry và application namespace; resource default deny.
- Browser mutation phải có CSRF và Origin phù hợp; menu ẩn không thay policy API.
- Grant/ACL áp dụng cả metadata lẫn bytes/version/ticket. Chia sẻ không được vượt
  khả năng ủy quyền. URL/message không tự cấp quyền cho file.
- Ticket có TTL; quyền bị thu hồi không đồng nghĩa mọi URL đã phát lập tức vô hiệu.
  Cần kiểm đường download thực tế và công bố cửa sổ revocation.
- Drive có ACL kế thừa theo thư mục: quyền của file là mức cao nhất trong quyền sở
  hữu, share trực tiếp trên file và share trên bất kỳ thư mục nào trên đường dẫn tới
  gốc. Ghi đồng nghĩa đọc; thư mục trong thùng rác không cấp quyền cho nội dung bên
  dưới. Chỉ chủ sở hữu đổi tên/di chuyển/xóa thư mục và quản lý chia sẻ thư mục, để
  người được chia sẻ quyền ghi không tự rút quyền kế thừa của người khác.
- Sau khi đổi chia sẻ hoặc di chuyển thư mục, grant của Core được tính lại cho cả
  cây con; trong cửa sổ đồng bộ tài liệu trả `409 permissions_syncing` thay vì dùng
  quyền cũ hoặc cấp ticket ở metadata.
- Sao chép tài liệu tạo một file Core mới với resource và quota riêng, nên share của
  bản gốc không tự động sang bản sao: được đọc không đồng nghĩa được phát tán. Người
  sao chép phải giữ quyền đọc bản gốc và quyền ghi thư mục đích. Nhãn là metadata
  riêng của Workspace, không mở rộng hay thu hẹp bất kỳ grant Core nào.
- Token OIDC offline đã phát có thể sống đến expiry (dev access token 5 phút).
  Không tuyên bố khóa tài khoản có tác dụng tức thì trên mọi đường truy cập.
- Nginx `/internal/` trả 404. Service action vẫn phải xác thực/kiểm quyền khi gọi
  qua mạng nội bộ; mạng nội bộ không phải lý do bỏ authorization.

## ONLYOFFICE

Chỉ bật khi cần bằng profile `office`. Giữ logo/notice và kiểm edition/license đúng
artifact. Document Server phải tới được URL file/callback theo cấu hình nội bộ;
trình duyệt phải tới được `/office/`. Cấm truyền user token dài hạn cho editor.

Callback ký JWT, kiểm session/document key. URL save chỉ được tải từ Document
Server allowlist, có giới hạn kích thước/thời gian và redirect. Không ACK lưu thành
công trước khi nội dung đã được lưu bền vững. Nếu đang chỉnh sửa chưa chốt được
version, phải chặn trình hồ sơ/chờ lưu, không âm thầm dùng bản cũ.

Triển khai hiện tại dùng **đóng editor + callback cuối** làm submit barrier, chưa
có force-save barrier. Content ticket Office TTL 8 giờ, gắn session; việc thu hồi
share không bảo đảm editor đang mở mất quyền tức thì. Cần kiểm vòng đời callback,
đóng phiên, cộng tác và cửa sổ thu hồi với Document Server thật trước production.

`ALLOW_PRIVATE_IP_ADDRESS=true` của Document Server chỉ để truy cập API trong mạng
Docker dev; nó không cho người dùng Workspace cấu hình URL tùy ý. Trước production
cần egress firewall và policy riêng cho Document Server.

## Nội dung và audit

JSON Schema validation không thay luật nghiệp vụ. Không eval Python/JavaScript hoặc
SQL tùy ý từ graph/form. File không được dùng tên gốc làm object key/path. Rich text
không thuộc phạm vi đợt đầu; tránh render nội dung không tin cậy với `v-html`.
Kiểm định dạng file/giới hạn giải nén không phải quét malware. Quét mã độc là tùy chọn,
xem mục "Quét mã độc (ClamAV)" bên dưới; sandbox scan chưa có. Audit của Core có chuỗi băm SHA-256 (`GET
/core/v1/audit-logs/verify`) và trigger chặn sửa/xóa trên PostgreSQL: sửa trực tiếp
bằng SQL bị phát hiện. Chuỗi không chống được người ghi lại toàn bộ bảng rồi tính lại mọi
hash; muốn chống điều đó phải lưu `head` ở nơi quản trị DB không sửa được (chưa làm).
Audit của Workspace và các dòng Core ghi trước `core_0003` chưa có chuỗi.
Không log Authorization/cookie/secret hoặc toàn bộ nội dung tài liệu.

## Quét mã độc (ClamAV)

Tùy chọn, mặc định TẮT. Bật bằng profile `security` (chạy `clamav/clamav`, container riêng)
và đặt `CLAMAV_HOST=clamav` trong `.env` (`CLAMAV_PORT` mặc định 3310 nếu dùng Core ngoài Compose):

```bash
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace --profile security up -d
```

Core quét từng tệp (upload và phiên bản mới) sau bước kiểm nội dung, trước khi ghi vào kho.
Phát hiện mã độc trả 422 `malware_detected` và ghi audit `file.malware_detected`.
**Lỗi quét = từ chối**: không kết nối được, hết thời gian hoặc trả lời lạ đều trả 503
`scan_unavailable`, tệp không được lưu. Vì vậy khi đã đặt `CLAMAV_HOST`, upload phụ thuộc
vào ClamAV; clamd phải đặt `StreamMaxLength` lớn hơn `MAX_UPLOAD_BYTES` (compose đặt 64M).

Tài nguyên: clamd nạp toàn bộ cơ sở dữ liệu chữ ký, cần khoảng 1–1.5 GB RAM và vài phút
cập nhật chữ ký lần đầu (xem số đo trong báo cáo kiểm thử). Chỉ quét lúc tải lên; tệp đã
lưu không được quét lại khi chữ ký mới ra.

## Cảnh báo dữ liệu cá nhân trong tệp

Khi xem trước một tệp trong Kho tài liệu, Workspace gọi `GET
/workspace/v1/drive/files/{id}/pii` (thêm `?redacted=true` để lấy văn bản đã che). Route
dùng cùng quyền đọc tệp như tải về, đếm số CCCD, CMND, điện thoại, tài khoản, mã số thuế
và e-mail bằng `dx-piivn`, rồi hiện một cảnh báo không chặn kèm nút "Xem bản đã che".
Giá trị tìm thấy không được ghi log hay lưu; chỉ số lượng và bản đã che được trả về.

Giới hạn: đây là gợi ý, không phải DLP. Chỉ đọc được chữ trong PDF có lớp văn bản, Word,
Excel, PowerPoint và văn bản thuần (ảnh và bản scan không được kiểm tra); mỗi trang bị cắt
ở 6.000 ký tự và tối đa 60 trang; tệp trên 20 MB bỏ qua. CCCD chỉ được kiểm tra cấu trúc,
không có chữ số kiểm tra. Danh sách mã tỉnh trong `dx-piivn` chưa đối chiếu với văn bản
chính thức, nên có thể bỏ sót hoặc báo thừa; số tài khoản và mã số thuế chỉ nhận khi có
từ khoá đứng trước.
