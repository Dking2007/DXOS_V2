# Desktiny

*Desk + destiny — văn phòng số cho cơ quan.* (Tên cũ: DX Workspace; tên nội bộ trong mã
nguồn, cơ sở dữ liệu và container vẫn là `dx_workspace` / `dx-workspace`.)

Nền tảng Core dùng chung và ứng dụng e-Office, viết bằng **FastAPI + Vue 3 /
TypeScript**. Bản triển khai này tập trung một tổ chức: dữ liệu cấu trúc, file có
version, workflow generic và luồng hồ sơ/phê duyệt. Cơ sở thiết kế:
[`Thiet_ke_DX_Workspace_FastAPI_Vue3.md`](Thiet_ke_DX_Workspace_FastAPI_Vue3.md).

> Đây là bản phát triển/pilot. Không coi danh sách thiết kế là tính năng đã được
> nghiệm thu, không coi Compose dev là cấu hình production. Kết quả và những bước
> cần dịch vụ thật được phân biệt trong [acceptance](docs/acceptance.md).

## Kiến trúc

| Tầng | Thành phần | Quyền sở hữu |
|---|---|---|
| Core | FastAPI, worker, Core admin, Keycloak, Nginx | Principal/ACL, schema/record, storage/version, workflow |
| Workspace | FastAPI, worker, web Vue | Tổ chức, Drive, form, hồ sơ, submission, quyết định |
| Tích hợp | PostgreSQL, RustFS, ONLYOFFICE tùy chọn | DB riêng mỗi service; private bytes; editor riêng |

Không share ORM hoặc SQL xuyên database. Payload live ở Core; Workspace giữ
snapshot đã trình, metadata và quyết định nghiệp vụ. Core phải phục vụ client
khác khi Workspace tắt. Xem [architecture](docs/architecture.md).

## Chạy bằng Docker Compose

### 1. Điều kiện

- Docker Desktop đang chạy Linux containers, Docker Compose v2; kiểm `docker info`.
- Python 3.13 cho bootstrap (stdlib, không cần cài dependency trước).
- Dung lượng và RAM đủ cho PostgreSQL, Keycloak và tùy chọn Document Server.
  ONLYOFFICE tương đối nặng; không bắt buộc bật để dùng form/hồ sơ không cần editor.
- Cổng local `8080` trống. Tất cả lệnh dưới chạy ở thư mục gốc repo.

### 2. Sinh cấu hình dev và credential riêng

```bash
python scripts/bootstrap.py
```

Script tạo `.env` và `infra/identity/generated/` có realm, subject demo và credential
ngẫu nhiên. **Không ghi mật khẩu cố định trong source**; không commit các file này.
Đọc tài khoản tại `infra/identity/generated/demo-credentials.txt` trên máy của bạn.
Script từ chối overwrite nếu đã có cấu hình; đổi `.env` không rotate mật khẩu đã
lưu trong database/Keycloak. Không dùng script này để provision production.

Nếu cần cổng khác, chạy bootstrap ngay từ đầu với
`python scripts/bootstrap.py --base-url http://localhost:8090`.

### 3. Build và khởi động

```bash
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace up --build -d
python scripts/seed.py --confirm-demo
```

- Workspace: <http://localhost:8080/>
- Core admin: <http://localhost:8080/console/>
- Keycloak console kỹ thuật: <http://localhost:8080/identity/admin/>
- Đăng nhập SSO bằng tài khoản do bootstrap tạo: `director`, `manager`, `staff`,
  `manager-b`, `staff-b`, `technical-admin`. Tên không phải mật khẩu.
- Seed tạo hai phòng Hành chính/Kỹ thuật và quan hệ demo từ subject của đúng realm.
  Dữ liệu giả được ghi nhãn; không mặc định có quyền đọc chéo mọi nội dung.

Migration chạy bằng one-shot jobs, API chỉ khởi động sau migration thành công.
DB và storage không publish cổng host. Có thể đọc readiness trong container hoặc
qua `docker compose ... ps`; không mở tuyến health/internal public chỉ để test.

### 4. Bật ONLYOFFICE khi cần

```bash
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace --profile office up -d
```

