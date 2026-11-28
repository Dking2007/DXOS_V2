# Changelog

Định dạng theo [Keep a Changelog](https://keepachangelog.com/vi/1.1.0/), đánh phiên bản theo
[SemVer](https://semver.org/lang/vi/). Ngày của mỗi phiên bản là ngày đăng GitHub Release (giờ Việt Nam); riêng 0.1.0
không có Release nên ghi ngày commit `f089bfb`. Mỗi mục trỏ tới commit thật trong lịch sử Git; số PR chỉ ghi khi thay
đổi vào `main` qua pull request. Bản có nhiều thay đổi để chi tiết riêng trong `docs/changes/`.
So sánh V1 → V2: [docs/V2_CHANGES.md](docs/V2_CHANGES.md); V2 → V3: [docs/V3_CHANGES.md](docs/V3_CHANGES.md).

### Ghi chú về đánh số phiên bản (ghi bổ sung ngày 28/11/2026)

Đối chiếu lại các tag đã phát hành với SemVer bằng cách so hợp đồng API giữa từng cặp tag. Các tag đã phát hành
giữ nguyên, vì SemVer không cho sửa một phiên bản đã phát hành; các sai lệch dưới đây chỉ được ghi lại.
- `0.2.2` thêm 17 thao tác API Workspace (tính năng mới tương thích) nhưng chỉ tăng số cuối. Theo SemVer, đúng ra
  phải là `0.3.0`.
- Tag `v0.2.0` và `v0.2.1` gắn lên mã có `package.json` vẫn ghi `0.1.0`, nên gói nguồn của hai bản này tự báo số
  0.1.0. Từ `v0.2.2` thì số trong mã khớp với tag.
- `0.2.2` → `3.0.0` xóa 15 thao tác API và cột `cases.assignee_id`, nên tăng số chính là đúng. Việc bỏ qua 1.x, 2.x
  để khớp tên gọi V3 được giải thích ở [docs/V3_CHANGES.md](docs/V3_CHANGES.md).
- `3.0.0` → `3.1.0` không đổi API công khai, chỉ thêm tính năng (plugin `.zip` qua route sẵn có), nên tăng số giữa
  là đúng. Bản kế tiếp `3.2.0` cũng chỉ thêm tính năng.

Từ bản kế tiếp, workflow phát hành chạy `scripts/check_version.py` để chặn ba lỗi trên: số phiên bản lệch giữa các
tệp, tag không khớp với mã hoặc CHANGELOG, và tăng số không đủ so với thay đổi API.

## [Unreleased]

Nâng cấp trải nghiệm người dùng của Workspace (PR #40, nhánh `feat/ui-ux-nang-cap`; đã vào `main`, chưa gắn tag):
trang Cài đặt cá nhân, trình thiết kế quy trình có sao chép/dán và hoàn tác, sơ đồ cơ cấu tổ chức, bộ chọn người có
tìm kiếm, rà soát nút bấm và khoảng cách. Không đổi API, không thêm migration hay thư viện mới; thay đổi phía máy chủ
duy nhất là luồng đăng nhập OIDC.

### Added
- `scripts/seed_demo.py`: nạp hồ sơ, công việc, bảng tin, trò chuyện và tài liệu minh họa qua API công khai; chạy lại không tạo trùng.
- Quét mã độc tệp tải lên bằng ClamAV (tùy chọn: profile `security`, biến `CLAMAV_HOST`); lỗi quét thì từ chối tệp, phát hiện thì ghi audit.
- Cảnh báo dữ liệu cá nhân (CCCD, số điện thoại, e-mail…) khi xem trước tệp và xem bản đã che (`GET /drive/files/{id}/pii`, dùng `dx-piivn`).
- `scripts/backup.py`, `scripts/restore.py`: sao lưu và khôi phục ba cơ sở dữ liệu và kho tệp, kèm manifest SHA-256; số đo diễn tập trong `docs/operations.md`.
- Tài khoản demo `lanh-dao-mfa` bắt buộc cài TOTP ở lần đăng nhập đầu (chỉ cài mới).
- `scripts/check_version.py`: workflow phát hành kiểm số phiên bản theo SemVer; Release đính kèm SBOM CycloneDX.
- **Trình soạn thảo ONLYOFFICE toàn màn hình**: nút "Toàn màn hình" trên trang chỉnh sửa tài liệu che cả cửa sổ (ẩn thanh
  bên, đầu trang) và bật chế độ toàn màn hình của trình duyệt; "Thu nhỏ" hoặc Esc để quay lại, không tải lại tài liệu.
- **Kho tài liệu** mặc định xem dạng lưới; lựa chọn danh sách/lưới của từng người được nhớ trên trình duyệt.
- **Hoạt động của công việc** vẽ thành sơ đồ quy trình (cùng kiểu trình thiết kế quy trình): mỗi bước là một nút có
  icon, người làm và giờ, nối bằng mũi tên theo màu trạng thái; cập nhật phụ nét đứt. Nút "Phóng to" mở sơ đồ ngang,
  tự xuống hàng theo bề rộng, kéo và thu phóng được.
- **Công việc dạng giấy** (kiểu xem mặc định, lựa chọn được nhớ trên trình duyệt): mỗi việc là một tờ giấy kẻ dòng
  có băng dính màu theo mức ưu tiên, góc gấp, mô tả ngắn, nhãn, tiến độ checklist, người nhận và hạn; dấu mộc
  "Quá hạn", "Trả lại", "Hoàn tất", "Đã hủy". Tờ giấy nghiêng nhẹ, nhấc lên khi rê chuột (đứng thẳng khi giảm chuyển động).
- **Bảng tin** làm mới giao diện: dải chào theo buổi kèm ngày và số bài mới hôm nay; thanh lọc dạng kính mờ dính dưới
  thanh trên cùng; thẻ bài bo tròn, bóng mềm, avatar có viền màu, nút thao tác dạng viên; ảnh đơn nằm trên nền mờ của
  chính nó thay cho khung đen; thông báo chính thức ở cột phải xếp theo dòng thời gian.
- **Cài đặt cá nhân** (`/preferences`, mọi người dùng; 9bf7477): giao diện sáng/tối/theo máy, mật độ hiển thị, thu
  gọn thanh bên, cỡ chữ 90–125% (toàn bộ cỡ chữ đổi sang `rem`), phông chữ, giãn dòng, giảm chuyển động, tăng tương
  phản, luôn hiện viền focus, gạch chân liên kết, định dạng ngày (dd/mm/yyyy hoặc yyyy-mm-dd), giờ 24h/12h, ngày đầu
  tuần, khôi phục mặc định. Áp dụng ngay, lưu theo từng người trên trình duyệt. Ngôn ngữ hiện chỉ có tiếng Việt.
- **Trình thiết kế quy trình** (c5d4bb9): sao chép/cắt/dán/nhân bản nhiều bước kèm đường nối, hoàn tác/làm lại,
  chọn tất cả, dịch bước bằng phím mũi tên; menu chuột phải cho bước, nền và đường nối; nút `+` ở cổng ra và giữa
  đường nối để chèn bước tự nối; sắp xếp tự động trái sang phải; bám lưới; căn chỉnh nhiều bước; bảng phím tắt (`?`).
- **Cơ cấu tổ chức** (Thiết lập; 345be65): ba chế độ xem Sơ đồ / Cây / Bảng; kéo, thu phóng, vừa khung, xuất SVG/PNG;
  thống kê phòng ban, thành viên, chưa xếp phòng, phòng chưa có lãnh đạo, độ sâu; bảng chi tiết phòng với thao tác
  nhanh; cảnh báo dữ liệu lỗi (vòng lặp phòng cha, phòng cha đã mất).
- **Bộ chọn người** khi giao việc (fd29309): tìm không dấu, nhóm Cá nhân/Đơn vị, chọn nhiều thành thẻ, chọn cả
  phòng, gợi ý người hay chọn, dùng được bằng bàn phím; vẫn mượt với khoảng 1000 người.
- Icon điều hướng có màu theo module, tương phản ≥ 3:1 ở cả nền sáng và tối (9bf7477); nút "Lên đầu trang" (9bf7477).

### Changed
- Trình bày lại README (sơ đồ kiến trúc, luồng nghiệp vụ, bảng công nghệ), CONTRIBUTING, SECURITY, CODE_OF_CONDUCT và mẫu issue.
- Gói giao diện đang dùng có màu riêng thì biểu tượng menu, nút trợ lý AI và trang đăng nhập (ánh sáng, vòng bạc, nút) ngả theo màu của gói thay vì giữ màu xanh mặc định; mỗi phân hệ vẫn giữ sắc riêng để phân biệt.
- Trang đăng nhập mặc định lại có khung (`framed`), thiết kế lại: viền đôi sáng dần về góc, góc bạc có viên đá, dấu thoi giữa cạnh, một vệt sáng chạy chậm quanh viền; tiêu đề mặc định chỉ xuống dòng giữa các cụm từ nên điện thoại 360 px không còn chữ "TỬ", "DUYỆT" đứng một mình. Gói giao diện vẫn chọn được `flat` hoặc `image`.
- Tài khoản demo mới có tên người và chức danh riêng; lời chào dùng đầy đủ họ tên.
- Hộp xác nhận trong ứng dụng thay hộp `confirm()` của trình duyệt.
- **Core không có giao diện khi chạy riêng** (đúng yêu cầu Core headless của đề thi): công cụ quản trị kỹ thuật
  Core admin (`apps/core-admin`) chuyển từ profile `core` sang profile mới `console` (vẫn có trong `workspace`).
  `--profile core` chỉ chạy Core API, worker, Keycloak, gateway và kho lưu trữ; gateway trả 404 kèm lời giải thích
  ở `/` và `/console/` thay vì 502. Muốn dùng Core admin khi chỉ chạy Core: thêm `--profile console`. README,
  `docs/installation.md`, `docs/operations.md`, `SELF_REVIEW.md` hướng dẫn thử Core bằng `examples/core-client` và
  `/core/v1/docs`; test triển khai kiểm `--profile core` không có ứng dụng giao diện nào.
- Trang Công việc bỏ kiểu xem Kanban và "Theo hạn"; còn dạng giấy (mặc định) và danh sách dạng bảng. Lọc theo trạng
  thái và "Quá hạn" vẫn có trong bộ lọc.
- Chuẩn hóa khoảng cách theo token (`--space-*`, `--gap-icon`, `--field-gap`, `--control-h`): nút, tab, ô nhập,
  cảnh báo, bảng, hộp thoại không còn dính nhau; viền focus rõ khi dùng bàn phím (9bf7477).
- Rà soát nút bấm trên các màn hình (fd29309, 0c682f3): chống gửi trùng, trạng thái "Đang …", nút bị khóa có lý do,
  xác nhận thao tác nguy hiểm, hỏi trước khi bỏ nội dung đã gõ (ModalDialog có `dirty`/`beforeClose`), ẩn thao tác
  khi thiếu quyền, trạng thái tải/trống/lỗi cho danh sách.
- Hộp Phát hành quy trình: "Lưu & phát hành" khi canvas chưa lưu, thay cho nút Phát hành bấm được nhưng lỗi.
- Tab "Giao diện" rời khỏi Thiết lập (quản trị) sang Cài đặt cá nhân; địa chỉ cũ tự chuyển hướng.
- Hiệu năng: canvas không tuần tự hóa sơ đồ trong lúc kéo bước và không vẽ lại cả trang theo từng khung thu phóng
  (c5d4bb9); nhắn tin và bảng tin chỉ vẽ lại dòng/bài thay đổi khi gõ phím (0c682f3); bộ định dạng ngày/dung lượng
  dùng lại thay vì tạo mới mỗi dòng; danh mục ít đổi không tải lại mỗi lần quay lại cửa sổ (9bf7477, c5d4bb9).
- Bộ chọn người có tìm kiếm thay ô chọn thường ở "Chuyển cho", cấu hình bước quy trình (người nhận, giao cho, đơn vị
  nhận, chuyển cấp) và thiết kế biểu mẫu (4e38e30); chặn tạo biểu mẫu khi bước "người cụ thể" chưa chọn người
  (3e8aa00).

### Fixed
- Trang chủ: tên hồ sơ dài trong "Hồ sơ gần đây" kết thúc bằng "…" thay vì chạy đè lên nhãn trạng thái.
- Xóa được biểu mẫu không còn dùng (B7): nút "Xóa biểu mẫu" cạnh ô chọn biểu mẫu khi tạo luồng, `DELETE /forms/{id}`. Biểu mẫu
  đã có hồ sơ thì được lưu trữ (hồ sơ vẫn xem được); biểu mẫu quy trình còn dùng hoặc do gói cài thì bị từ chối kèm lý do.
- Khung plugin co lại vừa nội dung: SDK khung đo chiều cao phần thân trang thay cho `scrollHeight` của `<html>` (giá trị này
  không bao giờ nhỏ hơn khung, nên khung chỉ giãn mà không co). Trạng thái công việc thống nhất "Đang thực hiện" (thanh
  tiến trình và bộ lọc trước ghi "Đang làm").
- Hồ sơ không còn kẹt ở "Đang xử lý" khi một nhánh quy trình hết bước mà không có bước Kết thúc (ví dụ kết thúc bằng "Gửi thông
  báo"): hồ sơ nhận quyết định cuối cùng trên đường đi (duyệt, trả lại, từ chối), không có quyết định nào thì là đã duyệt;
  diễn tập quy trình báo cùng kết quả. Hồ sơ đã kẹt vì một bước lỗi thì người tạo thu hồi được (B1).
- `desktiny-plugin check` (và bước đóng gói dùng nó) kiểm cả độ dài tiêu đề, mô tả và cấu trúc ô cấu hình (`settings_schema`,
  `config_schema`, `parameters`) như Desktiny, nên không còn manifest qua bước kiểm mà bị từ chối khi cài.
- Tiêu đề màn đăng nhập không còn bị cắt dấu tiếng Việt (Ử, Ệ…).
- Thanh trên cùng không tràn ngang ở 390 px; tên tổ chức và đường dẫn trang không bị rút khi còn chỗ.
- Canvas quy trình mở vừa khung, tên bước hai dòng, nhãn nhánh dễ đọc, gọn trên điện thoại.
- Điện thoại 360 px không còn cuộn ngang: nhóm nút thanh trên cùng không bị ép nhỏ hơn các nút (nút "Đăng xuất" lòi
  ra 4 px khi tên trang dài), cột Bảng tin không giãn theo nội dung rộng nhất (tràn 112 px). Canvas quy trình trên
  điện thoại mở ở cỡ đọc được (75%) từ bước kích hoạt thay vì thu cả luồng còn 20%; luồng ngắn vẫn hiện trọn và
  "Vừa màn hình" vẫn cho xem toàn cảnh. Dòng trạng thái luồng không còn ép câu thành cột một chữ chiếm nửa màn hình.
- Hộp thoại đặt tiêu điểm vào ô nhập đầu tiên; hướng dẫn làm quen chỉ hiện một lần; sửa lỗi tiếp cận bàn phím và nhãn.
- Giao việc có tên rất dài không còn lỗi 500; nhãn mức ưu tiên không xuống dòng.
- Người được giao gửi được hồ sơ do luồng tự động tạo (trước đây lỗi 404).
- Danh sách Cần phê duyệt tự làm mới; lịch sử hồ sơ hiện "Quyết định: Duyệt/Trả lại/Từ chối" thay mã `case.decision`.
- Bản cài bằng `make install` không nạp được gói giao diện dựng sẵn: mã tìm ở `$PREFIX/packs` trong khi gói được
  chép vào `$PREFIX/share/desktiny/packs`. `.env.example` thêm `DATABASE_URL` và `PACKS_DIR` (tuỳ chọn) cho bản cài.
- Đăng nhập để form Keycloak quá 5 phút trả JSON `oidc_state_invalid`: state đăng nhập nay sống 30 phút, callback
  lỗi chuyển về trang đăng nhập kèm thông báo (f3be40b).
- Nút thu gọn thanh bên không có tác dụng ở trang thiết kế quy trình (9bf7477).
- Hồ sơ báo "Đã phê duyệt" khi bước duyệt đã được người khác xử lý; "Nghiệm thu" đóng việc không hỏi; một tệp lỗi
  làm mất các tệp đã tải lên trước đó (fd29309).
- Dữ liệu trả về muộn ghi đè dữ liệu mới: tin cũ trộn vào hội thoại khác, gợi ý nhãn AI ghi sang tệp khác, nhận xét
  AI hiện số liệu kỳ cũ (fd29309, 0c682f3).
- Rò tài nguyên: tài liệu PDF và URL tạm khi đóng xem trước giữa chừng, trình soạn thảo ONLYOFFICE tạo sau khi rời
  trang, các hẹn giờ không được hủy (fd29309, 0c682f3, c5d4bb9).

## [3.1.0] - 2026-11-24

Cài tính năng mới bằng một tệp `.zip`: plugin đóng gói. Gói giao diện chỉnh được trang đăng nhập; "Gói ngành" đổi
tên thành "Gói giao diện". Gộp nhánh `feat/plugin-dong-goi` (Raphael-Fug, Mai1174), không qua PR riêng; bản này vào
`main` cùng PR #40. Thêm migration `workspace_0028`; không xóa hay đổi API cũ nên giữ số chính 3. SDK
`desktiny-plugin` lên 0.3.0 (thêm định dạng `desktiny-plugin/2`).

### Added
- **Plugin đóng gói** (`desktiny-plugin/2`, migration `workspace_0028`, [docs/plugins.md](docs/plugins.md)): cài một
  tệp `.zip` là có tính năng mới, không cần máy chủ riêng.
  - Desktiny lưu và tự phục vụ trang, script, CSS, ảnh của plugin ở `/workspace/v1/plugin-files/…` khi plugin đang
    bật, luôn kèm CSP `sandbox` (mở thẳng địa chỉ cũng không chạy với origin của Desktiny); địa chỉ theo SHA-256 của
    gói.
  - Plugin mang theo **gói giao diện** (`pack`): xem trước cùng plugin, cài/nâng cấp/gỡ cùng plugin, không gỡ riêng được.
  - Quản trị › Plugin: nhãn “Đóng gói”, số tệp giao diện, gói giao diện đi kèm; duyệt plugin đóng gói không cấp khoá.
  - SDK khung tự nhận địa chỉ Desktiny với trang đóng gói; `desktiny-plugin check` kiểm trang và gói giao diện trong thư
    mục. Plugin mẫu `examples/plugins/mot-cua-mau` (trang tính hạn theo ngày làm việc, phiếu tiếp nhận, quy trình một
    cửa).
- Gói giao diện chỉnh được trang đăng nhập: nền chuyển sắc (với ảnh nền là lớp phủ) có kiểm tương phản chữ trắng
  ≥ 4,5:1 ở trình tạo gói và máy chủ; chữ trên nút đăng nhập, dòng ghi chú dưới nút, bật/tắt hiệu ứng chuyển động;
  xem trước theo giá trị mới. Gói cũ giữ trang mặc định.

### Changed
- Đổi tên **Gói ngành** thành **Gói giao diện** trên menu, tiêu đề trang, hướng dẫn, thông báo và tài liệu (mã,
  đường dẫn `/packs`, API và định dạng `desktiny-pack/1` giữ nguyên).
- Tài liệu: README mô tả kiến trúc theo hai tầng của đề thi OLP PMNM 2026 (Core headless ở Tầng 1, ứng dụng giao diện
  ở Tầng 2), Core admin ghi là client riêng, không thuộc Core, thêm liên kết trực tiếp tới bug tracker và trang
  Releases; SELF_REVIEW thêm mục 5 đối chiếu từng tiêu chí PoF, yêu cầu bắt buộc, bốn nguyên tắc kỹ thuật và quy định
  nộp bài với thể lệ và đề thi gốc trên vfossa.vn (đọc ngày 21/11/2026).

### Removed
- Bỏ khỏi kho các ghi chép nội bộ về so sánh với dự án khác; sửa một liên kết hỏng trong `docs/design/`.

## [3.0.0] - 2026-11-15

DXOS V3: quy trình nghiệp vụ vẽ trên canvas, gói ngành, plugin kết nối và tính năng AI. Số phiên bản nhảy từ 0.2.2
lên 3.0.0 để khớp tên gọi V3 (V1 = 0.1.0, V2 = 0.2.x). Plugin đóng gói `.zip` chưa có trong bản này (xem 3.1.0).
Gói tách riêng (`dx-flowkit`, `desktiny-plugin`, `dx-piivn`) giữ số phiên bản của chính chúng.
Chi tiết đầy đủ: [docs/changes/3.0.0.md](docs/changes/3.0.0.md).

**Phá tương thích:**
- Migration `workspace_0014` xóa cột `cases.assignee_id`: hồ sơ bỏ "người phụ trách"; luồng tự động gửi tới người
  phụ trách nay gửi người lập hồ sơ.
- API `/business-packages*` và `/package-versions*` thay bằng `/processes`; `CaseCreate.package_version_id` đổi thành
  `process_id`; `/ai/package-versions/{id}/scenarios` đổi thành `/ai/processes/{id}/scenarios` (migration
  `workspace_0018`).

### Added
- Plugin kết nối `desktiny-plugin/1` và API plugin bản 2 (migration `workspace_0023`–`workspace_0027`, contract
  `contracts/plugin.openapi.json`, SDK `desktiny-plugin` 0.2.0; PR #39, nhánh `feat/plugin-ket-noi`).
- Gói ngành `desktiny-pack/1` (migration `workspace_0022`; PR #37, bị revert ở PR #38, áp dụng lại trong PR #39).
- Quy trình hồ sơ vẽ trên canvas tự động hóa, công việc có đính kèm tệp (migration `workspace_0017`, PR #35).
- Hồ sơ cá nhân và ảnh đại diện (migration `workspace_0021`, PR #36); trợ lý công việc và hỏi đáp AI trên trang hồ
  sơ; tài liệu theo từng bước của hồ sơ; 12 quy trình mẫu mới.
- 17 tính năng AI, mặc định tắt (migration `workspace_0016`); trợ lý AI dùng được máy chủ Ollama và vLLM tự cài.
- Đóng hồ sơ: xóa bản nháp, hủy, lưu trữ (migration `workspace_0015`); tab Nhật ký hoạt động; báo cáo theo phòng ban
  và xuất CSV hồ sơ.
- Chuỗi băm cho nhật ký audit của Core (migration `core_0003`), gói `dx-piivn` 0.1.0 và `scripts/audit_repo.mjs`
  (PR #34). Ba mục này trước đây ghi nhầm vào 0.2.2.

### Changed
- Quy trình nghiệp vụ (`/processes`) gộp Tự động hóa và Gói nghiệp vụ, phát hành theo phiên bản, có kịch bản thử
  (migration `workspace_0018`); node cấu hình linh hoạt (`workspace_0019`); một loại luồng với 14 node mới
  (`workspace_0020`); hạn xử lý theo từng bước duyệt. PR #35, #36.
- Giao diện theo design system: trang đăng nhập làm lại, thanh bên gọn, chi tiết công việc có khung tóm tắt, rà soát
  giao diện theo góp ý người dùng.
- Trợ lý AI trả lời về dữ liệu của người hỏi mở rộng phạm vi (tính năng `assistant_my_data`, vẫn tắt mặc định).
- Gọn chức năng trùng lặp: bước duyệt chỉ khai ở biểu mẫu, Core dùng `dx-flowkit` 0.2.0.
- Tìm kiếm không phân biệt dấu ở mọi nơi; công việc dùng "nghiệm thu", hồ sơ dùng "phê duyệt".

### Fixed
- Tab Quy trình của hồ sơ và thao tác nhân đôi node đứng im; bố cục bảng tin và nút trợ lý AI trên điện thoại; image
  web build lỗi `vue-tsc` vì thiếu `examples/plugins`.

## [0.2.2] - 2026-10-31

V2 bản dùng để chấm: trợ lý AI, `dx-flowkit`, plugin `vn-document-format`, sửa cài đặt và bootstrap. Phần lớn thay
đổi vào `main` qua PR #31; trợ lý AI gộp thẳng từ nhánh `feat/ai-assistant`.
Chi tiết đầy đủ: [docs/changes/0.2.2.md](docs/changes/0.2.2.md).

### Added
- Trợ lý AI ở góc màn hình, trả lời từ kiến thức do quản trị viên nhập (migration `workspace_0012`,
  `workspace_0013`); dịch vụ Claude, OpenAI, Gemini, DeepSeek hoặc cổng riêng.
- Gói `dx-flowkit` 0.1.0 (`packages/flowkit`): kiểm tra và chạy thử đồ thị quy trình JSON.
- Plugin ONLYOFFICE `vn-document-format` 0.1.0: kiểm thể thức văn bản hành chính theo Nghị định 30/2020/NĐ-CP.
- `desktiny-migrate`: chạy migration từ bản đã cài; mục "Đóng góp ngược cho cộng đồng nguồn mở" trong README.

### Changed
- Workspace API bỏ hai vòng phụ thuộc giữa module, không đổi hành vi hay API.
- `psycopg[binary]` đổi thành `psycopg` dùng `libpq5` của hệ điều hành; `make install` dùng pip của `.venv`.
- Thống nhất số phiên bản 0.2.2; thêm `.gitattributes`, `.editorconfig`, `.mailmap`; tài liệu cập nhật theo trạng
  thái thật.

### Fixed
- Chữ `WorkMMODIARY` thành `Workspace`; trường số không bắt buộc để trống bị từ chối; tài khoản demo không đăng nhập
  được với Keycloak 26; `make install` không cài `alembic.ini` và `migrations/`.

## [0.2.1] - 2026-10-26

### Fixed
- `reuse lint` lỗi do `scripts/add_spdx_headers.mjs` và `CONTRIBUTING.md` chứa mẫu header SPDX bị đọc nhầm; bỏ khóa không hợp lệ trong `REUSE.toml` — `d31d057`, `fdc0e7c`. CI toàn bộ xanh từ bản này; `v0.2.0` giữ nguyên làm mốc lịch sử. **Lưu ý:** `v0.2.0` được build từ commit `633b9ec` khi `reuse lint` còn lỗi, vì vậy bản dùng để chấm/cài đặt là `v0.2.1` trở lên, không phải `v0.2.0`.

## [0.2.0] - 2026-10-26

DXOS V2: sẵn sàng đối chiếu tiêu chí PoF.

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

## [0.1.0] - 2026-10-24

DXOS V1 (đường cơ sở). Ghi bổ sung: tại tag `v0.1.0` chưa có `CHANGELOG.md`; mục này viết sau, cùng lúc tạo
CHANGELOG ở bản 0.2.0. Tag tạo ngày 26/10/2026, không có GitHub Release.

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

[Unreleased]: https://github.com/Dking2007/DXOS_Desktiny/compare/v3.1.0...HEAD
[3.1.0]: https://github.com/Dking2007/DXOS_Desktiny/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/Dking2007/DXOS_Desktiny/compare/v0.2.2...v3.0.0
[0.2.2]: https://github.com/Dking2007/DXOS_Desktiny/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/Dking2007/DXOS_Desktiny/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Dking2007/DXOS_Desktiny/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Dking2007/DXOS_Desktiny/releases/tag/v0.1.0
