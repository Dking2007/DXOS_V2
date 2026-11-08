# Quy trình nghiệp vụ, chạy thử và truy vết

Tự động hóa và Gói nghiệp vụ nay là một mục: **Quy trình nghiệp vụ** (`/processes`, quyền `automations.manage`, mặc định
cho giám đốc và quản trị kỹ thuật), chỉ có một loại luồng. Node kích hoạt quyết định luồng chạy khi nào. Chọn sự kiện *Hồ sơ
được trình* và một biểu mẫu thì luồng là **đường đi của hồ sơ** biểu mẫu đó: thay cho bước duyệt trong biểu mẫu và kết quả
luồng là kết quả hồ sơ. Các trường hợp khác, luồng phản ứng với sự kiện và không có kết quả bắt buộc phải đạt. Mọi loại
bước dùng được cho mọi luồng; yêu cầu từ luồng không có hồ sơ được xử lý ngay ở màn **Cần phê duyệt**. Riêng *Yêu cầu bổ
sung* chỉ có nghĩa với hồ sơ. Phân quyền sử dụng chỉ áp dụng cho đường đi của hồ sơ.

## Kết quả của bước

Mỗi bước có một tên kết quả, mặc định là mã node, đổi được ở mục *Tên kết quả của bước*. Bước sau đọc kết quả trong điều
kiện và nội dung bằng `{ten.truong}`, ví dụ `{tham_dinh.ket_luan}`. Hai bước không được trùng tên kết quả.

- **Bắt buộc nộp:** bước Duyệt và Xin ý kiến đặt được các trường và số tệp phải nộp khi đồng ý; trả lại hoặc từ chối thì
  không phải nộp. Bước Giao việc và chờ đặt được số tệp kết quả, người làm thiếu thì không nộp được việc.
- **Đọc được:** bước cần người cho `decision`, `decided_by`, `reason`, `file_count`, `file_names`, `count`, `people` và các
  trường đã nộp. Bước tự động cho kết quả riêng, liệt kê ở bảng dưới.

## Các bước mới

| Bước | Việc làm | Đọc được |
|---|---|---|
| Rẽ nhiều nhánh | Đi nhánh đầu tiên thỏa theo giá trị một trường, không thỏa thì đi cổng Còn lại | `choice` |
| Chạy song song | Mọi bước nối từ đây cùng chạy | |
| Chờ đủ nhánh | Đi tiếp khi đủ các nhánh còn có thể đến, hoặc khi nhánh đầu tiên đến. Nhánh không còn đi được thì không chờ | |
| Chờ đến khi | Đến một ngày trong dữ liệu, hoặc kiểm tra lại đều đặn đến khi điều kiện đúng; có thể đặt hết thời gian chờ | `resumed_at` |
| Đặt giá trị | Gán hoặc cộng, trừ, nhân, chia; không đánh giá biểu thức tùy ý | đọc bằng `{ten}` |
| Xác nhận đã đọc | Nhiều người xác nhận, kể cả người tạo | `count`, `people` |
| Cập nhật hồ sơ/việc | Đổi độ ưu tiên, hạn, trường biểu mẫu của bản ghi luồng đang chạy trên đó | giá trị mới |
| Tạo văn bản | Sinh tệp Word từ dữ liệu, lưu vào kho của người tạo luồng, đính kèm hồ sơ | `file_id`, `name` |
| Lưu, chia sẻ tệp | Chuyển vào thư mục, cấp quyền xem; người tạo luồng phải là chủ tệp | `file_id`, `shared_with`, `link` |
| Tạo hồ sơ khác | Mở hồ sơ dạng nháp cho chủ bản ghi kiểm tra rồi tự trình; không tự trình | `case_id`, `code` |
| Nhắn tin, đăng tin | Gửi vào hội thoại người tạo luồng đang tham gia, hoặc đăng bảng tin | `message_id`, `post_id` |
| Gửi email | Xếp hàng gửi qua `SMTP_*`; chưa cấu hình thì luồng không qua kiểm tra | `to`, `queued` |
| Gọi API lấy dữ liệu | Gọi một kết nối đã khai, trong `AUTOMATION_ALLOWED_HOSTS`; cổng Thành công hoặc Lỗi | `ok`, `status`, các giá trị đơn trả về |
| AI trích xuất | Đọc tài liệu của hồ sơ và nội dung thêm, trả về các trường đã khai và bản tóm tắt; cần bật tính năng Hỏi AI trong luồng | các trường, `summary` |