Trước khi chạy lệnh trên, đổi `ONLYOFFICE_ENABLED=false` thành
`ONLYOFFICE_ENABLED=true` trong `.env` (không đổi JWT secret của phiên đang mở).
Lệnh `up -d` phải recreate `workspace-api`/`workspace-worker` để nhận env mới;
Compose tự recreate khi env thay đổi, hoặc dùng `--force-recreate` cho hai service
nếu cần. Chờ Document Server sẵn sàng rồi mở tài liệu từ Drive. JWT dùng secret riêng được
bootstrap tạo. Browser truy cập `/office/`, container dùng URL nội bộ; không nhầm
`localhost` của container. Khi chưa bật dịch vụ, editor không hoạt động — không có
mock lưu tài liệu thay thế. Giữ logo/notice; kiểm edition/license khi phân phối.

### 5. Chỉ chạy Core

```bash
docker compose --env-file .env -f infra/compose/compose.yaml --profile core up --build -d
```

Truy cập `/console/`; trang Workspace `/` không có khi profile này đứng riêng.
Client `core-example` được bootstrap cấp namespace `equipment`, khác `workspace`;
secret nằm trong `.env` dưới `CORE_EXAMPLE_CLIENT_SECRET`. Dùng ví dụ ở
[`examples/core-client`](examples/core-client) để thử schema/record/file/workflow.
Không bật password/direct grant để tiện gọi API; dùng code flow hoặc service client
đúng capability.

## Phát triển local

Cài Python 3.13 và Node.js 22, tạo môi trường riêng. Backend vẫn cần PostgreSQL,
Keycloak và S3 cho các tích hợp thực; SQLite/test doubles không thay nghiệm thu
concurrency, SSO hoặc Office thật.

```bash
python -m venv .venv
# Git Bash/Linux/macOS: source .venv/Scripts/activate (Windows) hoặc .venv/bin/activate
python -m pip install -r requirements-dev.txt
npm ci
```

Mỗi backend chạy từ thư mục service để dùng đúng Alembic config; cấu hình
`DATABASE_URL` riêng, không cho hai service trỏ cùng DB. `PUBLIC_BASE_URL`, issuer,
redirect, CORS/cookie và Vite proxy phải thống nhất. `.env` gốc là đầu vào Compose,
không có nghĩa Python tự nạp toàn bộ env cho một process local.

```bash
# Terminal Core (sau cấu hình environment đúng):
# cd services/core-api
python -m alembic upgrade head
python -m uvicorn dx_core.main:app --host 127.0.0.1 --port 8001
# Terminal Workspace, cwd services/workspace-api:
python -m alembic upgrade head
python -m uvicorn dx_workspace.main:app --host 127.0.0.1 --port 8002
# Worker từng package, env DB tương ứng:
python -m dx_core.worker
python -m dx_workspace.worker
# Frontend:
npm run dev --workspace apps/workspace-web
npm run dev --workspace apps/core-admin
```

Worker hiện poll PostgreSQL và đối soát workflow run trong DB; Valkey trong Compose
là hạ tầng dự phòng cho mở rộng broker/cache, chưa phải Celery integration đã nghiệm
thu. Outbox Core hiện được ghi/giữ pending để truy vết, **chưa có external dispatcher
hoặc event-trigger delivery**. Luật tự động hóa của Workspace chạy trong worker
Workspace qua outbox của chính nó (xem bên dưới), không qua broker và không phải engine
workflow của Core. Trạng thái bền vững ở DB.

## Kiểm thử và hợp đồng

```bash
python -m ruff check packages services scripts tests examples infra
python -m pytest -q
python -m unittest discover -s infra/tests -v  # cần Docker Compose CLI, không cần daemon
python scripts/export_contracts.py
npm run generate:api
npm run lint
npm run typecheck
npm run test
npm run build
npm audit
# Kiểm cấu hình Compose, không cần engine để render:
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace --profile office config --quiet
```

Chỉ chạy các lệnh theo cấu hình test/dependency thực trong repo. Test doubles có
thể kiểm logic nhưng không chứng minh được khóa PostgreSQL, IAM/SSO, callback Office
hoặc bộ cài sạch. OpenAPI/contracts phải sinh từ API đang chạy, không duy trì API
không tồn tại để làm tài liệu trông đầy đủ. Xem [checklist](docs/acceptance.md).

## Giới hạn triển khai hiện tại

