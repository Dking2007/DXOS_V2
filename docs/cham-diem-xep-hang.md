# Chấm điểm và xếp hạng sáu dự án (bản 2, theo thể lệ)

Ngày: 31/10/2026. **Bản 1 của tôi dùng thang tự đặt và đã sai hướng**: nó thưởng bảo mật, CI và vận hành, những thứ thể lệ
không chấm trực tiếp, nên đánh giá thấp dự án có sản phẩm và hồ sơ tốt. Bản này thay thế bản 1.

## 1. Thể lệ chấm điểm (nguồn và độ tin cậy)

Tổng 100 điểm: **I. Tiêu chí PoF (50, chấm trước chung kết)** và **II. Tiêu chí sản phẩm (50, chấm trong buổi chung kết)**.
Nguồn: bản sao bài "Thể lệ OLP PMNM 2026" (VFOSSA, đăng 09/06/2026) nằm trong `docs/` của repo FoodSafe-DX-OS. Tôi **chưa đọc
bản gốc trên vfossa.vn**; hai bản sao trong repo đó có vài chỗ khác chữ (ví dụ tiêu chí UX), và một "cẩm nang" ở đó do AI trích từ PDF.
Nên đối chiếu lại với thể lệ gốc trước khi dựa vào.

**I. PoF (50)**: quản lý mã nguồn 5; giấy phép OSI 10; có ít nhất một release 5; cài đặt/biên dịch từ mã nguồn 10;
thư viện và gói đính kèm 10; tài liệu và giao tiếp 10. Mỗi mục trừ điểm theo lỗi cụ thể (ví dụ: không có web viewer -3;
không có bug tracker, không có changelog, không có README -5 mỗi lỗi; không có release -5; sửa mã gói đính kèm -5).

**II. Sản phẩm (50), mỗi mục 10, chấm trong buổi thi**:
1. Tính nguyên gốc của giải pháp kỹ thuật (sự sáng tạo trình bày);
2. Mức độ hoàn thiện (live demo mượt, hạn chế lỗi/crash);
3. Mức độ thân thiện (UX/UI, tiện ích cho người dùng);
4. Mức độ phát triển bền vững (tài liệu kỹ thuật, kiến trúc, API docs, khả năng duy trì);
5. Phong cách trình diễn và khả năng thu hút cộng đồng nguồn mở.

**Điều quan trọng**: bảo mật, CI xanh và hạ tầng production **không phải tiêu chí riêng**. Chúng chỉ gián tiếp ảnh hưởng
tới "hoàn thiện" (không crash khi demo) và "bền vững" (tài liệu, kiến trúc).

**Đề thi (VFOSSA, đăng 30/09/2026)** không có thang điểm. Nó yêu cầu: Core headless ở Tầng 1 với bốn dịch vụ bắt buộc
(Identity/SSO, API Gateway, quản trị dữ liệu cấu trúc và phi cấu trúc, workflow) và **ít nhất một ứng dụng giao diện** ở Tầng 2
thuộc không gian H-P-D-I. "Bảy lớp công nghệ" chỉ là tham chiếu, đội tự chọn công nghệ. Bốn nguyên tắc kỹ thuật được nêu: vòng
đời dữ liệu, hội tụ IT/OT, truy nguồn và chất lượng dữ liệu, Zero-Trust gắn GitOps với kiểm dịch mã độc tại biên.
Chung kết: **trình bày 15 phút** (giải pháp, tính năng, demo, định hướng). Hạn nộp: **17:00 06/12/2026**, qua email.

## 2. Bảng điểm bản 2

| Tiêu chí (tối đa) | Desktiny | commune-dxos | PSA | OpenDXOS | FoodSafe | OpenCity |
|---|---|---|---|---|---|---|
| **I.1** Quản lý mã nguồn (5) | 4 | 5 | 5 | 2 | 1 | 3 |
| **I.2** Giấy phép (10) | 9 | 9 | 9 | 5 | 8 | 7 |
| **I.3** Release (5) | 5 | 5 | 5 | 0 | 3 | 0 |
| **I.4** Cài đặt/biên dịch (10) | 9 | 9 | 8 | 8 | 6 | 7 |
| **I.5** Thư viện/gói (10) | 10 | 6 | 9 | 8 | 8 | 9 |
| **I.6** Tài liệu, giao tiếp (10) | 10 | 10 | 6 | 7 | 3 | 3 |
| **Cộng I (50)** | **47** | **44** | **42** | **30** | **29** | **29** |
| **II.1** Nguyên gốc (10) | 6 | 8 | 9 | 8 | 5 | 4 |
| **II.2** Hoàn thiện, demo (10) | 7 | 7 | 6 | 6 | 5 | 4 |
| **II.3** Thân thiện, UX (10) | 8 | 7 | 5 | 7 | 5 | 6 |
| **II.4** Bền vững, tài liệu kỹ thuật (10) | 8 | 8 | 9 | 6 | 4 | 5 |
| **II.5** Trình diễn, cộng đồng (10) | 7 | 7 | 5 | 6 | 5 | 4 |
| **Cộng II (50)** | **36** | **37** | **34** | **33** | **24** | **23** |
| **TỔNG (100)** | **83** | **81** | **76** | **63** | **53** | **52** |

Hạng: 1 Desktiny, 2 commune-dxos, 3 PSA, 4 OpenDXOS, 5-6 FoodSafe và OpenCity (hòa trong sai số).

## 3. Lý do những điểm quan trọng

