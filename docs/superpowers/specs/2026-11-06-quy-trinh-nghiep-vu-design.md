# Quy trình nghiệp vụ: gộp Tự động hóa và Gói nghiệp vụ

Ngày 06/11/2026. Yêu cầu gốc ở `yc.md`, mục "Gộp quy trình và tự động hoá với nhau".

## Mục tiêu

Menu chỉ còn một mục **Quy trình nghiệp vụ**. Giám đốc và quản trị kỹ thuật chọn mẫu, chỉnh trên canvas, phân quyền
sử dụng, phân công người xử lý từng bước rồi phát hành. Nhân viên tạo hồ sơ theo quy trình mình được dùng và xem hồ
sơ đang ở bước nào trên chính sơ đồ đó.

## Các quyết định đã chốt

| Câu hỏi | Quyết định |
|---|---|
| Phần quản trị của gói | Chuyển hết sang quy trình canvas, không mất chức năng |
| Ai chọn mẫu | Hai tầng: người quản lý chọn mẫu và phát hành; nhân viên chỉ làm theo |
| Ai thiết kế | Giám đốc và quản trị kỹ thuật (`automations.manage`) |
| Phân quyền | Cả phân quyền sử dụng (vai trò, phòng ban) lẫn phân công người xử lý từng bước |
| Khả năng của node | Cả 8 mục, chia giai đoạn |
| Lưu trữ | Luồng canvas làm gốc, thêm bảng phiên bản (cách X) |

## Giai đoạn

1. **Gộp nền (spec này):** menu, thư viện mẫu, nháp/phát hành, phân quyền sử dụng, kịch bản thử, chuyển gói cũ.
2. **Bộ máy:** người xử lý linh hoạt, nhiều người cùng duyệt, xử lý quá hạn, quay lại bước trước.
3. **Bước mở rộng:** bước nhập liệu, quyền theo bước, ủy quyền theo bước, quy trình con.

## Giai đoạn 1

### Dữ liệu (migration `workspace_0018`)

- `automation_rules` thêm `allowed_roles`, `allowed_department_ids`, `required_file_count`, `active_version_id`.
  Với luồng loại `process`, `graph` là **bản nháp**; `enabled` đúng khi và chỉ khi có `active_version_id`.
- Bảng mới `process_versions`: ảnh chụp đã phát hành gồm đồ thị, biểu mẫu, số tài liệu tối thiểu, hash, trạng thái
  `published` hoặc `retired`.
- Bảng mới `process_scenarios` và `process_scenario_reports`: kịch bản thử gắn với quy trình, báo cáo gắn với hash.
- `cases.process_version_id` và `case_submissions.process_version_id`: hồ sơ ghim phiên bản.

### Chuyển dữ liệu gói

Mỗi gói thành một luồng `process` **giữ nguyên id**, mỗi phiên bản đã phát hành thành một `process_versions` giữ
nguyên id, nên các tham chiếu cũ (bài kiến thức, thống kê) vẫn đúng. Đồ thị dựng bằng `steps_graph`. Quyền hạn, số tài
liệu và bộ thử được chép sang; quyết định giả lập và đường đi kỳ vọng của bộ thử cũ không chép được vì đặt theo node
của Core, nên kịch bản chuyển sang chỉ kiểm tra kết thúc được hoặc đúng mã lỗi kỳ vọng. Bảng gói cũ giữ lại chỉ để
đọc lịch sử. Luồng `process` đang bật được phát hành thành phiên bản 1.

Lần trình đang chạy theo bước tuyến tính chạy tiếp như cũ. Biểu mẫu chưa có quy trình vẫn dùng bước duyệt của mình.

### Hành vi

- **Phát hành:** đồ thị hợp lệ, biểu mẫu đã phát hành, mọi kịch bản có báo cáo đạt đúng hash hiện tại. Phiên bản cũ
  chuyển `retired`. Sửa canvas không ảnh hưởng ai cho đến lần phát hành sau.
- **Một biểu mẫu nhiều quy trình:** được phép, vì gói vốn cho phép và cần cho phân quyền theo phòng ban. Thay cho quy
  tắc một quy trình mỗi biểu mẫu của PR #35. Khi tạo hồ sơ: một quy trình dùng được thì tự chọn, nhiều thì bắt buộc
  chọn (`process_required`), không có quyền thì `process_use_denied`.
- **Phân quyền sử dụng:** danh sách rỗng là không giới hạn; có cả vai trò và phòng ban thì phải khớp cả hai.
- **Chạy thử:** dùng `Execution` ở chế độ `dry_run`, cùng mã với lúc chạy thật, thay cho mô phỏng ở Core.
- **So sánh tác động:** chạy cùng kịch bản trên phiên bản đang áp dụng và bản nháp.
- **Quyền:** `technical_admin` được thêm `forms.manage` để tạo biểu mẫu. Lãnh đạo phòng không còn quản lý gói.

### API

