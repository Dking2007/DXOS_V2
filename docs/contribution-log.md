<!--
SPDX-FileCopyrightText: 2026 Desktiny contributors
SPDX-License-Identifier: Apache-2.0
-->

# Nhật ký đóng góp ngược

Tệp này ghi **từng bước đã làm**, có link kiểm chứng được và trạng thái thật tại thời điểm ghi.
Bảng tóm tắt nằm ở mục "Đóng góp ngược cho cộng đồng nguồn mở" trong [README](../README.md).
Khi có phản hồi của người bảo trì, thêm một dòng mới ở cuối bảng tương ứng, kèm link bình
luận công khai trên PR. Không sửa hoặc xóa dòng cũ.

Tại thời điểm ghi: 30/10/2026.

## Đóng góp gửi lên dự án bên ngoài

| Dự án | Việc | Link | Trạng thái | Ghi chú |
|---|---|---|---|---|
| ONLYOFFICE | Plugin `vn-document-format`: kiểm tra thể thức văn bản hành chính theo Nghị định 30/2020/NĐ-CP, Phụ lục I | [PR #730](https://github.com/ONLYOFFICE/onlyoffice.github.io/pull/730) | Đã gửi 30/10/2026, CLA đã ký, chờ người bảo trì xét | Commit ký DCO (`--signoff`). Nội dung PR nêu dự án Desktiny, giới hạn chưa kiểm và câu hỏi về giấy phép Apache-2.0. Chưa có phản hồi của người bảo trì |
| Keycloak | Bổ sung 2 ghi chú còn thiếu trong tài liệu nâng cấp 26.7.5 (đối chiếu `changes-26_7_5.adoc` tại tag `26.7.5` với `main`) | Issue [#53650](https://github.com/keycloak/keycloak/issues/53650), PR [#54464](https://github.com/keycloak/keycloak/pull/54464) | Đã gửi 29/10/2026, chờ xét (đã kiểm lại qua API GitHub 30/10) | Issue đang ở `status/triage`; bình luận duy nhất là của thành viên nhóm (tài khoản Dking2007) xin nhận việc. PR chưa có review hay bình luận |

## Sản phẩm của nhóm tách ra để dùng lại

| Việc | Link | Trạng thái |
|---|---|---|
| Gói `dx-flowkit` 0.1.0: kiểm tra đồ thị quy trình và mô phỏng không tác dụng phụ, tách từ `dx_core.workflow` | [PR #31](https://github.com/Raphael-Fug/DXOS_V2/pull/31), đã merge vào `main` | Đã merge. Chưa phát hành lên PyPI. `dx_core.workflow` vẫn dùng bản sao riêng |
| [PR #30](https://github.com/Raphael-Fug/DXOS_V2/pull/30) | Bản đầu của cùng thay đổi, dựa trên nhánh cũ | **Đã được thay thế**: thư mục `packages/flowkit` trên `main` giống hệt nhánh của PR này, và hai commit README của nó đã vào `main` qua các bản commit khác. Nên đóng PR, không cần merge |

## Việc đã cân nhắc nhưng không gửi

| Việc | Lý do |
|---|---|
| Bình luận vào RustFS #8992 | Người bảo trì đã trả lời, và vấn đề đã được sửa trong PR #9056 đã merge. Gửi thêm sẽ không có giá trị |

## Quá trình làm, theo thứ tự

1. **26-29/10:** rà soát repo, xác định đóng góp thật thay vì chỉ liệt kê. Kết luận: đề thi không có tiêu chí
   "đóng góp ngược" riêng, nên chỉ ghi việc có link và kết quả kiểm chứng được.
2. **29/10:** tách `dx-flowkit`, đối chiếu hành vi với bản gốc trên 20000 đồ thị và đầu vào ngẫu nhiên.
3. **30/10, plugin ONLYOFFICE:** viết plugin, 29 test, chạy thử trong Document Server 8.3.3 (Docker) trên hai tệp
   mẫu. Phát hiện bản 8.3.3 không có hàm đọc lề nên thêm phát hiện tính năng và ghi chú rõ trong plugin.
4. **30/10, gửi PR:** fork `onlyoffice.github.io`, một commit có `Signed-off-by`, mở PR #730. Bot CLA báo chưa ký,
   thành viên nhóm ký CLA, bot đổi sang "signed", 1 check đạt. Dòng "Merging is blocked" trên PR là bình thường
   vì chỉ người bảo trì mới merge được.
5. **30/10, ghi lại:** cập nhật README và tệp này. Chưa có phản hồi nào của người bảo trì nên không ghi gì thêm.
6. **31/10, `dx-flowkit` 0.2.0:** `dx_core.workflow` bỏ bản sao riêng và dùng gói này; thêm `compare` để điều
   kiện của biểu mẫu, bước duyệt và luồng tự động hóa trong Workspace cùng một quy tắc. 67 test. Vẫn chưa lên PyPI.

6. **30/10, kiểm lại trạng thái:** gọi API công khai của GitHub cho PR ONLYOFFICE #730, PR Keycloak #54464 và
   issue #53650. Cả ba còn mở, chưa merge, chưa có review. Bình luận duy nhất trên #730 là của bot CLA
   ("All committers have signed the CLA").
7. **30/10, chuẩn bị công bố `dx-flowkit` lên PyPI (chưa công bố):** trong container Python 3.13, `python -m build`
   tạo được sdist và wheel, `twine check` đạt cả hai, 56 test đạt sau khi cài gói. Tên `dx-flowkit` (và `dx_flowkit`)
   chưa có trên PyPI theo API JSON; gói gần tên nhất là `flowkit` (FlowKit, xử lý dữ liệu flow cytometry, không liên quan).
   Chưa tìm được kết quả tìm kiếm gói tương tự vì trang tìm kiếm PyPI chặn truy cập tự động.

## Phản hồi của người bảo trì

Chưa có. Thêm vào đây khi có, theo mẫu: `ngày, người, link bình luận, một câu trích ngắn, việc nhóm làm tiếp`.