- Drive có **ACL kế thừa theo thư mục**: chia sẻ thư mục kế thừa xuống mọi tài liệu
  bên trong, kể cả thư mục con và tài liệu thêm sau; cấp quyền cao nhất trong tất cả
  đường dẫn kế thừa được áp dụng. Thư mục có tạo, đổi tên, di chuyển (chặn chu trình) và
  xóa. Rename/move cho phép người được chia sẻ quyền ghi; đưa vào thùng rác và quản lý
  chia sẻ chỉ chủ sở hữu, để không thể âm thầm rút quyền kế thừa.
- Tài liệu Drive có **nhãn** và **sao chép**. Nhãn là metadata riêng của Workspace,
  được chuẩn hóa (không trùng khi chỉ khác hoa/thường) nên đổi tên nhãn không cần upload
  lại. Sao chép tạo một file Core **độc lập** với resource và quota riêng: sửa bản sao
  không đụng lịch sử version của bản gốc, và share của bản gốc cũng không tự động lọ
  sang bản sao. Phần mở rộng được giữ nguyên để không đổi định dạng tài liệu.
- Hồ sơ có **hạn xử lý, mức độ ưu tiên và người phụ trách**; người nhận phải thuộc phạm
  vi đơn vị của hồ sơ. Form hỗ trợ **ẩn/hiện và giá trị mặc định theo điều kiện giữa
  các trường**; backend validate lại cả phần ẩn trước khi dữ liệu vào Core.
- Sau khi thay đổi chia sẻ hoặc di chuyển thư mục, quyền được cấp lại trên từng tài
  liệu; trong cửa sổ đó tài liệu trả `409 permissions_syncing` thay vì phục vụ quyền cũ.
- Form đã published là bất biến; thay đổi bằng form/schema mới, chưa có API chuỗi
  phiên bản form. Chưa hỗ trợ nhiều membership.
- **Giao việc** (`/tasks`): giao cho người hoặc đơn vị; trưởng đơn vị nhận việc giao cho
  đơn vị rồi phân công người chịu trách nhiệm. Trạng thái `draft → assigned → accepted →
  in_progress → submitted → completed`, nhánh `blocked/returned/cancelled`; trả lại, báo
  vướng mắc, hủy và đổi hạn bắt buộc lý do và được ghi lịch sử. Checklist phải xong mới
  nộp được; việc cha chỉ nghiệm thu khi mọi việc con đã xong/hủy. Lãnh đạo phòng giao
  trong phòng mình, ban giám đốc giao liên phòng. UI có danh sách, Kanban và nhóm theo hạn
  (chưa có lịch dạng tháng hay Gantt).
- **Nhắn tin** (`/chat`): hội thoại riêng, nhóm, kênh phòng ban, trao đổi gắn công việc/hồ
  sơ; reply, nhắc tên, cảm xúc, sửa/xóa tin của mình, read cursor, chống gửi trùng bằng
  `client_message_id`. Khi thêm thành viên chọn được cho xem toàn lịch sử hay chỉ từ lúc
  vào; rời/bị xóa khỏi nhóm thì API chặn đọc ngay. Quản trị không mặc định đọc chat riêng.
  **Giao nhận bằng polling REST** (4–15 giây), chưa có WebSocket/presence/typing.
  Gửi được **ảnh, video, âm thanh và tệp** (chọn, kéo thả hoặc dán; tối đa 10 tệp, mỗi tệp
  50 MB), xem ảnh phóng to, phát video ngay trong hội thoại, có đánh dấu "Đã xem". Tệp lưu
  trong Core dưới service principal của Workspace; mỗi lần xem Workspace kiểm tra lại thành
  viên, phạm vi lịch sử và tin nhắn chưa bị xóa. Chỉ ảnh/video/âm thanh hiển thị trực tiếp,
  loại khác luôn tải về. Core nhận thêm GIF/WebP, MP4/MOV/WebM, MP3/OGG/WAV, ZIP — đều kiểm
  tra chữ ký nội dung; SVG/HTML/tệp chạy được vẫn bị từ chối. Chưa có thumbnail/nén video
  và chưa hỗ trợ tua video theo byte range.
