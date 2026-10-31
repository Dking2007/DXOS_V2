# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/), đánh phiên bản theo
[SemVer](https://semver.org/lang/vi/). Mỗi mục trỏ tới commit thật trong lịch sử Git; từ
0.2.0 trở đi mỗi thay đổi đi kèm issue/PR. So sánh chi tiết V1 → V2: [docs/V2_CHANGES.md](docs/V2_CHANGES.md).

## [Unreleased]

### Added
- 17 tính năng AI (migration `workspace_0016`), mô tả trong [docs/ai-features.md](docs/ai-features.md): đọc tài
  liệu để điền biểu mẫu (tạo căn cứ trường nguồn AI, câu trích phải có thật trong trang), tóm tắt hồ sơ cho
  người duyệt, soát hồ sơ trước khi trình, gợi ý ý kiến duyệt/lý do trả lại, soạn văn bản hành chính ra tệp
  Word theo NĐ 30/2020, tóm tắt và hỏi đáp trên tài liệu, tìm theo ý nghĩa (vector, lập chỉ mục trong
  worker), gợi ý nhãn và thư mục, giao việc bằng câu nói, tách việc con, bản tin việc hôm nay, nhận xét báo
  cáo bằng lời, tóm tắt hội thoại, hỗ trợ viết bài và mô tả ảnh, node "Hỏi AI" trong luồng tự động, trợ lý
  trả lời về dữ liệu của chính người hỏi, sinh kịch bản thử cho gói nghiệp vụ. Người có quyền
  `assistant.manage` bật từng tính năng và chọn dịch vụ riêng ở tab **Tính năng AI**; mặc định tắt hết. Dịch
  vụ AI nhận được ảnh và PDF (Claude, OpenAI, Gemini, Ollama, vLLM, cổng tương thích); tạo vector qua
  OpenAI, Gemini, Ollama, vLLM, cổng Chat Completions. Phụ thuộc mới `pypdf` 6.20.1 (BSD-3-Clause). 12 test
  backend, 1 test frontend; đã chạy thật với Ollama `gpt-oss:20b` và `bge-m3`.
  Một dịch vụ AI phục vụ nhiều tính năng, mỗi tính năng chọn model riêng trong danh sách model lấy thẳng từ
  dịch vụ (`POST /assistant/models` nay lấy được của mọi loại dịch vụ, tách model trò chuyện và model tạo vector).
- Trợ lý AI dùng được máy chủ AI tự cài: **Ollama** (gọi API gốc `/api/chat`, đặt `num_ctx` 16384 để
  kiến thức không bị cắt ngầm) và **vLLM** (OpenAI Chat Completions). Khóa API không bắt buộc với hai
  loại này; nút "Lấy danh sách model" đọc model có trên máy chủ (`POST /assistant/models`, dùng được
  cả cho cổng Chat Completions). Chờ tối đa 180 giây; bỏ phần `<think>…</think>` của model suy luận
  khỏi câu trả lời. Cấu hình ngay trong giao diện như các dịch vụ khác: địa chỉ nội bộ và HTTP được nhận
  mà không cần `ASSISTANT_ALLOWED_HOSTS`, nhưng chỉ ở gốc máy chủ (hoặc `/v1`) nên chỉ các đường dẫn cố
  định của máy chủ model được gọi, và địa chỉ link-local (metadata đám mây) vẫn bị chặn. Cổng `custom_*`
  giữ quy tắc cũ. Compose thêm `host.docker.internal` cho `workspace-api` để gọi Ollama chạy trên
  chính máy cài Docker. Logo từ `@lobehub/icons-static-svg` (đã có). 5 test backend, 1 test frontend.
- Đóng hồ sơ (migration `workspace_0015`, thêm `cases.deleted_at`, `cases.archived_at`). Trước đây
  không có cách nào bỏ một hồ sơ tạo nhầm. Người lập **xóa bản nháp chưa từng trình**
  (`DELETE /cases/{id}`; ẩn khỏi mọi danh sách, tìm kiếm, báo cáo, nhật ký vẫn ghi). Hồ sơ đã từng
  trình không xóa được: người lập **hủy** khi đang là bản nháp hoặc bị trả lại (`POST
  /cases/{id}/cancel`, trạng thái `cancelled`, lịch sử giữ nguyên). Lãnh đạo (quyền xem hồ sơ của
  phòng hoặc toàn cơ quan) **lưu trữ / bỏ lưu trữ** hồ sơ đã duyệt, từ chối hoặc đã hủy (`POST
  /cases/{id}/archive`). Hồ sơ đã hủy và đã lưu trữ rời danh sách mặc định, xem ở tab "Đã hủy",
  "Lưu trữ" và vẫn tìm thấy. 4 test.
- Tab **Nhật ký hoạt động** trong Thiết lập cho người có quyền `audit.read`: ai làm gì, lúc nào, có
  liên kết tới hồ sơ/công việc/luồng. Trước đây quyền này có trong ma trận phân quyền nhưng không có
  màn hình nào dùng. `GET /audit-logs` trả thêm `actor_name`. Test frontend bắt buộc mọi hành động
  backend ghi nhật ký đều có nhãn tiếng Việt.
- `GET /workspace/v1/package-versions/{id}/impact?against_id=&suite_id=`: so sánh tác động giữa hai phiên bản của một gói bằng cùng bộ fixture, chỉ đọc (không tạo task, không gửi, không phát hành). Trả về từng fixture đổi kết quả/đường đi/người nhận, nguyên nhân do quy tắc (`rule`), hash của hai phiên bản và của fixture, và cờ `recipient_drift` khi người nhận đã lưu trong báo cáo lần chạy thử gần nhất của bản gốc khác với người nhận hiện tại (cơ cấu tổ chức đổi). 3 test API mới. Giao diện tiếng Việt trong thẻ "So với vN" của màn Gói nghiệp vụ (tên hồ sơ mẫu, đổi kết quả/đường đi/người nhận, các bước duyệt hai bên, cảnh báo cơ cấu đổi; bộ thử của cả hai phiên bản đều chọn được) và 2 test vitest; đã kiểm bằng Chromium trên stack thật ở độ rộng desktop, chưa kiểm 390 px; chưa kiểm trên PostgreSQL. Cả hai phiên bản đều được đánh giá theo cơ cấu hiện tại, nên chênh lệch giữa chúng chỉ đến từ quy tắc.
- `docs/operations.md`: kết quả diễn tập backup/restore ngày 31/10/2026 (PostgreSQL + object storage sang project riêng, số dòng và hash khớp) và lỗi `pg_restore --no-owner`; `docs/acceptance.md` ghi lượt chạy ONLYOFFICE Document Server thật.
- Test API cho cổng phát hành gói nghiệp vụ (`test_packages.py`, 18 test, đã chỉnh theo quy tắc mới: bộ thử tùy chọn nhưng bộ đã viết phải đã chạy và đạt; cấu hình đổi, quyền, bản đã phát hành bất biến) và ma trận quyền truy cập (`test_access_matrix.py`, 9 test: tệp, hồ sơ, công việc, tìm kiếm, báo cáo với người ngoài luồng và quản trị kỹ thuật). Có thêm ca tác nhân service không được dùng API người dùng (15 route đều 403). Chưa phát hiện lỗi rò rỉ. Chat, bảng tin, đính kèm và Office callback đã có test riêng từ trước (`test_collaboration.py`, `test_office_save.py`); chưa phủ đường import evidence của AI và token khác namespace phía Workspace.
- CI chạy thêm `packages/flowkit/tests` (56 test) và test Node của plugin `vn-document-format` (29 test), trước đây không được chạy.

### Changed
- Hồ sơ: form nhập tay "Đối chiếu với tài liệu gốc" ẩn sau nút "Thêm căn cứ thủ công"; phần chính là các
  đề xuất chờ xác nhận. Liên kết tới console Core đổi tên thành "Bảng điều khiển kỹ thuật" (vẫn chỉ hiện cho
  Quản trị kỹ thuật); console ghi rõ là công cụ nền tảng và chỉ chỗ xem nhật ký nghiệp vụ.
- Gọn chức năng trùng lặp (rà soát ngày 31/10/2026):
  - **Bước duyệt chỉ khai báo ở biểu mẫu.** Gói nghiệp vụ không nhận `approval_steps` riêng nữa;
    mỗi phiên bản gói chụp lại bước duyệt của biểu mẫu (giao diện vốn đã làm vậy, chỉ API cho ghi đè).
  - **Hồ sơ bỏ "người phụ trách"** (migration `workspace_0014` xóa cột `cases.assignee_id`). Người
    xử lý hồ sơ là công việc gắn với hồ sơ, đã có nút tạo trong trang hồ sơ. Luồng tự động gửi tới
    "người phụ trách" của sự kiện hồ sơ nay gửi người lập hồ sơ.
  - **Core dùng `dx-flowkit`** thay cho bản sao trong `dx_core.workflow` (thông báo lỗi tiếng Việt
    giữ nguyên). `dx-flowkit` 0.2.0 thêm `compare` và các toán tử `contains`, `empty`, `not_empty`;
    điều kiện của biểu mẫu, bước duyệt và luồng tự động hóa cùng dùng `compare` (trước đây ba hàm
    viết riêng). So sánh lớn/nhỏ nhận hai số hoặc hai chuỗi; giá trị khác kiểu là "không khớp" ở
    Workspace, là lỗi `condition_type_error` ở Core như trước. CI chạy cả test của `packages/flowkit`.
  - **"Hồ sơ đang chờ lâu ở bước nào?" chuyển từ Trang chủ sang Báo cáo**, theo khoảng thời gian
    của trang Báo cáo. Trang chủ bỏ 4 ô số liệu trùng với huy hiệu thanh bên và bộ lọc lịch việc.
- Gói nghiệp vụ phát hành được khi đã kiểm tra cấu hình, không bắt buộc bộ kịch bản chạy thử; bộ
  kịch bản đã tạo thì vẫn phải đạt.
- Mẫu tự động hóa không lặp lại thông báo có sẵn nữa: thay bằng nhắc việc bị trả lại chưa làm lại
  sau 1 ngày, nhắc hồ sơ trả lại chưa trình lại sau 2 ngày, báo lãnh đạo khi việc khẩn được nộp,
  tạo việc lưu trữ khi hồ sơ được duyệt. Bước sau node Chờ nay đọc lại trạng thái hiện tại của công
  việc/hồ sơ (trước đây dùng dữ liệu lúc xảy ra sự kiện nên không viết được "nếu vẫn chưa xong").
- Từ ngữ: công việc dùng "nghiệm thu", hồ sơ dùng "phê duyệt". Công việc ở trạng thái `submitted`
  hiện "Chờ nghiệm thu" (trước đây hiện "Đã trình" của hồ sơ), `completed` hiện "Đã nghiệm thu".
- Tìm kiếm không phân biệt dấu ở mọi nơi: Ctrl+K, trang Tìm kiếm, danh sách công việc, hồ sơ, kho
  tài liệu, chọn bản ghi khi chạy luồng, lọc cuộc trò chuyện (gõ "bao cao" ra "Báo cáo"). Dùng chung
  `dx_workspace/text.py` và `apps/shared/src/text.ts`.
- Bỏ mũi tên ▾ ở nhãn "e-Office" trên thanh bên: không có chức năng chuyển không gian nào.

### Fixed
- Điện thoại: dòng "giờ · phạm vi" ở đầu bài viết bảng tin không còn xuống dòng từng chữ (cắt bằng dấu …,
  nhãn "Đã ghim" chỉ còn biểu tượng); nút trợ lý AI thu sang mép phải khi cuộn xuống và trang có thêm khoảng
  trống cuối, nên không còn che nút ở hàng cuối danh sách Việc hôm nay.

## [0.2.2] - 2026-10-31

### Added
- Trợ lý AI ở góc màn hình (migration `workspace_0012`): trả lời về quy trình nghiệp vụ và cách
  dùng phần mềm, chỉ dựa trên kiến thức do quản trị viên nhập, có ghi nguồn `[1]`. Quyền mới
  `assistant.manage` (mặc định Ban giám đốc, Quản trị kỹ thuật) cho màn **Trợ lý AI**: bật/tắt,
  lời chào, câu gợi ý, hướng dẫn thêm, giới hạn câu hỏi/người/ngày; dịch vụ Claude (SDK `anthropic`
  2.3.0), OpenAI, Gemini, DeepSeek với khóa API mã hóa, chỉ hiện 4 ký tự cuối, kiểm tra kết nối;
  kiến thức viết tay, nhập tệp `.md/.txt`, sinh từ gói nghiệp vụ đang áp dụng, thử tìm không tốn
  lượt gọi AI. Trợ lý không đọc hồ sơ/công việc/tài liệu/tin nhắn. 8 test backend, 4 test frontend.
  Logo các dịch vụ AI lấy từ `@lobehub/icons-static-svg` 1.95.0 (MIT; logo là nhãn hiệu của từng hãng).
  Cổng riêng (migration `workspace_0013`): dùng endpoint tự đặt theo giao thức Anthropic Messages,
  OpenAI Chat Completions hoặc OpenAI Responses (model như `auto`). Chỉ nhận HTTPS trên địa chỉ
  công khai; cổng nội bộ/HTTP phải có trong biến mới `ASSISTANT_ALLOWED_HOSTS`; kiểm lại trước mỗi
  lần gọi, không theo chuyển hướng.
- `packages/flowkit` (`dx-flowkit` 0.1.0): kiểm tra và chạy thử đồ thị quy trình JSON, tách từ `dx_core.workflow`, không phụ thuộc thư viện ngoài. 56 test; cùng kết quả với mã gốc trên 20.000 ca ngẫu nhiên. `dx_core.workflow` chưa dùng gói này.
- `plugins/vn-document-format` (0.1.0): plugin ONLYOFFICE kiểm tra thể thức văn bản hành chính theo Nghị định 30/2020/NĐ-CP, Phụ lục I. 29 test; đã chạy thử trong ONLYOFFICE 8.3.3 trên hai tệp mẫu. Có icon, ảnh chụp và CHANGELOG theo hướng dẫn marketplace. Chưa kiểm lề trên 8.3.3 (thiếu hàm đọc lề); chưa gửi lên marketplace.
- Mục "Đóng góp ngược cho cộng đồng nguồn mở" trong README, ghi trạng thái thật từng việc.
- `scripts/desktiny-migrate.sh` (cài thành `$PREFIX/bin/desktiny-migrate`): chạy migration CSDL từ bản đã cài, không cần thư mục mã nguồn.

### Fixed
- Sửa chữ `WorkMMODIARY` (lỗi thay chuỗi) thành `Workspace` trong chú thích mã và `docs/acceptance.md`.
- Tạo hồ sơ với trường số không bắt buộc để trống bị từ chối (`amount: None is not of type number`): form web gửi `null`, nay `validate_payload` coi giá trị `null` là chưa nhập. Có test hồi quy.
- Người dùng demo do `scripts/bootstrap.py` sinh có họ (`lastName`) trống; Keycloak 26 buộc điền họ ở bước `VERIFY_PROFILE`, nên lần đăng nhập đầu của mọi tài khoản demo bị chặn và Playwright E2E có đăng nhập không qua được. Nay `lastName` là `Demo`.
- `make install` không cài `alembic.ini` và `migrations/`, nên bản cài ra `PREFIX` không thể khởi tạo CSDL khi xóa thư mục mã nguồn (tiêu chí PoF 4, mục "chạy được ngoài thư mục mã nguồn"). Nay cài vào `$PREFIX/share/desktiny/<service>-api/`.

### Changed
- Cấu trúc Workspace API: bỏ hai vòng phụ thuộc bị che bằng import trong hàm (`tasks` ↔ `messaging`, `routers` ↔ `packages`). `validate_payload` và `step_evidence` chuyển vào `schemas.py`; `membership` và `message_readable` chuyển vào `policies.py`; các import cục bộ giữa `automations`, `messaging` và `tasks` đưa lên đầu tệp. Không đổi hành vi hay API (contract OpenAPI không đổi; 105 test dịch vụ + 4 test ranh giới đạt). `tests/test_boundaries.py` có thêm test chặn vòng phụ thuộc mới.
- Thêm `.gitattributes` và `.editorconfig` (LF thống nhất giữa Windows/Linux/macOS).
- `npm run generate:api` giữ header SPDX của hai tệp sinh ra (trước đây xóa mất, làm job `compliance` đỏ). CI so sánh `contracts/` và `apps/shared/src/generated/` với bản đã commit.
- Chuyển hai tài liệu thiết kế vào `docs/design/`; `docs/third-party-inventory.md` ghi rõ phạm vi so với `THIRD_PARTY.md`.
- Ba `pyproject.toml` khai báo `license = "Apache-2.0"` (trước đây `pip-licenses` báo UNKNOWN cho gói tự viết). Quét `pip-licenses` trên image runtime ngày 28/10/2026: 47 gói, không có GPL/SSPL/BUSL/Elastic; chỉ psycopg là LGPL-3.0 (đúng khai báo, nạp libpq của hệ điều hành).
- Cập nhật `docs/architecture.md`, `docs/installation.md`, `docs/acceptance.md` theo trạng thái thật (chat, bảng tin, canvas đã có; Docker/E2E đã chạy ngày 28/10/2026; ghi rõ mục chưa kiểm). `docs/issues-backlog.json` bổ sung các việc đã xong và việc còn mở.
- Thống nhất số phiên bản 0.2.2 ở `package.json` (gốc và 3 workspace), `package-lock.json`, 3 `pyproject.toml` (kèm ràng buộc `dx-platform-kit==`), tiêu đề OpenAPI của hai dịch vụ và `contracts/*.openapi.json` (trước đây còn ghi 0.1.0).
- Thêm `.mailmap` gộp tên hiển thị "unknown" của các commit cũ về `Dking2007` (cùng email; không viết lại lịch sử); CONTRIBUTING.md hướng dẫn cấu hình `user.name`/`user.email` trước khi commit.
- `make install` dùng pip của `.venv` (cần `make venv` trước) thay vì `python3 -m pip` của hệ thống (kèm `--ignore-installed` để mọi phụ thuộc thật sự nằm trong `PREFIX`, không bị bỏ qua vì đã có trong `.venv`): Python 3.13 từ deadsnakes trên Ubuntu 24.04 không có pip, nên lệnh cũ thất bại. `desktiny-migrate` tự chọn đúng `python3.X` đã cài gói thay vì `python3` mặc định. BUILD.md gọi `make venv deps PYTHON=python3.13`. Cả ba lỗi tìm ra khi chạy BUILD.md từng dòng trong Ubuntu 24.04 sạch (27/10/2026).
- Phụ thuộc `psycopg[binary]` đổi thành `psycopg` thuần Python: không còn đóng gói sẵn libpq trong wheel; hệ điều hành cung cấp `libpq5` (đã thêm vào `api.Dockerfile`, bước CI backend và BUILD.md). `psycopg-binary` bị loại khỏi `requirements.lock` và `THIRD_PARTY.md` (54 gói Python).
- BUILD.md: thêm mục Thư viện hệ thống và `libpq5` vào bảng yêu cầu.
- Tài liệu (`V2_CHANGES.md`, `SELF_REVIEW.md`) trỏ tới v0.2.2 là bản dùng để chấm (thay cho v0.2.1; v0.2.0 vẫn chỉ là mốc lịch sử có lỗi `reuse lint`).
- Hợp nhất nhánh `feat/ai-assistant` (trợ lý AI) vào `main`; đã chạy lại toàn bộ kiểm trên bản hợp nhất: ruff, pytest (118 đạt, 1 bỏ qua vì cần PostgreSQL thật), contract OpenAPI và kiểu TypeScript sinh ra khớp mã, lint/typecheck/test/build frontend, kiểm SPDX và `THIRD_PARTY.md`.

## [0.2.1] - 2026-10-26

### Fixed
- `reuse lint` lỗi do `scripts/add_spdx_headers.mjs` và `CONTRIBUTING.md` chứa mẫu header SPDX bị đọc nhầm; bỏ khóa không hợp lệ trong `REUSE.toml` — `d31d057`, `fdc0e7c`. CI toàn bộ xanh từ bản này; `v0.2.0` giữ nguyên làm mốc lịch sử. **Lưu ý:** `v0.2.0` được build từ commit `633b9ec` khi `reuse lint` còn lỗi, vì vậy bản dùng để chấm/cài đặt là `v0.2.1` trở lên, không phải `v0.2.0`.

## [0.2.0] - 2026-10-26 — DXOS V2: sẵn sàng đối chiếu tiêu chí PoF

Bản V2 giữ nguyên chức năng của V1 (0.1.0) và hoàn thiện phần kho mã nguồn: giấy phép, khai
báo thành phần ngoài, hướng dẫn biên dịch, phát hành và tài liệu cộng đồng.

### Added
- Header `SPDX-License-Identifier` + `SPDX-FileCopyrightText` cho 180 tệp mã/cấu hình; công cụ
  `scripts/add_spdx_headers.mjs` (idempotent, có `--check`).
- `LICENSES/Apache-2.0.txt` và `REUSE.toml` (khai báo tập trung cho JSON/Markdown/lockfile/HTML) — chuẩn REUSE.
- `THIRD_PARTY.md` sinh bởi `scripts/gen_third_party.mjs`: 309 gói npm, 55 gói Python, 9 dịch vụ/image với SPDX, nguồn, cách dùng.
- `Makefile` (venv, deps, build, test, lint, `install PREFIX=`, dist, up/down, reuse, licenses) và `BUILD.md`.
- `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SELF_REVIEW.md`.
- Mẫu issue (bug, tính năng), mẫu pull request, nhãn & quy ước commit.
- CI: job `compliance` (reuse lint, kiểm header, đối chiếu THIRD_PARTY.md, quét giấy phép), job build sạch.
- Workflow `release.yml`: đẩy tag `v*` tự tạo Release có `.tar.gz` + `SHA256SUMS`.
- `docs/V2_CHANGES.md`: bảng so sánh V1 → V2 và ánh xạ 6 tiêu chí PoF.
- README: mục *Giấy phép* (lý do chọn Apache-2.0, trỏ LICENSE/THIRD_PARTY) và *Đóng góp*.

### Changed
- `package.json` (gốc và 3 workspace) khai báo `"license": "Apache-2.0"`.
- README/docs trỏ về BUILD.md làm điểm vào cài đặt.

## [0.1.0] - 2026-10-24 — DXOS V1 (đường cơ sở)

Trạng thái kho trước khi bước vào V2, tag hồi tố tại `f089bfb`.

### Added
- Khung dự án, nền tảng Core + Workspace (FastAPI/Vue 3), SSO Keycloak, Docker Compose — `ded2d88`, `e29fa17`.
- Cập nhật nghiệp vụ Drive, hồ sơ, workflow, giao việc — `0fd1ef0`.
- Giao diện mới: banner chào, 4 ô số liệu, khối thời gian chờ theo bước — `15725c5`.
- Gói nghiệp vụ trực quan, tự động hóa theo công việc (canvas luồng), chat đa phương tiện, khung làm việc dễ dùng — `abab487`.
- Bảng tin có ảnh/video; xem PDF, ảnh, video, âm thanh ngay trong ứng dụng — `f949ab9`.

### Changed
- Đổi tên sản phẩm thành Desktiny — `f089bfb`.

### Fixed
- Thứ tự import trong `auth.py` để CI backend qua ruff — `d495abb`.

[Unreleased]: https://github.com/Raphael-Fug/DXOS_V2/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/Raphael-Fug/DXOS_V2/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Raphael-Fug/DXOS_V2/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Raphael-Fug/DXOS_V2/releases/tag/v0.1.0