**Phần I chấm theo đúng danh sách lỗi trừ điểm.**
- *I.1:* chỉ trừ khi không có web viewer, không công khai, hoặc "không thực sự dùng VCS" (chỉ upload một commit cuối).
  Desktiny có lịch sử và issue; tôi chỉ trừ 1 vì một tác giả. OpenDXOS (5 commit trong một ngày) và FoodSafe (29 commit cùng một
  ngày) có nguy cơ bị coi là upload gộp.
- *I.3:* thể lệ chỉ cần **một** release có phiên bản, trước hạn nộp. Phát hành hằng tuần không cho thêm điểm. OpenDXOS và OpenCity
  hiện chưa có release, nhưng họ còn thời gian; điểm này sẽ thay đổi.
- *I.5:* "gói đính kèm bị sửa" trừ -5. commune-dxos chép các thành phần shadcn vào repo và chỉnh sửa (README của họ nói không chép), nên tôi trừ.
- *I.6:* thiếu changelog -5, bug tracker -5, README -5. PSA ghi "bật GitHub Issues, có issue của người dùng thử" là việc chưa làm trong danh sách của họ;
  FoodSafe và OpenCity không có CHANGELOG.

**Phần II tôi không quan sát được trực tiếp** (chấm trong buổi thi). Đây là ước lượng từ tài liệu, ảnh chụp và mô tả:
- *Nguyên gốc:* PSA cao nhất (niêm phong và xác minh công khai không cần tin quản trị viên); OpenDXOS và commune-dxos cao (cổng duyệt
  cho nhân sự AI; thủ tục một cửa dạng thư mục kèm OCR/RAG/ký PDF). Desktiny ở mức vừa: canvas tự động hóa và plugin Nghị định 30 là
  điểm riêng, phần còn lại là chức năng văn phòng quen thuộc.
- *Hoàn thiện:* Desktiny có sản phẩm rộng nhưng ONLYOFFICE thật, backup và `make up` từ đúng commit chưa kiểm; PSA nặng và nhiều thứ chưa chạy thật.
- *UX:* Desktiny có Ctrl+K, chế độ tối, điều hướng mobile, hướng dẫn lần đầu; PSA chỉ có cổng xác minh và trang quản trị tối giản.
- *Bền vững:* PSA có spec, ADR, OpenAPI, runbook; Desktiny và commune-dxos tài liệu kiến trúc và hợp đồng API tốt.
- *Cộng đồng:* Desktiny có hai PR gửi lên Keycloak/ONLYOFFICE và gói `dx-flowkit`; chưa dự án nào có sao hay fork.

## 4. Vì sao OpenDXOS "nét" nhưng vẫn xếp sau

Nhận xét của bạn đúng ở phần II: OpenDXOS đạt 33/50, sát Desktiny (36), nhờ ý tưởng nhân sự AI có cổng duyệt, cửa hàng và console
rộng, giao diện có đầu tư. Họ tụt ở **phần I (30/50)**, chấm trước chung kết bằng kho mã: chưa release, CI đỏ, 5 commit, kiểm SPDX chỉ
4 loại tệp, dữ liệu cá nhân trong kho. Phần này sửa được trong 5 tuần nếu họ làm đúng việc, nên đừng xem họ là yếu về cuối cùng.
Họ cũng bám sát đề hơn ở phần LLM và AI so với Desktiny (chưa có LLM).

## 5. Độ tin cậy

- Phần II là ước lượng từ tài liệu, sai số khoảng ±8 điểm mỗi dự án. Ba dự án đầu (83, 81, 76) **nằm trong sai số của nhau**; chỉ nên kết luận
  rằng ba dự án này thuộc nhóm đầu và OpenDXOS, FoodSafe, OpenCity thấp hơn rõ rệt.
- Phần I sát hơn nhưng dựa trên trang công khai, chưa clone, chưa chạy. Số test của đối thủ không được dùng làm cơ sở.
- Tôi đọc mã Desktiny nhiều nhất và nhiều chỗ đã tự kiểm; dự án khác chủ yếu qua tài liệu. Điều này có thể làm Desktiny trông tốt hơn
  hoặc xấu hơn tùy chỗ.
- Thể lệ tôi dùng là bản sao trong một repo khác. Cần đối chiếu với bản gốc.

## 6. Hệ quả cho Desktiny

| Việc | Ảnh hưởng tới | Mức |
|---|---|---|
| Demo ổn định, không crash (kiểm ONLYOFFICE, `make up` từ tag, backup) | II.2 | Cao |
| Nút "chờ duyệt", cảnh báo CCCD, xác minh audit: câu chuyện riêng của Desktiny | II.1, II.5 | Cao |
| Làm ClamAV: đề thi nêu kiểm dịch mã độc tại biên | II.1, II.2 và độ khớp đề | Cao |
| Trình bày 15 phút: ba kịch bản rõ, video dự phòng | II.2, II.5 | Cao |
| Tài liệu kiến trúc, API docs, `DEPENDENCIES.md` | II.4, I.5, I.6 | Vừa |
| Thêm tác giả và PR | I.1 (tối đa +1 theo thể lệ) | Thấp về điểm, vẫn nên làm vì rủi ro "không dùng VCS" |
| Compose production, phát hành hằng tuần | Không có tiêu chí riêng | Thấp |
| LLM/RAG: đề có nhắc | II.1 | Cần quyết định có làm không; tôi khuyên không, trừ khi còn thời gian |

Xem thêm mục "Đính chính" ở cuối `huong-dan-buoc-tiep-theo.md`.
