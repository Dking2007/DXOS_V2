Một phần 28/10: E2E tạo hồ sơ nháp và tải lại; luồng gửi/trả lại/duyệt mới kiểm bằng pytest |||

## Trạng thái tại thời điểm tạo bộ cài

Đây là checklist thực thi, không phải báo cáo tích xanh theo thiết kế. Người chạy
release phải ghi commit/source snapshot, dependency lock, image digest, cấu hình,
lệnh, ngày chạy và kết quả. Không suy ra test đạt chỉ vì đã có endpoint hoặc UI.

### Cập nhật 28/10/2026 (stack Docker Compose thật)

Chạy trên Docker Desktop (Windows), stack 11 container từ một bản sao cục bộ (image dựng trước
các nhánh PoF; **chưa phải** `make up` từ đúng commit phát hành). Các mục dưới đây thay cho
nhiều dòng "chưa chạy" ở phần lịch sử bên dưới; phần lịch sử giữ nguyên để truy vết.

- Tổng số test hiện tại: pytest **108 đạt** với PostgreSQL 17.5 thật (27/10), `npm run test` 45 đạt.
- Playwright E2E có đăng nhập qua Keycloak và gateway (Chromium, tài khoản `staff`): **3/3 đạt**
  (chuyển hướng khi chưa đăng nhập, tạo hồ sơ nháp rồi tải lại vẫn thấy, `staff` bị chặn truy cập
  audit kỹ thuật). Lượt chạy đầu thất bại vì người dùng demo thiếu họ (Keycloak 26 chặn ở
  `VERIFY_PROFILE`); đã sửa trong `scripts/bootstrap.py`.
- I03 (Core độc lập): dừng `workspace-web`, `workspace-api`, `workspace-worker`; tuyến `/workspace/`
  trả 502 nhưng `examples/core-client/main.py` (client `core-example`, namespace `equipment`) tạo
  schema, record, file và chạy workflow thành công qua gateway. Sau đó khởi động lại Workspace.
- Lượt 31/10/2026 (v0.2.2, Docker Desktop trên Windows, Document Server 8.3.3 thật, profile `office`, `ONLYOFFICE_ENABLED=true`): `GET /office/healthcheck` qua gateway trả `true`; đăng nhập `staff` qua Keycloak, tạo DOCX trống từ Kho tài liệu, mở trình soạn thảo thật (iframe `documenteditor`, giao diện tiếng Việt), gõ một câu tiếng Việt có dấu rồi đóng bằng "Về kho tài liệu". Sau vài giây Drive có phiên bản 2 (25 310 byte so với 929 byte của bản 1) và log `workspace-api` ghi `office/content` rồi `office/callback` trả 200. Chỉ một người dùng và một lần lưu; chưa kiểm hai người cùng sửa (I11), callback trùng/muộn/JWT sai với Document Server thật (I12), force-save và thu hồi quyền khi đang mở (I13), phông chữ tiếng Việt khi xuất. Chưa mở lại tệp để đối chiếu nội dung đã lưu. Playwright E2E cũ: 2/3 đạt; ca tạo hồ sơ bỏ qua điều kiện đầu vào vì DB mới chưa có biểu mẫu đã phát hành, không phải lỗi ứng dụng đã được xác nhận.
- Còn chưa chạy: hai người cùng sửa (I11–I13),
  outbox fault injection (I10), đo thu hồi quyền (I14). Backup/restore (I15) đã diễn tập một phần ngày 31/10, xem `docs/operations.md`.

### Kết quả đã chạy trên máy phát triển

- Bootstrap chạy trong thư mục tạm: tạo 4 OIDC clients, 8 Keycloak user/service
  identities, secret ngẫu nhiên; cùng deployment không cho overwrite.
- `docker compose ... --profile workspace --profile office config --quiet`: render
  hợp lệ với env được tạo trong thư mục tạm, không cần Docker daemon.
- Object storage init bằng mock: bucket thiếu được tạo, bucket đã có không tạo lại; chưa
  kiểm S3/RustFS thật. Seed wrapper được kiểm lệnh/đường dẫn bằng mock subprocess.