Bước hành động chạy theo quyền của người tạo luồng, không rộng hơn người đó.

## Vòng đời một quy trình

1. **Chọn mẫu:** thư viện mẫu, hoặc dựng từ bước duyệt của một biểu mẫu. Chọn biểu mẫu có sẵn hay tạo mới ngay tại đây.
2. **Vẽ:** canvas là **bản nháp**. Lưu bản nháp không ảnh hưởng ai.
3. **Phân quyền:** vai trò và phòng ban được dùng. Danh sách trống là không giới hạn; chọn cả hai thì phải khớp cả hai.
   Quyền sử dụng có hiệu lực ngay; số tài liệu tối thiểu thuộc nội dung quy trình, áp dụng từ lần phát hành sau.
4. **Kịch bản thử (không bắt buộc):** mỗi kịch bản là một hồ sơ mẫu với câu trả lời biểu mẫu, số tài liệu, quyết định ở
   từng bước và kết quả mong đợi. Kịch bản đi qua bản nháp bằng chính `Execution` chạy thật ở chế độ `dry_run`, không tạo
   nhiệm vụ, việc hay thông báo. Mã lỗi mong đợi được: `required_documents_missing`, `form_validation_error`,
   `approver_unresolved`, `consultees_missing`.
5. **Phát hành:** đồ thị hợp lệ, biểu mẫu đã phát hành, và mọi kịch bản đã viết có báo cáo đạt trên đúng hash bản nháp
   lẫn đúng tập kịch bản hiện tại (không thì `simulation_required`). Hash gồm biểu mẫu, các node, đường nối và số tài
   liệu; không gồm vị trí node trên canvas. Phiên bản trước chuyển `retired`.
6. **So sánh tác động:** trước khi phát hành lại, chạy cùng các kịch bản trên phiên bản đang áp dụng và bản nháp, liệt kê
   bước thêm, bỏ, đổi và kịch bản đổi kết quả. Cả hai bên đánh giá theo cơ cấu tổ chức hiện tại.

Ngừng áp dụng thì hồ sơ mới không dùng quy trình nữa; hồ sơ đã ghim vẫn đi theo phiên bản của mình.

## Hồ sơ đi theo quy trình

Khi tạo hồ sơ, người dùng chọn trong các quy trình mình được dùng. Một biểu mẫu có thể có nhiều quy trình, ví dụ mỗi
phòng ban một đường đi: có một quy trình dùng được thì tự chọn, có nhiều thì bắt buộc chọn (`process_required`), không
có quyền thì `process_use_denied`. Hồ sơ ghim phiên bản lúc tạo (`cases.process_version_id`); bản nháp cũ chưa ghim dùng
phiên bản đang áp dụng lúc trình. Biểu mẫu chưa có quy trình vẫn chạy theo bước duyệt khai trong biểu mẫu, và lần trình
đang chạy theo bước tuyến tính chạy tiếp như cũ.

| Bước | Hành vi |
|---|---|
| Duyệt | Một người (lãnh đạo đơn vị của hồ sơ hoặc người cụ thể) quyết định; cổng Duyệt / Trả lại / Từ chối. Cổng không nối thì hồ sơ kết thúc tương ứng: đã duyệt, cần bổ sung, bị từ chối. |
| Xin ý kiến | Nhiều người trả lời cùng lúc (Đồng ý / Không đồng ý kèm lý do). Chế độ "tất cả" chờ đủ người và chỉ đi cổng Đồng ý khi mọi người đồng ý; chế độ "một người" đi tiếp ngay khi có người đồng ý và đóng các yêu cầu còn lại. |
| Giao việc và chờ | Tạo việc gắn với hồ sơ dưới quyền người tạo quy trình; đi cổng Xong khi việc được nghiệm thu, cổng Hủy khi việc bị hủy. |
| Yêu cầu bổ sung / Kết thúc | Chốt kết quả hồ sơ, gửi thông báo cho người tạo kèm lời nhắn; các bước khác còn chờ được đóng. |
| Điều kiện, Chờ, Thông báo, Tạo việc, Webhook, Hỏi AI | Như luồng tự động; Điều kiện đọc thêm `form.<trường>`, `file_count`, `file_names`, `submission_no`. |


