# So sánh Desktiny (DXOS V2) với PSA-OVNCR/dxos (DX-OS Trust Core)

Ngày: 30/10/2026. Nguồn bên PSA: README, ARCHITECTURE.md, BUILD.md, `docs/acceptance.md`,
`docs/legal-mapping.md` trên nhánh `main` và danh sách "Việc còn lại" của họ (ngày 23/10).
**Chưa đọc mã nguồn của họ**; mọi nhận xét về PSA là theo tài liệu họ tự viết, chưa chạy lại.
Nhận xét về Desktiny dựa trên mã và tài liệu trong kho này.

## 1. Hai dự án giải hai bài toán khác nhau

| | Desktiny | PSA Trust Core |
|---|---|---|
| Trọng tâm | Văn phòng số dùng được ngay: giao việc, chat, bảng tin, hồ sơ/phê duyệt, Drive, tự động hóa kéo-thả | Lõi tin cậy không giao diện nghiệp vụ: cách ly file, niêm phong, sổ cái Merkle, xác minh công khai |
| Ứng dụng mẫu | 1 ứng dụng lớn (≈13k dòng frontend, ≈8k dòng Workspace API) | 2 app mẫu nhỏ (hồ sơ số, chứng nhận số) + portal xác minh |
| Hạ tầng | 11 container: Keycloak, Postgres, RustFS, Valkey, Nginx, ONLYOFFICE tùy chọn | Keycloak, APISIX, Postgres, SeaweedFS, Flowable, ClamAV, OpenBao, Caddy; cần 16 GB (p16) hoặc ≈5 GB đỉnh (p8) |
| Thông điệp | "Dùng được" | "Kiểm chứng được" |

## 2. Đánh giá công tâm

### Desktiny mạnh hơn
- **Sản phẩm**: phạm vi chức năng và UX rộng hơn hẳn (Ctrl+K, Kanban, ủy quyền phê duyệt, canvas tự động hóa, xem PDF/video trong app, chế độ tối, mobile).
- **Gọn và chạy được**: ít thành phần hơn, dễ cài trên máy 8 GB; Playwright E2E có đăng nhập Keycloak thật đã chạy.
- **Đóng góp cộng đồng thật**: PR Keycloak, PR ONLYOFFICE (plugin Nghị định 30/2020), gói `dx-flowkit` tách độc lập. PSA không ghi điều này.
- **Tuân thủ giấy phép**: SPDX 100% tệp, REUSE, THIRD_PARTY sinh tự động và CI kiểm khớp lockfile.
- **Cách ly dữ liệu giữa hai tầng** (DB riêng, không SQL xuyên tầng, test chặn import vòng) tốt, tương đương PSA ở mức nguyên tắc.

### PSA mạnh hơn
- **Chiều sâu bảo mật có thể chứng minh**: 5 bất biến, 8 chính sách sàn, mô hình đe dọa X1–X4 nói rõ cái gì *không* được bảo vệ.
- **Ma trận nghiệm thu AT-01…AT-28** gắn từng dòng với tên test cụ thể, và một test kiểm chính ma trận đó (không dòng nào bịa).
- **Vận hành**: 9 mạng Docker tách biệt có `make netcheck`; `deploy.sh` chỉ nhận tag ký, tự quay lui; sao lưu mã hóa + bài diễn tập khôi phục; SBOM CycloneDX; image ghim digest.
- **Quét mã độc thật** (ClamAV, file chỉ dùng được khi CLEAN). Desktiny hiện ghi rõ "chưa có quét antivirus".
- **Audit chống sửa** (sổ cái Merkle, neo ra repo công khai). Desktiny trước đây chỉ có bảng audit thường.
- **Kỷ luật trung thực trong tài liệu**: phân biệt cái đã chạy với cái chưa, kể cả tuyên bố giới hạn của "niêm phong" so với chữ ký số.

### Điểm yếu của PSA (theo chính tài liệu của họ)
- Phần lớn mục "chạy thật" (VPS, OpenBao 3-of-5, witness độc lập, AT-18/21/23/26) còn chờ; danh sách việc ngày 23/10 còn rất nhiều bước thủ công trước hạn 06/12.
- Độ phức tạp cao so với quỹ thời gian; sản phẩm người dùng thấy được là hẹp.
- Có mâu thuẫn phiên bản: BUILD.md nói `git checkout v1.0.0 # bản nộp` nhưng README mới ở v0.9.0 chưa gắn tag.
- Tuyên bố tự đánh giá chưa được kiểm độc lập; tôi cũng chưa chạy lại.

### Điểm yếu của Desktiny cần nhìn thẳng
- Lịch sử Git **một tác giả**, chưa có Pull Request nào (ảnh hưởng tiêu chí quản lý mã nguồn).
- ONLYOFFICE thật, backup/restore, `make up` từ đúng commit, ScanCode chưa kiểm.
- Compose chỉ là cấu hình dev (HTTP, `start-dev`), một mạng `dx` chung cho mọi dịch vụ.
- Không quét mã độc; trước thay đổi này audit không chống sửa.
- Chưa có ma trận nghiệm thu có test kiểm tra tự động; `docs/acceptance.md` là văn bản.

