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

Profile `core` chạy Core/SSO/storage độc lập, không có giao diện nào; `console` thêm
công cụ quản trị kỹ thuật Core admin; `workspace` thêm Workspace, web và Core admin. Profile `office` chỉ thêm editor, không tự thêm Workspace. Không chạy chỉ
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

## Sao lưu và khôi phục

Hai script chuẩn (Python stdlib, chạy trên Windows/Linux, cần Docker Compose; không in secret):

```bash
# Sao lưu: 3 DB (pg_dump -Fc) + volume object storage (tar.gz) + manifest.json (kích thước, SHA-256)
python scripts/backup.py --project dxos-main --env-file .env --out /duong/dan/ngoai/repo

# Khôi phục vào project đích đã chạy sẵn postgres + object-storage (cùng mật khẩu .env)
docker compose -p dx-restore --env-file .env -f infra/compose/compose.yaml --profile core up -d --no-deps postgres object-storage
python scripts/restore.py <thu-muc-backup> --project dx-restore --env-file .env --confirm
```

`restore.py` kiểm SHA-256 trước, từ chối chạy thiếu `--confirm`, từ chối nếu DB đích đã có bảng (trừ `--force`,
dùng `pg_restore --clean`), và không dùng `--no-owner` (xem lỗi 31/10 bên dưới).

**Có phạm vi:** `dx_core`, `dx_workspace`, `dx_identity` (gồm realm/user Keycloak đã lưu trong DB) và toàn bộ object
storage (RustFS). **Chưa phạm vi:** `.env` và khóa mã hóa (backup tách biệt, có kiểm soát truy cập), dữ liệu
ONLYOFFICE, broker (cache), realm JSON sinh từ bootstrap, image/source. Tar volume khi hệ thống đang ghi không phải
snapshot nhất quán giữa DB và object; muốn RPO chặt thì dừng ghi trong lúc sao lưu.

### Diễn tập đo 28/11/2026 (Docker Desktop 29.9 trên Windows 11, máy phát triển 20 luồng CPU, PostgreSQL 17.5)

Nguồn: stack đang chạy `dxos-main` (chỉ đọc, không dừng); đích: project tạm `dxos-restore-test` chỉ gồm
`postgres` và `object-storage`, đã `down -v` sau khi đối chiếu.

| Mục | Kết quả |
|---|---|
| Backup | 3,9 giây (dx_core 82.561 B, dx_workspace 747.531 B, dx_identity 217.920 B, objects.tar.gz 10.831 B) |
| Restore (gồm kiểm SHA-256, dừng/khởi động lại object-storage) | 6,2 giây |
| Đối chiếu số dòng | khớp: records 10, audit_logs 65, storage_files 7, human_tasks 9, resources 17 (Core); cases 10, tasks 7, users 6, audit_logs 134, drive_files 7 (Workspace); user_entity 9, client 17 (Identity) |
| Object | 23 tệp / 179.381 B ở nguồn; mọi tệp dữ liệu giống hệt về đường dẫn và kích thước ở đích (đích có thêm 1 tệp khóa 0 B do RustFS tự tạo khi chạy) |
| Từ chối an toàn | thiếu `--confirm` bị chặn; DB đích có 23 bảng bị chặn khi không có `--force` |

Giải thích số: dữ liệu demo rất nhỏ nên thời gian ngắn; RTO thực tế sẽ tăng theo kích thước dữ liệu và chưa gồm
thời gian dựng hạ tầng, nạp `.env`, khởi động API/gateway. Chưa đo: đăng nhập SSO trên môi trường đã khôi phục,
tải tệp qua API, workflow đang chờ.

**RPO khuyến nghị:** sao lưu mỗi ngày (cron/Task Scheduler gọi `backup.py`), tức mất tối đa tới 24 giờ dữ liệu;
giảm xuống theo nhu cầu vì một lần backup chỉ mất vài giây ở quy mô này. **RTO đã đo:** 6,2 giây cho bước khôi phục
dữ liệu ở quy mô demo; hãy đo lại trên dữ liệu thật của bạn trước khi cam kết.

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

### Kết quả diễn tập 31/10/2026 (Docker Desktop/Windows, PostgreSQL 17.5, dữ liệu demo nhỏ)

Quy trình: dừng `core-api`, `workspace-api` và hai worker; `pg_dump -Fc` ba DB; `tar` volume object-storage;
khởi động lại nguồn; dựng project Compose riêng (`-p dx-restore`, volume mới) và khôi phục vào đó.

- Backup 9 giây, restore 10 giây (DB dump 47 KB / 134 KB / 218 KB, objects 29 KB, 19 tệp). Đây là số quan sát
  trên dữ liệu rất nhỏ, **không** dùng làm RPO/RTO.
- Đối chiếu: số dòng của mọi bảng khớp (Core 23 bảng, Workspace 47, Keycloak 88); hash tổng và số tệp object khớp;
  `alembic_version` là `workspace_0013` / `core_0002`; `core-api` và `workspace-api` lên `healthy` trên dữ liệu đã
  khôi phục, job migration không đổi gì.
- **Lỗi quy trình đã gặp:** `pg_restore --no-owner` làm bảng thuộc `dx_bootstrap`, role `dx_core` mất quyền
  (`permission denied for table alembic_version`) và `core-migrate` thất bại. Khôi phục **không** dùng `--no-owner`
  (các role đã được `init-databases.sh` tạo trên môi trường mới), hoặc cấp lại quyền sau restore.
- Chưa kiểm: SSO và đăng nhập trên môi trường đã khôi phục (không dựng gateway), tải tệp đúng hash qua API,
  tiếp tục workflow đang chờ, đối soát outbox/unknown outcome, khóa mã hóa và `.env` (dùng lại đúng `.env` của nguồn),
  snapshot nhất quán khi hệ thống đang ghi (lần này dừng ghi trước khi sao lưu), Office data.

## Dừng và dữ liệu

`docker compose ... stop` dừng mà giữ dữ liệu. `down` giữ named volumes theo mặc
định; `down -v` xóa dữ liệu vĩnh viễn và **không** là lệnh reset an toàn. Chỉ xóa
volume demo sau khi kiểm đúng deployment và được người vận hành cho phép.