Đồ thị được ghim vào lượt chạy lúc bắt đầu. Mỗi bước Duyệt
hoặc mỗi người được xin ý kiến là một run của workflow Core một bước (`human_task`) tạo riêng cho lần trình; quyết
định ghi ở Workspace trước rồi mới hoàn tất human task, như bước duyệt tuyến tính. Thu hồi hồ sơ hủy lượt chạy
và các run Core còn chờ. Lượt chạy không còn bước nào chờ mà chưa có kết quả (ví dụ người duyệt bị khóa, không
xác định được lãnh đạo đơn vị) được đánh dấu lỗi, lần trình chuyển `configuration_error`, người tạo hồ sơ và
người tạo quy trình được báo.

`GET /workspace/v1/cases/{id}/process` trả đồ thị và trạng thái từng bước theo quyền xem hồ sơ; tab **Quy trình**
trong chi tiết hồ sơ vẽ nó dạng chỉ đọc. Hồ sơ theo bước duyệt tuyến tính cũng được vẽ (mỗi bước một node Duyệt,
bước có điều kiện đứng sau node Điều kiện). Chạy thử trên canvas nhận `decisions` (theo id node) để giả lập
quyết định từng bước; chạy thử không tạo nhiệm vụ, việc hay thông báo.


## Cấu hình từng bước

Các bước Duyệt, Xin ý kiến và Nhập thông tin có chung những lựa chọn sau.

| Lựa chọn | Cách hoạt động |
|---|---|
| Người xử lý | Lãnh đạo đơn vị của hồ sơ, một người, một nhóm, theo vai trò (trong đơn vị hoặc toàn tổ chức), thành viên một phòng ban, hoặc người ghi trong một trường biểu mẫu. Trường phải khớp đúng một họ tên; tên trùng hoặc không khớp thì quy trình dừng và báo lỗi. Người tạo hồ sơ không bao giờ được duyệt hay cho ý kiến hồ sơ của mình, nhưng có thể được hỏi ở bước Nhập thông tin. |
| Nhiều người | Bước Duyệt: người đầu tiên trả lời, tất cả, hoặc đủ số người. Một người trả lại là đi cổng Trả lại ngay; không còn đủ người để đạt số cần thì đi cổng Từ chối. Bước Xin ý kiến: tất cả, một người, hoặc đủ số người đồng ý. Số cần lớn hơn số người hỏi được thì bước báo lỗi `quorum_impossible`. |
| Khi quá hạn | Nhắc người đang xử lý, chuyển cho người khác (mặc định lãnh đạo đơn vị), hoặc đi cổng Quá hạn. Việc này chạy một lần qua outbox, và không tác động nếu bước đã xong hoặc đã được hỏi lại. |
| Quay lại bước trước | Nối cổng Trả lại về một bước đã qua. Từ bước đó trở đi được chạy lại; câu trả lời cũ vẫn lưu, đánh dấu đã thay thế. Mỗi bước chạy tối đa 5 lần, quá thì lượt chạy dừng và báo người tạo hồ sơ và người tạo quy trình. Chỉ cổng Trả lại được đi ngược; vòng lặp khác bị từ chối khi kiểm tra đồ thị. |
| Được xem, được sửa | Giới hạn trường biểu mẫu và tài liệu mà người ở bước đó xem được, kiểm tra ở API chi tiết hồ sơ, tải tệp và tính năng AI trên hồ sơ. Không áp dụng cho người tạo hồ sơ và người vốn được đọc hồ sơ theo vai trò (giám đốc, lãnh đạo đơn vị của hồ sơ). Trường được sửa khi duyệt ghi vào dữ liệu hồ sơ; bản chụp lần trình giữ nguyên, nhật ký ghi lại giá trị mới. |
| Chuyển người xử lý | Tắt được việc người được ủy quyền xử lý thay ở từng bước. Bật được việc người được hỏi chuyển yêu cầu cho người khác kèm lý do. |

