# Đánh giá Desktiny so với năm dự án khác (PSA, OpenDXOS, commune-dxos, FoodSafe-DX-OS, OpenCity)

Ngày: 31/10/2026. Cùng chủ đề DX-OS của OLP PMNM 2026 (riêng OpenCity chưa xác nhận được tên cuộc thi).
Các mục 1-8 chỉ gồm Desktiny, PSA và OpenDXOS. **Mục 9**: commune-dxos. **Mục 10**: FoodSafe-DX-OS và OpenCity.
**Mục 11**: bảng xếp hạng tổng hợp sáu dự án.

**Cách đọc.** Số liệu về hai dự án kia đọc qua trang công khai của GitHub ngày 31/10, chưa clone,
chưa chạy test, chưa đọc log CI. Số test của họ là số họ tự báo. Mục nào "chưa đọc" được ghi rõ ở cuối.
Nhận xét về Desktiny dựa trên mã và tài liệu trong kho này. Xếp hạng (Mạnh / Vừa / Yếu) là nhận định
của tôi theo bằng chứng đã đọc, không phải điểm chấm của BTC.

## 1. Ba dự án là ba hướng khác nhau

| | **Desktiny** (nhóm bạn) | **PSA Trust Core** | **OpenDXOS** |
|---|---|---|---|
| Ý tưởng | Văn phòng số cho cơ quan | Lõi tin cậy: niêm phong, sổ cái, xác minh công khai | "Hệ điều hành" doanh nghiệp thương mại, nhân sự AI có cổng duyệt |
| Miền nghiệp vụ | Hồ sơ, việc, chat, bảng tin, Drive | Hồ sơ số, chứng nhận số | Cửa hàng (demo "NovaCommerce"): kho, thanh toán SePay, CRM, marketing |
| Stack | FastAPI, Vue 3, Keycloak, Postgres, RustFS | FastAPI, Vue 3, Keycloak, APISIX, OpenBao, Flowable, SeaweedFS, ClamAV | Express 5 + React, FastAPI + Temporal, Keycloak, MinIO, ClamAV |
| AI | Chưa có (hoãn) | Không | Có: 10 danh tính agent, OpenRouter, đo chi phí token |
| Mã (ước lượng) | ≈25k dòng (web ≈14k, API ≈10k, gói ≈1k) | Chưa đo | Chưa đo |

## 2. Bảng đánh giá

