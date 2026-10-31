<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# Tính năng AI

17 tính năng AI rải trong các màn hình. Ban giám đốc và Quản trị kỹ thuật (quyền `assistant.manage`, cùng
quyền với trợ lý AI) bật từng tính năng ở **Trợ lý AI › Tính năng AI**, chọn dịch vụ AI riêng cho từng tính
năng nếu muốn. Tính năng chưa bật thì không có nút nào hiện ra. Mặc định mọi tính năng đều tắt.

Một **dịch vụ AI** (một khóa API hoặc một máy chủ, khai ở tab Dịch vụ AI) dùng được cho nhiều tính năng.
Mỗi tính năng chọn dịch vụ rồi chọn **model** trong danh sách model dịch vụ đó đang có (lấy trực tiếp từ
dịch vụ: OpenAI, Gemini, Claude, DeepSeek, Ollama, vLLM, cổng tương thích), ví dụ model nhỏ nhanh cho gợi
ý nhãn và model mạnh cho tóm tắt hồ sơ. Để trống model thì dùng model mặc định của dịch vụ. Danh sách tách
model trò chuyện với model tạo vector (theo tên model; Gemini theo khả năng model tự khai báo).

## Nguyên tắc chung

- AI chỉ **đề xuất**: điền sẵn, tóm tắt, gợi ý. Không có tính năng nào tự trình, duyệt, giao việc hay gửi đi.
- Mỗi tính năng kiểm tra quyền như màn hình nó phục vụ trước khi đọc gì, và chỉ gửi cho dịch vụ AI những gì
  người đang dùng được xem.
- Nội dung tài liệu, tin nhắn được bọc trong thẻ `<du_lieu>` và dặn model không làm theo lệnh nằm trong đó.
- Mỗi lần dùng tính một lượt vào giới hạn lượt/người/ngày (chung với trợ lý, chỉnh ở Cấu hình chung).
- Kết quả không đổi khi dữ liệu không đổi (tóm tắt hồ sơ, tóm tắt tài liệu, bản tin, nhận xét báo cáo) được
  lưu trong bảng `ai_results` để không trả tiền hai lần.
- Thao tác đáng kể được ghi Nhật ký hoạt động (đổi cấu hình, AI đọc tài liệu để đề xuất trường).

## Danh sách

| Nhóm | Tính năng | Ở đâu | Ghi chú |
|---|---|---|---|
| Hồ sơ | 1. Đọc tài liệu, tự điền biểu mẫu | Hồ sơ nháp › Thông tin | Tạo "căn cứ trường" nguồn AI, mỗi giá trị kèm trang và câu trích. Câu trích không có thật trong tài liệu, hoặc giá trị sai kiểu, bị bỏ. Người lập xác nhận rồi bấm "Điền … giá trị đã xác nhận vào biểu mẫu". |
| | 2. Tóm tắt hồ sơ cho người duyệt | Đầu trang hồ sơ | Tóm tắt lại khi nội dung, tài liệu hoặc quyết định thay đổi. |
| | 3. Soát hồ sơ trước khi trình | Hồ sơ nháp | Quy tắc cứng (trường bắt buộc, số tài liệu của gói) cộng điểm AI thấy lệch giữa biểu mẫu và tài liệu. |
| | 4. Gợi ý ý kiến duyệt, lý do trả lại | Hộp xác nhận Phê duyệt/Trả lại/Từ chối | Chỉ người có bước duyệt đang chờ. |
| Văn bản | 5. Soạn văn bản hành chính | Kho tài liệu › Mới | Tờ trình, công văn, thông báo, kế hoạch, báo cáo, giấy mời. Trình bày cố định theo NĐ 30/2020 (A4, lề 20/20/30/15 mm, Times New Roman, quốc hiệu 13, tiêu ngữ 14, nội dung 14), mở bằng ONLYOFFICE để plugin `vn-document-format` kiểm tra. |
| | 6. Tóm tắt và hỏi đáp trên tài liệu | Kho tài liệu › Hỏi AI | Câu trích được đối chiếu với trang; câu không tìm thấy nguyên văn được đánh dấu. |
| | 7. Tìm theo ý nghĩa | Trang Tìm kiếm | Cần chọn dịch vụ và model tạo vector (ví dụ Ollama `bge-m3`). Chỉ mục tài liệu, công việc, hồ sơ chạy trong worker; kết quả lọc theo quyền xem. |
| | 8. Gợi ý nhãn và thư mục | Kho tài liệu › Nhãn | Ưu tiên nhãn đã dùng, chỉ gợi ý thư mục người dùng được ghi. |
| Công việc | 9. Giao việc bằng câu nói | Hộp Giao việc mới | Người nhận phải nằm trong danh sách được giao; không chắc thì để trống. |
| | 10. Tách việc lớn thành việc con | Chi tiết công việc | Việc con tạo ra ở dạng nháp chưa giao; hạn không quá hạn việc lớn. |
| | 11. Bản tin "Việc hôm nay" | Trang chủ | Lưu theo người, theo ngày. |
| | 12. Báo cáo điều hành bằng lời | Trang Báo cáo | Theo đúng kỳ và phạm vi đang xem. |
| Trao đổi | 13. Tóm tắt hội thoại dài | Chat › nút ✨ | Chỉ thành viên; mỗi việc cần làm có nút "Tạo việc" (dùng tính năng 9). |
| | 14. Hỗ trợ viết bài bảng tin | Khung soạn bài | Viết gọn, sửa chính tả, gợi ý tiêu đề, mô tả ảnh cho trình đọc màn hình (lưu ở `post_attachments.alt`). |
| Mở rộng | 15. Bước "Hỏi AI" trong luồng | Trình thiết kế luồng | AI chọn một đáp án; node Điều kiện rẽ nhánh theo trường kết quả (mặc định `ai_label`). |
| | 16. Trợ lý trả lời về dữ liệu của người hỏi | Trợ lý AI | Thêm vào lời dặn: hồ sơ, việc, việc chờ duyệt của chính người hỏi. Không bao giờ của người khác. |
| | 17. Sinh kịch bản thử cho Gói nghiệp vụ | Gói nghiệp vụ › Chạy thử | Kết quả mong đợi lấy từ lần chạy thử thật của gói, người dùng kiểm tra lại trước khi lưu. |

## Đọc tài liệu

`dx_workspace/ai_text.py` đọc PDF bằng `pypdf` (BSD-3-Clause); Word, Excel, PowerPoint đọc thẳng XML trong tệp.
Tệp scan hoặc ảnh không có lớp chữ: tính năng gửi chính tệp cho dịch vụ đọc được ảnh (Claude, OpenAI, Gemini
đọc được cả PDF; Ollama, vLLM, cổng Chat Completions xem được ảnh nếu model có thị giác). DeepSeek chỉ đọc chữ.
Tối đa 20 MB một tệp, 60 trang.

## Đã kiểm tra

- 12 test backend (`services/workspace-api/tests/test_ai.py`) với dịch vụ AI giả, gồm cả việc không gọi ra mạng
  từ worker; 1 test frontend.
- Ngày 31/10/2026 gọi thật Ollama `gpt-oss:20b` (đọc báo giá ra JSON đúng câu trích, câu giao việc, soạn tờ
  trình ra tệp Word) và `bge-m3` (vector 1024 chiều). Mỗi lần gọi model chạy trên máy mất khoảng 50 giây.
- Chưa thử với Claude, OpenAI, Gemini thật; chưa thử tài liệu scan với model có thị giác.
