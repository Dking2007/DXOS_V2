# ĐỀ XUẤT CẢI THIỆN NỀN TẢNG QUY TRÌNH SỐ DX-OS

**Định hướng:** Thiết kế, kiểm chứng và vận hành quy trình linh hoạt, tích hợp tài liệu và AI có căn cứ.  
**Backend:** Python + FastAPI · **Frontend:** Vue.js 3 + TypeScript  
**Ngày:** 20/10/2026 · **Phiên bản:** 1.0  
**Trạng thái cập nhật:** Bản P0 cơ bản, một phần P1 và P2 đã có mã: gói nghiệp vụ, kiểm chứng, chạy thử, trace, cổng phát hành, so sánh phiên bản, căn cứ trường, dashboard thời gian chờ, gợi ý kiểm tra định lượng, bộ thử nhiều fixture và thư viện mẫu nội bộ. Xem [hướng dẫn triển khai](docs/process-packages.md). OCR/LLM tự động và sandbox integration vẫn là đề xuất. Chưa chạy kiểm thử tích hợp trên môi trường Compose.

---

## 1. Mục tiêu cải thiện

Sản phẩm đã có hướng quản lý file, ONLYOFFICE, biểu mẫu, giao việc, phê duyệt, chat và AI. Giá trị cần làm rõ hơn là khả năng cho tổ chức **tự thiết kế nghiệp vụ, kiểm tra trước khi chạy và giải thích được quá trình xử lý**.

Định vị đề xuất:

> Nền tảng thiết kế và vận hành quy trình số linh hoạt, tích hợp tài liệu và AI.

Các chức năng nền được giữ lại nhưng cùng phục vụ một vòng đời:

**Thiết kế → kiểm chứng → phát hành → vận hành → truy vết → cải tiến.**

Không khẳng định các tính năng dưới đây là mới trên thị trường. Chúng là trọng tâm khác biệt cần chứng minh trong sản phẩm của đội và trong bài demo; không phải yêu cầu bổ sung của BTC.

## 2. Bốn hướng cải thiện chính

| Hướng | Vấn đề giải quyết | Kết quả người dùng thấy |
|---|---|---|
| Cấu hình nghiệp vụ | Mỗi thay đổi phải nhờ lập trình viên | Tạo form, nhánh, người xử lý và hành động trên giao diện |
| AI có nguồn đối chiếu | Khó kiểm tra thông tin AI điền | Giá trị đề xuất gắn trang nguồn và trạng thái xác nhận |
| Truy vết và giải thích | Không biết hồ sơ chờ ai, vì sao đi nhánh | Timeline kèm dữ liệu, điều kiện, phiên bản và căn cứ |
| Chạy thử trước phát hành | Lỗi người nhận/nhánh chỉ lộ khi chạy thật | Chạy hồ sơ mẫu, xem đường đi và lỗi mà không tác động dữ liệu thật |

Ưu tiên làm sâu bốn hướng này thay vì tăng số màn hình. Drive, ONLYOFFICE, giao việc và thông báo trở thành các thành phần trong quy trình.

## 3. Cải thiện A — Tự cấu hình nghiệp vụ

### 3.1. Gói cấu hình nghiệp vụ

Người quản trị tạo một **gói nghiệp vụ** gồm:

- Tên, mục đích, đơn vị sở hữu và người được sử dụng.
- Schema dữ liệu và bố cục biểu mẫu.
- Danh sách tài liệu bắt buộc, mẫu tài liệu và quyền chỉnh sửa.
- Các bước xử lý, người nhận và điều kiện chuyển bước.
- Thời hạn, quy tắc nhắc việc và ngoại lệ.
- AI profile, connector và hành động được phép gọi.
- Bộ dữ liệu chạy thử và điều kiện nghiệm thu.

Ví dụ cùng nền tảng có các gói: đề nghị mua sắm, xin nghỉ phép, tiếp nhận yêu cầu hỗ trợ. Mỗi gói có quy tắc riêng nhưng dùng chung Core lưu trữ, dữ liệu, quyền và workflow.

### 3.2. Các màn hình cần có

