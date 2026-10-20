# Kiểm chứng và checklist nghiệm thu

## Trạng thái tại thời điểm tạo bộ cài

Đây là checklist thực thi, không phải báo cáo tích xanh theo thiết kế. Người chạy
release phải ghi commit/source snapshot, dependency lock, image digest, cấu hình,
lệnh, ngày chạy và kết quả. Không suy ra test đạt chỉ vì đã có endpoint hoặc UI.

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
- `python -m pytest -q` (WorkMMODIARY): **35 passed, 2 warnings** — 28 test luồng
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
- Core outbox được lưu pending; chưa có external dispatcher/event-trigger delivery.
  Worker DB poll/reconciler của run không chứng minh pipeline broker đã hoạt động.

## Checklist bắt buộc với deployment thực

| Mã | Kịch bản | Điều kiện đạt | Kết quả deployment |
|---|---|---|---|
| I01 | Bootstrap/cài sạch | Không dùng credential riêng của tác giả, migration jobs thành công | Chưa chạy stack thật |
| I02 | SSO Workspace/Core | State/nonce/PKCE, issuer/audience, CSRF/session hoạt động | Cần Keycloak thật |
| I03 | Core độc lập | Dừng Workspace, generic schema/record/file/run vẫn dùng được | Cần stack |
| I04 | Namespace | Token equipment không thấy workspace, body không đổi namespace | Cần API integration |
| I05 | ACL và metadata | User ngoài quyền không đọc tên/snippet/bytes/version | Cần test quyền |
| I06 | Revision/idempotency | Retry cùng intent trả cùng kết quả; khác body 409 | Cần API tests |
| I07 | File hold | File được submission pin không bị GC | Cần storage integration |
| I08 | Hồ sơ | Tạo → gửi → trả lại → sửa → trình lại → duyệt có lịch sử/snapshot đúng | Cần E2E |
| I09 | Concurrency | Hai decision cùng revision chỉ một có hiệu lực | Cần PostgreSQL thật |
| I10 | Outbox crash | Kill sau tác động/trước ACK không tạo hai run/decision | Cần fault injection |
| I11 | Office cộng tác | Hai user cùng document key, lưu bền vững đúng file/version | Cần Docs thật |
| I12 | Office callback | JWT sai bị từ chối, trùng không thêm version, muộn không overwrite | SQLite/HTTP contract đã kiểm; cần Docs thật |
| I13 | Submit/save barrier | Đóng editor và nhận callback cuối trước submit; không âm thầm dùng bản cũ | Open-session barrier đã kiểm; chưa force-save, cần Docs thật |
| I14 | Grant revocation | Download/API chặn theo cửa sổ đã công bố; không giả chặn URL tức thì | Cần đo |
| I15 | Restore | Restore DB/objects/keys, references đúng, không replay action mù | Chưa diễn tập |

Backend test dùng SQLite hoặc in-process mock chỉ chứng minh đúng hành vi được
kiểm trong môi trường đó; PostgreSQL concurrency cần kiểm riêng. Office mock callback
không thay kiểm tương thích văn bản tiếng Việt/font/editor edition. Không thay
`chưa chạy` thành `đạt` chỉ vì lệnh syntax/build đã qua.

## Giới hạn hiện tại cần thể hiện trong demo

Drive đã có ACL kế thừa theo thư mục và API rename/move/xóa thư mục: folder share
kế thừa xuống mọi tài liệu trong cây, người được cấp quyền ghi được đổi tên/di chuyển,
còn trash và quản lý share folder chỉ chủ sở hữu. Test WorkMMODIARY kiểm inheritance,
nested folder, cycle guard, move tính lại quyền và folder trashed chặn quyền ở mức
SQLite/in-process. Tài liệu Drive cũng đã có **nhãn** (chuẩn hóa, không trùng khi
khác hoa/thường) và **sao chép**: bản sao là file Core độc lập với resource và quota
riêng nên sửa bản sao không đụng version của bản gốc và share của bản gốc không lọ
sang bản sao. Chưa kiểm ACL trên PostgreSQL với dữ liệu folder sâu và concurrent
share/move. Form đã publish bất biến, tạo form/schema mới
khi đổi; chưa form-version-chain API. Chưa multiple memberships/delegation hoặc
workflow action/HTTP connector. Worker dùng DB polling, không Celery. Chưa scan/AV.
Office content ticket TTL 8 giờ/session-scoped, không instant editor revocation.
Submit yêu cầu close + final callback, chưa force-save barrier. Các giới hạn này
không được mô tả là đã hoàn thiện chỉ vì happy path hồ sơ đã có test.

## Ngoài phạm vi đợt đầu

Các mục OCR/RAG, chat/WS reconnect, feed privacy, advanced canvas/HTTP connector,
parallel quorum, load p95, RPO/RTO mục tiêu trong thiết kế **chưa nghiệm thu** và
không được coi đã hoàn thành bởi bản Core + e-Office này.
