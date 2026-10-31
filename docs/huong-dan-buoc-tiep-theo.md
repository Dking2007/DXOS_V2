# Hướng dẫn bước tiếp theo cho Desktiny (DXOS V2)

Ngày lập: 31/10/2026. Còn 36 ngày đến hạn nộp **17:00 06/12/2026**; đề nghị đóng băng mã **03/12**.
Nền tảng: so sánh với PSA, OpenDXOS, commune-dxos, FoodSafe-DX-OS, OpenCity (xem `02-Danh-gia-6-du-an.md`).

**Cách dùng tài liệu.** Mỗi việc có: mục đích, các bước cụ thể, tiêu chí hoàn thành (kiểm được), công sức ước lượng và
bằng chứng cần lưu. Công sức là ước lượng của tôi theo cỡ mã đã đọc, chưa đo; coi là mức sơ bộ. Tôi chưa đọc mã của
`automations.py`, `flowkit/engine.py` và giao diện canvas, nên các việc P1 chạm vào đó cần đọc lại các tệp ấy trước khi sửa.

## 1. Tóm tắt điều học được

| Dự án | Học điều gì | Tránh điều gì |
|---|---|---|
| **commune-dxos** | Phát hành đều (9 release/10 ngày); mọi thay đổi qua PR vào `develop`; `make check` ánh xạ 1-1 với job CI; `DEPENDENCIES.md` có cột giấy phép và bảng "không dùng"; test phân quyền bằng đăng nhập thật | Mặc định dev lỏng (`start-dev`, khóa mở lưu cùng máy); tài liệu tự mâu thuẫn về audit |
| **PSA** | Mô hình đe dọa nói thẳng giới hạn; ma trận nghiệm thu có test kiểm chính nó; tách mạng; deploy tag ký; backup có diễn tập; SBOM | Tuyên bố mạnh hơn mã (`verify_log`, dò CCCD); quá nặng (16 GB) |
| **OpenDXOS** | Cổng duyệt của người trong sơ đồ luồng; compose production chặt (`read_only`, `cap_drop`, mạng `internal`, biến bắt buộc); script kiểm kho; test đồng thời | CI đỏ; dữ liệu cá nhân trong kho; README lệch mã |
| **OpenCity** | Danh mục dịch vụ dạng JSON có script kiểm; kiểm giấy phép trong CI kèm nói rõ giới hạn | Không release, `main` lệch `dev`, chưa test |
| **FoodSafe** | Lỗi chặn nghiệp vụ có cấu trúc (mã, căn cứ, việc cần làm); test đặt tên theo quy tắc; demo một chạm | Không xác thực; endpoint xóa dữ liệu không bảo vệ; tài liệu nói hơn mã |

**Định vị đề xuất cho Desktiny**: *văn phòng số tự động hóa mà mọi việc đều có người duyệt, có dấu vết không sửa được, biết che
dữ liệu cá nhân người Việt, và chạy được trên laptop 8 GB.* Mọi việc P1 dưới đây phục vụ câu này.

## 2. Đối chiếu tiêu chí PoF

Điểm tối đa theo `docs/V2_CHANGES.md`: Quản lý mã nguồn 5, Giấy phép 10, Release 5, Cài đặt/biên dịch 10, Thư viện 10, Tài liệu 10.
Cột "Hiện trạng" dựa trên `SELF_REVIEW.md` (26-28/10); các ô "chưa kiểm" cần người chạy.

| Tiêu chí | Hiện trạng | Việc cần làm | Bằng chứng |
|---|---|---|---|
| 1. Quản lý mã nguồn (5) | Một tác giả; 0 PR | **P0-1**, **P0-2** | Lịch sử Git có ≥3 tác giả; ≥10 PR đã merge có review |
| 2. Giấy phép (10) | SPDX, REUSE, CI kiểm; `reuse lint` chạy trên clone sạch (227/227) | Giữ xanh; thêm `audit_repo.mjs` (đã có) | CI xanh trên `main` |
| 3. Release (5) | v0.1.0, v0.2.0, v0.2.1 | **P0-3**: tag nhỏ hằng tuần | ≥1 release/tuần đến 03/12 |
| 4. Cài đặt (10) | Chạy được trong `ubuntu:24.04` sạch (27/10); `make up` từ đúng commit **chưa** | **P3-1**, **P3-2** | `docs/progress/<ngày>-cai-sach.md` |
| 5. Thư viện (10) | THIRD_PARTY sinh tự động; giấy phép Python đã quét trên image | **P0-4** | `DEPENDENCIES.md` |
| 6. Tài liệu (10) | Tốt, nhiều chỗ ghi "chưa nghiệm thu" | **P3-3**, cập nhật README khi tính năng đổi | Tài liệu khớp mã |

## 3. Kế hoạch theo mức ưu tiên

### P0. Quy trình và hồ sơ (tuần 1, 31/10-06/11). Rẻ nhất, tác động lớn nhất