| Màn hình | Chức năng |
|---|---|
| Danh mục gói | Tạo, sao chép, tìm kiếm, lưu trữ và xem phiên bản |
| Thiết kế biểu mẫu | Kéo thả trường, validation, quyền xem/sửa, điều kiện hiện |
| Thiết kế luồng | Thêm bước, nối nhánh, chọn action và mapping |
| Người nhận | Chọn cá nhân/vai trò/resolver trong phạm vi hợp lệ |
| Tài liệu | Chọn mẫu Office, tài liệu bắt buộc, điều kiện chốt version |
| Kiểm chứng | Chạy kịch bản, xem đường đi, phát hiện lỗi |
| Phát hành | Xem khác biệt và tạo phiên bản bất biến |

Wizard nghiệp vụ hiển thị “Lãnh đạo phòng người gửi” thay vì bắt người dùng nhập ID/path. Canvas kỹ thuật và cấu hình connector nâng cao chỉ dành người có quyền.

### 3.3. Ví dụ quy trình đề nghị mua sắm

Các mức tiền sau chỉ là quy tắc demo giả định của tổ chức, không phải quy định pháp luật hay chuẩn chung.

| Điều kiện | Hành vi |
|---|---|
| Thiếu trường bắt buộc | Chặn gửi và chỉ ra trường thiếu |
| Thiếu báo giá theo cấu hình | Trả về yêu cầu bổ sung trước khi trình |
| Giá trị dưới 10 triệu | Chuyển trưởng phòng |
| Giá trị từ 10 triệu trở lên | Trưởng phòng rồi giám đốc |
| Người duyệt không tồn tại | Báo lỗi cấu hình; không tự bỏ qua bước |
| Được duyệt | Tạo công việc cho đơn vị mua sắm |
| Bị trả lại | Giữ snapshot lần trình, tạo nháp bổ sung |

Cần định nghĩa rõ đơn vị tiền, cách làm tròn, thời điểm quy đổi nếu có và tính bao gồm của ngưỡng. Bộ thử phải có cả giá trị đúng 10 triệu.

### 3.4. Phiên bản và tái sử dụng

Gói có draft, validated, published, retired. Bản published bất biến; chỉnh sửa tạo version mới. Hồ sơ đang chạy pin phiên bản gói, form, workflow và tài liệu đã trình.

Đổi quy trình mua sắm không sửa hồ sơ cũ ngầm. Gói được export/import bỏ secret, quyền cá nhân và endpoint nhạy cảm; khi import phải ánh xạ vai trò, connector và credential.

**Tiêu chí đạt:** đổi trường, ngưỡng hoặc người xử lý bằng cấu hình; không đổi source Core, không sửa trực tiếp DB và không làm run cũ đổi đường đi ngoài ý muốn.

## 4. Cải thiện B — AI có căn cứ và có người kiểm tra

### 4.1. Gắn AI vào từng bước

Ví dụ: nhận PDF → trích văn bản → đề xuất các trường → kiểm tra schema → người dùng xác nhận → lưu hồ sơ nháp. Không dùng một chatbot chung làm bằng chứng thay cho việc AI tham gia quy trình.

Các chức năng ban đầu:

- OCR/trích text theo từng trang.
- Đề xuất số văn bản, ngày, đơn vị, giá trị và mô tả.
- Phát hiện thiếu trường hoặc thiếu tài liệu theo cấu hình.
- Tóm tắt hồ sơ có dẫn nguồn.
- Gợi ý công việc sau khi duyệt, chờ xác nhận theo quyền.

### 4.2. Mô hình dữ liệu một giá trị đề xuất

```json
{
  "field_key": "requested_amount",
  "suggested_value": 12500000,
  "confirmed_value": null,
  "review_state": "needs_review",
  "source": {
    "file_version_id": "file-version-example",
    "page": 2,
    "quote": "Tổng giá trị đề nghị: 12.500.000 đồng"
  },
  "provenance": {
    "extraction_job_id": "job-example",
    "ai_profile_version": 3,
    "prompt_version": 2
  }
}
```

