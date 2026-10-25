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
make venv deps                # môi trường ảo Python + npm ci
make build                    # biên dịch frontend → apps/*/dist
make test                     # pytest + vitest
make install PREFIX=$HOME/desktiny   # cài ra ngoài thư mục mã nguồn
```

Sau `make install`, gói Python (`dx_core`, `dx_workspace`, `dx_platform_kit`) nằm dưới
`$PREFIX/lib/python3.13/site-packages`, web tĩnh dưới `$PREFIX/share/desktiny/`, cấu hình
mẫu ở `$PREFIX/share/desktiny/config/env.example`. Có thể xóa thư mục mã nguồn rồi chạy:

```bash
export PYTHONPATH=$HOME/desktiny/lib/python3.13/site-packages
export DATABASE_URL=postgresql+psycopg://USER:PASS@HOST:5432/DB   # mỗi service một DB
python3.13 -m uvicorn dx_core.main:app --host 127.0.0.1 --port 8001
```

Các biến cấu hình (URL, secret, issuer SSO…) liệt kê trong `.env.example`; `python scripts/bootstrap.py`
sinh giá trị ngẫu nhiên. Backend vẫn cần PostgreSQL, Keycloak và S3 cho tích hợp thật
(xem README, mục *Phát triển local*). Chỉ xem giao diện: `npm run dev` rồi mở http://localhost:5173/
(API sẽ lỗi nếu không có backend).

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
| `python3.13: not found` | Cài Python 3.13 (deadsnakes) hoặc `make venv PYTHON=python3.13` |
| `permission denied` với docker | Thêm user vào group `docker`, đăng nhập lại |
| Cổng 8080 bận | `make up BASE_URL=http://localhost:8090` ngay từ lần bootstrap đầu |
| `bootstrap.py` từ chối ghi đè | `.env` đã tồn tại; xóa `.env` và `infra/identity/generated/` **và** volume nếu muốn tạo lại |
| `npm ci` lệch lockfile | Dùng Node 22 + npm 10; không chạy `npm install` rồi commit lockfile mới tùy ý |

> Ghi chú trung thực: các lệnh `make` ở trên chưa được chạy thử trong container Ubuntu sạch
> ở lần cập nhật này (máy phát triển Windows không có Python/Docker/make). Mục
> [SELF_REVIEW.md](SELF_REVIEW.md) ghi rõ việc cần chạy thử trước khi phát hành.