**P0-1. Tách thay đổi hiện tại thành PR riêng, mỗi PR một việc.** Công sức: 0,5 ngày.
Hiện tại mọi thứ nằm chưa commit trên `claude/changes`, lẫn hai tệp không phải của đợt này (`docs/contribution-log.md`,
`docs/huong-dan-dong-gop-flowkit.md`). Không `git add -A`.

```bash
git switch claude/changes
git switch -c feat/audit-hash-chain
git add services/core-api/src/dx_core/audit_chain.py services/core-api/src/dx_core/models.py \
        services/core-api/src/dx_core/transactions.py services/core-api/src/dx_core/main.py \
        services/core-api/migrations/versions/0003_audit_hash_chain.py \
        services/core-api/tests/test_audit_chain.py contracts/core.openapi.json \
        apps/shared/src/generated/core-api.ts docs/security.md
git add -p CHANGELOG.md        # chỉ chọn mục "Chuỗi băm cho nhật ký audit"
git commit -s -m "feat(core): chuỗi băm cho nhật ký audit và endpoint xác minh"
```

Làm tương tự cho `feat/pii-vn` (`packages/pii-vn/`, mục CHANGELOG `pii-vn`), và `chore/audit-repo` (`scripts/audit_repo.mjs`,
`.github/workflows/ci.yml`, mục CHANGELOG `audit_repo`). Tài liệu so sánh đưa vào `docs/` trong một PR `docs/...`.
Mỗi PR mô tả: vấn đề, cách giải, **đã kiểm gì, chưa kiểm gì** (theo mẫu `.github/pull_request_template.md`).
Tiêu chí hoàn thành: 4 PR mở, CI xanh, được **người khác ngoài tác giả** xem và merge.

**P0-2. Mỗi thành viên commit bằng tài khoản riêng.** Công sức: 0,5 ngày cho cả nhóm, rồi liên tục.
- Mỗi người: `git config user.name` và `user.email` đúng tài khoản GitHub; bật email xác minh.
- Chia việc theo mục P1 dưới, mỗi người một nhánh `feat/...` và một PR. Người khác duyệt.
- Bật bảo vệ nhánh `main` (Settings → Branches): bắt buộc PR, ≥1 review, CI phải xanh.
- Thêm `.mailmap` nếu ai đó đã commit nhầm tên (kho đã có `.mailmap`).
Tiêu chí hoàn thành: `git shortlog -sne` thấy ≥3 người; PR không do chính người merge.

**P0-3. Phát hành đều.** Công sức: 0,25 ngày mỗi lần.
- Tuần này gắn `v0.3.0` sau khi P0-1 merge; sau đó mỗi tuần một tag (`v0.3.1`, `v0.4.0`...). Tag nhỏ hơn thay vì một tag lớn.
- Quy trình: cập nhật `CHANGELOG.md` (chuyển `[Unreleased]` thành mục có ngày) → `make check` → `git tag -s vX.Y.Z` → push tag → workflow `release.yml`.
- Ký tag nếu có khóa; nếu chưa có, ghi rõ trong release là tag không ký.
Tiêu chí hoàn thành: trang Releases có ≥1 bản mỗi tuần; mỗi bản có `.tar.gz` và `SHA256SUMS`.

**P0-4. `DEPENDENCIES.md`.** Công sức: 0,5 ngày. Lấy ý từ commune-dxos: mỗi dịch vụ/gói chính có phiên bản, giấy phép
(SPDX), cách dùng (liên kết hay chạy riêng), và **bảng "đã cân nhắc nhưng không dùng"** (ví dụ MinIO vì không còn pull được,
Redis vì giấy phép; ghi lý do thật của nhóm). Có sẵn `THIRD_PARTY.md` sinh tự động; `DEPENDENCIES.md` là bản viết tay giải thích lựa chọn.

### P1. Tạo khác biệt (tuần 1-3, 31/10-20/11)

**P1-1. Nối `dx-piivn` vào Workspace.** Công sức: 3-4 ngày. Đây là phần demo được ngay.

*Thiết kế.*
- Cài gói: thêm `./packages/pii-vn` vào bước cài của `api.Dockerfile` và `Makefile install`; thêm vào `requirements.lock` nếu cần.
- API: trong Workspace thêm `POST /pii/check` nhận `{ "text": "..." }`, trả `{ "findings": [{ "kind", "start", "end", "confidence" }] }`.
  **Không lưu và không ghi văn bản hay giá trị vào log**; chỉ ghi đếm theo loại.
- Điểm gọi: form hồ sơ (trường văn bản), bài bảng tin, mô tả công việc, tin nhắn. Chỉ **cảnh báo**, không chặn, vì heuristic có dương tính giả.
- Giao diện: sau khi bấm Gửi, nếu có phát hiện thì hộp xác nhận: "Văn bản có 1 CCCD, 1 số điện thoại. Che trước khi gửi?" với ba nút Che / Gửi nguyên / Sửa lại. Che dùng `redact`.
- Quyền riêng tư: mọi lần người dùng chọn "Gửi nguyên" ghi một sự kiện audit `pii.override` kèm loại và số lượng (không kèm giá trị).