- RustFS thay MinIO trong `infra/compose/compose.yaml`: đổi `image` +
  `MINIO_ROOT_USER/PASSWORD` → `RUSTFS_ACCESS_KEY/SECRET_KEY`, `user: 10001:10001` và
  command mới; `docker compose config` render hợp lệ. Lý do: `minio/minio` trả
  `pull access denied` trên cả Docker Hub lẫn `quay.io/minio/minio` (`docker manifest
  inspect` báo `no such manifest` cho mọi tag đã thử, trong khi các image khác cùng
  registry vẫn pull được). Core chỉ dùng 4 thao tác S3 (`put_object`, `get_object`,
  `head_bucket`, `create_bucket`) nên tương thích API là đủ.
  **Chưa chạy container RustFS thật**, chưa kiểm `storage-init` tạo bucket, upload/get
  trên HTTP thật, hay log/volume sau khi chạy. Đổi service không tự động nghiệm thu I07.
- Ruff lint/format cho bootstrap, seed wrapper, storage initializer đã đạt.
- Chưa pull/build/chạy image, SSO hay callback Office thật. Docker daemon của môi
  trường phát triển ban đầu không sẵn sàng (`dockerDesktopLinuxEngine` missing).
- `python -m pytest -q` (Core): **29 passed, 1 warning**.
- `python -m pytest -q` (Workspace): **35 passed, 2 warnings** — 28 test luồng
  Drive/hồ sơ, 2 test Office save, 3 test phục hồi retry, 2 test chuỗi Alembic.
  Test mới cho hồ sơ và Drive: hạn xử lý + mức độ + người phụ trách khi tạo hồ sơ;
  hiển thị/giá trị mặc định có điều kiện theo trường khác, kể cả trường không được tự
  tham chiếu mình; nhãn tài liệu được chuẩn hóa và lưu lại; sao chép tài liệu tạo tài
  liệu Core độc lập (bản gốc giữ nguyên version và quota chia sẻ), kế thừa nhãn, đặt
  vào thư mục đích, từ chối thư mục không ghi được/người bị thu hồi quyền đọc, và giữ
  nguyên phần mở rộng khi đổi tên/sao chép. Hai test Alembic kiểm chuỗi là linear và
  idempotent với baseline `create_all` cho cả 4 revision.
  PostgreSQL concurrency test bị skip vì chưa đặt `DX_TEST_POSTGRES_URL`.
- `python -m unittest discover -s infra/tests -v`: **2 passed**. Kiểm offline các
  claim/audience/namespace, Settings và startup gates qua Compose config; không
  khởi chạy container hay xác nhận Keycloak thực tế đã phát token.
- Alembic cả hai service: upgrade → downgrade → upgrade bằng SQLite tạm đã đạt;
  chưa chạy migration trên PostgreSQL thật.
- Ruff cho packages/services/scripts/tests/examples/infra đạt; `pip check` không
  phát hiện dependency hỏng.
- `npm run lint` và `npm run typecheck`: đạt cho cả hai ứng dụng.
  `npm run test`: **19 passed** (helper nhãn quyền chia sẻ thư mục, helper chuẩn hóa
  nhãn tài liệu và câu tóm tắt bản sao);
  `npm run build`: hai production builds đạt.
  `npm audit --audit-level=low`: **0 vulnerabilities** tại lần kiểm.
- Browser Chromium: trang đăng nhập Workspace hiển thị ở 1440×960 và 390×844,
  nút SSO có mặt, không có page error hay tràn ngang mobile. Ảnh:
  `test-results/workspace-login-desktop.png` và `workspace-login-mobile.png`.
  Core console smoke với fixture `/me` trả 401 chỉ kiểm UI/link đăng nhập, không
  phải nghiệm thu SSO. Chưa chạy authenticated Playwright E2E với toàn stack.
- OpenAPI được sinh từ factory API thực: **34 Core paths, 37 Workspace paths**
  (thêm `POST /drive/files/{id}/copy`, `PATCH /drive/folders/{id}` và
  `GET`/`PUT /drive/folders/{id}/shares`);
  TypeScript types được sinh bằng `npm run generate:api`.
- Kiểm Compose/build/UI chưa thay kiểm API, routing Nginx hoặc Office trong deployment thật.
- Workspace báo **33 test qua Core HTTP thật trong cùng process với SQLite** đã đạt
  (28 test luồng + 2 Office save + 3 phục hồi retry):
  duyệt hai bước; trả lại/sửa/trình lại; idempotency/privacy; chia sẻ trực tiếp từng
  file và chia sẻ kế thừa theo thư mục; triage hồ sơ, hiển thị có điều kiện, nhãn và
  sao chép tài liệu; Office JWT/status4/open-session submit barrier,
  save dedupe/late callback; phục hồi retry sau Core run commit/upload complete. Office
  chỉ mock tải bytes từ Document Server trong các kịch bản callback. Đây không phải network
  deployment, PostgreSQL concurrency, Keycloak SSO hoặc Docs integration thật.