- **Khung làm việc dễ dùng hơn**: menu chia nhóm (Làm việc · Trao đổi · Tài liệu & báo cáo
  · Quản trị) ẩn mục không có quyền và hiện số việc đang chờ; nút **+ Tạo mới** ở thanh
  trên; **Ctrl + K** mở bảng lệnh tìm việc/hồ sơ/tài liệu và chạy lệnh; thông báo dạng
  bảng thả xuống, lọc theo loại, chia "Hôm nay/Trước đó", đánh dấu tất cả đã đọc
  (`POST /notifications/read-all`). Trang chủ là **Việc cần làm hôm nay**, lấy từ
  `GET /me/overview` (việc được giao, việc phòng cần phân công, kết quả cần nghiệm thu, hồ
  sơ chờ duyệt kể cả duyệt thay, lời nhắc), xếp quá hạn trước, có nút Nhận việc ngay trên
  danh sách. Chi tiết hồ sơ chia tab và có thanh quyết định dính đáy. Thiết lập có **bảng
  phân quyền theo vai trò** (`PATCH /roles/{key}`; không cho bỏ "Quản lý tổ chức" khỏi
  vai trò của chính người sửa) và tab Giao diện. Có **chế độ tối** (sáng/tối/theo máy, nhớ
  trên trình duyệt), thanh điều hướng dưới trên điện thoại, hướng dẫn lần đầu theo vai trò
  (nhớ theo trình duyệt, xem lại trong Thiết lập), thông báo nhanh sau thao tác, khung
  xương khi tải và hỏi lại trước khi bỏ thay đổi chưa lưu. Badge cập nhật mỗi 30 giây và
  khi chuyển trang, chưa đẩy tức thời.
- **Xem tệp ngay trong ứng dụng**: PDF, ảnh (PNG/JPEG/GIF/WebP), video, âm thanh và
  TXT/CSV mở trong khung xem ở Kho tài liệu, tab Tài liệu và bản đã trình của hồ sơ (đúng
  phiên bản đã trình), và tệp đính kèm trong chat. PDF được pdf.js vẽ thành hình (lật
  trang, phóng to, vừa khung) nên mã nhúng trong PDF không chạy; trình duyệt đọc tệp qua
  liên kết tải ngắn hạn sẵn có, Core vẫn trả `attachment` và không có endpoint mới. Văn bản
  chỉ hiện 512 KB đầu. Tệp Office vẫn mở bằng ONLYOFFICE; SVG/ZIP chỉ tải về.
- **Bảng tin** (`/feed`): bài toàn tổ chức hoặc phòng ban, thông báo chính thức (gửi
  notification cho phạm vi nhận), ghim, bình luận, cảm xúc, lưu bài. Nội dung là văn bản
  thuần (đường dẫn http/https tự thành liên kết). Bài đăng kèm được **tối đa 10 ảnh/video**
  (PNG/JPEG/GIF/WebP, MP4/WebM/MOV; chọn, kéo thả hoặc dán; migration `workspace_0011`):
  tệp tải lên trước và chỉ người tải xem được cho tới khi bài đăng; sau đó Workspace kiểm tra
  quyền xem bài ở mỗi lần đọc, bài bị xóa thì ảnh/video cũng ẩn. Bài hiện lưới ảnh, xem toàn
  màn hình có lướt ảnh. Chưa nén ảnh/tạo thumbnail, chưa tua video theo byte range, chưa có
  rich text hay kiểm duyệt trước khi đăng.
- **Tìm kiếm chung** (`/search`, ô tìm ở header) trên công việc, hồ sơ, tài liệu, bài
  viết, tin nhắn; lọc quyền trước khi đếm và cắt trang. Tìm trực tiếp trên bảng (không có
  chỉ mục full-text riêng), phù hợp quy mô pilot.
- **Báo cáo** (`/reports`): việc theo trạng thái, quá hạn, hoàn tất trễ, phân bổ theo
  người, hồ sơ theo trạng thái, số lần trả lại; mỗi chỉ số có định nghĩa và thời điểm
  tính. Xuất CSV công việc chạy đồng bộ, chưa có report job nền.
- **Ủy quyền phê duyệt** (trong `/approvals`): có thời hạn (tối đa 90 ngày), có lý do,
  thu hồi được; người được ủy quyền chỉ xử lý hồ sơ giao cho người ủy quyền, quyết định
  lưu cả người duyệt thật (`decided_by_id`) và người được đại diện. Không cho ủy quyền
  dây chuyền.
- **Thu hồi hồ sơ đã trình** khi chưa ai ra quyết định: nhiệm vụ duyệt đang chờ bị đóng
  ngay, worker hủy run Core, hồ sơ về bản nháp để trình lại.