*Kiểm.* Test API (có/không có CCCD, văn bản rất dài, giới hạn kích thước 64 KB); test UI (Vitest) cho hộp xác nhận; test rằng log và audit không chứa giá trị.

*Trước khi dùng cho hồ sơ thi*: **một thành viên đối chiếu** danh sách mã tỉnh và đầu số di động trong `packages/pii-vn/src/dx_piivn/detect.py` với
Thông tư 07/2016/TT-BCA và quy hoạch kho số của Bộ TT&TT; sửa hằng số và README nếu khác.

*Hoàn thành khi*: quay được video 60 giây: dán đoạn văn có CCCD và số điện thoại → hệ thống cảnh báo → che → gửi; audit hiển thị sự kiện không chứa giá trị.

**P1-2. Nút "chờ duyệt" trong tự động hóa.** Công sức: 4-5 ngày. Lấy ý từ OpenDXOS.
- Thêm loại node `approval` vào `NODE_TYPES` của `packages/flowkit/src/dx_flowkit/engine.py`, với tham số `role`, `timeout_hours`.
- Trong engine chạy thật của Workspace (`automations.py`), node này tạo một việc duyệt cho vai trò đó và **tạm dừng lượt chạy** (dùng cơ chế outbox đã có cho node Chờ). Hai nhánh ra: `approved`, `rejected`; hết hạn thì mặc định `rejected`.
- Ràng buộc an toàn: **mọi node có tác động ra ngoài** (Gọi webhook, Gửi thông báo cho nhiều người) nằm sau một node `approval` nếu luồng được đánh dấu "cần duyệt". Trình kiểm cảnh báo khi vi phạm.
- Mô phỏng (`simulate_graph`) hiển thị nút duyệt như điểm dừng, không tác động thật.
- Giao diện canvas: thêm node, panel cấu hình vai trò; lịch sử chạy hiển thị ai duyệt và lúc nào.
*Kiểm.* Test flowkit (hợp lệ/không hợp lệ, vòng lặp, nhánh thiếu); test Workspace (duyệt, từ chối, hết hạn, người tự duyệt luồng của chính mình bị chặn); test đồng thời hai người duyệt cùng lúc.
*Hoàn thành khi*: video demo: luồng "tạo việc → chờ trưởng phòng duyệt → gọi webhook" chạy đúng ở cả hai nhánh.

**P1-3. Chuỗi băm cho audit của Workspace + màn hình xác minh.** Công sức: 2-3 ngày.
- Sao chép mẫu `dx_core/audit_chain.py` sang Workspace (đừng chia sẻ ORM giữa hai tầng, theo quy ước kho); migration `workspace_00xx` thêm `seq`, `prev_hash`, `entry_hash`; trigger PostgreSQL chặn UPDATE/DELETE.
- Endpoint `GET /audit-logs/verify` và một trang "Xác minh nhật ký" trong khu quản trị: nút Kiểm tra, kết quả OK hoặc dòng hỏng đầu tiên, và hiển thị `head`.
- **Neo `head` ra ngoài** (nếu không, người ghi lại cả bảng vẫn qua mặt): mỗi lần phát hành, chạy script in `head` của Core và Workspace vào ghi chú release (`docs/progress/` hoặc nội dung Release). Đó là mức neo đủ rẻ cho kỳ thi.
- Cập nhật `docs/security.md`: nói đúng giới hạn (đã làm ở Core; mở rộng cho Workspace).
*Kiểm.* Sửa một dòng bằng SQL trực tiếp → trang báo đúng `seq`; test song song ghi audit từ hai tiến trình trên PostgreSQL (chưa kiểm trước đây).
*Hoàn thành khi*: demo "sửa audit bằng SQL → trang xác minh đỏ" trong video.

### P2. Củng cố bảo mật vận hành (tuần 2-4, 07/11-27/11)

**P2-1. Quét mã độc ClamAV.** Công sức: 3-4 ngày.
- Thêm dịch vụ `clamav` (image ghim phiên bản) vào compose, mạng nội bộ, không mở cổng.
- Trạng thái file mới: `PENDING → CLEAN | INFECTED`; trong Core worker, quét qua giao thức `clamd` INSTREAM; file chưa `CLEAN` không tải xuống được (giống nguyên tắc fail-closed của PSA và OpenDXOS).
- ClamAV tắt hoặc lỗi → file ở `PENDING`, thử lại; **không bao giờ** coi là sạch.
- Giao diện: nhãn "Đang quét", "Bị cách ly".
- Kiểm bằng tệp EICAR (chuỗi thử chuẩn, không phải mã độc thật).
- Cập nhật `README.md` mục "chưa có quét antivirus" và `docs/security.md`.
*Lưu ý tài nguyên*: ClamAV tốn bộ nhớ khi tải cơ sở dữ liệu chữ ký; đo RAM trên laptop 8 GB và đặt giới hạn trong compose; làm thành profile tùy chọn nếu quá nặng.