- Đợt bổ sung giao việc, nhắn tin, bảng tin, tìm kiếm, báo cáo, ủy quyền, thu hồi hồ
  sơ và luật tự động hóa (migration `workspace_0007`):
  - `python -m pytest -q` (Workspace): **46 passed** — thêm 11 test trong
    `tests/test_collaboration.py` qua Core HTTP thật trong cùng process với SQLite:
    vòng đời công việc + checklist + nghiệm thu; phạm vi giao việc theo phòng/tổ chức và
    trưởng đơn vị phân công; trả lại cần lý do, việc cha chờ việc con; chat chống trùng
    `client_message_id`, phạm vi lịch sử khi thêm thành viên, mất quyền đọc khi bị xóa,
    quản trị kỹ thuật không đọc được chat riêng; tạo việc từ tin nhắn cần tin đọc được;
    bảng tin theo phạm vi, thông báo chính thức, ghim; tìm kiếm và báo cáo chỉ đếm dữ liệu
    được phép; ủy quyền duyệt thay, thu hồi ủy quyền, `decided_by_id`; thu hồi hồ sơ hủy
    run Core và trình lại được; luật tự động chạy một lần/sự kiện, chặn tự lặp, webhook
    chỉ tới host được phép, timeout ghi `unknown` không gửi lại (HTTP webhook dùng mock).
  - Test chuỗi Alembic được cập nhật cho 7 revision (trước đó còn ghi 4 revision và đang
    lỗi). Upgrade → downgrade 0006 → upgrade bằng SQLite tạm đã đạt; chưa chạy PostgreSQL.
  - `npm run lint`, `npm run typecheck`, `npm run test` (19 passed), `npm run build`: đạt.
  - Chromium với API giả lập (Playwright route mock, không backend thật): các màn
    `/tasks`, `/tasks/:id`, `/chat`, `/feed`, `/reports`, `/search`, `/automations`,
    `/approvals` hiển thị ở 1440 px và 390 px, không page error, không tràn ngang.
    **Chưa chạy E2E có đăng nhập với stack thật** cho các màn này.
  - OpenAPI Workspace: **89 paths**; Core không đổi (38).
- Đợt chuyển tự động hóa sang canvas kiểu n8n (migration `workspace_0008`, chuyển luật cũ
  sang đồ thị):
  - `python -m pytest -q` (Workspace): **48 passed**. Test luồng: chạy một lần/sự kiện,
    chặn tự lặp, webhook theo node (mock bên nhận), kiểm tra đồ thị báo lỗi theo node (điều
    kiện thiếu nhánh, node treo, vòng lặp), rẽ nhánh Đúng/Sai với chế độ "ít nhất một", node
    Chờ giữ job tới hạn rồi tiếp tục (thời gian được dời trong test, không chờ thật).
  - Alembic upgrade → downgrade 0007 → upgrade bằng SQLite tạm: đạt.
  - `npm run test`: **24 passed** (thêm 5 test chuyển đổi đồ thị ↔ canvas và tóm tắt node);
    lint, typecheck, build: đạt; `npm audit`: 0 vulnerabilities sau khi thêm Vue Flow.
  - Chromium với API giả lập: danh sách luồng, chọn mẫu, canvas, panel cấu hình, chạy thử tô
    đường, vẽ lại lượt chạy đang chờ, **kéo thả node từ bảng vào canvas** (6 → 7 node) ở
    1440 px; mobile 390 px không tràn ngang. Chưa thử với backend thật.
- Đợt chat có tệp đính kèm (migration `workspace_0010`): Workspace **52 passed**, Core **48
  passed** (thêm 18 test kiểm tra chữ ký tệp: media/ZIP hợp lệ được nhận, sai chữ ký và
  SVG/HTML/EXE bị từ chối). Test chat kiểm tra thành viên xem được ảnh, người ngoài/quản trị
  kỹ thuật/thành viên vào sau không xem được, tin xóa thì tệp ẩn, không gắn được tệp của người
  khác. Giao diện chat mới chỉ kiểm bằng API giả lập (Chromium 1440 px và 390 px).
- Đợt dễ dùng toàn hệ thống (14 đề xuất, không thêm migration): Workspace **55 passed**
  (thêm test `/me/overview`, phân loại thông báo + đọc tất cả, bảng phân quyền chặn tự khóa
  quyền), Core **48 passed**; `npm run test` **36 passed** (thêm test menu theo quyền, nhãn
  quyền khớp danh sách quyền của backend, tour theo vai trò, toast); lint, typecheck, build
  đạt. Giao diện mới (menu, Tạo mới, thông báo, Ctrl + K, trang Việc hôm nay, tab hồ sơ,
  bảng phân quyền, chế độ tối, tour, thanh dưới điện thoại) **chỉ kiểm bằng API giả lập**
  trên Chromium 1440 px và 390 px (không tràn ngang); chưa chạy với backend thật hay Docker.