Định danh trong ví dụ là placeholder. Có thể lưu bounding box nếu OCR hỗ trợ. Chỉ lưu confidence khi provider cung cấp và có cách hiểu rõ, không yêu cầu LLM tự tạo điểm rồi coi là độ tin cậy đã đo.

### 4.3. UI đối chiếu

Một bên là file/trang nguồn, một bên là các trường. Bấm trường mở đúng trang; hiện giá trị đề xuất, người xác nhận và nội dung đã sửa. Trường thiếu nguồn hoặc mâu thuẫn được đánh dấu cần kiểm tra.

Giá trị AI không tự ghi đè giá trị con người đã xác nhận. Nếu chạy OCR lại trên version khác, tạo đề xuất mới và hiển thị khác biệt. Báo cáo chỉ dùng giá trị được xác nhận theo chính sách.

### 4.4. Kiểm tra trước hành động

Schema và luật nghiệp vụ kiểm tra bằng backend. AI không tự cấp quyền hoặc vượt bước duyệt. Model trả JSON sai thì repair có giới hạn hoặc chuyển xử lý thủ công. Khi dịch vụ lỗi, hồ sơ vẫn có đường nhập thủ công.

API ngoài hoặc LLM local đều qua adapter/profile. Thay model không sửa luật nghiệp vụ. Không fallback gửi tài liệu ra ngoài khi chưa cấu hình.

**Tiêu chí đạt:** người dùng kiểm tra được nguồn, sửa được kết quả và biết dữ liệu nào đã được xác nhận; quyền tài liệu tiếp tục áp dụng trong OCR, context AI và lịch sử trả lời.

## 5. Cải thiện C — Giải thích và truy vết quy trình

### 5.1. Những câu hỏi cần trả lời

1. Hồ sơ đang ở bước nào và ai cần xử lý?
2. Vì sao hồ sơ đi nhánh này?
3. Dữ liệu nào đã được dùng khi đánh giá điều kiện?
4. Tài liệu phiên bản nào được gửi và duyệt?
5. Ai đã sửa, trả lại hoặc thay người nhận?
6. Bước nào chậm hoặc lỗi; hành động nào đã thực hiện?

### 5.2. Decision trace

```json
{
  "node_id": "amount_branch",
  "workflow_version": 4,
  "expression": "requested_amount >= 10000000",
  "evaluated_inputs": {"requested_amount": 12500000},
  "result": true,
  "selected_edge": "manager_then_director",
  "payload_revision": 7
}
```

Đây là log quyết định tất định của engine, không phải giải thích do LLM phỏng đoán sau khi chạy. UI chuyển thành câu dễ đọc: “Giá trị 12.500.000 đồng đạt ngưỡng 10.000.000 đồng, nên cần thêm bước giám đốc duyệt.”

Truy cập trace theo quyền; không hiển thị dữ liệu của trường bị hạn chế chỉ vì người dùng có quyền xem timeline tổng quát.

### 5.3. Dữ liệu cần giữ

- Run/node/attempt ID, workflow/action version.
- Inputs hoặc snapshot/reference tối thiểu đủ giải thích; che bí mật.
- Kết quả điều kiện, cạnh được chọn, nhánh bị bỏ qua.
- Người nhận đã phân giải và lý do theo resolver.
- Thời điểm tạo, bắt đầu, kết thúc; tách thời gian chờ và thời gian xử lý.
- File/version/hash và submission ID liên quan.
- Actor, delegation, lỗi, retry và kết quả tác động bên ngoài.

Không lưu toàn bộ file hoặc key API vào mỗi node log. Retention trace cần tương thích retention hồ sơ và quyền truy cập.

### 5.4. Dashboard cải tiến quy trình

Hiển thị thời gian chờ theo bước, số hồ sơ quá hạn, số lần trả lại và nhóm nguyên nhân. Có thể drill-down từ chỉ số tới hồ sơ được phép xem. Thống kê hiển thị khoảng thời gian, số mẫu và độ mới dữ liệu.

“Bước chậm nhất” là dấu hiệu để kiểm tra, không tự kết luận cá nhân làm việc kém; phải phân biệt nghỉ lễ, thiếu dữ liệu và thời gian chờ dịch vụ.

