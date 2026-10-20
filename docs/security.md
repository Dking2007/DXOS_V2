# Bảo mật và giới hạn triển khai

## Cấu hình dev không phải production

Compose chỉ bind gateway vào `127.0.0.1`. Các service, DB, RustFS và broker không có
host port; không mở chúng bằng cách thêm `ports` tùy tiện. Profile dev dùng HTTP,
Keycloak `start-dev` và `COOKIE_SECURE=false`; chỉ dùng trên máy cá nhân/lab.

Trước pilot/prod: TLS và cookie Secure, Keycloak production mode/MFA, giới hạn console,
credential riêng từng môi trường, network/egress policy, tài nguyên CPU/RAM, backup
có mã hóa, kiểm tra dependency/image và threat model. Không đưa Compose dev lên
Internet rồi coi là hardening đầy đủ.

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
Kiểm định dạng file/giới hạn giải nén không phải quét malware; hiện chưa tích hợp
antivirus hoặc sandbox scan. Audit qua API là lịch sử ứng dụng, không phải bằng
chứng storage bất biến/chống sửa.
Không log Authorization/cookie/secret hoặc toàn bộ nội dung tài liệu.
