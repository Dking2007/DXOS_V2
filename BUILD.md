# BUILD — Biên dịch và cài đặt Desktiny từ mã nguồn

Hướng dẫn từ máy sạch (Ubuntu 24.04) đến chạy được. Không bước nào đòi sửa tay mã
nguồn hay tệp header; cấu hình qua biến môi trường / tệp `.env` sinh tự động.
Bản chi tiết hơn (Windows, ONLYOFFICE, xử lý sự cố): [docs/installation.md](docs/installation.md).

## 1. Yêu cầu

| Công cụ | Phiên bản | Ghi chú |
|---|---|---|
| Git | ≥ 2.34 | |
| Python | 3.13 | `apt install python3.13 python3.13-venv` (hoặc deadsnakes) |
| Node.js + npm | 22 LTS / 10 | https://nodejs.org hoặc NodeSource |
| make | GNU Make ≥ 4 | `apt install make` |
| libpq5 | bất kỳ | `apt install libpq5` — thư viện PostgreSQL mà `psycopg` nạp lúc chạy |
| Docker Engine + Compose v2 | ≥ 24 | **chỉ** cho cách A (chạy cả nền tảng) |

Phụ thuộc thư viện được khóa trong `requirements.lock` (pip) và `package-lock.json`
(npm), lấy từ trình quản lý gói; repo không chứa mã thư viện của bên khác.
Danh sách đầy đủ và giấy phép: [THIRD_PARTY.md](THIRD_PARTY.md).

## 2. Cách A — Docker Compose (toàn bộ nền tảng, có SSO)

```bash
git clone https://github.com/Raphael-Fug/DXOS_V2.git && cd DXOS_V2
make up                       # bootstrap .env, build image, khởi động, nạp dữ liệu demo
# cổng khác: make up BASE_URL=http://localhost:8090
```

Mở http://localhost:8080/ . Tài khoản demo ngẫu nhiên nằm ở
`infra/identity/generated/demo-credentials.txt`. Dừng: `make down`.

## 3. Cách B — Biên dịch trực tiếp (không Docker)

```bash
git clone https://github.com/Raphael-Fug/DXOS_V2.git && cd DXOS_V2
make venv deps PYTHON=python3.13   # môi trường ảo Python 3.13 + npm ci (Ubuntu 24.04: python3 mặc định là 3.12)
make build                    # biên dịch frontend → apps/*/dist
make test                     # pytest + vitest
make install PREFIX=$HOME/desktiny   # cài ra ngoài thư mục mã nguồn
```

Sau `make install`, gói Python (`dx_core`, `dx_workspace`, `dx_platform_kit`) nằm dưới
`$PREFIX/lib/python3.13/site-packages`, web tĩnh dưới `$PREFIX/share/desktiny/`, migration
CSDL ở `$PREFIX/share/desktiny/{core,workspace}-api/`, lệnh `$PREFIX/bin/desktiny-migrate`, cấu hình mẫu ở
`$PREFIX/share/desktiny/config/env.example`. Có thể xóa thư mục mã nguồn rồi chạy:

```bash
export PYTHONPATH=$HOME/desktiny/lib/python3.13/site-packages
export DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/DB   # mỗi service một DB
$HOME/desktiny/bin/desktiny-migrate core          # tạo/cập nhật bảng (alembic upgrade head)
python3.13 -m uvicorn dx_core.main:app --host 127.0.0.1 --port 8001
```

Các biến cấu hình (URL, secret, issuer SSO…) liệt kê trong `.env.example`; `python scripts/bootstrap.py`
sinh giá trị ngẫu nhiên. Backend vẫn cần PostgreSQL, Keycloak và S3 cho tích hợp thật
(xem README, mục *Phát triển local*). Chỉ xem giao diện: `npm run dev` rồi mở http://localhost:5173/
(API sẽ lỗi nếu không có backend).

### Thư viện hệ thống

Bản dựng không đính kèm thư viện của dự án khác. Từ bản 0.2.2, dự án dùng `psycopg==3.2.10` thuần Python
(không `[binary]`, không còn wheel đóng gói sẵn libpq) và nạp `libpq5` của hệ điều hành lúc chạy. Cần `apt install libpq5`
trước khi chạy backend; image Docker `api.Dockerfile` đã cài sẵn.

## 4. Kiểm thử và kiểm tra tuân thủ

```bash
make lint test                # ruff, eslint, vue-tsc, pytest, vitest
pipx install reuse && make reuse    # giấy phép từng tệp (REUSE)
make licenses                 # cập nhật THIRD_PARTY.md từ lockfile
```

## 5. Đóng gói bản phát hành

```bash
make dist                     # dist/dxos-<phiên bản>.tar.gz + dist/SHA256SUMS
```

Đẩy tag `vX.Y.Z` thì workflow `.github/workflows/release.yml` tự tạo Release kèm tar.gz.

## 6. Lỗi thường gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `python3.13: not found` | Cài Python 3.13 (deadsnakes): `add-apt-repository ppa:deadsnakes/ppa && apt install python3.13 python3.13-venv` |
| `make install`: `No module named pip` | Chạy `make venv PYTHON=python3.13` trước; `make install` dùng pip trong `.venv`, không dùng pip hệ thống |
| `permission denied` với docker | Thêm user vào group `docker`, đăng nhập lại |
| Cổng 8080 bận | `make up BASE_URL=http://localhost:8090` ngay từ lần bootstrap đầu |
| `bootstrap.py` từ chối ghi đè | `.env` đã tồn tại; xóa `.env` và `infra/identity/generated/` **và** volume nếu muốn tạo lại |
| `npm ci` lệch lockfile | Dùng Node 22 + npm 10; không chạy `npm install` rồi commit lockfile mới tùy ý |

> Ghi chú trung thực: cách B (`make venv deps`, `build`, `test`, `install`, `desktiny-migrate`, `uvicorn`) đã được chạy từng
> dòng trong container `ubuntu:24.04` sạch ngày 27/10/2026. Cách A (`make up`, toàn bộ nền tảng với SSO) chưa được chạy thử
> trong lần này. Mục [SELF_REVIEW.md](SELF_REVIEW.md) ghi rõ phần đã kiểm và chưa kiểm.