**Tiêu chí đạt:** chọn một hồ sơ bất kỳ có thể tái dựng đường đi từ snapshot và trace, không cần đọc source hoặc nhờ AI bịa lý do.

## 6. Cải thiện D — Chạy thử quy trình trước khi phát hành

### 6.1. Mục tiêu

Người quản trị kiểm tra cấu hình bằng hồ sơ mẫu, nhìn thấy đường đi dự kiến và lỗi trước khi áp dụng cho dữ liệu thật.

Phân biệt ba mức:

| Mức | Cách thực hiện | Tác động |
|---|---|---|
| Static validation | Kiểm tra graph/schema/action/quyền tham chiếu | Không gọi dịch vụ nghiệp vụ |
| Simulation/dry-run | Chạy cùng semantics điều kiện với fixture/snapshot | Không tạo việc, gửi thông báo hay đổi hồ sơ thật |
| Sandbox integration | Dịch vụ và dữ liệu thử riêng, người dùng chọn rõ | Có thể tạo dữ liệu trong sandbox, không phải production |

Không gọi một luồng thật rồi cố rollback toàn bộ để giả làm dry-run, vì HTTP ngoài và thông báo có thể không đảo ngược được.

### 6.2. Static validation

Kiểm tra node đầu/cuối, cạnh mồ côi, chu trình ngoài phạm vi hỗ trợ, đường tới kết thúc, kiểu dữ liệu, field mapping, action version, credential reference và người có quyền publish.

Kiểm tra người nhận bằng resolver trên snapshot tổ chức: không có người, nhiều người khi yêu cầu một người, tài khoản khóa hoặc vi phạm tự duyệt. Kết quả là lỗi trong cấu hình hiện tại; runtime vẫn phải kiểm tra lại do tổ chức có thể thay đổi sau test.

### 6.3. Simulation

Người dùng chọn draft/version, dữ liệu mẫu, snapshot cơ cấu tổ chức, thời gian mô phỏng và kết quả giả lập của node dịch vụ. Engine chạy biểu thức/nhánh/merge cùng bộ thực thi logic với runtime, nhưng executor tác động được thay bằng mock.

Output:

- Sơ đồ tô đường đã đi và nhánh bỏ qua.
- Người nhận dự kiến, dữ liệu điều kiện và lý do.
- Các hành động dự kiến, chưa thực hiện.
- Các bước cần quyết định con người và fixture quyết định.
- Lỗi validation, thiếu mapping hoặc node chưa có fixture.

Không suy ra phản hồi OCR/LLM/HTTP ngoài bằng cách giả vờ đã gọi thật. Mỗi output ghi nguồn mock/live và chế độ chạy; simulation mặc định không gọi provider để tránh chi phí hoặc rò dữ liệu.

### 6.4. Bộ thử ví dụ

| Kịch bản | Dữ liệu | Kỳ vọng |
|---|---|---|
| SC01 | 5 triệu, đủ tài liệu | Nhánh trưởng phòng |
| SC02 | Đúng 10 triệu, đủ tài liệu | Có thêm giám đốc |
| SC03 | 12,5 triệu, thiếu báo giá | Chặn gửi/bổ sung theo cấu hình |
| SC04 | Không có trưởng phòng | Lỗi người nhận, không tự bỏ bước |
| SC05 | Người tạo trùng người duyệt và cấm tự duyệt | Báo lỗi hoặc chuyển resolver thay thế đã cấu hình |
| SC06 | OCR trả JSON sai | Needs review/nhập thủ công, không tự gửi |
| SC07 | Action tạo việc timeout chưa rõ kết quả | Unknown outcome; không tạo lại mù |
| SC08 | Trả lại rồi sửa và trình lại | Submission mới, snapshot cũ còn nguyên |

### 6.5. Điều kiện publish

Draft đã validate, bộ case bắt buộc đạt, action/credential references hợp lệ và người publish có quyền. Lưu hash cấu hình, test report và phiên bản dùng khi kiểm chứng. Đổi graph, schema hoặc mapping làm kết quả kiểm chứng cũ không còn đủ để publish.

