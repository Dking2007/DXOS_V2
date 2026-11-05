# Gói nghiệp vụ và chạy thử quy trình

Phần P0 của [đề xuất cải thiện](design/Cai_thien_nen_tang_quy_trinh_so_DXOS.md) dùng biểu mẫu đã phát hành làm schema bất biến. Trong Workspace, người có quyền `forms.manage` mở **Gói nghiệp vụ**, chọn biểu mẫu, số tài liệu tối thiểu và vai trò được sử dụng. Điều kiện và người duyệt nằm trong biểu mẫu; muốn đổi chúng, tạo biểu mẫu mới rồi tạo phiên bản gói mới.

Bước duyệt chỉ khai báo ở biểu mẫu; mỗi phiên bản gói giữ bản sao các bước duyệt của biểu mẫu tại lúc tạo, tham chiếu biểu mẫu và hash cấu hình. Gói cần ít nhất một bước duyệt không có điều kiện để mọi hồ sơ luôn có đường xử lý. Trình tự phát hành: tạo draft → kiểm tra cấu hình → (không bắt buộc) nhập fixture, số tài liệu mẫu và quyết định giả lập, lưu đường đi hoặc mã lỗi kỳ vọng, chạy bộ thử → phát hành. Các mã lỗi kỳ vọng gồm thiếu tài liệu, biểu mẫu không hợp lệ, thiếu người duyệt và tự duyệt. Cổng phát hành yêu cầu phiên bản đã kiểm tra cấu hình, và mọi bộ thử đã tạo cho đúng hash cấu hình đều có báo cáo mới nhất đạt. Một preview hoặc bộ thử đang chờ quyết định không được tính là đạt.

Core chạy simulation bằng cùng hàm đánh giá điều kiện và chọn cạnh của runtime. Simulation chỉ ghi bản chạy thử và trả đường đi, người nhận, trace; nó không tạo human task, hồ sơ, thông báo hay gọi provider ngoài. Người tạo và phòng ban của fixture được ghim khi lưu bộ thử; người duyệt vẫn được phân giải lại theo cơ cấu hiện tại khi chạy, để phát hiện tài khoản khóa hoặc thay đổi người nhận. Core hiện hỗ trợ `start`, `map`, `if`, `human_task`, `end`; chưa có action/HTTP connector. Kết quả người duyệt trong fixture là dữ liệu giả lập, không phải quyết định thật.

Khi tạo hồ sơ từ biểu mẫu có gói đang hoạt động, người dùng phải chọn phiên bản gói được phép dùng. Hồ sơ ghim phiên bản ấy; lần trình ghim thêm payload revision, file version và bằng chứng chọn/bỏ qua bước duyệt. Trang chi tiết hồ sơ hiển thị bằng chứng và trace nhánh lấy từ Core theo quyền xem hồ sơ.

P1 bổ sung so sánh phiên bản gói, bảng thời gian chờ theo bước trên trang tổng quan và căn cứ theo trường trên trang hồ sơ. Người tạo hồ sơ nhập một giá trị đề xuất cùng trích đoạn, trang và tài liệu nguồn; hệ thống ghim file version/hash, cho xác nhận, sửa hoặc bác bỏ. Danh sách căn cứ và mở tài liệu nguồn đều kiểm tra quyền truy cập file hiện tại. Bản nhập tay được ghi `manual_import` và không tự nhận là kết quả OCR/AI. Dịch vụ tích hợp có endpoint riêng `/workspace/v1/cases/{id}/field-evidence/import`, yêu cầu service token, phiên bản file hiện hành và provenance job/profile/prompt; kết quả hiện nhãn AI nhưng luôn cần người dùng xác nhận. Chưa có provider OCR/LLM chạy tự động. Xác nhận căn cứ không tự sửa dữ liệu biểu mẫu; người dùng sửa và lưu bản nháp qua luồng hiện có. Dashboard chỉ tính nhiệm vụ tạo sau migration thêm `approval_tasks.created_at`; dữ liệu lịch sử không có mốc này được loại khỏi mẫu. Chỉ số tôn trọng quyền xem hồ sơ, có khoảng thời gian, cỡ mẫu và thời điểm cập nhật.