- **Tự động hóa** (`/automations`, quyền `automations.manage`): **trình thiết kế luồng
  dạng canvas kiểu n8n** (Vue Flow). Kéo thả node Kích hoạt, Điều kiện (nhánh Đúng/Sai,
  "tất cả" hoặc "ít nhất một"), Chờ, Gửi thông báo, Tạo công việc, Gọi webhook; nối dây,
  cấu hình ở panel bên phải, chèn biến `{title}`… bằng một click; có 4 mẫu luồng. Lỗi cấu
  hình hiện ngay trên từng node (thiếu kết nối, vòng lặp, node treo…). **Chạy thử** với dữ
  liệu mẫu tô sáng đường đi trên canvas mà không tác động thật; **Lịch sử chạy** vẽ lại
  từng lượt chạy thật lên canvas. Luồng lưu dạng đồ thị DAG; mỗi lượt chạy ghim bản đồ thị
  lúc bắt đầu nên sửa luồng không ảnh hưởng lượt đang chạy; node Chờ tiếp tục qua outbox
  (tối đa 7 ngày, luồng bị tắt trong lúc chờ thì lượt chạy bị hủy). Luồng mới ở trạng thái
  tắt; mỗi sự kiện chạy một lần cho mỗi luồng; luồng không tự kích hoạt lại chính nó và
  chuỗi bị chặn ở độ sâu 3. Tạo việc chạy dưới quyền hiện tại của người tạo luồng.
  Mỗi luồng về công việc (trừ "Công việc được tạo") chọn được **Áp dụng cho**: *Mọi công
  việc* hoặc *Chỉ công việc được gắn*. Ở chế độ gắn, trang chi tiết công việc có khung
  **Luồng tự động** để người giao, người phụ trách hoặc lãnh đạo đơn vị nhận bật/tắt từng
  luồng đang bật cho việc đó; gắn/gỡ được ghi vào lịch sử công việc. Nút **Chạy ngay** chạy
  thật một luồng với một công việc/hồ sơ/bài viết có sẵn, kể cả khi luồng đang tắt; lịch sử
  chạy ghi rõ bản ghi và người chạy tay. Webhook chỉ gọi tới host trong `AUTOMATION_ALLOWED_HOSTS` (mặc định rỗng = tắt),
  gửi `Idempotency-Key`, khóa bí mật mã hóa bằng `CREDENTIAL_ENCRYPTION_KEY` và không
  trả lại qua API; quá thời gian chờ thì ghi "chưa rõ kết quả" và **không tự gửi lại**.
  Chưa có node vòng lặp, gọi HTTP đọc dữ liệu về, biểu thức tùy ý hay connector OAuth;
  editor dùng tốt nhất trên màn hình rộng (mobile xem và thêm node qua nút +).
- Office chặn submit khi phiên chỉnh sửa còn mở; phải đóng editor và nhận callback
  cuối hợp lệ trước khi trình. Đây **không phải force-save barrier**. Content ticket
  Office có TTL 8 giờ và gắn session; thu hồi share không đẩy người đang mở editor
  ra ngay lập tức. Chưa kiểm Document Server thật hoặc cộng tác hai browser.
- Engine workflow Core chưa có action/HTTP connector và external event dispatcher (webhook
  ở trên thuộc luật Workspace). File có kiểm định dạng/giới hạn cơ bản, **chưa có quét
  antivirus/malware**.
- PostgreSQL concurrency, SSO thật và cài sạch bằng Docker vẫn cần nghiệm thu.

## Phạm vi hoãn

Chưa bao gồm OCR/RAG/LLM, WebSocket realtime cho chat, Gantt/lịch tháng cho công việc,
dashboard tùy biến widget, node vòng lặp/biểu thức cho luồng tự động, connector OAuth2,
phê duyệt quorum,
SaaS đa tổ chức, chữ ký số pháp lý hoặc mobile native. Quyền tài khoản phê duyệt và
audit không thay chữ ký số. Không cam kết hiệu năng/RPO/RTO khi chưa đo.

## Vận hành và giấy phép

- [Cài đặt (Ubuntu/Windows, Docker và local)](docs/installation.md)
- [Vận hành/backup/restore](docs/operations.md)
- [Bảo mật, session/revocation và cấu hình dev](docs/security.md)
- [Inventory bên thứ ba](docs/third-party-inventory.md)
- [Kịch bản demo](docs/demo.md)
- [Gói nghiệp vụ, chạy thử và truy vết quy trình](docs/process-packages.md)