| Phương thức | Đường dẫn | Việc |
|---|---|---|
| GET | `/processes/available` | Quy trình người hỏi được dùng để tạo hồ sơ |
| PUT | `/processes/{id}/settings` | Quyền sử dụng, số tài liệu tối thiểu |
| POST | `/processes/{id}/publish`, `/unpublish` | Phát hành, ngừng áp dụng |
| GET | `/processes/{id}/versions` | Lịch sử phiên bản |
| GET, POST, DELETE | `/processes/{id}/scenarios` | Kịch bản thử |
| POST, GET | `/processes/{id}/scenario-reports` | Chạy và xem báo cáo |
| GET | `/processes/{id}/impact` | Tác động của bản nháp so với bản đang áp dụng |

Bỏ `/business-packages*`, `/package-versions*` và wizard `/processes` của nhánh rà soát. `CaseCreate` đổi
`package_version_id` thành `process_id`. `/automations/{id}/enabled` với luồng `process` tương đương phát hành hoặc
ngừng áp dụng.

### Giao diện

- `/processes` thay cho `/automations` và `/packages` (đường dẫn cũ chuyển hướng), hai tab *Quy trình hồ sơ* và *Tự
  động hóa*.
- Tạo quy trình bắt đầu từ thư viện mẫu; chọn biểu mẫu có sẵn hoặc tạo mới bằng `FormDesigner`.
- Trình thiết kế có thêm phần phân quyền, kịch bản thử, phiên bản và nút Phát hành.
- Tạo hồ sơ chọn theo quy trình được dùng; tab Quy trình trong hồ sơ giữ nguyên.

### Kiểm thử

Chuyển các trường hợp của `test_packages.py` và `test_processes.py` sang `test_process_versions.py`: cổng phát hành,
hash cũ, kịch bản không đạt chặn phát hành, phân quyền, ghim phiên bản, chuyển dữ liệu gói trên PostgreSQL. Chạy thật
trên trình duyệt: chọn mẫu, phát hành, nhân viên tạo hồ sơ, xem tiến độ.

## Giai đoạn 2 và 3

Hành vi chi tiết ở `docs/process-packages.md`, mục "Cấu hình từng bước". Các quyết định thiết kế:

- **Đi ngược:** đồ thị chỉ được có chu trình qua cổng `return`. Khi quay lại, các bước từ đó trở đi được đánh dấu
  `superseded`, không xóa, và mỗi bước chạy tối đa `MAX_VISITS` lần. Khóa run Core kèm số lần hỏi để hỏi lại thật sự.
- **Nhiều người:** hàm `tally` quyết định cổng từ các câu trả lời, dùng chung cho Duyệt và Xin ý kiến.
- **Quá hạn:** job outbox `process.overdue` đặt lịch lúc hỏi, mang số lần hỏi để không tác động lên lượt sau.
- **Nhập liệu và sửa trường:** dùng chung `POST /approval-tasks/{id}/decisions`, không tạo đường thứ hai.
- **Quy trình con:** `expand_subprocesses` bung đồ thị lúc phát hành và lúc chạy thử; lượt chạy không phân biệt được bước
  của con với bước của cha, nên không cần cơ chế run lồng nhau. `sub_end` thay cho các điểm kết thúc của con.
- **Quyền theo bước:** `step_limits` tính phần hồ sơ được xem; hợp của các bước đã hỏi người đó. Tính năng AI đọc toàn bộ
  hồ sơ nên từ chối người bị giới hạn.

## Gộp thành một loại luồng

Quyết định: gộp thật, phần Kết quả gồm cả bắt buộc nộp lẫn đọc lại, làm đủ 13 node.

- `automation_rules.kind` nay suy ra từ trigger: có `form_id` là `process`. Mọi luồng phát hành theo `process_versions`.
- `approval_tasks.submission_id`, `case_id` có thể trống; `run_id` nối yêu cầu với lượt chạy. `ProcessExecution` nhận
  `submission=None`, khi đó `conclude` chỉ kết thúc lượt chạy mà không đụng hồ sơ.
- **Hai bộ máy, một hành vi:** luồng chỉ gồm bước tự động không cần Core vẫn chạy bằng `Execution`; luồng có bước cần người
  hoặc cần Core chạy bằng `ProcessExecution` (`needs_engine`). Giữ vậy để không đổi đường chạy và cách đếm trạng thái của
  các luồng đang hoạt động.
- **Chờ đủ nhánh:** `edge_state` phân loại mỗi đường vào là đã đi, không còn đi được, hay còn chờ; `walk` xét lại các bước
  chờ khi hết việc, nên nhánh chết không làm luồng kẹt.
- **Kết quả:** `set_output` ghi vào `run.data` theo `output_key`, nên `value_of` và `render` đọc được mà không cần cơ chế mới.

## Ngoài phạm vi

Xóa bảng gói cũ. Thay đổi mô phỏng ở Core. Tự hủy việc đã giao khi quay lại bước trước.