**P2-2. Compose production.** Công sức: 2 ngày. Thêm `infra/compose/compose.production.yaml` kế thừa và siết (OpenDXOS, commune-dxos):
- mạng riêng: `edge` (chỉ gateway), `app`, `data` với `internal: true`; DB, S3, broker chỉ ở `data`;
- `read_only: true`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]` cho các dịch vụ ứng dụng; kiểm từng dịch vụ có chạy được không, ghi lại ngoại lệ;
- biến bắt buộc dạng `${VAR:?thiếu VAR}` để không khởi động với giá trị trống;
- Keycloak chạy `start` (không `start-dev`) qua TLS, bind `127.0.0.1` sau gateway;
- **không** gộp vào bản dev; tài liệu hóa rõ hai bản khác nhau ở đâu.
Mở rộng `scripts/audit_repo.mjs` để kiểm file production không có `start-dev` và không có mật khẩu mặc định. Kiểm bằng `docker compose config` và chạy thật một lần.

**P2-3. Ma trận phân quyền thử bằng đăng nhập thật.** Công sức: 2 ngày.
- Bảng vai trò × đường dẫn (director, manager, staff, technical-admin...) kỳ vọng 200/403/404 trong `docs/security.md`.
- Một script (pytest hoặc Playwright API) đăng nhập từng vai trò qua Keycloak, gọi từng đường dẫn, so với bảng; chạy trong CI trên stack Compose nếu đủ thời gian, nếu không thì chạy tay và lưu kết quả.
- Mỗi dòng bảng trỏ tới test cụ thể, và một test kiểm bảng không có dòng trống (ý của PSA `test_at_matrix`).

**P2-4. Test đồng thời.** Công sức: 1-2 ngày. Với PostgreSQL thật (đặt `DX_TEST_POSTGRES_URL` để test hiện đang bị skip chạy): 20 yêu cầu duyệt cùng một hồ sơ → đúng một thành công; 20 ghi audit song song → chuỗi băm vẫn hợp lệ.

### P3. Bằng chứng, demo, kiểm độc lập (tuần 4-5, 21/11-04/12)

**P3-1. Cài sạch từ đúng commit.** Chạy `make up` trên máy sạch từ commit của tag mới nhất, theo `BUILD.md`, bấm giờ từng bước, ghi mọi vướng mắc vào `docs/progress/<ngày>-cai-sach.md`. Ưu tiên một **người ngoài nhóm** làm việc này (PSA gọi là AT-23; họ lên kế hoạch nhưng chưa làm, đây là cơ hội vượt họ).
**P3-2. Những mục "chưa kiểm" đã nêu trong `SELF_REVIEW.md`**: ONLYOFFICE Document Server thật (mở, sửa, lưu, trình hồ sơ), sao lưu và khôi phục (viết một kịch bản `ops/backup_restore_drill.sh`, chạy và ghi kết quả), `make dist`, ScanCode.
**P3-3. Ma trận nghiệm thu có test kiểm chính nó.** Biến `docs/acceptance.md` thành bảng có cột "test tương ứng"; thêm `tests/test_acceptance_matrix.py` kiểm mỗi dòng "đạt" trỏ tới tên test tồn tại (ý của PSA).
**P3-4. Mô hình đe dọa ngắn** (`docs/threat-model.md`): ai làm được gì, ta phát hiện bằng gì, **không bảo vệ gì** (dạng bảng như X1-X4 của PSA). Ví dụ: người có quyền ghi DB; người có quyền root trên máy chủ; quản trị viên Workspace; trình duyệt người dùng.
**P3-5. Video dự phòng và tập demo.** Quay 5-6 đoạn ngắn: SSO; tạo hồ sơ → duyệt có ủy quyền; canvas tự động hóa với nút duyệt; cảnh báo CCCD; sửa audit → trang xác minh đỏ; tải EICAR → bị cách ly. Không quay mật khẩu, token. Tập tối thiểu 5 lần bấm giờ trước 10/12, tập cả tình huống lỗi (mất mạng, container chết).

## 4. Lịch đề xuất

| Tuần | Mục tiêu | Việc |
|---|---|---|
| 1 (31/10-06/11) | Hồ sơ sạch, bắt đầu khác biệt | P0-1..4, bắt đầu P1-1 |
| 2 (07-13/11) | Hoàn thành P1-1, P1-3; bắt đầu P1-2 | Release v0.4.0; P2-2 bắt đầu |
| 3 (14-20/11) | Hoàn thành P1-2; P2-1 | Release v0.5.0; cổng năng suất 16/11: tự kiểm tiến độ |
| 4 (21-27/11) | Củng cố | P2-3, P2-4, P3-2, P3-4; **đóng băng tính năng 27/11** |
| 5 (28/11-04/12) | Bằng chứng và kiểm độc lập | P3-1, P3-3, P3-5; sửa lỗi; **tag cuối 03/12** |
| 6 (05-06/12) | Nộp | Kiểm danh sách nộp bài; **gửi trước 17:00 06/12** |

Ngày cổng 16/11 và ngày đóng băng 27/11 là đề xuất của tôi, không phải mốc của BTC (trừ hạn nộp 06/12 theo `docs/V2_CHANGES.md`).
Hãy đối chiếu lại thể lệ và đề thi gốc trước khi chốt.

## 5. Phân công gợi ý

Điền tên thật, tôi không biết nhóm có mấy người:

| Vai trò | Việc chính |
|---|---|
| Trưởng nhóm | P0 (PR, review, release, bảo vệ nhánh), nộp bài |
| Backend 1 | P1-1 (API PII), P1-3 (chuỗi băm Workspace) |
| Backend 2 | P1-2 (nút duyệt, engine), P2-4 |
| Frontend | Giao diện cảnh báo PII, node duyệt trên canvas, trang xác minh nhật ký |
| DevOps / bảo mật | P2-1, P2-2, P2-3, P3-2 |
| Tài liệu / QA | P0-4, P3-3, P3-4, P3-1, kịch bản và video demo |

## 6. Điều không nên làm (và vì sao)

- Không thêm Temporal, OpenBao, APISIX, Flowable, Merkle đầy đủ, witness hay agent LLM: nặng, lệch hướng văn phòng số, khó hoàn thành và kiểm được trong 5 tuần.
- Không viết tài liệu nói hơn mã. FoodSafe tuyên bố "bất biến", "100% offline" mà mã không làm; OpenDXOS ghi "Battle-tested" khi không có release. Giữ thói quen ghi **đã chạy / chưa chạy**.
- Không để `main` lệch xa nhánh làm việc (lỗi của OpenCity); nếu dùng `develop`, merge về `main` mỗi lần phát hành.
- Không đưa dữ liệu cá nhân thật vào dữ liệu seed, tài liệu hay test (OpenDXOS); `dx-piivn` chỉ dùng số giả.
- Không coi mọi tuyên bố của các đội khác là đúng: số test họ nêu là tự báo; tôi chưa chạy lại mã của họ.

## 7. Danh sách kiểm trước khi nộp (03/12 đến 06/12)

- [ ] `main` xanh CI; tag `v1.0.0` (hoặc tag cuối) đã gắn, có Release với `.tar.gz` và `SHA256SUMS`.
- [ ] `git shortlog -sne` thấy từ 3 tác giả; có PR được review.
- [ ] `reuse lint`, `add_spdx_headers --check`, `audit_repo.mjs`, `gen_third_party` đều sạch.
- [ ] README, `docs/security.md`, `docs/acceptance.md` khớp mã; mọi chỗ "chưa nghiệm thu" còn đúng.
- [ ] `SELF_REVIEW.md` có chữ ký hai lần (ít nhất hai thành viên) và ngày.
- [ ] Người ngoài nhóm đã cài thành công theo `BUILD.md`, kết quả lưu trong `docs/progress/`.
- [ ] Danh sách mã tỉnh, đầu số di động của `dx-piivn` đã được đối chiếu văn bản chính thức.
- [ ] Video dự phòng đã lưu ngoài Git (USB, laptop); không chứa mật khẩu hay token.
- [ ] Email nộp bài đúng mẫu của đề, **gửi trước 17:00 06/12/2026**; đối chiếu lại thể lệ gốc về địa chỉ và tiêu đề email.

## 8. Rủi ro chính

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Quy trình Git (một tác giả, 0 PR) kéo điểm tiêu chí 1 | Cao | P0-1, P0-2 ngay tuần này |
| Tính năng P1 không kịp | Vừa | Cắt theo thứ tự: P1-1 → P1-3 → P1-2; mỗi cái phải demo được độc lập |
| ClamAV làm máy 8 GB quá tải | Vừa | Profile tùy chọn; đo RAM; giới hạn bộ nhớ |
| Dò PII báo nhầm / sót | Vừa | Chỉ cảnh báo, không chặn; nêu rõ giới hạn trong README (đã làm); đối chiếu danh sách |
| Chuỗi băm bị hiểu là "chống mọi tấn công" | Thấp | Giữ văn bản giới hạn trong `docs/security.md`; neo `head` mỗi release |
| Hai PR gửi ngoài (Keycloak, ONLYOFFICE) không được merge kịp | Vừa | Không phụ thuộc; ghi đúng trạng thái "chờ xét" |
| Đối thủ commune-dxos có nhịp phát hành và CI xanh vượt trội | Vừa | Đua ở độ rộng sản phẩm và độ gọn, đồng thời P0 |

## 9. Hạn chế của hướng dẫn này

- Đánh giá về năm dự án khác dựa trên trang công khai của họ, ngày 31/10/2026; chưa clone, chưa chạy, nhiều mã chưa đọc.
- Ước lượng công sức là sơ bộ. Chưa đo thời gian thật.
- Chưa đọc mã `automations.py`, engine flowkit, giao diện canvas và mã audit của Workspace; thiết kế P1-2, P1-3 cần xác nhận khi đọc.
- Chuỗi băm audit của Core mới chạy thử migration/trigger trên PostgreSQL 17; chưa kiểm ghi đồng thời.
- Danh sách mã tỉnh và đầu số di động của `dx-piivn` chưa đối chiếu văn bản chính thức.


## 10. Đính chính (31/10, sau khi đọc thể lệ chấm điểm)

Bản hướng dẫn ở trên được viết trước khi tôi đọc thể lệ. Hai điều cần sửa, chi tiết ở `docs/cham-diem-xep-hang.md`:

1. **Phát hành hằng tuần (P0-3) không cho thêm điểm.** Thể lệ chỉ yêu cầu **một** release có phiên bản trước hạn nộp (tiêu chí 3, 5 điểm).
   Chỉ cần một release tử tế gần cuối (tag `v1.0.0` ngày 03/12) và các bản trước đó nếu thuận tiện. Tương tự, số PR và số tác giả không phải
   tiêu chí chấm; chúng chỉ giúp tránh bị coi là "không thực sự dùng VCS" (tiêu chí 1). Giữ P0-1 và P0-2 vì rủi ro đó, nhưng đừng đặt nặng.
2. **Bảo mật, CI và hạ tầng production không phải tiêu chí chấm riêng.** Phần 50 điểm chung kết gồm: nguyên gốc, hoàn thiện (live demo),
   thân thiện, bền vững, trình diễn và cộng đồng. Vì vậy:
   - **Nâng ưu tiên**: P3-5 (kịch bản demo 15 phút, video dự phòng), P3-2 (ONLYOFFICE, backup, `make up` từ tag, vì demo không được crash),
     P1-1, P1-2, P1-3 (câu chuyện riêng), **P2-1 ClamAV** (đề thi nêu rõ kiểm dịch mã độc tại biên, nên ClamAV vừa gắn với đề vừa demo được bằng tệp EICAR).
   - **Hạ ưu tiên**: P2-2 (compose production), P2-3, P2-4. Chỉ làm nếu còn thời gian sau khi demo ổn định; chúng làm hồ sơ chắc hơn nhưng không có ô điểm riêng.
   - **Giữ**: P0-4 (`DEPENDENCIES.md`), P3-3, P3-4 vì chúng phục vụ tiêu chí tài liệu và bền vững.
   - **Chỗ trống so với đề**: đề nhắc LLM/RAG (lớp 6, không gian Trí tuệ số [I]), vòng đời dữ liệu (đẩy dữ liệu lịch sử xuống kho) và IT/OT.
     Desktiny chưa có các phần này. Chúng không bắt buộc (chỉ Core headless và một ứng dụng giao diện là bắt buộc), nhưng cần quyết định sớm có làm
     một lát mỏng nào không và nói rõ trong buổi trình bày.
   - Cần hỏi lại BTC (nhóm Telegram nêu trong đề) liệu Core có được kèm một trang quản trị hay không, vì đề nói Core "hoàn toàn không cung cấp giao diện UI".
     Desktiny có `apps/core-admin`.


## 11. Đảm bảo project đi đúng đích: bám tiêu chí chấm và nộp đúng địa chỉ

Mục này làm hai việc: (a) buộc mọi việc trong kế hoạch phải trỏ tới một ô điểm hoặc một yêu cầu bắt buộc của đề, (b) giữ cho bài nộp
đến đúng địa chỉ, đúng mẫu, đúng hạn. Nguồn: đề thi VFOSSA đăng 30/09/2026 (tôi đã đọc ngày 31/10) và bản sao thể lệ trong repo FoodSafe
(chưa đối chiếu với bản gốc). **Mọi địa chỉ, tiêu đề và hạn dưới đây phải được đối chiếu lại với đề gốc trước khi gửi.**

### 11.1 Yêu cầu bắt buộc của đề: Desktiny đang ở đâu

Đề nói bắt buộc: Core headless ở Tầng 1 với bốn dịch vụ, và ít nhất một ứng dụng giao diện ở Tầng 2 thuộc không gian H-P-D-I.

| Yêu cầu của đề | Bằng chứng trong Desktiny | Tình trạng | Việc cần làm |
|---|---|---|---|
| Core chạy ngầm, không UI nghiệp vụ | `services/core-api` + worker; I03: dừng Workspace, `examples/core-client` vẫn tạo schema, record, file, workflow qua gateway | Có bằng chứng | Quay lại clip I03 từ đúng tag; nêu rõ trong buổi trình bày |
| Identity/SSO | Keycloak OIDC code flow, PKCE, E2E 3/3 đạt | Có | Giữ |
| API Gateway | `infra/gateway/nginx.conf` (Nginx) | **Cần xem lại**: tôi chưa đọc cấu hình; giám khảo có thể kỳ vọng xác thực, giới hạn tần suất ở cổng | Đọc và ghi đúng cổng đang làm gì, không làm gì; nếu thiếu thì thêm giới hạn tần suất và kích thước yêu cầu |
| Quản trị dữ liệu cấu trúc và phi cấu trúc | Schema/record có phiên bản; file có phiên bản trên S3 | Có | Giữ; ghi rõ chưa quét mã độc cho tới khi làm P2-1 |
| Workflow | Engine đồ thị, run, human task ở Core | Có | Giữ; thêm nút duyệt (P1-2) |
| Ứng dụng giao diện thuộc H-P-D-I | Workspace: H (giao việc, chat, bảng tin), P (hồ sơ, phê duyệt, tự động hóa), D (báo cáo, một phần) | **I (Trí tuệ) chưa có** | Quyết định có làm lát mỏng I hay không (xem 11.5) |
| Core "không cung cấp UI" | `apps/core-admin` là một giao diện quản trị | **Câu hỏi mở** | Hỏi BTC qua nhóm Telegram nêu trong đề; trong lúc chờ, mô tả nó là công cụ quản trị, không phải ứng dụng nghiệp vụ |
| Bốn nguyên tắc kỹ thuật (đề nêu, không ghi bắt buộc) | Vòng đời dữ liệu: chưa. IT/OT: chưa. Truy nguồn: một phần (phiên bản, snapshot, audit). Zero-Trust và kiểm dịch: chưa quét mã độc | Còn trống | P2-1 ClamAV (kiểm dịch); nói rõ phần còn lại là định hướng |

### 11.2 Mỗi ô điểm: bằng chứng, việc, và nơi hiện ra trong buổi trình bày

| Ô điểm | Điều giám khảo sẽ thấy ở Desktiny | Việc để chắc điểm | Hiện ở đâu |
|---|---|---|---|
| II.1 Nguyên gốc (10) | Canvas tự động hóa có nút duyệt; cảnh báo CCCD kiểm cấu trúc; nhật ký audit có thể xác minh; plugin thể thức Nghị định 30 | P1-1, P1-2, P1-3; một slide "điều gì mới so với các hệ thống có sẵn" (đã có bảng so sánh Base, MISA, Power Platform trong tài liệu nhóm) | Phút 4-12 |
| II.2 Hoàn thiện (10) | Một kịch bản chạy xuyên suốt, không crash | P3-2, P3-5; viết một script kiểm trước mỗi lần tập (các dịch vụ khỏe, đăng nhập thử từng vai trò); video dự phòng | Toàn bộ |
| II.3 Thân thiện (10) | Ctrl+K, chế độ tối, mobile, hướng dẫn lần đầu | Kiểm lại trên màn chiếu thật; chữ ≥ 16 px; không đưa tính năng chưa xong vào demo | Phút 4-9 |
| II.4 Bền vững (10) | Kiến trúc, OpenAPI, CONTRIBUTING, test, changelog | P0-4, P3-3, P3-4; một slide kiến trúc hai tầng; mở sẵn tab tài liệu | Phút 13-14 |
| II.5 Trình diễn, cộng đồng (10) | Hai PR gửi Keycloak và ONLYOFFICE, gói `dx-flowkit`, plugin | Công bố `dx-flowkit` lên PyPI; chuẩn bị đoạn 30 giây về cộng đồng; nêu đúng trạng thái "chờ xét" | Phút 13-14 |
| I.1-I.6 (PoF 50) | Chấm trước bằng kho mã | Danh sách 11.4 và mục 7 | Trước 06/12 |

### 11.3 Gợi ý phân bổ 15 phút theo ô điểm

Đây là đề xuất của tôi, không phải quy định. Đề chỉ nói 15 phút gồm giải pháp thiết kế, tính năng và ứng dụng, kết quả và demo, định hướng.

| Phút | Nội dung | Ô điểm |
|---|---|---|
| 0-2 | Bài toán, hai tầng, vì sao Core tách riêng | II.1, II.4 |
| 2-4 | Core chạy một mình: client ngoài tạo schema, record, file, workflow; SSO | Bắt buộc của đề, II.2 |
| 4-9 | Kịch bản hồ sơ: tạo, nộp, duyệt có ủy quyền, tự động hóa có nút duyệt | II.2, II.3 |
| 9-11 | Dán văn bản có CCCD và số điện thoại: cảnh báo, che | II.1, II.3 |
| 11-12 | Sửa audit bằng SQL: trang xác minh báo đỏ | II.1 |
| 12-13 | Tải tệp EICAR: bị cách ly (nếu ClamAV xong; nếu chưa, bỏ đoạn này, đừng mô phỏng) | Bốn nguyên tắc của đề |
| 13-14 | Nguồn mở: giấy phép, release, hai PR ngoài, gói tái sử dụng | II.5, II.4 |
| 14-15 | Hạn chế đã biết và định hướng | II.4 |

Nguyên tắc: chỉ demo cái đã chạy; gắn nhãn rõ cái mô phỏng (đúng tinh thần `docs/demo.md` và các tài liệu "chưa nghiệm thu" hiện có).

### 11.4 Địa chỉ và mẫu nộp bài

Theo đề (30/09/2026), nộp bằng email:

| Mục | Nội dung theo đề |
|---|---|
| Hạn | 17:00 Chủ Nhật 06/12/2026 |
| Gửi tới | `olpvietnam@vaip.vn` và `thuky@vfossa.vn` |
| Tiêu đề | `BÀI THI PMNM 2026 - [Tên Đội] - [Tên Trường]` |
| Nội dung thư | Danh sách thành viên (họ tên, năm sinh, ngành); tên người hướng dẫn và khoa/viện/trường; đường dẫn kho mã chứa đầy đủ kết quả; xác nhận đã đăng ký qua trường; cam kết bản quyền theo quy tắc phần mềm tự do nguồn mở |

Địa chỉ trên do tôi đọc từ trang đề thi công khai ngày 31/10; trang đó không nói rõ có phải đính kèm tệp nào (tài liệu thiết kế, video) hay không.
Thể lệ PoF yêu cầu kho mã **truy cập tự do trên Internet** và có **release đầu tiên trước thời điểm nộp**. Hãy đối chiếu thể lệ gốc về đính kèm.

Mẫu thư (điền tên thật; **không gửi khi chưa qua danh sách kiểm 11.5**):

```
Tiêu đề: BÀI THI PMNM 2026 - <Tên đội> - <Tên trường>
Kính gửi Ban tổ chức OLP Phần mềm nguồn mở 2026,

