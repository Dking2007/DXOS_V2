# DX Workspace

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
hoặc event-trigger delivery**. Không xem event automation hay delivery qua broker là
tính năng đã hoạt động. Trạng thái bền vững ở DB.

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
  phiên bản form. Chưa hỗ trợ nhiều membership hoặc ủy quyền phê duyệt.
- Office chặn submit khi phiên chỉnh sửa còn mở; phải đóng editor và nhận callback
  cuối hợp lệ trước khi trình. Đây **không phải force-save barrier**. Content ticket
  Office có TTL 8 giờ và gắn session; thu hồi share không đẩy người đang mở editor
  ra ngay lập tức. Chưa kiểm Document Server thật hoặc cộng tác hai browser.
- Workflow chưa có action/HTTP connector và external event dispatcher. File có
  kiểm định dạng/giới hạn cơ bản, **chưa có quét antivirus/malware**.
- PostgreSQL concurrency, SSO thật và cài sạch bằng Docker vẫn cần nghiệm thu.

## Phạm vi hoãn

Chưa bao gồm task module độc lập, chat, feed, OCR/RAG/LLM, dashboard phân tích nâng cao,
automation canvas nâng cao, arbitrary HTTP/credential connector, phê duyệt quorum,
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
