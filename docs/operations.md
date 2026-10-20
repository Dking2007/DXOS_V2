# Vận hành, backup và phục hồi

## Lệnh thường dùng (từ thư mục gốc)

```bash
python scripts/bootstrap.py
# Bật Docker Desktop trước, dùng Linux containers.
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace up --build -d
python scripts/seed.py --confirm-demo
# Tùy chọn editor, cùng deployment: sửa ONLYOFFICE_ENABLED=true trong .env trước.
# Recreate workspace-api/worker để nhận cấu hình mới.
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace --profile office up -d
```

Profile `core` chạy Core/SSO/console/storage độc lập; `workspace` thêm Workspace và
web. Profile `office` chỉ thêm editor, không tự thêm Workspace. Không chạy chỉ
`--profile office` rồi mong toàn nền tảng xuất hiện. Không đổi project name giữa
các lệnh nếu muốn dùng cùng volume.

```bash
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace ps
docker compose --env-file .env -f infra/compose/compose.yaml --profile workspace logs --tail 100 core-api workspace-api core-worker workspace-worker
```

Migration là one-shot service `core-migrate`/`workspace-migrate`. Sau đổi migration,
chạy lại job migrate có chủ ý; không cho mỗi process API tự migrate. Nếu migration
job lỗi, API không được khởi động thành công giả.

## Readiness và lỗi phổ biến

- Docker báo `dockerDesktopLinuxEngine` không tồn tại: bật Docker Desktop, chờ engine
  ready, kiểm `docker info`. Đây không phải lỗi source code.
- Keycloak chưa ready: chờ startup/import, đọc log identity; kiểm public issuer và
  client callback. Không tắt audience/issuer validation để né lỗi.
- URL Office không tải/callback không tới: phân biệt browser public URL và URL giữa
  container; `localhost` trong container không phải host hoặc container khác.
- Login sau khi regenerate secret không chạy: realm cũ vẫn giữ secret cũ. Bootstrap
  không rotate dữ liệu đã lưu. Không xóa volume để sửa lỗi production.
- Seed không tìm subject: chỉ seed từ `demo-users.json` đi cùng realm đã import.

## Backup

Chưa có cam kết RPO/RTO. Đặt lịch chỉ sau khi restore đã thử và đo. Tối thiểu backup:
1. Ba database PostgreSQL (Core/Workspace/Keycloak), cùng mốc phù hợp.
2. Toàn bộ object data của RustFS và các immutable file version liên quan.
3. `.env`/realm/config và khóa mã hóa được bảo vệ tách biệt.
4. Office durable data nếu có phiên đang xử lý; không coi Office data thay Core bytes.
5. Phiên bản source/image/migration và file inventory.

Ví dụ dump DB vào stdout (dùng công cụ backup ghi binary an toàn; không dựa vào
PowerShell bản cũ để redirect binary):

```bash
docker compose --env-file .env -f infra/compose/compose.yaml exec -T postgres pg_dump -U dx_bootstrap -d dx_core -Fc > backups/core.dump
```

Lệnh ví dụ không tự backup objects hoặc khóa; không coi một DB dump là full backup.
Nếu cần snapshot nhất quán, tạm dừng tác vụ ghi hoặc dùng quy trình snapshot/WAL
và object retention đã được kiểm chứng. Giữ quyền truy cập backup vì chứa dữ liệu
nhạy cảm. Không thực hiện xóa blob/GC khi chưa đối soát holds/references.

## Restore có kiểm soát

1. Tạo môi trường phục hồi riêng, không ghi đè deployment đang dùng.
2. Chặn worker/action tác động ra ngoài; dừng dispatcher trước khi đưa DB lên.
3. Khôi phục config/secret và Keycloak/DB/objects tương ứng; đối chiếu phiên bản.
4. Kiểm schema migration, checksum/version references, submission snapshots/holds.
5. Đối soát outbox pending, lease hết hạn, run waiting và unknown outcomes; không
   replay hàng loạt action ngoài khi chưa biết action cũ đã thành công hay chưa.
6. Rebuild cache/projection nếu có; bật Core rồi Workspace, dispatcher/worker sau.
7. Smoke SSO, metadata và download đúng hash, hồ sơ/approval history, workflow resume.
8. Ghi thời gian thực tế và mất dữ liệu nếu có trước khi đặt mục tiêu RPO/RTO.

## Dừng và dữ liệu

`docker compose ... stop` dừng mà giữ dữ liệu. `down` giữ named volumes theo mặc
định; `down -v` xóa dữ liệu vĩnh viễn và **không** là lệnh reset an toàn. Chỉ xóa
volume demo sau khi kiểm đúng deployment và được người vận hành cho phép.