Test đạt không bảo đảm mọi trường hợp production đúng. Connector đổi, người dùng nghỉ việc hay quyền bị thu hồi vẫn cần runtime validation. Cho phép ngoại lệ publish chỉ nếu policy tổ chức cho phép, có lý do/audit và không vượt lỗi cứng như graph không hợp lệ.

**Tiêu chí đạt:** người quản trị nhìn thấy rõ “sẽ tạo công việc” trong simulation nhưng DB sản xuất, inbox và hệ thống ngoài không bị thay đổi.

## 7. Bổ sung vào kiến trúc Core–Workspace

### 7.1. Phân chia trách nhiệm

| Năng lực | Tầng 1 — Core | Tầng 2 — Workspace |
|---|---|---|
| Gói nghiệp vụ | Schema/record/workflow generic | Danh mục gói, layout, quy tắc nghiệp vụ |
| Chọn người nhận | Nhận principal/resolver contract tổng quát | Hiểu trưởng phòng, cơ cấu, tự duyệt |
| Simulation | Runtime mode, graph semantics, executor interface, trace | Bộ fixture nghiệp vụ, snapshot tổ chức, cách đọc kết quả |
| Giải thích | Decision trace có cấu trúc | Câu diễn giải và timeline dễ đọc |
| AI | Connector/action/capability tổng quát | OCR mapping, xác nhận trường, quyền nguồn |
| Office | Storage/version bất biến | Editor, mẫu tài liệu và chốt bản trình |

Core không thêm nhánh `if case_type == purchase` trong code. Workspace đăng ký schema, resolver/action và cấu hình; runtime dùng hợp đồng generic. Console kỹ thuật Tầng 1 và UI nghiệp vụ Tầng 2 tiếp tục tách đúng vai trò.

### 7.2. Backend FastAPI cần bổ sung

- `package_service`: gói cấu hình, version và publish gate ở Workspace.
- `simulation_service`: quản lý test suite/run; gọi Core validation/simulation.
- `execution_mode`: live/simulation/sandbox, bất biến cho mỗi run.
- `executor_interface`: LiveExecutor và SimulationExecutor dùng chung schema nhưng khác tác động.
- `decision_trace_service`: ghi điều kiện, snapshot reference và kết quả.
- `evidence_service`: liên kết field AI với nguồn và xác nhận.
- `explanation_presenter`: format giải thích từ trace, không tự suy luận thêm.

Không để client tự đổi simulation sang live bằng một field không kiểm tra. Chế độ được server xác định, phân quyền và lưu cùng run; network/credentials của simulation không có quyền production.

### 7.3. Frontend Vue 3 cần bổ sung

Wizard gói nghiệp vụ, form designer, canvas, bộ tạo kịch bản, màn hình chạy thử, timeline giải thích, so sánh version và UI đối chiếu AI. Dùng lại component Drive/ONLYOFFICE và bộ chọn tổ chức.

Các nhãn bắt buộc: “Chạy thử — không thực hiện hành động thật”, “Kết quả giả lập”, “Đã gọi dịch vụ thử” và “Đã phát hành”. Không hiển thị simulation thành hồ sơ production hoàn tất.

## 8. Dữ liệu và API bổ sung

### 8.1. Bảng/đối tượng

| Đối tượng | Chủ sở hữu | Trường chính |
|---|---|---|
| business_packages | Workspace | owner, name, permissions, active_version |
| business_package_versions | Workspace | form/workflow/action refs, state, config_hash |
| simulation_suites/cases | Workspace | fixture, expected_path, expected_actions, version refs |
| simulation_runs | Core | execution_mode, workflow_version, fixture_ref, seed/clock, state |
| simulation_reports | Workspace | core_run_id, assertions, passed/failed, config_hash |
| decision_traces | Core | node, expression, inputs_ref, result, edge, revision |
| resolver_evidence | Workspace | snapshot, rule, candidates, selected, reason |
| field_evidence | Workspace | source_file_version, page, quote/bbox, suggested/confirmed |
| publish_checks | Workspace | package_version, check type, report, actor, timestamp |

