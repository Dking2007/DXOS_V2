# Cài đặt và chạy thử DX Workspace

Hướng dẫn hai đường: **Docker Compose** (chạy được toàn bộ nền tảng, khuyên dùng) và
**chạy cục bộ thuần** (chỉ cho phát triển/test, không có SSO thật). Các lệnh chạy từ
**thư mục gốc repo** trừ khi ghi rõ khác.

> Đây là bản pilot/phát triển. Compose trong repo là cấu hình **dev**, không phải
> production. Không dùng `.env` do bootstrap sinh cho môi trường thật.

---

## 1. Yêu cầu

| Thành phần | Phiên bản / ghi chú |
|---|---|
| Docker Engine + Compose v2 | Bắt buộc cho phương án A |
| Python | **3.13** (bootstrap chỉ dùng stdlib; môi trường ảo dùng 3.13) |
| Node.js | **22 LTS** + npm 10 |
| Dung lượng | ≥ 8 GB trống (PostgreSQL, Keycloak, RustFS, ONLYOFFICE nếu bật) |
| RAM | ≥ 6 GB; ONLYOFFICE nên có ≥ 8 GB |
| Cổng | `8080` trống (đổi được bằng `--base-url`) |

Image được dùng cố định phiên bản, không dùng `latest`: PostgreSQL `17.5-alpine`,
Keycloak `26.2.5`, RustFS `1.0.3`, Valkey `8.1.1-alpine`,
Nginx `1.28.0-alpine`, ONLYOFFICE `8.3.3`, Python `3.13.5-slim`, Node `22.17.0-alpine`.

Gateway chỉ bind `127.0.0.1:8080` nên **không** phơi ra mạng LAN theo mặc định. DB và
RustFS không publish cổng host.

---

## Phương án A — Docker Compose (khuyên dùng)

### A1. Ubuntu 22.04 / 24.04

**Cài Docker Engine** (không dùng snap, vì Compose v2 cần plugin chính thức):

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
```

**Đăng xuất rồi đăng nhập lại** để nhận quyền group `docker` (không đăng nhập lại thì
phải `sudo docker`, và mọi lệnh `docker compose` phía dưới đều cần `sudo`).

Kiểm tra:

```bash
docker version
docker compose version
docker info | grep -i "server version"   # báo lỗi permission → chưa đăng nhập lại
```

Nếu dùng SSH/headless, khởi động và bật tự chạy:

```bash
sudo systemctl enable --now docker
```

### A2. Windows 10/11

1. Cài **Docker Desktop for Windows**, chọn **WSL 2 backend**.
2. Bật WSL 2 nếu chưa có: `wsl --install` trong PowerShell admin, rồi khởi động lại.
3. Trong Docker Desktop → Settings → General, để **Use the WSL 2 based engine**.
4. Khởi động Docker Desktop, chờ biểu tượng ổn định, kiểm tra ở terminal:

```powershell
docker version
docker compose version
```

Lưu ý Windows:
- Chạy các lệnh bằng **Git Bash** hoặc **WSL 2 shell**, tránh `cmd`/PowerShell cũ khi
  redirect dữ liệu nhị phân (backup, `pg_dump`).
- `scripts/bootstrap.py` in trên Windows: *"restrict the generated files with your
  NTFS account permissions"* — file `.env` và `infra/identity/generated/` chứa secret,
  hãy giữ ranh giới tài khoản NTFS chặt.

### A3. Các bước chạy (giống nhau cả hai hệ điều hành)

```bash
cd <thư-mục-repo>

# 1. Sinh .env + realm Keycloak + credential ngẫu nhiên
python scripts/bootstrap.py

# 2. Build và khởi động profile workspace (đầy đủ Workspace + web + SSO + storage)
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace up --build -d