Code tự viết: [Apache-2.0](LICENSE), xem [NOTICE](NOTICE). ONLYOFFICE, RustFS và các
service/dependency giữ giấy phép của họ. Cần rà soát artifact, notice, source offer
và trademark đúng bản phát hành; tích hợp API không phải giấy miễn nghĩa vụ.

## Giấy phép

Mã nguồn do dự án tự viết phát hành theo **Apache License 2.0** (SPDX: `Apache-2.0`).

- **Vì sao chọn Apache-2.0**: giấy phép OSI rộng rãi, có điều khoản cấp quyền bằng sáng chế, tương thích với
  toàn bộ thư viện dùng trong dự án (MIT/BSD/Apache/MPL/PSF/OFL; psycopg LGPL-3.0 dùng như thư viện liên kết động,
  không sửa). Dịch vụ copyleft (ONLYOFFICE AGPL-3.0, tùy chọn) chạy riêng qua HTTP, không liên kết vào mã.
- Bản toàn văn: [LICENSE](LICENSE) (và [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt) theo chuẩn
  [REUSE](https://reuse.software/)). Mỗi tệp mã mang header `SPDX-License-Identifier`; tệp không ghi chú được
  khai báo trong [REUSE.toml](REUSE.toml). Kiểm bằng `reuse lint`.
- Thành phần bên ngoài và giấy phép của chúng: [THIRD_PARTY.md](THIRD_PARTY.md), thông báo: [NOTICE](NOTICE).

## Biên dịch, phát hành và đóng góp

- Cài đặt/biên dịch từ mã nguồn: [BUILD.md](BUILD.md) (`make venv deps build test`, `make install PREFIX=...`).
- Lịch sử phiên bản: [CHANGELOG.md](CHANGELOG.md); bản V2 khác V1 thế nào: [docs/V2_CHANGES.md](docs/V2_CHANGES.md).
- Báo lỗi / đề xuất: tab **Issues** của repo. Cách đóng góp: [CONTRIBUTING.md](CONTRIBUTING.md),
  [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), bảo mật: [SECURITY.md](SECURITY.md).
- Tự rà soát tiêu chí PoF OLP PMNM 2026: [SELF_REVIEW.md](SELF_REVIEW.md).

## Đóng góp ngược cho cộng đồng nguồn mở

Mục này ghi **trạng thái thật** của từng việc; sẽ cập nhật khi có link và kết quả. Tại thời điểm ghi (30/10/2026)
mới có một mục được gửi lên dự án bên ngoài (Keycloak) và chưa được người bảo trì xét.

| Việc | Dự án nhận | Link | Trạng thái | Ghi chú |
|---|---|---|---|---|
| Bổ sung 2 ghi chú còn thiếu cho mục "Migrating to 26.7.5" của hướng dẫn nâng cấp | Keycloak | Issue [keycloak#53650](https://github.com/keycloak/keycloak/issues/53650); PR [keycloak#54464](https://github.com/keycloak/keycloak/pull/54464) | **Đã gửi 30/10/2026, chờ người bảo trì xét** (chưa merge) | Sửa tài liệu +16 dòng, commit có Signed-off-by. Đã build tài liệu bằng Maven (Java 21) và kiểm đủ 4 ghi chú, liên kết hoạt động. Trạng thái sẽ đổi khi có kết quả; có dùng trợ lý AI soạn thảo, đã được người nộp xem lại |
| `dx-flowkit`: kiểm tra và chạy thử đồ thị quy trình JSON, không phụ thuộc thư viện ngoài | Gói độc lập tách từ Desktiny ([`packages/flowkit`](packages/flowkit)) | Chưa công bố ngoài kho này | **Chưa công bố** | 56 test đạt; cùng kết quả với mã gốc trên 20.000 ca ngẫu nhiên. Chưa lên PyPI hay kho riêng; chưa kiểm xem đã có gói tương tự |
| Lỗi quyền volume khi nâng RustFS lên image chạy non-root (uid 10001) | RustFS ([#8992](https://github.com/rustfs/rustfs/issues/8992)) | Không gửi | **Đã xem xét, không gửi** | Nhóm tự tái hiện lỗi, nhưng người bảo trì đã xử lý độc lập ngày 29/10/2026 (PR #9056) nên không còn gì để bổ sung. Bản vá `chown` cho compose của Desktiny đã soạn nhưng chưa áp dụng vào kho này |