ID giữa hai tầng là reference/API contract, không FK SQL xuyên database. Artefact lớn lưu kho object theo quyền; trace chỉ giữ reference phù hợp.

### 8.2. Endpoint đề xuất

| API | Chủ sở hữu | Ý nghĩa |
|---|---|---|
| POST /workspace/v1/business-packages | Workspace | Tạo gói |
| POST /workspace/v1/business-packages/{id}/versions | Workspace | Tạo draft version |
| POST /workspace/v1/package-versions/{id}/test-suites | Workspace | Bộ kiểm chứng |
| POST /workspace/v1/package-versions/{id}/simulate | Workspace | Chạy fixture qua Core |
| GET /workspace/v1/simulation-reports/{id} | Workspace | Kết quả và assertions |
| POST /workspace/v1/package-versions/{id}/publish | Workspace | Kiểm tra gate và phát hành |
| GET /workspace/v1/cases/{id}/explanation | Workspace | Timeline/giải thích có kiểm tra quyền |
| GET /workspace/v1/extractions/{id}/field-evidence | Workspace | Nguồn các giá trị AI |
| POST /core/v1/workflow-versions/{id}/validate | Core | Static validation |
| POST /core/v1/workflow-versions/{id}/simulations | Core | Dry-run tổng quát |
| GET /core/v1/workflow-runs/{id}/decision-traces | Core | Trace theo quyền |

Các endpoint là đặc tả đề xuất, chưa phải API đã triển khai. Mutations áp dụng revision/idempotency theo bản thiết kế chính. Simulation và live run có quota riêng để tránh test chiếm hết tài nguyên.

## 9. Phạm vi ưu tiên thực hiện

| Mức | Nội dung |
|---|---|
| P0 — Ưu tiên | Gói nghiệp vụ có version, form+workflow config; static validation; simulation nhánh/người nhận; decision trace; publish gate cơ bản |
| P1 — Bổ sung giá trị | AI field evidence, UI đối chiếu; so sánh version; dashboard thời gian chờ |
| P2 — Mở rộng | Sandbox integration, batch simulation, gợi ý cải tiến, template marketplace nội bộ |

Không đưa chatbot sinh toàn bộ quy trình từ ngôn ngữ tự nhiên vào P0. Nếu làm sau, AI chỉ tạo draft graph hợp lệ theo schema; vẫn phải validate, simulation và người có quyền publish.

Giữ chat/feed và giao diện đẹp nhưng ưu tiên độ đúng của quy trình và bằng chứng vận hành. Đây là thứ tự chức năng, không phải phân công nhân sự hay cam kết tiến độ.

## 10. Kiểm thử và tiêu chí nghiệm thu

| Mã | Kiểm tra | Phải đạt |
|---|---|---|
| AC01 | Đổi quy trình mua sắm sang nghỉ phép | Thêm cấu hình/schema/action phù hợp, không sửa source Core |
| AC02 | Ngưỡng tiền dưới/bằng/trên 10 triệu | Chọn đúng nhánh theo cấu hình |
| AC03 | Không có người duyệt | Báo lỗi có căn cứ, không bỏ qua |
| AC04 | Simulation có action tạo task/notify | Không có dữ liệu production hoặc thông báo thật |
| AC05 | Cùng snapshot/fixture và version | Kết quả logic có thể tái lập; node ngoài được mock rõ |
| AC06 | Đổi draft sau test | Report cũ không tự đủ điều kiện publish |
| AC07 | Run live cùng fixture kiểm chứng trong sandbox | Đường đi khớp semantics được hỗ trợ; khác biệt được báo |
| AC08 | Giải thích nhánh | Có expression, input revision và edge thực tế |
| AC09 | User không có quyền trường/file | Không lộ qua trace, quote, source preview hoặc AI |
| AC10 | AI đề xuất sai | Người dùng sửa/xác nhận; giữ nguồn và lịch sử |
| AC11 | Callback ONLYOFFICE chậm/lỗi | Không trình bản tài liệu cũ âm thầm |
| AC12 | Retry tạo hồ sơ/công việc | Không nhân bản tác động cùng intent |
| AC13 | Run cũ khi publish bản mới | Giữ version cũ |
| AC14 | Core chạy khi Workspace dừng | Generic data/file/workflow vẫn hoạt động; resolver/action Workspace chờ/lỗi có kiểm soát |

