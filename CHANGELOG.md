# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/), đánh phiên bản theo
[SemVer](https://semver.org/lang/vi/). Mỗi mục trỏ tới commit thật trong lịch sử Git; từ
0.2.0 trở đi mỗi thay đổi đi kèm issue/PR. So sánh chi tiết V1 → V2: [docs/V2_CHANGES.md](docs/V2_CHANGES.md).

## [Unreleased]

### Changed
- **Trang đăng nhập** làm lại: thẻ tiêu đề có khung viền trang trí trên nền xanh đậm, luôn vừa một màn hình, hiệu
  ứng xuất hiện, vệt sáng, hạt sáng, vòng biểu tượng xoay, ánh kim trên tiêu đề và nút; tắt khi máy đặt giảm chuyển
  động. Một nút "Đăng nhập bằng SSO".
- Rà soát giao diện theo góp ý người dùng:
  - Công việc: tab mới **Chờ tôi nghiệm thu** (`GET /tasks?scope=review`) khớp đúng số trên menu; các tab hiện số
    đếm; trang tự mở tab đang có việc chờ.
  - Kho tài liệu: mục **Được chia sẻ với tôi** (`shared=true` cho `/drive/files` và `/drive/folders`) liệt kê tệp,
    thư mục người khác chia sẻ mà không thư mục nào mình mở được dẫn tới; gốc “Tài liệu của tôi” chỉ còn đồ của
    mình; dòng tệp ghi “chia sẻ bởi …”.
  - Danh sách hồ sơ: cột **Đang chờ** (người, bước, hạn; trả về trong `waiting_on`) thay cột “Lần sửa”; bản nháp
    của mình có nút **Tiếp tục soạn** và **Trình** ngay trên dòng.
  - Chân trang không còn bị nút trợ lý AI che; gợi ý bật hỏi đáp AI chỉ cho người quản trị AI, có nút ẩn.
  - Trang Trợ lý AI: lời giải thích đúng phạm vi dữ liệu trợ lý đọc; “Mức sẵn sàng” cho biết tính năng dữ liệu
    của người hỏi đang bật hay tắt.
  - Bỏ chữ kỹ thuật (`AUTOMATION_ALLOWED_HOSTS`, “độ sâu 3”, mã tài khoản đăng nhập); “Thêm thành viên” thay
    “Thêm hồ sơ thành viên”.
  - Cần phê duyệt: bỏ chữ “Hồ sơ” thừa, bỏ nhãn in hoa; ủy quyền chia nhóm “Bạn đang ủy quyền cho” / “Bạn đang
    được ủy quyền”, mục đã hết hạn gập lại.
  - Chi tiết công việc: luồng áp dụng cho mọi công việc chỉ hiện với quản trị luồng; người không gắn được luồng
    chỉ thấy luồng đang gắn.
  - Thành viên: ô tìm, lọc theo phòng ban, ảnh đại diện và chức danh.
  - Tìm kiếm: bỏ ô tìm trùng, dùng ô tìm trên thanh trên cùng (nút “Đổi từ khóa” mở sẵn từ khóa).
  - Trình thiết kế quy trình: ô tìm bước, nhóm bước thu gọn được; nút Lưu chuyển “Đã lưu” khi không có thay đổi.

### Added
- **12 quy trình mẫu mới** trong Tạo luồng: hồ sơ khẩn trình thẳng ban giám đốc, nghỉ phép theo số ngày, mua sắm theo
  giá trị, công tác và tạm ứng, công văn đến, trình ký văn bản đi, rà soát hợp đồng song song, thanh toán theo chứng từ,
  sửa chữa tài sản, đề xuất tuyển dụng, ban hành quy định có xác nhận đã đọc, quá hạn thì chuyển cấp trên. Bước ban
  giám đốc chọn theo vai trò nên chạy được ngay; các mẫu khai sẵn tài liệu cần có và hạn từng bước. Bước giao cho vai
  trò hiện tên vai trò thay cho mã.
- **Hồ sơ: tài liệu theo từng bước.** Bấm một bước trong tab Quy trình thấy mục Tài liệu: số tệp cần nộp, tên các
  tài liệu cần có (`required_documents`, khai trong trình thiết kế ở bước đầu, các bước có người xử lý và Giao việc)
  và các tệp thực nộp ở bước đó (kèm khi trình, nộp ở bước, kết quả công việc) với người nộp, thời điểm, dung lượng.
  Tệp Word/Excel/PowerPoint mở bằng OnlyOffice chỉ xem (`POST /drive/files/{id}/office-sessions?case_id=`, ai xem
  được hồ sơ thì đọc được), tệp khác mở trong khung xem. `GET /cases/{id}/process` có thêm `files`. Sửa lỗi tệp nộp ở
  bước duyệt (sau khi trình) không tải về được. 2 test backend.
- **Trợ lý công việc:** trên trang hồ sơ, trợ lý AI có thêm tab "Trợ lý công việc" hỏi đáp riêng về hồ sơ đó (thay
  khung hỏi đáp hồ sơ cũ); nút "Hỏi AI về hồ sơ" và câu gợi ý mở thẳng tab này.
- **Khung tiến trình hồ sơ** làm mới: nhãn tóm tắt hồ sơ đang ở đâu, đường nối tô theo đoạn đã đi, biểu tượng và màu
  riêng cho bước đã duyệt, đang chờ, trả lại, từ chối.
- **Hồ sơ cá nhân** (`/profile`, migration `workspace_0021`): mỗi người tự sửa họ tên, chức danh, số điện thoại,
  email liên hệ, giới thiệu ngắn (`PATCH /me/profile`) và ảnh đại diện PNG/JPEG/WebP tối đa 2 MB
  (`PUT`/`DELETE /me/avatar`, lưu ở Core, xem qua `GET /users/{id}/avatar`). Vai trò và phòng ban vẫn do quản
  trị viên đổi. Ảnh hiện ở thanh trên cùng, Bảng tin và Nhắn tin (hội thoại riêng có thêm `peer_id`); người chưa
  có ảnh vẫn hiện chữ cái đầu. Nhật ký ghi lại việc sửa hồ sơ và đổi/gỡ ảnh. 3 test backend.
- **Hỏi đáp AI về hồ sơ** (tính năng `case_qa`, `POST /ai/cases/{id}/ask`): nút “Hỏi AI về hồ sơ” mở ngăn kéo hỏi
  đáp ngay trên trang hồ sơ. AI đọc nội dung biểu mẫu, quy trình đã đi qua (bước, người quyết định, lý do, người
  đang chờ, hạn), công việc gắn hồ sơ trong quyền người hỏi và tài liệu kèm; trả lời kèm nguồn đã đối chiếu với hồ
  sơ, nhớ ngữ cảnh các câu hỏi trước trong cùng tab. Cùng quyền với tóm tắt hồ sơ. 1 test backend.
- Tab **Quy trình** của hồ sơ làm lại: chiếm hết bề ngang, sơ đồ cao hơn, chế độ toàn màn hình, bản đồ thu nhỏ;
  dải trạng thái (kết quả, đang chờ ai, hạn, tiến độ); đường đã đi tô liền, nhánh chưa đi mờ, đoạn đang chờ chạy
  hiệu ứng; mỗi bước đã qua có số thứ tự; cột **Đường đi của hồ sơ** liệt kê các bước theo thời gian (kể cả lượt
  quay lại), bấm để zoom tới bước và xem người xử lý, quyết định, lý do, thời điểm. Lượt chạy quy trình ghi thêm
  thời điểm tới bước (`at`) và xong bước (`done_at`).
- **Quy trình hồ sơ trên canvas tự động hóa** (migration `workspace_0017`): tab **Quy trình hồ sơ** trong
  `/automations` vẽ đường đi của hồ sơ bằng đúng trình thiết kế luồng, thêm các bước **Duyệt** (lãnh đạo đơn vị
  hoặc người cụ thể; cổng Duyệt / Trả lại / Từ chối, tắt được từng lựa chọn, hạn xử lý, hướng dẫn cho người
  duyệt), **Xin ý kiến** song song (cần tất cả hoặc một người đồng ý), **Giao việc và chờ** (tạo việc gắn hồ sơ,
  đi tiếp khi việc được nghiệm thu hoặc bị hủy), **Yêu cầu bổ sung** và **Kết thúc**. Node Điều kiện đọc được
  câu trả lời biểu mẫu (`form.<trường>`), số và tên tài liệu đính kèm. 5 mẫu có sẵn và mẫu "Từ bước duyệt của
  biểu mẫu" (`GET /automations/process-template`). Bật quy trình cho một biểu mẫu thì hồ sơ trình sau đó đi
  theo quy trình thay cho bước duyệt khai trong biểu mẫu; mỗi biểu mẫu bật một quy trình
  (`process_already_enabled`), hồ sơ ghim bản quy trình lúc trình. Mỗi bước Duyệt/Xin ý kiến vẫn là một human
  task Core; quyết định ghi ở Workspace trước, bước không cho phép thì từ chối (`decision_not_offered`). Chi
  tiết hồ sơ có tab **Quy trình** (`GET /cases/{id}/process`) vẽ sơ đồ chỉ đọc, tô bước đã qua, bước đang chờ
  ai, ý kiến và kết quả; hồ sơ theo bước duyệt tuyến tính cũng được vẽ như vậy. Thu hồi hồ sơ dừng quy trình
  và hủy các run Core còn chờ. Chạy thử quy trình nhận quyết định giả lập theo từng bước. 9 test backend, 4 test
  frontend.
- Công việc có đính kèm tệp: thẻ **Tài liệu** trong chi tiết công việc cho tải tệp lên hoặc chọn từ kho
  tài liệu, xem trước và tải về qua công việc (`POST /tasks/{id}/files/{file_id}/download`, ghi nhật ký
  `task.file_download`), nên người nhận việc mở được tệp mà không cần chia sẻ riêng. Người làm được thêm
  tệp kết quả và chỉ gỡ được tệp do mình đính kèm (`task_file_not_yours`); người giao gỡ được mọi tệp.
  Hộp thoại **Giao việc mới** đính kèm được tệp ngay khi giao. Hoạt động ghi `files_changed`. 2 test
  backend, 1 test frontend.
- Báo cáo theo phòng ban: bảng "Tình hình từng đơn vị" (việc đang mở, quá hạn, hoàn tất trong kỳ; hồ sơ, đang chờ
  duyệt, quá hạn, lần trả lại), phòng nhiều việc/hồ sơ quá hạn đứng đầu (`by_department` trong
  `/reports/overview`). Xuất CSV hồ sơ (`GET /reports/cases.csv`): bước đang chờ, người đang xử lý, hạn bước, quá
  hạn, chỉ những hồ sơ người tải được xem. 1 test.
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
- `docs/operations.md`: kết quả diễn tập backup/restore ngày 31/10/2026 (PostgreSQL + object storage sang project riêng, số dòng và hash khớp) và lỗi `pg_restore --no-owner`; `docs/acceptance.md` ghi lượt chạy ONLYOFFICE Document Server thật.
- CI chạy thêm `packages/flowkit/tests` (56 test) và test Node của plugin `vn-document-format` (29 test), trước đây không được chạy.

### Changed
- **Trợ lý AI trả lời về dữ liệu của người hỏi** (tính năng `assistant_my_data`, vẫn tắt mặc định) mở rộng: ngoài hồ sơ
  mình lập, việc được giao và việc chờ duyệt, trợ lý còn biết việc mình giao, điều phối, theo dõi, việc xong 30 ngày
  qua; bàn giao việc 60 ngày qua và ủy quyền duyệt; hồ sơ mình đã xử lý; tài liệu của mình và đang chia sẻ với ai,
  tài liệu và thư mục người khác chia sẻ cho mình. Chỉ những gì người hỏi mở được; mỗi nhóm tối đa 12 mục, ưu tiên
  mục khớp câu hỏi. Câu trả lời ghi mã `@n` cạnh từng mục, giao diện biến thành nút mở và danh sách **Mở nhanh**
  (`items` trong `POST /assistant/chat`); mã cũ bị bỏ khỏi lịch sử gửi lại. `GET /assistant` có `my_data` và
  thêm câu hỏi gợi ý. 2 test backend, 2 test giao diện.
- **Thanh bên** sáng và gọn: cùng nền với trang, chỉ một viền mảnh; trang đang mở tô nền nhạt và chữ đậm. Gộp còn
  hai nhóm (việc hằng ngày và Quản trị), số đang chờ hiện nhỏ cuối dòng, nút thu gọn thành biểu tượng cạnh logo, bỏ
  dòng phiên bản. Chế độ tối, thu gọn và ngăn kéo trên điện thoại vẫn hoạt động.
- **Chi tiết công việc** dễ theo dõi hơn: khung tóm tắt ở đầu trang cho thấy việc đang ở bước nào (Đã giao →
  Tiếp nhận → Đang làm → Chờ nghiệm thu → Hoàn tất), một câu nói rõ bước tiếp theo cho đúng người đang xem (người
  làm, người giao), hạn còn bao lâu hoặc đã quá bao lâu, nút Đổi hạn ngay cạnh hạn. Nút hủy/từ chối xếp cuối, tách
  khỏi thao tác chính. **Báo cáo** dùng lời thường cho phạm vi, kỳ và giờ; định nghĩa số liệu gom vào một mục mở
  ra khi cần.
- **Giao diện theo design system** ([design-system/desktiny/MASTER.md](design-system/desktiny/MASTER.md), tạo bằng skill
  ui-ux-pro-max): phong cách tối giản, màu chính navy, bỏ nền chuyển sắc và bóng đổ nặng; cỡ chữ tối thiểu 12px (trước đó
  có chữ 8px), nút tối thiểu 40px và 44px trên màn hình cảm ứng; viền focus rõ; tôn trọng giảm chuyển động. Bỏ các khẩu
  hiệu và nhãn thừa, tiêu đề trang nói thẳng tên trang, Trang chủ bỏ banner, thay emoji bằng icon, số hiển thị có phân cách
  hàng nghìn, thanh trên cùng không còn tràn ngang trên điện thoại.
- **Một loại luồng** (migration `workspace_0020`): bỏ hai tab Quy trình hồ sơ và Luồng tự động. Node kích hoạt quyết định
  luồng chạy khi nào; chọn biểu mẫu thì luồng là đường đi của hồ sơ biểu mẫu đó. Mọi loại bước dùng được cho mọi luồng,
  kể cả Duyệt, Xin ý kiến, Nhập thông tin trên luồng của công việc hay bài viết (`approval_tasks.case_id` nay có thể trống,
  xử lý ngay ở màn Cần phê duyệt). Mọi luồng đều phát hành theo phiên bản; `/automations/{id}/enabled` tương đương phát
  hành hoặc ngừng áp dụng. **Kết quả của bước:** bước cần người đặt được trường và số tệp phải nộp khi đồng ý
  (`step_result_required`), bước Giao việc chặn nộp khi thiếu tệp (`task_result_required`), và bước sau đọc được kết quả
  qua `{ten_buoc.truong}`. **14 node mới:** Rẽ nhiều nhánh, Chạy song song, Chờ đủ nhánh, Chờ đến khi, Đặt giá trị, Xác nhận
  đã đọc, Cập nhật hồ sơ/việc, Tạo văn bản, Lưu và chia sẻ tệp, Tạo hồ sơ khác, Nhắn tin và đăng tin, Gửi email (cấu hình
  `SMTP_*`), Gọi API lấy dữ liệu, AI trích xuất. Các bước hành động theo quyền của người tạo luồng. 31 test backend, 4 test
  frontend.
- **Node quy trình cấu hình linh hoạt** (migration `workspace_0019`), mô tả trong
  [docs/process-packages.md](docs/process-packages.md). Người xử lý theo người cụ thể, nhóm, vai trò, thành viên phòng
  ban, lãnh đạo đơn vị hoặc người ghi trong biểu mẫu; bước Duyệt hoàn tất theo người đầu tiên, tất cả hoặc đủ số người,
  bước Xin ý kiến thêm đủ số người. Khi quá hạn: nhắc, chuyển người khác hoặc đi cổng **Quá hạn**
  (outbox `process.overdue`). Cổng **Trả lại** nối được về bước trước: câu trả lời cũ giữ lại và đánh dấu đã thay thế,
  tối đa 5 lần mỗi bước (`loop_limit`); vòng lặp qua cổng khác vẫn bị từ chối. Bước mới **Nhập thông tin** (`input`): một
  người điền thêm trường, tệp, dùng được trong điều kiện sau đó qua `form.<mã>`, kể cả người tạo hồ sơ. Từng bước đặt
  được trường và tài liệu người ở bước đó được xem, trường được sửa khi trả lời; có áp dụng ở API, không chỉ ở giao diện.
  Người được hỏi chuyển được cho người khác (`POST /approval-tasks/{id}/forward`) và bước có thể không nhận người được
  ủy quyền. Bước mới **Quy trình con** (`subprocess`) chạy một quy trình đã phát hành, kết quả chọn cổng đi tiếp; phiên
  bản cha ghim phiên bản con lúc phát hành. 32 test backend, 3 test frontend.
- **Quy trình nghiệp vụ** gộp Tự động hóa và Gói nghiệp vụ thành một mục (`/processes`; `/automations` và `/packages`
  chuyển hướng), migration `workspace_0018`. Luồng canvas là gốc: canvas là bản nháp, **Phát hành** tạo phiên bản
  (`process_versions`) và hồ sơ ghim phiên bản đó khi tạo. Bảng phát hành có phân quyền sử dụng theo vai trò và phòng ban
  (`PUT /processes/{id}/settings`), số tài liệu tối thiểu, kịch bản thử (`/processes/{id}/scenarios`,
  `/scenario-reports`) chạy bằng đúng bộ máy thật ở chế độ không ghi dữ liệu, so sánh tác động với bản đang áp dụng
  (`/processes/{id}/impact`) và lịch sử phiên bản. Mọi kịch bản đã viết phải đạt trên đúng bản nháp mới phát hành được
  (`simulation_required`). Một biểu mẫu có thể có nhiều quy trình; tạo hồ sơ chọn trong các quy trình người đó được dùng
  (`GET /processes/available`, `process_required`, `process_use_denied`). Tạo quy trình bắt đầu từ thư viện mẫu, tạo
  hoặc sửa biểu mẫu ngay trong màn này. Mỗi gói cũ được chuyển thành một quy trình giữ nguyên id, hồ sơ đã ghim và quyền
  được giữ, bộ thử cũ chép sang nhưng không kèm quyết định giả lập và đường đi vì chúng đặt theo node của Core; bảng gói
  cũ giữ lại chỉ để đọc. Quản trị kỹ thuật được thêm `forms.manage`; lãnh đạo phòng không còn quản lý quy trình. Thay API
  `/business-packages*`, `/package-versions*`; `CaseCreate.package_version_id` đổi thành `process_id`;
  `/ai/package-versions/{id}/scenarios` đổi thành `/ai/processes/{id}/scenarios`. Đã chạy migration lên và xuống trên bản
  sao dữ liệu PostgreSQL. 14 test backend thay `test_packages.py`, `test_processes.py`; 2 test frontend. Spec:
  [docs/superpowers/specs/2026-11-06-quy-trinh-nghiep-vu-design.md](docs/superpowers/specs/2026-11-06-quy-trinh-nghiep-vu-design.md).
- **Hạn xử lý theo từng bước duyệt** (migration `workspace_0017`, `approval_tasks.due_at`): mỗi bước có "thời
  hạn xử lý" (giờ hoặc ngày), tính từ lúc hồ sơ tới bước đó. Hồ sơ quá hạn khi một bước đang chờ quá hạn của nó;
  lịch việc của người duyệt, danh sách Cần phê duyệt và thẻ "chờ lâu ở bước nào" (thêm số bước quá hạn) dùng hạn
  này. Bỏ ô "Hạn xử lý" do người lập tự đặt khi tạo hồ sơ (API vẫn nhận `due_at` cho dữ liệu cũ). 2 test backend,
  1 test frontend.
- Tính năng AI: nút "Gói khuyến nghị" bật 13 tính năng chỉ đọc những gì người dùng đã được xem (để riêng tìm
  theo ý nghĩa, bước AI trong luồng, trợ lý xem dữ liệu người hỏi, sinh kịch bản thử). Khi một lần gọi AI quá 6
  giây, góc dưới màn hình báo "AI đang xử lý… N giây"; quá 15 giây nói rõ máy chủ AI của cơ quan có thể mất 1–2
  phút. Test frontend đối chiếu danh sách tính năng với `ai_core.FEATURES`.
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
- Tab **Quy trình** trong hồ sơ và thao tác nhân đôi node đứng im do `structuredClone` không nhận dữ liệu reactive.
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
- `scripts/audit_repo.mjs` và bước CI tương ứng: thoát 1 nếu Git đang theo dõi tệp `.env` (trừ `.example`), khóa/chứng chỉ riêng, bản dump, `infra/identity/generated/`, hoặc image Compose không ghim phiên bản hay dùng `latest`. Chạy trên kho hiện tại: sạch (269 tệp); thử trên kho mẫu có lỗi: 3 vi phạm, thoát 1. Ý tưởng từ gagaduy/OpenDXOS.
- `packages/pii-vn` (`dx-piivn` 0.1.0): dò CCCD, CMND, số điện thoại di động, số tài khoản, mã số thuế và e-mail trong văn bản, không phụ thuộc thư viện ngoài. CCCD được kiểm mã tỉnh, chữ số thế kỷ và năm sinh; số 12 chữ số ngẫu nhiên qua khoảng 1,6% (test đo, ngưỡng 3%). 12 test, `ruff` sạch. Danh sách mã tỉnh và đầu số di động chưa đối chiếu văn bản chính thức; chưa nối vào Workspace. Xem `docs/danh-gia-3-du-an.md`.
- Chuỗi băm cho nhật ký audit của Core (`dx_core/audit_chain.py`, migration `core_0003`): mỗi dòng audit mới chứa `seq`, `prev_hash`, `entry_hash` (SHA-256) nên sửa, xóa hoặc đảo dòng bị phát hiện. `GET /core/v1/audit-logs/verify` (quản trị) trả `ok`, số dòng đã kiểm, `head` và dòng đầu tiên bị hỏng. Trên PostgreSQL, trigger chặn `UPDATE`/`DELETE` bảng `audit_logs`. 5 test mới; migration và trigger đã chạy thử trên PostgreSQL 17. Dòng audit cũ (trước migration) được báo là `unchained`, không coi là hợp lệ. Ý tưởng lấy từ dự án PSA-OVNCR/dxos (I4); xem `docs/so-sanh-psa-dxos.md`. Chưa neo `head` ra ngoài và chưa có chuỗi cho audit của Workspace.
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