- Xem tệp trong ứng dụng (không đổi backend): `npm run test` **39 passed** (thêm test nhận
  loại tệp, SVG/HTML/Office/ZIP không xem trước); lint, typecheck, build đạt; pdf.js tách
  thành chunk riêng, worker build ra `.js`. Chromium với API giả lập: PDF 3 trang do trình
  duyệt tạo hiện đủ 3 trang, lật trang, phóng to, Esc đóng; ảnh PNG hiện đúng kích thước;
  390 px không tràn ngang. Chưa thử với Core/gateway thật. `npm audit` báo 2 lỗ hổng mức
  trung bình ở `vitest`/`@vitest/mocker` (chỉ dùng khi chạy test, có từ trước, chưa nâng cấp).
- Bảng tin mới và ảnh/video trong bài (migration `workspace_0011`): Workspace **56 passed**
  (thêm test: trước khi đăng chỉ người tải xem được, PDF bị từ chối 415, người cùng phòng xem
  được ảnh của bài phòng, phòng khác 404, không đăng lại/mượn ảnh người khác, xóa bài thì ảnh
  404), Core **48 passed**; `npm run test` **45 passed**; lint, typecheck, build đạt; Alembic
  upgrade → downgrade 0010 → upgrade bằng SQLite tạm: đạt. Chromium với API giả lập: chọn 2
  ảnh + 1 PDF (PDF bị từ chối), nút Đăng khóa khi đang tải, bài gửi đúng 2 mã ảnh; lưới 4 ô
  "+2", xem toàn màn hình lướt bằng phím; video WebM thật phát trong bài; 390 px không tràn.
  Chưa thử với Core/gateway thật.
- Trợ lý AI (migration `workspace_0012`, nhánh `feat/ai-assistant`): Workspace + Core **115
  passed, 1 skipped** (thêm 8 test: hỏi đáp có nguồn, khóa API không lộ, bài ẩn/xóa không được dùng,
  lỗi dịch vụ không trừ lượt, giới hạn/ngày, chỉ một dịch vụ đang dùng, Claude qua SDK có
  fallbacks/effort và bắt `refusal`, cấu trúc request Gemini/DeepSeek, tìm kiến thức không dấu,
  sinh bài từ gói nghiệp vụ); `npm run test` **49 passed**; lint, typecheck, build, ruff, kiểm SPDX
  đạt. Alembic upgrade → downgrade 0011 → upgrade bằng SQLite tạm đạt; thử riêng việc cấp/thu hồi
  `assistant.manage` cho vai trò có sẵn: đúng. Dịch vụ AI **chỉ được giả lập** (transport giả):
  chưa gọi thật Claude/OpenAI/Gemini/DeepSeek với khóa thật. Giao diện kiểm bằng API giả lập
  (Chromium 1440 px sáng/tối, 390 px không tràn ngang).
  Bổ sung cổng riêng (migration `workspace_0013`): Workspace + Core **118 passed, 1 skipped** (thêm 3
  test: kiểm URL — HTTP, IP nội bộ/link-local, tên trỏ một phần về loopback, có user:pass, có query
  bị từ chối; danh sách trắng cho cổng nội bộ; cấu trúc request 3 giao thức; tên miền đổi sang IP
  nội bộ bị chặn ở lần gọi sau; luồng tạo cổng → hỏi đáp qua cổng). DNS và cổng đều **giả lập**,
  chưa gọi một gateway thật.
- Core outbox được lưu pending; chưa có external dispatcher/event-trigger delivery.
  Worker DB poll/reconciler của run không chứng minh pipeline broker đã hoạt động.

## Checklist bắt buộc với deployment thực