Đội <Tên đội> (trường <Tên trường>) xin nộp bài thi chủ đề DX-OS Open-Core.

1. Thành viên:
   - <Họ tên>, <năm sinh>, <ngành>
   - <Họ tên>, <năm sinh>, <ngành>
   - <Họ tên>, <năm sinh>, <ngành>
2. Người hướng dẫn: <Họ tên>, <khoa/viện/trường>
3. Kho mã nguồn: <URL công khai>
   Bản phát hành: <URL release v1.0.0>
4. Đội đã đăng ký dự thi qua trường <Tên trường>.
5. Chúng tôi cam kết sản phẩm tuân thủ các quy tắc của phần mềm tự do nguồn mở (giấy phép Apache-2.0; xem LICENSE và NOTICE trong kho).

Trân trọng,
<Họ tên người gửi>
```

Thành viên điền họ tên và năm sinh của mình; tôi không điền thay.

### 11.5 Danh sách kiểm trước khi bấm Gửi (làm trong 05/12, gửi sáng 06/12)

- [ ] Mở kho bằng **cửa sổ ẩn danh** (không đăng nhập GitHub): thấy mã, README, LICENSE, Releases.
- [ ] Release `v1.0.0` tồn tại **trước** khi gửi thư; có `.tar.gz` và `SHA256SUMS`, không chỉ `.zip`.
- [ ] `git clone` bản công khai về máy sạch, làm theo `BUILD.md`, chạy được (do người ngoài nhóm kiểm nếu có thể).
- [ ] Mọi thành viên đã điền họ tên, năm sinh, ngành; người hướng dẫn xác nhận tên và đơn vị.
- [ ] Địa chỉ nhận, tiêu đề, hạn đã đối chiếu với đề gốc ngày gửi (đề có thể được cập nhật).
- [ ] Liên kết trong thư mở được từ tài khoản không phải thành viên.
- [ ] Có bản sao thư đã gửi (thư mục "Đã gửi") và ảnh chụp thời điểm gửi; gửi **trước 17:00**, tốt nhất sáng 06/12 hoặc 05/12 để còn thời gian sửa.
- [ ] Lưu bản sao toàn bộ kho (zip ngoài Git) và video dự phòng trên USB.
- [ ] README, `docs/security.md`, `SELF_REVIEW.md` khớp với mã và trạng thái thật; không để câu "đã nghiệm thu" khi chưa chạy.
- [ ] Không có mật khẩu, token, `.env`, dữ liệu cá nhân thật trong kho (`node scripts/audit_repo.mjs` sạch).

### 11.6 Quyết định cần chốt sớm

| Câu hỏi | Hạn chốt đề xuất | Người quyết định |
|---|---|---|
| Có làm một lát mỏng cho không gian Trí tuệ [I] (ví dụ: gợi ý phân loại văn bản bằng quy tắc, hoặc tra cứu có trích dẫn) hay nói rõ là định hướng? | 07/11 | Cả nhóm |
| `apps/core-admin` có phải gỡ khỏi phần "Core" khi trình bày? | Hỏi BTC trước 07/11 | Trưởng nhóm |
| ClamAV làm hay bỏ? Nếu bỏ, không đưa vào demo | 10/11 | Cả nhóm |
| Ai gửi email, từ tài khoản nào, ai kiểm lần cuối | 28/11 | Trưởng nhóm |