| Tiêu chí | Desktiny | PSA | OpenDXOS |
|---|---|---|---|
| **Phạm vi sản phẩm người dùng thấy** | **Mạnh**: giao việc, chat, bảng tin, Drive ACL, ủy quyền, canvas tự động hóa, Ctrl+K, mobile | Vừa: 2 app mẫu nhỏ + cổng xác minh + trang quản trị | **Mạnh**: console, storefront 3D, CRM, marketing, workflow studio |
| **Chiều sâu bảo mật** | Vừa: BFF cookie, PKCE, ACL default-deny, CSRF; trước nay audit không chống sửa, không quét mã độc | **Mạnh**: 5 bất biến, Merkle RFC 6962, STH ký ngoài, niêm phong, mô hình đe dọa X1–X4 | Vừa: mô hình quyền rõ, agent tách danh tính, ClamAV fail-closed; nhưng có điểm yếu cấu hình (mục 4) |
| **Bằng chứng kiểm thử** | Vừa: 108 pytest trên PostgreSQL thật (27/10), 45 vitest, 3 E2E có đăng nhập | **Mạnh** (tự báo): >2200 test + 500 integration, ma trận AT-01…28; infra/e2e chưa vào CI | Vừa (tự báo): hàng nghìn test, kịch bản đồng thời, kill worker; nhưng CI hiện đỏ và không chạy test Python/integration |
| **CI** | Vừa: lint, test, contract diff, REUSE, kiểm giấy phép | **Mạnh**: 8 job, action ghim SHA, gitleaks, license scan, integration, nightly ClamAV thật | Yếu: 2 job; 6/6 lần chạy nhìn thấy đều lỗi |
| **Tuân thủ giấy phép (PoF)** | **Mạnh**: SPDX mọi tệp, REUSE, THIRD_PARTY sinh tự động đối chiếu lockfile | **Mạnh**: REUSE lint, license scan, SBOM trong release | Yếu: kiểm SPDX chỉ 4 loại tệp, không REUSE/SBOM; ghi tên bản quyền không thống nhất |
| **Phát hành** | Vừa: tag v0.1.0, v0.2.0, v0.2.1 + `SHA256SUMS` | **Mạnh**: tag v0.1.0–v0.3.0, release có SBOM, digest image; v0.9.0/v1.0.0 chưa gắn | Yếu: không release, không tag, README nói v0.1.0 |
| **Quản lý mã nguồn** | Yếu: một tác giả, chưa có PR | Vừa: 178 commit, 3 thành viên; số PR/issue công khai = 0 | Yếu: 5 commit trong một ngày, một tác giả, 0 PR |
| **Tài liệu và độ trung thực** | **Mạnh**: tách rõ "đã chạy" và "chưa chạy" | **Mạnh** nhưng có tài liệu cũ mâu thuẫn nhau | Vừa: nhiều tài liệu tốt, README lệch mã (PostgreSQL 16 vs 18, Redis không có thật), tự khen quá mức |
| **Hạ tầng triển khai** | Yếu: Compose dev, một mạng chung | **Mạnh**: 9 mạng, `deploy.sh` tag ký + tự quay lui, backup mã hóa + diễn tập | **Mạnh**: compose production, mạng `internal`, `read_only`, `cap_drop`, mTLS Temporal, biến bắt buộc fail-fast |
| **Tài nguyên** | **Mạnh**: chạy máy 8 GB | Yếu: p16 cần 16 GB, p8 đỉnh ≈5 GB | Yếu: ≈20 dịch vụ gồm Temporal, Keycloak, ClamAV |
| **Đóng góp cộng đồng** | **Mạnh**: 2 PR (Keycloak, ONLYOFFICE chờ xét), gói `dx-flowkit` | Không thấy | Không thấy |
| **Tính khác biệt** | Trình thiết kế luồng kéo-thả, plugin thể thức Nghị định 30 | Niêm phong + xác minh công khai không cần tin quản trị viên | Cổng duyệt của người cho AI, mỗi agent một danh tính |

## 3. Điều tôi thấy trong mã của PSA mà tài liệu của họ không nói to

Đây là chỗ Desktiny có thể làm tốt hơn, không phải để chê.

- **Dò dữ liệu cá nhân chỉ kiểm độ dài, tiền tố và từ khóa.** CCCD chỉ cần 3 số đầu trong 1–96, không kiểm chữ số thế kỷ hay năm sinh. Số 12 chữ số ngẫu nhiên có khoảng 10% bị báo là CCCD.
- **`verify_log` không tính lại gốc Merkle**, chỉ kiểm hash từng lá và `idx` liên tục. Xóa các dòng cuối vẫn qua. Họ ghi rõ rằng phải đối chiếu với STH đã ký.
- **Gói bằng chứng mang sẵn khóa công khai của STH lấy từ máy chủ**, nên người kiểm ngoại tuyến phải ghim khóa vào repo neo mới thật sự độc lập.
- **Repo neo chính chưa tạo** (mới dùng repo lab), **witness độc lập chưa chạy**. Hai thứ này là phần làm nên giá trị của cả thiết kế.
- Số liệu và tài liệu lệch nhau ở vài chỗ: số loại sự kiện (18 so với 22), tiến độ gắn tag.

## 4. Điều đáng chú ý ở OpenDXOS

Điểm tốt:
- **Cổng duyệt của người** là loại nút riêng trong sơ đồ luồng (`approval_gate`), ngưỡng tự duyệt đọc từ bản đã xuất bản.
- **Mỗi agent một danh tính** với token theo audience; tiến trình nhận yêu cầu và tiến trình thực thi tách nhau.
- **Compose production** chặt: chỉ Caddy mở cổng, mạng `internal`, `read_only`, `cap_drop: ALL`, `${VAR:?}` bắt buộc.
- **Script kiểm kho** chặn `:latest`, `.env` bị theo dõi, bản dump bị theo dõi.
- **Kiểm thử đồng thời** (20 lần thanh toán cùng lúc trên 10 đơn vị tồn) và kill worker.
- `AGENTS.md`: luật rõ cho trợ lý AI khi viết mã trong kho.