Đo hiệu quả: thời gian cấu hình thay đổi, lỗi tìm được trước publish, số thao tác nhập lại, tỷ lệ sửa AI, khả năng trả lời đúng câu hỏi truy vết. Báo kết quả trên tập thử và điều kiện đo, không tự đặt số cải thiện khi chưa thử nghiệm.

## 11. Kịch bản trình diễn điểm khác biệt

### 11.1. Thiết kế và kiểm tra

Admin tạo biểu mẫu đề nghị mua sắm; chọn ngưỡng, trưởng phòng, giám đốc và action tạo việc. Nhập hồ sơ mẫu 12,5 triệu. Simulation tô đường qua hai cấp; đổi mẫu thành 5 triệu thì đường đi thay đổi.

Cố ý để thiếu người duyệt hoặc báo giá, cho thấy hệ thống phát hiện trước publish. Xem “hành động dự kiến” và chứng minh chưa có task/thông báo thật.

### 11.2. Vận hành có căn cứ

Tải PDF, AI điền nháp kèm trang nguồn; người dùng sửa/xác nhận. Chỉnh tài liệu qua ONLYOFFICE, chốt version rồi gửi. Hồ sơ chạy đúng luồng, quyết định hợp lệ tạo task và dashboard cập nhật theo cơ chế đã công bố.

### 11.3. Giải thích và thay đổi

Mở timeline trả lời “vì sao cần giám đốc duyệt”, “đang chờ ai”, “đã duyệt file nào”. Đổi ngưỡng tạo phiên bản mới, test và publish; hồ sơ cũ vẫn giữ bản cũ.

Điểm cần chứng minh là **thay đổi được cấu hình, kiểm tra được trước chạy và truy nguyên được sau chạy**, không chỉ trình diễn nhiều màn hình.

## 12. Cách mô tả sản phẩm trong báo cáo

### 12.1. Mô tả đề xuất

DX Workspace là nền tảng thiết kế và vận hành quy trình số theo kiến trúc Core–Workspace. Nền tảng cung cấp biểu mẫu, tài liệu, workflow và kết nối dịch vụ có thể cấu hình; hỗ trợ chạy thử trước khi phát hành, truy vết quyết định theo phiên bản dữ liệu và AI trích xuất thông tin có nguồn đối chiếu.

### 12.2. Đóng góp cần chứng minh

1. Cơ chế gói cấu hình nghiệp vụ và version liên kết form/workflow/action/tài liệu.
2. Simulation dùng cùng logic điều kiện với runtime nhưng cô lập tác động.
3. Decision trace giải thích được đường đi và phiên bản nguồn.
4. AI field evidence gắn trích xuất với người kiểm tra và file version.
5. Core dùng lại cho cấu hình nghiệp vụ khác mà không chứa luật chuyên biệt.

Các mục này là đóng góp kỹ thuật dự kiến của sản phẩm; muốn tuyên bố tính mới nghiên cứu hoặc ưu thế thị trường cần khảo sát và đối chứng riêng.

### 12.3. Quan hệ với bản thiết kế chính

Tài liệu này bổ sung chiều sâu cho bản thiết kế FastAPI + Vue 3 đã thống nhất, không thay kiến trúc hai tầng. Khi hiện thực, tích hợp các service, bảng và API đề xuất vào module chủ sở hữu tương ứng; giữ nguyên nguyên tắc headless end-user của Core, console admin được phép, SSO/Gateway và các dịch vụ lõi.

Căn cứ phạm vi là đề thi và đoạn giải thích BTC người dùng đã cung cấp. Bốn hướng cải thiện không phải nghĩa vụ bổ sung của cuộc thi và cũng chưa phải tính năng đã được kiểm chứng.