## 3. Ý tưởng đáng lấy, xếp theo giá trị/công sức

| # | Ý tưởng (nguồn PSA) | Vì sao hợp Desktiny | Công sức | Trạng thái |
|---|---|---|---|---|
| 1 | Chuỗi băm cho audit (I4) | Lấp đúng giới hạn đã tự ghi trong `docs/security.md`; không cần thêm dịch vụ | Nhỏ | **Đã làm** (mục 4) |
| 2 | Quét ClamAV khi tải lên, file `PENDING → CLEAN/INFECTED` (I2) | Chat/bảng tin/hồ sơ nhận file từ người dùng; hiện không quét | Vừa: thêm service `clamav`, bước quét trong Core worker, trạng thái file, UI báo "đang quét/bị cách ly" | Đề xuất |
| 3 | Ma trận nghiệm thu có test kiểm tra (`test_at_matrix`) | Biến `acceptance.md` từ văn bản thành thứ CI kiểm; hợp tinh thần "không tuyên bố quá mức" | Nhỏ | Đề xuất |
| 4 | Tách mạng Docker (edge / app / data) + kiểm bằng script | Hiện một mạng `dx`; DB, S3, Keycloak cùng mạng với web | Nhỏ–vừa | Đề xuất |
| 5 | Bảng mô hình đe dọa "ai làm được gì, ta phát hiện bằng gì, không bảo vệ gì" | Chỉ là tài liệu, tăng độ tin cậy của `docs/security.md` | Nhỏ | Đề xuất |
| 6 | SBOM CycloneDX trong Release, ký tag | Release hiện có `SHA256SUMS`; thêm SBOM là một bước CI | Nhỏ | Đề xuất |
| 7 | Neo `head` của chuỗi audit ra ngoài (repo công khai hoặc thư mục chỉ-ghi) | Hoàn thiện mục 1 để chống cả người sửa toàn bộ DB | Vừa | Đề xuất |

**Không nên sao chép**: OpenBao, APISIX, Flowable, Merkle/RFC 6962 đầy đủ, witness độc lập và
`legal-mapping.md`. Chúng làm tăng gấp đôi hạ tầng và công kiểm thử trong khi còn dưới 6 tuần,
và Desktiny không đặt mục tiêu "bằng chứng pháp lý". Chuỗi băm đơn giản đã đủ cho một văn phòng số một tổ chức.

## 4. Đã hiện thực hóa: chuỗi băm audit

- `services/core-api/src/dx_core/audit_chain.py`: mỗi dòng audit mới có `seq`, `prev_hash`, `entry_hash` (SHA-256 trên JSON chuẩn hóa của nội dung + hash dòng trước), theo từng ứng dụng.
- `GET /core/v1/audit-logs/verify` (quản trị): trả `ok`, số dòng đã kiểm, `head`, và dòng đầu tiên hỏng với lý do (`content_modified`, `prev_hash_mismatch`, `missing_or_reordered`).
- Migration `core_0003`: thêm cột, chỉ mục duy nhất `(application, seq)`; trên PostgreSQL thêm trigger chặn `UPDATE`/`DELETE`.
- Dòng cũ không có hash được đếm riêng là `unchained`, không bao giờ báo hợp lệ.
- Kiểm: 5 test mới (sửa dòng, xóa dòng, dòng cũ, tách theo ứng dụng); toàn bộ 53 test Core đạt, `ruff check` sạch; contract OpenAPI và kiểu TypeScript đã sinh lại. Migration + trigger đã chạy thật trên PostgreSQL 17 (UPDATE và DELETE bị chặn).

**Giới hạn đã biết**: chưa kiểm tải đồng thời nhiều ghi cùng lúc trên PostgreSQL (dùng `FOR UPDATE` và chỉ mục duy nhất làm lưới an toàn; nếu va chạm, một request sẽ lỗi thay vì ghi sai). Người có quyền ghi lại cả bảng và tính lại hash vẫn qua mặt được cho tới khi có mục 7. Audit của Workspace (`workspace-api`) chưa có chuỗi.

## 5. Đề xuất thứ tự tiếp theo (đến 06/12)

1. Mục 2 (ClamAV) — lấp khoảng trống bảo mật lớn nhất mà tài liệu đã tự nhận.
2. Mục 3 + 5 — rẻ, tăng độ tin cậy của hồ sơ nộp.
3. Việc không phải mã nhưng ảnh hưởng điểm hơn mọi mục trên: mỗi thành viên commit/PR bằng tài khoản riêng, mở PR thật, chạy `make up` từ đúng commit, gắn tag phát hành mới.