Điểm cần cảnh giác (đừng học theo):
- CI đỏ ở mọi lần chạy nhìn thấy; test Python và integration không nằm trong CI.
- Kho có dữ liệu cá nhân thật trong CHANGELOG và dữ liệu seed, trong khi SECURITY.md cấm điều này.
- Thời hạn token và phiên 1 năm trong realm dev; Postgres dev dùng `trust` và mở cổng; Temporal `ALLOW_NO_AUTH`.
- README lệch mã (phiên bản PostgreSQL/Keycloak/FastAPI, Redis không tồn tại), ghi "Battle-tested" khi không có release.
- Lịch sử công khai chỉ 5 commit trong khi tài liệu kể về nhiều PR.
- Có điểm cần xem lại về giấy phép: CHANGELOG nói giao diện luồng "adopted" thiết kế của n8n, trong khi NOTICE nói mọi thứ đều theo giấy phép OSI. Tôi chưa kiểm tra giấy phép n8n.

Vì vậy về độ tin cậy, tôi không coi OpenDXOS là đối thủ trực tiếp về PoF; điều đáng lấy là các ý kiến trúc ở trên.

## 4b. Luận điểm "đột phá" cho Desktiny

Không dự án nào có cả bốn điều dưới đây cùng lúc:

1. **Tự động hóa có người duyệt**: luồng của Desktiny chạy việc thật (tạo việc, gửi thông báo, gọi webhook); thêm nút "chờ duyệt" kiểu OpenDXOS thì mọi hành động có tác động ra ngoài phải qua người.
2. **Bằng chứng chống sửa** cho mọi quyết định và lượt chạy (chuỗi băm kiểu PSA, nhưng không cần OpenBao hay GitHub neo).
3. **Bảo vệ dữ liệu cá nhân Việt Nam có kiểm cấu trúc**, tốt hơn heuristic của PSA.
4. **Chạy được trên laptop 8 GB**, ít dịch vụ.

Câu chuyện: *văn phòng số tự động hóa mà mọi việc đều có người duyệt, có dấu vết không sửa được, và biết che dữ liệu cá nhân người Việt, trên một máy tính thường.*

## 5. Ý tưởng khai thác

| # | Ý tưởng | Lấy từ | Trạng thái |
|---|---|---|---|
| 1 | Chuỗi băm audit + endpoint xác minh + trigger chặn sửa | PSA I4 | **Đã làm** (Core, nhánh này) |
| 2 | **Dò dữ liệu cá nhân Việt Nam có kiểm cấu trúc** (`packages/pii-vn`) | PSA S1, làm chặt hơn | **Đã làm** (gói độc lập, 12 test) |
| 3 | Gắn #2 vào điểm tải lên, chat, bảng tin: cảnh báo "văn bản có CCCD/STK" trước khi gửi | PSA S1 | Đề xuất, cần nối vào Workspace |
| 4 | Nút "chờ duyệt" trong canvas tự động hóa, ngưỡng đọc từ bản đã xuất bản | OpenDXOS | Đề xuất |
| 5 | Mở rộng chuỗi băm sang audit của Workspace (hiện chỉ Core có) | PSA I4 | Đề xuất |
| 6 | Quét ClamAV khi tải file, `PENDING → CLEAN/INFECTED` | PSA I2, OpenDXOS | Đề xuất |
| 7 | Compose production: mạng `internal`, `read_only`, `cap_drop`, `${VAR:?}` | OpenDXOS | Đề xuất |
| 8 | Script kiểm kho: cấm `:latest`, `.env`/dump bị theo dõi | OpenDXOS | Đề xuất, rẻ |
| 9 | Test đồng thời cho phê duyệt và ghi audit trên PostgreSQL | OpenDXOS | Đề xuất |
| 10 | Ma trận nghiệm thu có test kiểm chính nó | PSA | Đề xuất |
| 11 | SBOM CycloneDX trong release, ghim digest image | PSA | Đề xuất |

**Không lấy**: Temporal, OpenBao, APISIX, Merkle đầy đủ, witness, OpenRouter/agent LLM. Quá nặng so với 5 tuần còn lại.

## 6. Đã làm trong đợt này