P2 hiện có bộ thử nhiều hồ sơ mẫu (tối đa 20 fixture mỗi suite) và thư viện mẫu nội bộ: sao chép phiên bản gói đang phát hành thành gói nháp mới, rồi kiểm chứng và phát hành riêng. Trang Báo cáo đưa gợi ý kiểm tra bước chờ lâu khi có ít nhất 5 nhiệm vụ hoàn thành và trung bình từ 24 giờ, hoặc xem lý do trả lại khi có ít nhất 3 lần. Đây là quy tắc gợi ý cố định, không phải kết luận về cá nhân. Chưa có sandbox integration với dịch vụ thử tách biệt; chế độ simulation vẫn không gọi connector ngoài.

Sau khi cập nhật mã, chạy migration Core và Workspace trước khi khởi động API. Với Compose, các job `core-migrate` và `workspace-migrate` thực hiện bước này. Cấu hình đã phát hành không bị sửa trực tiếp; việc đổi quy trình tạo phiên bản mới.

## Quy trình hồ sơ dạng canvas

Ngoài bước duyệt tuyến tính khai trong biểu mẫu, người có quyền `automations.manage` vẽ được **quy trình hồ sơ**
trên canvas tự động hóa (tab *Quy trình hồ sơ*). Quy trình là luồng loại `process` gắn với một biểu mẫu qua node
kích hoạt "Hồ sơ được trình"; mỗi biểu mẫu chỉ bật được một quy trình. Khi bật, hồ sơ của biểu mẫu trình sau đó
không dùng `approval_steps` mà chạy quy trình; tắt thì quay lại bước duyệt của biểu mẫu.

| Bước | Hành vi |
|---|---|
| Duyệt | Một người (lãnh đạo đơn vị của hồ sơ hoặc người cụ thể) quyết định; cổng Duyệt / Trả lại / Từ chối. Cổng không nối thì hồ sơ kết thúc tương ứng: đã duyệt, cần bổ sung, bị từ chối. |
| Xin ý kiến | Nhiều người trả lời cùng lúc (Đồng ý / Không đồng ý kèm lý do). Chế độ "tất cả" chờ đủ người và chỉ đi cổng Đồng ý khi mọi người đồng ý; chế độ "một người" đi tiếp ngay khi có người đồng ý và đóng các yêu cầu còn lại. |
| Giao việc và chờ | Tạo việc gắn với hồ sơ dưới quyền người tạo quy trình; đi cổng Xong khi việc được nghiệm thu, cổng Hủy khi việc bị hủy. |
| Yêu cầu bổ sung / Kết thúc | Chốt kết quả hồ sơ, gửi thông báo cho người tạo kèm lời nhắn; các bước khác còn chờ được đóng. |
| Điều kiện, Chờ, Thông báo, Tạo việc, Webhook, Hỏi AI | Như luồng tự động; Điều kiện đọc thêm `form.<trường>`, `file_count`, `file_names`, `submission_no`. |

Đồ thị được ghim vào lượt chạy lúc trình, nên sửa quy trình chỉ ảnh hưởng hồ sơ trình sau đó. Mỗi bước Duyệt
hoặc mỗi người được xin ý kiến là một run của workflow Core một bước (`human_task`) tạo riêng cho lần trình; quyết
định ghi ở Workspace trước rồi mới hoàn tất human task, như bước duyệt tuyến tính. Thu hồi hồ sơ hủy lượt chạy
và các run Core còn chờ. Lượt chạy không còn bước nào chờ mà chưa có kết quả (ví dụ người duyệt bị khóa, không
xác định được lãnh đạo đơn vị) được đánh dấu lỗi, lần trình chuyển `configuration_error`, người tạo hồ sơ và
người tạo quy trình được báo.

`GET /workspace/v1/cases/{id}/process` trả đồ thị và trạng thái từng bước theo quyền xem hồ sơ; tab **Quy trình**
trong chi tiết hồ sơ vẽ nó dạng chỉ đọc. Hồ sơ theo bước duyệt tuyến tính cũng được vẽ (mỗi bước một node Duyệt,
bước có điều kiện đứng sau node Điều kiện). Chạy thử trên canvas nhận `decisions` (theo id node) để giả lập
quyết định từng bước; chạy thử không tạo nhiệm vụ, việc hay thông báo.

Giới hạn hiện tại: quy trình là DAG, trả lại thì người tạo sửa và trình lại từ đầu; chưa có phê duyệt theo vai trò
tùy ý, quorum hay ủy quyền theo bước; cấu hình gói nghiệp vụ (hash, bộ thử, cổng phát hành) chưa bao gồm quy
trình canvas.

