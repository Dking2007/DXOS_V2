# Đóng góp cho Desktiny

Cảm ơn bạn đã quan tâm. Tài liệu này mô tả cách báo lỗi, đề xuất và gửi mã. Tham gia cộng đồng theo
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## 1. Người duy trì

| GitHub | Mảng phụ trách |
|---|---|
| [Dking2007](https://github.com/Dking2007) | Core headless, biên dịch, CI và phát hành, tuân thủ giấy phép, vận hành, bảo mật |
| [Raphael-Fug](https://github.com/Raphael-Fug) | Workspace web và design system, quy trình nghiệp vụ, trợ lý và tính năng AI, plugin đóng gói |
| [Mai1174](https://github.com/Mai1174) | Gói giao diện, plugin kết nối, API plugin và SDK, quy trình hồ sơ trên canvas |

## 2. Nguyên tắc kiến trúc bắt buộc

- **Core không có giao diện.** Mọi chức năng Core đi qua API `/core/v1/`; console quản trị (`apps/core-admin`) chỉ là
  một client.
- **Workspace chỉ gọi Core qua API** (`CoreClient`), không đọc hay ghi CSDL của Core. Không có khóa ngoại hay SQL xuyên
  CSDL; `tests/test_boundaries.py` kiểm Core và Workspace không import lẫn nhau.
- **Nghiệp vụ riêng của từng cơ quan** đặt trong gói giao diện hoặc plugin ([docs/packs.md](docs/packs.md),
  [docs/plugins.md](docs/plugins.md)), không sửa mã Core.
- **Mọi tệp có thông tin giấy phép:** header SPDX, hoặc khai báo trong [REUSE.toml](REUSE.toml) với tệp không ghi
  được header.

Chi tiết: [docs/architecture.md](docs/architecture.md).

## 3. Quy trình

1. **Issue:** tìm hoặc tạo issue bằng mẫu có sẵn (báo lỗi, đề xuất, phản hồi dùng thử), gắn **label** và
   **milestone**, tự gán (assign) mình làm.
2. **Nhánh** tạo từ `main` (hoặc fork rồi tạo nhánh): `feat/<số-issue>-<mô-tả>`, `fix/<số-issue>-<mô-tả>` hoặc
   `docs/<số-issue>-<mô-tả>`.
3. **Cấu hình:** `python scripts/bootstrap.py` sinh `.env` và mật khẩu ngẫu nhiên tại máy; không commit `.env` hay
   `infra/identity/generated/`. Môi trường phát triển: [BUILD.md](BUILD.md).
4. **Sửa và kiểm** trước khi đẩy:

   ```bash
   python -m ruff check packages services scripts tests examples infra
   python -m pytest -q
   npm run lint && npm run typecheck && npm run test && npm run build
   node scripts/add_spdx_headers.mjs --check   # mọi tệp mới phải có header SPDX
   reuse lint                                  # pipx install reuse
   ```

   Trên Linux có thể gộp hai dòng đầu và dòng npm bằng `make lint test`.
5. **Commit** theo mục 4.
6. **Pull Request** theo mục 5; merge vào `main` rồi **xóa nhánh**. Khi xong một phạm vi (milestone), làm
   **phát hành** theo mục 6.

## 4. Quy ước commit

- Theo [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `ci:`,
  `chore:`, `refactor:`; có thể thêm phạm vi, ví dụ `fix(ho-so): …`.
- Viết tiếng Việt, ngắn, nói thay đổi làm gì; ghi số issue trong thân commit hoặc PR (`Fixes #12`).
- Commit nhỏ, mỗi commit một ý.
- **Dùng tài khoản và email của chính bạn** để lịch sử phản ánh đúng người làm. Trước commit đầu tiên:
  `git config user.name "Tên của bạn"` và `git config user.email "email-gắn-với-tài-khoản-GitHub"` (đừng để git dùng
  tên mặc định như `unknown`). Kiểm tra: `git log --format="%an <%ae>" -3`. Nếu cùng một người xuất hiện dưới nhiều
  tên, thêm một dòng vào [.mailmap](.mailmap).

## 5. Yêu cầu với Pull Request

- Mô tả có `Fixes #<số-issue>` và điền checklist của [mẫu PR](.github/pull_request_template.md).
- Có test cho logic mới hoặc lỗi vừa sửa.
- Cập nhật [CHANGELOG.md](CHANGELOG.md) mục `[Unreleased]` trong **cùng PR**.
- Đổi giao diện thì kèm ảnh trước/sau, dùng dữ liệu mẫu giả.
- CI xanh (lint, test, build, `compliance`) và ít nhất **một người khác** duyệt; không tự duyệt PR của mình.

## 6. Phát hành

Chỉ làm khi phạm vi của milestone đã xong. Mọi bước dưới đây chạy ở thư mục gốc kho.

1. Tạo nhánh `release/x.y.z` từ `main` và đặt số phiên bản mới ở **mọi** chỗ sau (hiện là `3.1.0`):
   - `package.json`
   - `apps/core-admin/package.json`, `apps/shared/package.json`, `apps/workspace-web/package.json`; trong hai tệp
     `apps/core-admin` và `apps/workspace-web` còn phải sửa phụ thuộc `"@dx/web-shared"`
   - `package-lock.json`: không sửa tay, chạy `npm install --package-lock-only`
   - `packages/platform-kit/pyproject.toml`
   - `services/core-api/pyproject.toml` và `services/workspace-api/pyproject.toml`; trong cả hai còn phải sửa
     `dx-platform-kit==x.y.z`
   - `version=` trong `services/core-api/src/dx_core/main.py` và `services/workspace-api/src/dx_workspace/main.py`
     (đây là phiên bản hiện trong OpenAPI)
2. Sinh lại hợp đồng API và kiểu TypeScript: `python scripts/export_contracts.py` (ghi `contracts/*.openapi.json`),
   rồi `npm run generate:api`.
3. Chuyển mục `[Unreleased]` của [CHANGELOG.md](CHANGELOG.md) thành `## [x.y.z] - ngày`; workflow phát hành lấy ghi chú
   từ chính mục này.
4. Chạy `python scripts/check_version.py --tag vx.y.z --since v<bản trước>`: mọi tệp khai cùng một số, CHANGELOG có
   mục của bản này, loại tăng số đủ so với thay đổi API. Workflow phát hành cũng chạy lệnh này và dừng nếu sai.
5. Chạy `make check` (lint và test) phải xanh, mở PR `release/x.y.z`, duyệt và merge vào `main`.
6. Gắn tag `vx.y.z` trên `main` rồi đẩy tag. Workflow [release.yml](.github/workflows/release.yml) tự tạo Release kèm
   `dxos-x.y.z.tar.gz`, SBOM (`sbom-*.cdx.json`) và `SHA256SUMS`.
7. Kiểm bản phát hành: tải các tệp vào cùng thư mục và chạy `sha256sum -c SHA256SUMS`, phải báo `OK` cho từng tệp.

### Quy tắc đánh số (SemVer)

| Thay đổi | Tăng |
|---|---|
| Sửa lỗi, không đổi hành vi công khai | PATCH (`x.y.Z`) |
| Tính năng mới tương thích ngược | MINOR (`x.Y.0`) |
| Phá vỡ tương thích: bỏ API hoặc cột, đổi định dạng dữ liệu | MAJOR (`X.0.0`) |

"API công khai" gồm ba hợp đồng trong `contracts/`, định dạng gói `desktiny-pack/1`, `desktiny-plugin/1` và `/2`,
và dữ liệu đã lưu (migration). Xóa thao tác, bỏ thuộc tính hoặc thêm trường bắt buộc mới vào hợp đồng là phá tương
thích. Tăng MAJOR thì MINOR và PATCH về 0; tăng MINOR thì PATCH về 0. Chỉ đặt tag dạng `vX.Y.Z` cho bản phát hành;
mốc sao lưu dùng nhánh, không dùng tag.

Phiên bản kế tiếp là **3.2.0**. Không bao giờ gắn lại (re-tag) hay xóa một tag đã đẩy, và không bao giờ lùi số phiên bản;
nếu bản phát hành có lỗi thì sửa và phát hành số mới.

Các gói Python tách riêng giữ số phiên bản **riêng**, không đi theo số của nền tảng: `dx-flowkit` (`packages/flowkit`,
hiện 0.2.0), `desktiny-plugin` (`packages/desktiny-plugin`, hiện 0.3.0), `dx-piivn` (`packages/pii-vn`, hiện 0.1.0).
Chỉ tăng khi chính gói đó đổi; nếu `dx-flowkit` đổi số thì sửa cả ràng buộc `dx-flowkit==` trong
`services/core-api/pyproject.toml` và `services/workspace-api/pyproject.toml`.

## 7. Giấy phép phần đóng góp

- Đóng góp gửi vào kho được cấp phép theo **Apache-2.0**, theo điều 5 của giấy phép, trừ khi bạn ghi rõ khác. Muốn
  xác nhận nguồn gốc rõ hơn, bạn có thể ký commit theo [DCO](https://developercertificate.org/) bằng `git commit -s`
  (thêm dòng `Signed-off-by`); không bắt buộc.
- Mã mới dùng **Apache-2.0**: chạy `node scripts/add_spdx_headers.mjs` để thêm header (dòng định danh giấy phép
  Apache-2.0 và dòng bản quyền "2026 Desktiny contributors").
- **Không** sao chép mã từ web, từ đầu ra AI hay từ dự án khác khi chưa kiểm tra nguồn và giấy phép.
- **Không** commit thư viện (`node_modules/`, `vendor/`, `.jar`, `.so`…). Thêm phụ thuộc qua manifest + lockfile,
  rồi chạy `make licenses` và commit `THIRD_PARTY.md`. Chỉ nhận giấy phép OSI; không dùng SSPL, BSL, Elastic, RSAL…
- Cần sửa thư viện ngoài: gửi bản vá lên upstream hoặc fork công khai và ghi trong THIRD_PARTY.md.

## 8. Báo lỗi và bảo mật

- Lỗi và đề xuất: [Issues](https://github.com/Dking2007/DXOS_Desktiny/issues), dùng mẫu có sẵn; không dán mật khẩu,
  token hay dữ liệu thật.
- Lỗ hổng bảo mật: **không** mở issue công khai, xem [SECURITY.md](SECURITY.md).
