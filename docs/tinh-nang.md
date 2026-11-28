<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# Tính năng chi tiết

Tệp này mô tả từng tính năng của ứng dụng Workspace và Core, kèm phạm vi hiện tại của mỗi tính năng (dòng
**Phạm vi hiện tại**). Phần tóm tắt nằm ở [README](../README.md#tính-năng-chính); tính năng AI nằm ở
[ai-features.md](ai-features.md); gói giao diện và plugin ở [packs.md](packs.md) và [plugins.md](plugins.md).

## Công việc

- **Giao việc** (`/tasks`): giao cho người hoặc đơn vị; trưởng đơn vị nhận việc giao cho đơn vị rồi phân công
  người chịu trách nhiệm. Trạng thái `draft → assigned → accepted → in_progress → submitted → completed`, nhánh
  `blocked/returned/cancelled`; trả lại, báo vướng mắc, hủy và đổi hạn bắt buộc lý do và được ghi lịch sử.
  Checklist phải xong mới nộp được; việc cha chỉ nghiệm thu khi mọi việc con đã xong/hủy. Lãnh đạo phòng giao
  trong phòng mình, ban giám đốc giao liên phòng. UI có dạng giấy (mặc định, mỗi việc một tờ) và danh sách dạng bảng.
  - Phạm vi hiện tại: chưa có lịch dạng tháng hay Gantt.

## Hồ sơ và phê duyệt

- Hồ sơ có **hạn xử lý, mức độ ưu tiên và người phụ trách**; người nhận phải thuộc phạm vi đơn vị của hồ sơ.
  Form hỗ trợ **ẩn/hiện và giá trị mặc định theo điều kiện giữa các trường**; backend validate lại cả phần ẩn
  trước khi dữ liệu vào Core.
  - Phạm vi hiện tại: form đã published là bất biến; thay đổi bằng form/schema mới, chưa có API chuỗi phiên bản
    form. Chưa hỗ trợ một người thuộc nhiều đơn vị (nhiều membership).
- **Ủy quyền phê duyệt** (trong `/approvals`): có thời hạn (tối đa 90 ngày), có lý do, thu hồi được; người được
  ủy quyền chỉ xử lý hồ sơ giao cho người ủy quyền, quyết định lưu cả người duyệt thật (`decided_by_id`) và người
  được đại diện. Không cho ủy quyền dây chuyền.
- **Thu hồi hồ sơ đã trình** khi chưa ai ra quyết định: nhiệm vụ duyệt đang chờ bị đóng ngay, worker hủy run Core,
  hồ sơ về bản nháp để trình lại.

## Quy trình nghiệp vụ và luồng tự động

- **Trình thiết kế luồng dạng canvas** (`/processes`, quyền `automations.manage`; địa chỉ cũ `/automations` tự
  chuyển về đây), dựng trên Vue Flow. Kéo thả node Kích hoạt, Điều kiện (nhánh Đúng/Sai, "tất cả" hoặc "ít nhất
  một"), Chờ, Gửi thông báo, Tạo công việc, Gọi webhook; nối dây, cấu hình ở panel bên phải, chèn biến `{title}`…
  bằng một click; có 4 mẫu luồng. Lỗi cấu hình hiện ngay trên từng node (thiếu kết nối, vòng lặp, node treo…).
  **Chạy thử** với dữ liệu mẫu tô sáng đường đi trên canvas mà không tác động thật; **Lịch sử chạy** vẽ lại từng
  lượt chạy thật lên canvas. Luồng lưu dạng đồ thị DAG; mỗi lượt chạy ghim bản đồ thị lúc bắt đầu nên sửa luồng
  không ảnh hưởng lượt đang chạy; node Chờ tiếp tục qua outbox (tối đa 7 ngày, luồng bị tắt trong lúc chờ thì lượt
  chạy bị hủy). Luồng mới ở trạng thái tắt; mỗi sự kiện chạy một lần cho mỗi luồng; luồng không tự kích hoạt lại
  chính nó và chuỗi bị chặn ở độ sâu 3. Tạo việc chạy dưới quyền hiện tại của người tạo luồng.
- Mỗi luồng về công việc (trừ "Công việc được tạo") chọn được **Áp dụng cho**: *Mọi công việc* hoặc *Chỉ công việc
  được gắn*. Ở chế độ gắn, trang chi tiết công việc có khung **Luồng tự động** để người giao, người phụ trách hoặc
  lãnh đạo đơn vị nhận bật/tắt từng luồng đang bật cho việc đó; gắn/gỡ được ghi vào lịch sử công việc. Nút
  **Chạy ngay** chạy thật một luồng với một công việc/hồ sơ/bài viết có sẵn, kể cả khi luồng đang tắt; lịch sử chạy
  ghi rõ bản ghi và người chạy tay.
- Webhook chỉ gọi tới host trong `AUTOMATION_ALLOWED_HOSTS` (mặc định rỗng = tắt), gửi `Idempotency-Key`, khóa bí
  mật mã hóa bằng `CREDENTIAL_ENCRYPTION_KEY` và không trả lại qua API; quá thời gian chờ thì ghi "chưa rõ kết quả"
  và **không tự gửi lại**.
  - Phạm vi hiện tại: chưa có node vòng lặp, gọi HTTP đọc dữ liệu về, biểu thức tùy ý hay connector OAuth; editor
    dùng tốt nhất trên màn hình rộng (trên điện thoại xem và thêm node qua nút +).
- **Quy trình hồ sơ** (cũng ở trang Quy trình nghiệp vụ, cùng quyền `automations.manage`): vẽ đường đi của hồ sơ
  trên chính canvas tự động hóa với các bước Duyệt, Xin ý kiến (song song), Giao việc và chờ, Yêu cầu bổ sung, Kết
  thúc, xen được Điều kiện (trường biểu mẫu `form.…`, số/tên tài liệu), Chờ, Thông báo, Tạo việc, Webhook. Bắt đầu
  từ 5 mẫu có sẵn hoặc từ bước duyệt của biểu mẫu. Bật cho một biểu mẫu thì hồ sơ trình sau đó theo quy trình thay
  cho bước duyệt khai trong biểu mẫu; tắt thì quay về bước duyệt cũ. Hồ sơ ghim bản quy trình lúc trình; cổng
  Duyệt/Trả lại/Từ chối không nối thì hồ sơ kết thúc đúng như tên cổng. Mỗi lần hỏi ý kiến/duyệt là một human task
  Core. Tab **Quy trình** trong chi tiết hồ sơ cho mọi người xem được hồ sơ thấy hồ sơ đang ở bước nào, chờ ai, ai
  đã quyết định gì. Người xử lý, nhiều người duyệt, xử lý quá hạn, quyền theo bước và quy trình con cấu hình ngay
  trên node. Canvas là bản nháp; hồ sơ đi theo phiên bản đã phát hành, sau khi qua phân quyền và kịch bản thử (xem
  [process-packages.md](process-packages.md)).
  - Phạm vi hiện tại: quy trình là DAG (chỉ cổng Trả lại được đi ngược, tối đa 5 lần mỗi bước).

## Tài liệu

- Drive có **ACL kế thừa theo thư mục**: chia sẻ thư mục kế thừa xuống mọi tài liệu bên trong, kể cả thư mục con
  và tài liệu thêm sau; cấp quyền cao nhất trong tất cả đường dẫn kế thừa được áp dụng. Thư mục có tạo, đổi tên,
  di chuyển (chặn chu trình) và xóa. Rename/move cho phép người được chia sẻ quyền ghi; đưa vào thùng rác và quản
  lý chia sẻ chỉ chủ sở hữu, để không thể âm thầm rút quyền kế thừa.
  - Sau khi thay đổi chia sẻ hoặc di chuyển thư mục, quyền được cấp lại trên từng tài liệu; trong cửa sổ đó tài
    liệu trả `409 permissions_syncing` thay vì phục vụ quyền cũ.
- Tài liệu Drive có **nhãn** và **sao chép**. Nhãn là metadata riêng của Workspace, được chuẩn hóa (không trùng
  khi chỉ khác hoa/thường) nên đổi tên nhãn không cần upload lại. Sao chép tạo một file Core **độc lập** với
  resource và quota riêng: sửa bản sao không đụng lịch sử version của bản gốc, và share của bản gốc cũng không tự
  động lọt sang bản sao. Phần mở rộng được giữ nguyên để không đổi định dạng tài liệu.
- **Xem tệp ngay trong ứng dụng**: PDF, ảnh (PNG/JPEG/GIF/WebP), video, âm thanh và TXT/CSV mở trong khung xem ở
  Kho tài liệu, tab Tài liệu và bản đã trình của hồ sơ (đúng phiên bản đã trình), và tệp đính kèm trong chat. PDF
  được pdf.js vẽ thành hình (lật trang, phóng to, vừa khung) nên mã nhúng trong PDF không chạy; trình duyệt đọc tệp
  qua liên kết tải ngắn hạn sẵn có, Core vẫn trả `attachment` và không có endpoint mới. Văn bản chỉ hiện 512 KB
  đầu. Tệp Office mở bằng ONLYOFFICE; SVG/ZIP chỉ tải về.
- **ONLYOFFICE** (tùy chọn): Office chặn submit khi phiên chỉnh sửa còn mở; phải đóng editor và nhận callback cuối
  hợp lệ trước khi trình. Đây **không phải force-save barrier**. Content ticket Office có TTL 8 giờ và gắn session.
  - Phạm vi hiện tại: thu hồi share không đẩy người đang mở editor ra ngay lập tức. Chưa kiểm Document Server thật
    hoặc cộng tác hai browser.

## Trao đổi, tìm kiếm và báo cáo

- **Nhắn tin** (`/chat`): hội thoại riêng, nhóm, kênh phòng ban, trao đổi gắn công việc/hồ sơ; reply, nhắc tên,
  cảm xúc, sửa/xóa tin của mình, read cursor, chống gửi trùng bằng `client_message_id`. Khi thêm thành viên chọn
  được cho xem toàn lịch sử hay chỉ từ lúc vào; rời/bị xóa khỏi nhóm thì API chặn đọc ngay. Quản trị không mặc định
  đọc chat riêng. Gửi được **ảnh, video, âm thanh và tệp** (chọn, kéo thả hoặc dán; tối đa 10 tệp, mỗi tệp 50 MB),
  xem ảnh phóng to, phát video ngay trong hội thoại, có đánh dấu "Đã xem". Tệp lưu trong Core dưới service
  principal của Workspace; mỗi lần xem Workspace kiểm tra lại thành viên, phạm vi lịch sử và tin nhắn chưa bị xóa.
  Chỉ ảnh/video/âm thanh hiển thị trực tiếp, loại khác luôn tải về. Core nhận thêm GIF/WebP, MP4/MOV/WebM,
  MP3/OGG/WAV, ZIP — đều kiểm tra chữ ký nội dung; SVG/HTML/tệp chạy được vẫn bị từ chối.
  - Phạm vi hiện tại: **giao nhận bằng polling REST** (4–15 giây), chưa có WebSocket/presence/typing. Chưa có
    thumbnail/nén video và chưa hỗ trợ tua video theo byte range.
- **Bảng tin** (`/feed`): bài toàn tổ chức hoặc phòng ban, thông báo chính thức (gửi notification cho phạm vi
  nhận), ghim, bình luận, cảm xúc, lưu bài. Nội dung là văn bản thuần (đường dẫn http/https tự thành liên kết). Bài
  đăng kèm được **tối đa 10 ảnh/video** (PNG/JPEG/GIF/WebP, MP4/WebM/MOV; chọn, kéo thả hoặc dán; migration
  `workspace_0011`): tệp tải lên trước và chỉ người tải xem được cho tới khi bài đăng; sau đó Workspace kiểm tra
  quyền xem bài ở mỗi lần đọc, bài bị xóa thì ảnh/video cũng ẩn. Bài hiện lưới ảnh, xem toàn màn hình có lướt ảnh.
  - Phạm vi hiện tại: chưa nén ảnh/tạo thumbnail, chưa tua video theo byte range, chưa có rich text hay kiểm duyệt
    trước khi đăng.
- **Tìm kiếm chung** (`/search`, ô tìm ở header) trên công việc, hồ sơ, tài liệu, bài viết, tin nhắn; gõ không dấu
  vẫn tìm thấy chữ có dấu ("bao cao" ra "Báo cáo"); lọc quyền trước khi đếm và cắt trang. Tìm trực tiếp trên bảng
  (không có chỉ mục full-text riêng), phù hợp quy mô pilot. Tìm theo ý nghĩa là một tính năng AI riêng, cần dịch vụ
  tạo vector (xem [ai-features.md](ai-features.md)).
- **Báo cáo** (`/reports`): việc theo trạng thái, quá hạn, hoàn tất trễ, phân bổ theo người, hồ sơ theo trạng
  thái, số lần trả lại; mỗi chỉ số có định nghĩa và thời điểm tính.
  - Phạm vi hiện tại: xuất CSV công việc chạy đồng bộ, chưa có report job nền.

## Khung làm việc

- Menu chia nhóm (Làm việc · Trao đổi · Tài liệu & báo cáo · Quản trị) ẩn mục không có quyền và hiện số việc đang
  chờ; nút **+ Tạo mới** ở thanh trên; **Ctrl + K** mở bảng lệnh tìm việc/hồ sơ/tài liệu và chạy lệnh; thông báo
  dạng bảng thả xuống, lọc theo loại, chia "Hôm nay/Trước đó", đánh dấu tất cả đã đọc
  (`POST /notifications/read-all`).
- Trang chủ là **Việc cần làm hôm nay**, lấy từ `GET /me/overview` (việc được giao, việc phòng cần phân công, kết
  quả cần nghiệm thu, hồ sơ chờ duyệt kể cả duyệt thay, lời nhắc), xếp quá hạn trước, có nút Nhận việc ngay trên
  danh sách. Chi tiết hồ sơ chia tab và có thanh quyết định dính đáy.
- Thiết lập có **bảng phân quyền theo vai trò** (`PATCH /roles/{key}`; không cho bỏ "Quản lý tổ chức" khỏi vai trò
  của chính người sửa) và sơ đồ cơ cấu tổ chức (Sơ đồ / Cây / Bảng).
- **Cài đặt cá nhân** (`/preferences`): giao diện sáng/tối/theo máy, mật độ hiển thị, cỡ chữ, tăng tương phản,
  giảm chuyển động, định dạng ngày giờ; lưu theo từng người trên trình duyệt. Hướng dẫn lần đầu theo vai trò (nhớ
  theo trình duyệt) xem lại được ở đây. Ngôn ngữ hiện chỉ có tiếng Việt.
- Trên điện thoại có thanh điều hướng dưới; thông báo nhanh sau thao tác, khung xương khi tải và hỏi lại trước khi
  bỏ thay đổi chưa lưu.
  - Phạm vi hiện tại: badge cập nhật mỗi 30 giây và khi chuyển trang, chưa đẩy tức thời.

## Trợ lý AI

- **Trợ lý AI** (nút góc màn hình, Ctrl + K › "Hỏi trợ lý AI"; quản trị ở `/assistant`), **mặc định tắt**: trả lời
  câu hỏi về quy trình nghiệp vụ và cách dùng phần mềm từ **kho kiến thức** do người có quyền `assistant.manage`
  nhập (viết tay, tệp `.md/.txt`, hoặc sinh từ quy trình đang áp dụng). Mỗi câu hỏi tìm đoạn liên quan bằng BM25
  trên chữ đã bỏ dấu (không cần dịch vụ tìm kiếm riêng) rồi gửi kèm câu hỏi tới dịch vụ AI đang chọn: Claude,
  OpenAI, Gemini, DeepSeek, Ollama, vLLM hoặc **cổng riêng** nói giao thức Anthropic Messages / OpenAI Chat
  Completions / OpenAI Responses (ví dụ LiteLLM, OpenRouter).
- Dịch vụ chính hãng có địa chỉ cố định trong mã; cổng riêng phải là HTTPS trên địa chỉ công khai, còn cổng nội bộ
  hoặc HTTP chỉ dùng được khi tên máy có trong `ASSISTANT_ALLOWED_HOSTS` (kiểm khi lưu và trước mỗi lần gọi, không
  theo chuyển hướng); khóa API mã hóa bằng `CREDENTIAL_ENCRYPTION_KEY`, không bao giờ trả về.
- Trợ lý chỉ xem dữ liệu nghiệp vụ khi quản trị bật thêm tính năng "Trợ lý trả lời về dữ liệu của người hỏi", và
  khi đó chỉ dữ liệu của chính người hỏi theo quyền xem. Lịch sử hội thoại chỉ giữ trong tab trình duyệt. Giới hạn
  câu hỏi/người/ngày, chỉ trừ lượt khi có câu trả lời. Container `workspace-api` cần được ra Internet (hoặc tới máy
  chủ AI nội bộ) của dịch vụ đã chọn.
- Ngoài trợ lý có 19 tính năng AI rải trong các màn hình, bật từng cái: xem [ai-features.md](ai-features.md).
  - Phạm vi hiện tại: chưa có trả lời dạng stream; kho kiến thức của trợ lý tìm bằng BM25, chưa dùng vector, và chưa
    nhập tệp PDF/Word làm kiến thức.

## Core

- Engine workflow Core chưa có action/HTTP connector và external event dispatcher (webhook ở trên thuộc luật
  Workspace). Outbox Core được ghi/giữ pending để truy vết.
- File có kiểm định dạng/giới hạn cơ bản, **chưa có quét antivirus/malware**.
- Kết quả nghiệm thu và những bước còn cần dịch vụ thật (PostgreSQL concurrency, SSO, cài sạch bằng Docker) ghi ở
  [acceptance.md](acceptance.md).