**Nhập thông tin:** người được hỏi điền các trường do bước đặt ra và đính kèm tệp nếu được phép. Giá trị dùng được trong
điều kiện sau đó qua `form.<mã>` và hiện trong tab Quy trình; tệp được thêm vào hồ sơ. Mã trường không được trùng trường
của biểu mẫu.

**Quy trình con:** chạy một quy trình đã phát hành. Kết quả Duyệt, Yêu cầu bổ sung, Từ chối chọn cổng đi tiếp; cổng không
nối thì hồ sơ kết thúc theo kết quả đó. Quy trình con được bung thành các bước ngay lúc phát hành, nên phiên bản cha ghim
phiên bản con; con phát hành lại thì cha báo có thay đổi và phải phát hành lại. Không gọi lại chính mình
(`subprocess_cycle`). Điều kiện của quy trình con đọc dữ liệu hồ sơ của quy trình cha, nên hai bên nên dùng chung biểu mẫu.

Giới hạn hiện tại:

- Gửi email chỉ báo đã xếp hàng; lỗi ở máy chủ thư được thử lại trong outbox và không đưa luồng sang nhánh khác.
- Trong kịch bản thử, quyết định chỉ đặt được cho bước của chính quy trình; bước trong quy trình con coi như được duyệt.
  Quyết định giả lập áp dụng cho lần hỏi đầu, các lần sau coi như duyệt.
- Quay lại bước trước không tự hủy việc đã giao ở bước Giao việc và chờ; việc đó giữ nguyên, kết quả của nó bị bỏ qua.
- Bước Giao việc và chờ chưa có xử lý quá hạn.

## Chuyển từ Gói nghiệp vụ

Migration `workspace_0018` chuyển mỗi gói thành một quy trình giữ nguyên id và mỗi phiên bản đã phát hành hoặc có hồ sơ
ghim thành một `process_versions` giữ nguyên id. Phiên bản mới nhất, dù chưa phát hành, trở thành bản nháp trên canvas.
Bộ thử cũ chép sang thành kịch bản nhưng bỏ quyết định giả lập và đường đi kỳ vọng, vì chúng đặt theo node của Core; kịch
bản chuyển sang chỉ kiểm tra đi được đến kết thúc hoặc đúng mã lỗi. Bảng `business_packages`, `simulation_suites` và
`simulation_reports` giữ lại chỉ để đọc lịch sử. Luồng `process` đang bật được phát hành thành phiên bản 1.

Sau khi cập nhật mã, chạy migration Core và Workspace trước khi khởi động API. Với Compose, các job `core-migrate` và
`workspace-migrate` thực hiện bước này.

## Căn cứ và chỉ số

Trang hồ sơ có căn cứ theo trường. Người tạo hồ sơ nhập một giá trị đề xuất cùng trích đoạn, trang và tài liệu nguồn; hệ thống ghim file version/hash, cho xác nhận, sửa hoặc bác bỏ. Danh sách căn cứ và mở tài liệu nguồn đều kiểm tra quyền truy cập file hiện tại. Bản nhập tay được ghi `manual_import` và không tự nhận là kết quả OCR/AI. Dịch vụ tích hợp có endpoint riêng `/workspace/v1/cases/{id}/field-evidence/import`, yêu cầu service token, phiên bản file hiện hành và provenance job/profile/prompt; kết quả hiện nhãn AI nhưng luôn cần người dùng xác nhận. Chưa có provider OCR/LLM chạy tự động. Xác nhận căn cứ không tự sửa dữ liệu biểu mẫu; người dùng sửa và lưu bản nháp qua luồng hiện có. Dashboard chỉ tính nhiệm vụ tạo sau migration thêm `approval_tasks.created_at`; dữ liệu lịch sử không có mốc này được loại khỏi mẫu. Chỉ số tôn trọng quyền xem hồ sơ, có khoảng thời gian, cỡ mẫu và thời điểm cập nhật.

Trang Báo cáo đưa gợi ý kiểm tra bước chờ lâu khi có ít nhất 5 nhiệm vụ hoàn thành và trung bình từ 24 giờ, hoặc xem lý do trả lại khi có ít nhất 3 lần. Đây là quy tắc gợi ý cố định, không phải kết luận về cá nhân.