# 3. Nạp dữ liệu demo (hai phòng Hành chính / Kỹ thuật)
python scripts/seed.py --confirm-demo
```

`bootstrap.py` **từ chối chạy lại** nếu `.env` hoặc `infra/identity/generated/` đã tồn
tại — đây là chủ ý, để không xóa secret của deployment đang dùng. Muốn làm lại từ đầu
thì backup và tự xóa các file đó.

Script sinh secret ngẫu nhiên và **không in** ra màn hình. Đọc tài khoản tại:

```bash
infra/identity/generated/demo-credentials.txt
```

Không đưa file này hoặc `.env` lên màn hình chiếu, screenshot hay commit.

### A4. Kiểm tra và truy cập

```bash
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace ps
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace logs --tail 100 core-api workspace-api
```

`ps` phải cho `core-api`/`workspace-api` ở trạng thái `healthy` (vài phút đầu cho
migrate + Keycloak import). Nếu API không healthy, đọc log `core-migrate` /
`workspace-migrate` trước khi kết luận lỗi source.

| Đường dẫn | Nội dung |
|---|---|
| <http://localhost:8080/> | Workspace web |
| <http://localhost:8080/console/> | Core admin console |
| <http://localhost:8080/identity/admin/> | Keycloak console kỹ thuật |
| <http://localhost:8080/office/> | ONLYOFFICE (chỉ khi bật profile `office`) |

Migration là one-shot job `core-migrate` / `workspace-migrate`; API chỉ khởi động sau
khi job này thành công. **Không** sửa `.env` rồi mong thay đổi tự áp dụng — cần
`up -d` lại service liên quan.

### A5. Bật ONLYOFFICE (tùy chọn)

Editor khá nặng; không bật nếu chỉ dùng form và hồ sơ không cần chỉnh sửa văn bản.

```bash
# 1. Sửa .env: ONLYOFFICE_ENABLED=false → true
# 2. Khởi động thêm profile office
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace --profile office up -d
```

Lệnh trên phải recreate `workspace-api`/`workspace-worker` để nhận env mới; Compose tự
recreate khi env đổi, hoặc thêm `--force-recreate` cho hai service đó. Chờ Document
Server sẵn sàng rồi mới mở tài liệu từ Drive. Trên Windows, Docker Desktop có thể cần
được khởi động lại sau khi cài WSL integration trước khi pull được image
`onlyoffice/documentserver` (khoảng 1.5 GB).

Profile `office` **không** tự thêm Workspace — luôn đi kèm `--profile workspace`.

Khi `ONLYOFFICE_ENABLED=false`, editor **không hoạt động** — repo không có mock lưu tài
liệu để thay thế. Đây là chủ ý: không hiển thị lưu thành công giả.

### A6. Chỉ chạy Core độc lập

```bash
docker compose --env-file .env -f infra/compose/compose.yaml --profile core up --build -d
```

Truy cập `/console/`; trang Workspace `/` không có trong profile này. Client
`core-example` được bootstrap cấp namespace `equipment` (khác `workspace`); secret nằm
trong `.env` dưới `CORE_EXAMPLE_CLIENT_SECRET`. Ví dụ gọi API ở
[`examples/core-client`](../examples/core-client).

---

## Phương án B — chạy cục bộ thuần (phát triển / test)

Phương án này **không** cho bạn SSO thật, vì backend cần Keycloak, PostgreSQL và S3.
Nó dùng để chạy lint, unit test, typecheck và generate contract.

```bash
python -m venv .venv
# Windows Git Bash:  source .venv/Scripts/activate
# Linux/macOS:       source .venv/bin/activate
python -m pip install -r requirements-dev.txt
npm ci
```

Lệnh chạy được ở đường này:

```bash
python -m ruff check packages services scripts tests examples infra
python -m pytest -q
npm run lint
npm run typecheck
npm test
npm run build
npm audit
python scripts/export_contracts.py
npm run generate:api
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace --profile office config --quiet
```

Chạy API local mà không có PostgreSQL/Keycloak/S3 thì các route cần SSO sẽ không dùng
được; SQLite chỉ phục vụ test. Không thay SQLite bằng bài nghiệm thu SSO/concurrency.

---

## Tài khoản demo và luồng đầu tiên

Bootstrap tạo 8 identity trong Keycloak và 4 OIDC client. Đăng nhập các tài khoản này
(tên không phải mật khẩu — mật khẩu ngẫu nhiên nằm trong file credential):

| Tài khoản | Vai trò | Phòng |
|---|---|---|
| `director` | Ban giám đốc | administration |
| `manager` | Lãnh đạo phòng | administration |
| `staff` | Nhân viên | administration |
| `manager-b` | Lãnh đạo phòng | engineering |
| `staff-b` | Nhân viên | engineering |
| `technical-admin` | Quản trị kỹ thuật | — |

Luồng thử nhanh 5 phút:

1. Đăng nhập `staff` tại <http://localhost:8080/>.
2. **Drive** → tạo thư mục, upload tài liệu, gán **nhãn**, thử **Tạo bản sao**.
3. **Hồ sơ** → Tạo hồ sơ: chọn mẫu, đặt hạn xử lý + mức độ + người phụ trách.
4. Gửi hồ sơ; đăng nhập `manager` ở browser session khác → trả lại có lý do; `staff`
   sửa và trình lại; `manager` duyệt.
5. Đăng nhập `staff-b` mở thử tài liệu chưa chia sẻ — cả metadata lẫn bytes phải bị chặn.

Kịch bản demo đầy đủ: [demo.md](demo.md).

---

## Xử lý sự cố

| Hiện tượng | Nguyên nhân thường gặp / cách xử lý |
|---|---|
| `dockerDesktopLinuxEngine` không tồn tại | Docker Desktop chưa chạy. Chờ engine ready, kiểm `docker info`. Không phải lỗi source. |
| `permission denied` khi chạy docker (Ubuntu) | Chưa thêm user vào group `docker` hoặc chưa đăng nhập lại. |
| Cổng 8080 đã chiếm | `python scripts/bootstrap.py --base-url http://localhost:8090` từ đầu (xóa `.env`/`generated/` cũ trước). |
| Keycloak chưa ready | Chờ import realm xong, đọc `logs identity`. Không tắt kiểm issuer/audience để né lỗi. |
| Login lỗi sau khi regenerate secret | Realm cũ giữ secret cũ. Bootstrap không rotate dữ liệu đã lưu. |
| Seed báo "Run bootstrap first" | Thiếu `.env` hoặc `demo-users.json`. Chạy bootstrap trước seed. |
| Editor Office không lưu | Phân biệt URL public của browser và URL nội bộ container; `localhost` trong container không phải host. |
| `No such image: postgres:17.5-alpine` / `nginx` / `alpine` sau một lần `up` bị lỗi | Hệ quả kép: một image khác pull thất bại nên `up --build` bị ngắt giữa đường và các image kia chưa kịp kéo. Sửa image lỗi trước rồi chạy lại đúng lệnh `up --build -d`. |
| `pull access denied for minio/minio, repository does not exist or may require 'docker login'` | MinIO **không còn** publish image công khai trên Docker Hub lẫn `quay.io/minio/minio` — không phải lỗi đăng nhập. Repo hiện dùng RustFS (`rustfs/rustfs`), tương thích S3. Nếu bạn đang ở bản cũ hơn thì thay `image:` thành `rustfs/rustfs:1.0.3`, đổi `MINIO_ROOT_USER/PASSWORD` thành `RUSTFS_ACCESS_KEY/SECRET_KEY`, và dùng `command: [rustfs, --address, ":9000", --console-address, ":9001", /data]`. Nếu bạn tự đổi sang image khác, kiểm `docker manifest inspect <image>` trước. |
| Migration job lỗi | API không được khởi động thành công giả. Đọc log `core-migrate`/`workspace-migrate`. |

---

## Dừng, cập nhật, gỡ cài đặt

```bash
# Dừng mà giữ dữ liệu
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace stop

# Dừng và giữ named volume (mặc định)
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace down

# Sau khi đổi code/migration: build lại và chạy lại job migrate có chủ ý
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace up --build -d
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace run --rm core-migrate python -m alembic upgrade head
```

`down -v` **xóa dữ liệu vĩnh viễn**. Đây không phải lệnh reset an toàn cho deployment
đang dùng. Muốn dựng lại môi trường demo thì chỉ chạy sau khi đã xác nhận đúng
deployment cần xóa.

---

## Còn chưa nghiệm thu

Hướng dẫn này chạy được stack dev, nhưng các mục sau **chưa có bằng chứng trên máy
phát triển ban đầu** (thiếu Docker Engine và PostgreSQL) và cần kiểm trên môi trường
thật trước khi gọi là hoàn thiện: cài sạch idempotent, SSO qua gateway, concurrency
PostgreSQL, outbox fault injection, ONLYOFFICE cộng tác hai người, backup/restore.
Chi tiết: [acceptance.md](acceptance.md).