| Mã | Kịch bản | Điều kiện đạt | Kết quả deployment |
|---|---|---|---|
| I01 | Bootstrap/cài sạch | Không dùng credential riêng của tác giả, migration jobs thành công | Chưa chạy stack thật |
| I02 | SSO Workspace/Core | State/nonce/PKCE, issuer/audience, CSRF/session hoạt động | Đã chạy 28/10: đăng nhập SSO qua Keycloak + gateway bằng Playwright; chưa kiểm riêng state/nonce/PKCE |
| I03 | Core độc lập | Dừng Workspace, generic schema/record/file/run vẫn dùng được | Đã chạy 28/10: dừng Workspace, `examples/core-client` vẫn tạo schema/record/file/run |
| I04 | Namespace | Token equipment không thấy workspace, body không đổi namespace | Cần API integration |
| I05 | ACL và metadata | User ngoài quyền không đọc tên/snippet/bytes/version | Một phần 31/10: `test_access_matrix.py` (tệp, hồ sơ, công việc, tìm kiếm, báo cáo, tác nhân service); chưa phủ import evidence AI và token namespace khác phía Workspace |
| I06 | Revision/idempotency | Retry cùng intent trả cùng kết quả; khác body 409 | Cần API tests |
| I07 | File hold | File được submission pin không bị GC | Cần storage integration |
| I08 | Hồ sơ | Tạo → gửi → trả lại → sửa → trình lại → duyệt có lịch sử/snapshot đúng | Một phần 28/10: E2E tạo hồ sơ nháp và tải lại; luồng gửi/trả lại/duyệt mới kiểm bằng pytest |
| I09 | Concurrency | Hai decision cùng revision chỉ một có hiệu lực | Cần PostgreSQL thật |
| I10 | Outbox crash | Kill sau tác động/trước ACK không tạo hai run/decision | Cần fault injection |
| I11 | Office cộng tác | Hai user cùng document key, lưu bền vững đúng file/version | Một phần 31/10: một user mở, sửa, lưu thành phiên bản 2 qua Docs thật; chưa kiểm hai user |
| I12 | Office callback | JWT sai bị từ chối, trùng không thêm version, muộn không overwrite | SQLite/HTTP contract đã kiểm; cần Docs thật |
| I13 | Submit/save barrier | Đóng editor và nhận callback cuối trước submit; không âm thầm dùng bản cũ | Open-session barrier đã kiểm; chưa force-save, cần Docs thật |
| I14 | Grant revocation | Download/API chặn theo cửa sổ đã công bố; không giả chặn URL tức thì | Cần đo |
| I15 | Restore | Restore DB/objects/keys, references đúng, không replay action mù | Một phần 31/10: dump/restore 3 DB và objects sang project riêng, số dòng và hash khớp, API lên healthy; chưa kiểm SSO, tải file qua API, workflow resume, outbox (xem docs/operations.md) |

Backend test dùng SQLite hoặc in-process mock chỉ chứng minh đúng hành vi được
kiểm trong môi trường đó; PostgreSQL concurrency cần kiểm riêng. Office mock callback
không thay kiểm tương thích văn bản tiếng Việt/font/editor edition. Không thay
`chưa chạy` thành `đạt` chỉ vì lệnh syntax/build đã qua.

## Giới hạn hiện tại cần thể hiện trong demo

Drive đã có ACL kế thừa theo thư mục và API rename/move/xóa thư mục: folder share
kế thừa xuống mọi tài liệu trong cây, người được cấp quyền ghi được đổi tên/di chuyển,
còn trash và quản lý share folder chỉ chủ sở hữu. Test Workspace kiểm inheritance,
nested folder, cycle guard, move tính lại quyền và folder trashed chặn quyền ở mức
SQLite/in-process. Tài liệu Drive cũng đã có **nhãn** (chuẩn hóa, không trùng khi
khác hoa/thường) và **sao chép**: bản sao là file Core độc lập với resource và quota
riêng nên sửa bản sao không đụng version của bản gốc và share của bản gốc không lọ
sang bản sao. Chưa kiểm ACL trên PostgreSQL với dữ liệu folder sâu và concurrent
share/move. Form đã publish bất biến, tạo form/schema mới
khi đổi; chưa form-version-chain API. Chưa multiple memberships. Ủy quyền chỉ áp
dụng cho phê duyệt hồ sơ. Webhook thuộc luật tự động Workspace; engine workflow Core
vẫn chưa có action/HTTP connector. Chat giao nhận bằng polling REST, chưa WebSocket.
Worker dùng DB polling, không Celery. Chưa scan/AV.
Office content ticket TTL 8 giờ/session-scoped, không instant editor revocation.
Submit yêu cầu close + final callback, chưa force-save barrier. Các giới hạn này
không được mô tả là đã hoàn thiện chỉ vì happy path hồ sơ đã có test.

## Ngoài phạm vi đợt đầu

Các mục OCR/RAG, WebSocket realtime/reconnect cho chat, kiểm duyệt bảng tin, advanced
canvas/connector OAuth, parallel quorum, load p95, RPO/RTO mục tiêu trong thiết kế
**chưa nghiệm thu** và
không được coi đã hoàn thành bởi bản Core + e-Office này.