- `packages/pii-vn` (`dx-piivn` 0.1.0): `find_pii`, `redact`, `mask`. CCCD kiểm mã tỉnh, chữ số thế kỷ và năm sinh không ở tương lai; số điện thoại phải có đầu số di động đang dùng; STK và MST chỉ báo khi có từ khóa. Trên 100.000 số 12 chữ số ngẫu nhiên, test đảm bảo dưới 3% qua được (tính lý thuyết ≈1,6%), so với ≈10% của kiểm tiền tố đơn giản. 12 test đạt, `ruff` sạch. **Chưa nối vào Workspace.**
- Chuỗi băm audit của Core (xem `docs/so-sanh-psa-dxos.md` mục 4).

**Chưa kiểm**: danh sách mã tỉnh và đầu số di động trong `dx-piivn` tôi viết từ trí nhớ về Thông tư 07/2016/TT-BCA và danh mục nhà mạng, chưa đối chiếu văn bản chính thức; cần một thành viên đối chiếu trước khi nêu trong hồ sơ.

## 7. Thứ tự đề xuất đến 06/12

1. Nối `dx-piivn` vào Workspace (#3) rồi quay video demo: tải văn bản có CCCD, hệ thống cảnh báo và đề nghị che.
2. Nút "chờ duyệt" trong tự động hóa (#4) và chuỗi băm cho audit Workspace (#5): hoàn thiện câu chuyện đột phá.
3. ClamAV (#6), compose production (#7), script kiểm kho (#8): lấp khoảng trống mà cả hai đội kia đều đã có.
4. Việc không phải mã: mỗi thành viên commit và mở PR bằng tài khoản riêng, chạy `make up` từ đúng commit, gắn tag mới.

## 8. Chưa đọc / chưa kiểm

- PSA: mã `registry/`, `guards.py`, `records/`, `witness/`, `deploy/`, nội dung test; log CI; số liệu đóng góp.
- OpenDXOS: mã nguồn `apps/` và `services/`, phần sau của CHANGELOG (đọc dạng tóm tắt), `docs/` phần lớn, nhánh `develop`, log CI.
- Cả hai: số test là số tự báo; tôi chưa chạy.

## 9. Bổ sung: commune-dxos/commune-dxos ("Commune DX-OS", đội DTU_DZ_2)

Đọc qua trang công khai ngày 31/10/2026, chưa clone, chưa chạy. Mã nguồn của họ gần như chưa đọc (chỉ cây thư mục,
tệp cấu hình và tài liệu); các số test là số họ tự báo.

**Là gì.** "Hệ điều hành" cho bộ phận một cửa cấp xã: người dân nộp một lần, nhận mã tra cứu; cán bộ thấy hồ sơ đang ở
đâu và còn bao lâu hạn. Ba tầng: `nen-tang/` (lõi không nghiệp vụ), `mot-cua/` (động cơ một cửa + cổng công dân/cán bộ
React), `thu-tuc/<mã>/` (mỗi thủ tục một thư mục: YAML, BPMN, JSON Schema giấy tờ, dữ liệu mẫu giả). Có 4 thủ tục: khai
sinh, bản sao trích lục, đăng ký kết hôn, hòa giải đất đai. Stack: Keycloak, APISIX, PostgREST, PostgreSQL 17 (pgAudit,
pgvector), Flowable, Garage, ClamAV, OpenBao, RabbitMQ, step-ca, Gotenberg, Meilisearch, Ollama, Superset.

| Tiêu chí | Desktiny | commune-dxos |
|---|---|---|
| Phát hành | 3 tag | **Mạnh**: 9 release (v0.0.1 đến v0.8.0) trong 10 ngày, changelog sinh bằng git-cliff |
| Quy trình Git | 0 PR, một tác giả | **Mạnh**: 65 PR đã đóng, nhánh `develop`, kiểm quy ước commit, gắn nhãn tự động. Vẫn gần như một tác giả |
| CI | Vừa | **Mạnh**: 365 lần chạy, 25 lần gần nhất đều xanh; 8 job gồm test SQL trên PostgreSQL thật. Test smoke 1176/1176 là số tự báo, không nằm trong CI |
| Giấy phép | Apache-2.0, SPDX + REUSE | GPL-3.0-or-later, SPDX + REUSE 100% (tự báo); `DEPENDENCIES.md` có cột tương thích GPL và bảng "không dùng" kèm lý do |
| Sản phẩm | Văn phòng số tổng quát | Hẹp nhưng sâu: thủ tục một cửa, tra cứu công khai, khay việc cán bộ, OCR điền sẵn, trợ lý RAG, PDF ký PAdES, dữ liệu mở CC-BY |
| Dữ liệu cá nhân | Chưa có bộ dò | Chủ yếu là giảm thiểu: DB không lưu CCCD, ngày sinh, địa chỉ; tài liệu nằm ở kho tệp |
| Phân quyền | ACL kế thừa theo thư mục | Role Keycloak → role PostgreSQL + RLS bắt buộc trên mọi bảng; script thử 27 cặp danh tính/đường dẫn bằng đăng nhập thật |
| Audit chống sửa | Chuỗi băm (mới làm) | Chuỗi SHA-256 + pgAudit. Tài liệu tự mâu thuẫn: có chỗ nói chặn cả superuser, có chỗ nói superuser tắt được trigger |
| Triển khai | Compose dev | Compose dev, `start-dev` qua HTTP, mở cổng mọi giao diện, khóa mở OpenBao lưu cùng máy theo mặc định (ghi "chỉ dùng cho máy dev"). VPS/HTTPS chưa làm |
| Tài nguyên | 8 GB | Yếu: cần ≈4 GB RAM chỉ cho lõi, thêm AI/BI thì nặng hơn nhiều |
| Rủi ro | | Không có SECURITY.md, dependabot, CODEOWNERS; thông báo cho công dân mới giả lập; vài chỗ README mâu thuẫn mã (Tầng 2 "chỉ gọi qua APISIX" nhưng compose nối thẳng PostgREST/Flowable) |

**Đánh giá.** Đây là đối thủ mạnh nhất về **quy trình và hồ sơ PoF**: tần suất phát hành, PR, CI xanh, tài liệu
phụ thuộc. Về chiều sâu bảo mật vận hành, PSA vẫn trội hơn; về độ rộng sản phẩm, Desktiny trội hơn. Họ cho thấy
các tiêu chí 1, 3 và 6 của PoF (quản lý mã nguồn, phát hành, tài liệu) có thể đạt rất cao nếu làm đều từ tuần đầu.
Chuỗi băm audit của Desktiny không còn là điểm độc nhất sau khi họ cũng có; cái còn độc nhất là chuỗi băm cộng với việc
nói đúng giới hạn của nó.

**Ý tưởng đáng lấy:**

| # | Ý tưởng | Công sức | Trạng thái |
|---|---|---|---|
| 12 | Phát hành đều: tag nhỏ hằng tuần, changelog sinh tự động | Nhỏ | Đề xuất (việc của nhóm, không phải mã) |
| 13 | Nhánh `develop`, mọi thay đổi qua PR, kiểm quy ước commit | Nhỏ | Đề xuất |
| 14 | `DEPENDENCIES.md` có cột tương thích giấy phép và bảng "không dùng, vì sao" | Nhỏ | Đề xuất |
| 15 | `make check` ánh xạ 1-1 với job CI, ghi trong CONTRIBUTING | Nhỏ | Đề xuất |
| 16 | Ma trận phân quyền được thử bằng đăng nhập thật (vai trò × đường dẫn) | Vừa | Đề xuất |
| 17 | Sổ migration ghi hash SHA-256, migration đã áp dụng bị sửa thì dừng | Vừa | Đề xuất |
| 18 | Kiểm hai lớp: trình duyệt rồi máy chủ kiểm lại cùng một schema | Có sẵn một phần (form) | Xem lại |
| 19 | Dữ liệu mở sinh từ gói nghiệp vụ, kiểm lệch trong CI | Vừa | Đề xuất |
| 20 | Script kiểm kho (cấm `:latest`, `.env`/dump bị theo dõi) | Nhỏ | **Đã làm** (`scripts/audit_repo.mjs`, chạy trong CI) |

**Không lấy**: OCR/RAG/Ollama, pgvector, step-ca và PAdES, Superset, RabbitMQ. Nặng và lệch hướng văn phòng số.

**Chưa đọc**: phần sau của CHANGELOG và kiến trúc (đọc dạng tóm tắt), nửa dưới của docker-compose, mã Python/SQL, test,
log CI, `docs/en/`, các thư mục `scripts/`, `du-lieu-mo/`.

## 10. Bổ sung: FoodSafe-DX-OS và HouHackathon-CHP/opencity-frontend

Đọc qua trang công khai ngày 31/10/2026, chưa clone, chưa chạy. Chưa đọc: mã giao diện FoodSafe (`app.js`, `graph.js`),
một số router, ~20 tài liệu; với OpenCity chưa đọc mã `src/pages`, `src/components`, repo `dxos-core`, `opencity-backend`
(chỉ README) và `opencity-mobile`.

### 10.1 FoodSafe-DX-OS (an toàn thực phẩm bếp ăn tập thể)

- **Là gì**: lõi quy tắc "poka-yoke" cho bếp ăn trường học và khu công nghiệp: kiểm thực 3 bước (QĐ 1246/QĐ-BYT), nhiệt độ
  nhập hàng và nấu chín, tủ lưu mẫu 24 giờ, truy vết ngộ độc, tra cứu quy định cục bộ. FastAPI + PostgreSQL + giao diện HTML thuần.
- **Mạnh**: logic chặn vi phạm viết thành hàm thuần tách khỏi router; lỗi trả về dạng có cấu trúc (`error_code`,
  `standard_ref`, `action_required`, `blocked_operation`, HTTP 422); test đặt tên theo quy tắc; đồng hồ 24 giờ tính ở máy chủ;
  có cơ chế cho người duyệt ghi đè; dependency ghim phiên bản; Apache-2.0 + SPDX.
- **Yếu (đã đọc trong mã)**: không có đăng nhập hay phân quyền; `POST /db/seed?force=true` xóa và nạp lại dữ liệu mà không
  cần xác thực và nginx chuyển tiếp ra cổng công khai; mật khẩu duyệt ghi đè là một chuỗi cố định trong mã; CORS `*` kèm
  credentials; Postgres mở cổng với mật khẩu mặc định; container chạy root; không CI; không CHANGELOG; chỉ 1 tag, 0 release,
  0 issue, 0 PR dù commit nhắc "Merge pull request #1-#8".
- **Tài liệu nói hơn mã**: tuyên bố audit "bất biến, không xóa được" nhưng không có bảng audit (endpoint trả
  `LOGGED_SECURELY` mà không ghi gì); "100% offline" nhưng giao diện tải Tailwind, FontAwesome, Google Fonts từ CDN;
  "build nhiều tầng" nhưng Dockerfile một tầng; số liệu hiệu năng và "16/16, 50/50" là nhãn tĩnh, không phải CI.
- **Mâu thuẫn nội bộ**: lô hàng đã bị từ chối có thể được duyệt lại ở lần kiểm sau; ngưỡng nấu chín 70 °C trên giao diện,
  75 °C trong mã; tủ lưu mẫu không kiểm nhiệt độ hay khối lượng như tài liệu nói.
- **Đánh giá**: nhỏ và có miền nghiệp vụ rõ, nhưng kém Desktiny ở gần như mọi tiêu chí vận hành, bảo mật và PoF. Không phải
  đối thủ về độ hoàn thiện; đáng lấy một vài ý thiết kế (mục 10.3).

### 10.2 OpenCity (HouHackathon-CHP): cổng dịch vụ công dân

- **Là gì**: nhóm có 4 repo: `dxos-core` (lõi), `opencity-backend`, `opencity-frontend`, `opencity-mobile` (Android). Frontend
  là cổng dịch vụ công dân, "lấy cảm hứng từ iHanoi", ghi rõ không phải dịch vụ chính thức. Danh mục 60 dịch vụ, mới 4
  hoạt động (báo cáo hiện trường, tin và cảnh báo, khảo sát); 47 cần tích hợp, 9 dự kiến. React 19, Vite, Keycloak PKCE.
  **Chưa xác nhận đây có phải bài thi OLP PMNM hay không**: trang đã đọc không nhắc tên cuộc thi.
- **Mạnh**: danh mục dịch vụ là một tệp JSON có kiểm tra bằng script trong CI (ID duy nhất, chỉ HTTPS, trạng thái ba mức);
  cổng kiểm giấy phép trong CI kèm nói rõ giới hạn; tài liệu "hợp đồng dịch vụ" nêu ranh giới giữa các tầng; README nói thẳng
  những gì chưa làm; ứng dụng di động riêng; 15 lần chạy CI đều xanh.
- **Yếu**: chưa có test; không có release hay tag; 6 commit trên `main` do một tài khoản; nhánh `dev` đi trước `main` nên
  README và `license-audit` trên `main` lệch với `dev` (kiểm giấy phép nói không nhúng bản đồ, `dev` thì nhúng); thiếu CHANGELOG,
  CONTRIBUTING, SECURITY, NOTICE; LICENSE không ghi chủ bản quyền; tự nhận chưa có quét mã độc, chưa giới hạn tần suất.
  Giao diện đọc vai trò từ JWT ở trình duyệt chỉ để ẩn/hiện, còn quyết định thật ở backend (chưa đọc backend).
- **Đánh giá**: sản phẩm mỏng nhưng cấu trúc gọn; điểm chính là "danh mục dịch vụ có kiểm tra" và tách nhiều repo. Về
  tuân thủ PoF thì còn thiếu release, tài liệu và test.

### 10.3 Ý tưởng đáng lấy từ hai repo này

| # | Ý tưởng | Nguồn | Công sức | Trạng thái |
|---|---|---|---|---|
| 21 | Lỗi chặn nghiệp vụ trả về dạng có cấu trúc: mã, điều khoản căn cứ, việc cần làm, thao tác bị chặn | FoodSafe | Nhỏ | Đề xuất cho guard của phê duyệt và tự động hóa |
| 22 | Test đặt tên theo quy tắc nghiệp vụ, tiện truy vết từ quy định tới test | FoodSafe | Nhỏ | Đề xuất |
| 23 | Kịch bản demo một chạm (nạp sẵn ca vi phạm / ca đạt) | FoodSafe | Nhỏ | Đề xuất cho video demo |
| 24 | Danh mục gói nghiệp vụ là tệp JSON có script kiểm trong CI | OpenCity | Nhỏ-vừa | Đề xuất, hợp với `docs/process-packages.md` |
| 25 | Cổng kiểm giấy phép trong CI kèm văn bản nêu giới hạn | OpenCity | Nhỏ | Một phần có sẵn (`license scan` Python/npm) |
| 26 | Tách repo: lõi, ứng dụng web, ứng dụng di động | OpenCity | Lớn | Không lấy ở giai đoạn này |

**Bài học tiêu cực cần tránh**, vì giám khảo PoF đọc kho: tài liệu nói "bất biến", "100% offline", "50/50" khi mã không làm
điều đó (FoodSafe); `main` lệch `dev` (OpenCity); không release hoặc không CI (cả hai). Desktiny đang làm tốt phần tách
"đã chạy / chưa chạy"; cần giữ như vậy.

## 11. Xếp hạng tổng hợp sáu dự án (nhận định, không phải điểm chấm)

| Dự án | Sản phẩm | Bảo mật vận hành | Kiểm thử và CI | Hồ sơ PoF (release, PR, giấy phép, tài liệu) | Rủi ro lớn nhất |
|---|---|---|---|---|---|
| **Desktiny** | Mạnh | Vừa | Vừa | Vừa (giấy phép mạnh; release ít, 0 PR) | Git một tác giả, chưa quét mã độc |
| **PSA** | Vừa | Mạnh | Mạnh | Mạnh | Nhiều thứ chưa chạy thật; nặng tài nguyên |
| **commune-dxos** | Vừa-Mạnh (hẹp, sâu) | Vừa | Mạnh | **Mạnh nhất** (9 release, 65 PR, CI xanh) | Mặc định dev lỏng; tài liệu tự mâu thuẫn |
| **OpenDXOS** | Mạnh | Vừa | Yếu (CI đỏ) | Yếu | Dữ liệu cá nhân trong kho; README lệch mã |
| **OpenCity** | Yếu-Vừa (mỏng) | Vừa | Vừa (CI xanh, chưa có test) | Yếu | Chưa có release, `main` lệch `dev` |
| **FoodSafe** | Yếu-Vừa (hẹp) | Yếu | Yếu (không CI) | Yếu | Không xác thực; tài liệu nói hơn mã |

Hai đối thủ đáng cạnh tranh trực diện về hồ sơ là **PSA** (chiều sâu bảo mật) và **commune-dxos** (quy trình). Desktiny
cạnh tranh bằng độ rộng sản phẩm và độ gọn; điểm thiếu nhìn thấy được là quy trình Git và phát hành.
