// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Desktiny contributors
// How to use each screen, shown from the (!) button beside the page name in the top bar.
// Keyed by the route's path pattern; a screen without an entry shows no button.

export interface HelpTopic {
  /** What the screen is for, in one or two sentences. */
  purpose: string
  /** The usual way through it, in order. */
  steps: string[]
  /** Things people often miss. */
  tips: string[]
}

export const HELP: Record<string, HelpTopic> = {
  '/home': {
    purpose: 'Mọi việc cần bạn xử lý hôm nay ở một chỗ: công việc, hồ sơ chờ duyệt và lời nhắc đến bạn.',
    steps: [
      'Xem danh sách "Việc cần làm hôm nay"; các mục quá hạn hoặc sắp tới hạn đứng đầu.',
      'Dùng các nút lọc (Quá hạn, Công việc, Phê duyệt, Nhắc đến tôi) để thu hẹp danh sách.',
      'Bấm nút ở cuối mỗi dòng để xử lý ngay, ví dụ "Nghiệm thu" hoặc "Xem và duyệt".',
      'Dùng "Bắt đầu nhanh" để giao việc, lập hồ sơ hoặc mở kho tài liệu.',
    ],
    tips: [
      'Bấm Ctrl + K ở bất kỳ đâu để tìm hoặc mở nhanh một mục.',
      'Nút "Tạo mới" trên thanh trên cùng tạo công việc, hồ sơ hay tài liệu từ mọi màn hình.',
    ],
  },
  '/tasks': {
    purpose: 'Giao việc theo cấp quản lý, theo dõi tiến độ và nghiệm thu kết quả.',
    steps: [
      'Bấm "Giao việc", nhập tên, người hoặc đơn vị nhận, hạn hoàn thành; đính kèm tài liệu nếu cần.',
      'Chọn tab để xem: Việc của tôi, Tôi đã giao, Đang theo dõi, Tôi điều phối, Tất cả.',
      'Lọc theo trạng thái, đánh dấu "Quá hạn" hoặc tìm theo tên việc.',
      'Đổi kiểu hiển thị: danh sách, bảng Kanban hoặc theo hạn.',
      'Bấm vào một việc để mở chi tiết, cập nhật tiến độ và trao đổi.',
    ],
    tips: [
      'Việc chỉ hoàn tất khi người giao bấm "Nghiệm thu"; người làm chỉ "Nộp kết quả".',
      'Việc có thể yêu cầu nộp tệp kết quả: thiếu tệp thì chưa nộp được.',
    ],
  },
  '/tasks/:id': {
    purpose: 'Toàn bộ thông tin của một việc: yêu cầu, tài liệu, việc con, trao đổi và lịch sử thay đổi.',
    steps: [
      'Người nhận bấm "Tiếp nhận", làm việc rồi "Nộp kết quả".',
      'Thêm tài liệu ở thẻ "Tài liệu": tải lên hoặc chọn từ kho; xem trước ngay trên trang.',
      'Chia nhỏ việc ở "Việc con"; việc cha chỉ nghiệm thu được khi mọi việc con đã xong hoặc hủy.',
      'Người giao "Nghiệm thu" hoặc "Trả lại" kèm lý do.',
    ],
    tips: [
      'Người làm chỉ gỡ được tệp do chính mình đính kèm.',
      'Bấm "Trao đổi" để mở cuộc trò chuyện gắn với việc này.',
    ],
  },
  '/approvals': {
    purpose: 'Các hồ sơ và yêu cầu đang chờ bạn quyết định, kể cả những việc bạn xử lý thay người đã ủy quyền.',
    steps: [
      'Xem danh sách: bước xử lý, thời điểm nhận, hạn xử lý và trạng thái.',
      'Bấm "Xem hồ sơ" để đọc nội dung, tài liệu và ý kiến trước khi quyết định.',
      'Yêu cầu từ luồng không có hồ sơ (ví dụ về một công việc) thì bấm "Xử lý" để quyết định ngay.',
      'Ở mục "Khi bạn vắng mặt", bấm "Ủy quyền" để người khác duyệt thay trong một khoảng thời gian.',
    ],
    tips: [
      'Trả lại hoặc từ chối luôn cần ghi lý do.',
      'Một số bước yêu cầu nộp kết quả (trường hoặc tệp) khi đồng ý.',
      'Không ai được tự duyệt hồ sơ của chính mình.',
    ],
  },
  '/cases': {
    purpose: 'Các hồ sơ điện tử, từ bản nháp đến quyết định cuối cùng.',
    steps: [
      'Bấm "Tạo hồ sơ", chọn quy trình bạn được dùng, điền thông tin và đính kèm tài liệu.',
      'Hồ sơ được lưu ở dạng bản nháp; kiểm tra lại rồi "Chuyển duyệt".',
      'Lọc theo trạng thái: Bản nháp, Đang xử lý, Cần sửa, Đã duyệt, Đã hủy, Lưu trữ.',
      'Bấm vào hồ sơ để xem đang ở bước nào và ai đang xử lý.',
    ],
    tips: [
      'Mỗi quy trình có thể yêu cầu số tài liệu tối thiểu; thiếu thì chưa trình được.',
      'Hồ sơ giữ phiên bản quy trình lúc tạo, kể cả khi quy trình được sửa sau đó.',
    ],
  },
  '/cases/:id': {
    purpose: 'Nội dung, tài liệu, tiến độ quy trình và lịch sử của một hồ sơ.',
    steps: [
      'Tab "Thông tin": nội dung biểu mẫu. Người tạo sửa được khi hồ sơ là bản nháp hoặc bị trả lại.',
      'Tab "Quy trình": sơ đồ các bước, bước đang chờ ai, ý kiến và kết quả từng bước.',
      'Tab "Tài liệu": xem, tải tài liệu đính kèm theo từng lần trình.',
      'Người được hỏi ở một bước thấy thanh quyết định cuối trang: Phê duyệt, Trả lại, Từ chối hoặc Nhập thông tin.',
    ],
    tips: [
      'Bấm "Trao đổi" để thảo luận về hồ sơ, hoặc "Tạo việc" để giao việc gắn với hồ sơ.',
      'Khi được bật, khung "Hỏi đáp về hồ sơ" trả lời câu hỏi về nội dung và tiến độ của hồ sơ.',
    ],
  },
  '/chat': {
    purpose: 'Nhắn tin trực tiếp, nhóm, và trao đổi gắn với công việc hay hồ sơ.',
    steps: [
      'Chọn một cuộc trò chuyện ở cột trái, hoặc bắt đầu cuộc trò chuyện mới.',
      'Gõ tin nhắn; đính kèm tệp, ảnh; gõ @ để nhắc tên một người.',
      'Trả lời một tin cụ thể để giữ mạch trao đổi.',
    ],
    tips: ['Trao đổi mở từ một công việc hay hồ sơ luôn gắn với nó, mọi người liên quan đều thấy.'],
  },
  '/feed': {
    purpose: 'Thông báo chính thức, tin tức và lời chia sẻ trong cơ quan.',
    steps: [
      'Viết bài ở ô soạn thảo, thêm ảnh hoặc video, chọn người xem: toàn cơ quan hoặc phòng ban.',
      'Lọc để chỉ xem thông báo chính thức, bài đã lưu hoặc bài của phòng.',
      'Bày tỏ cảm xúc, bình luận hoặc lưu bài để xem lại.',
    ],
    tips: ['Chỉ người có quyền mới đăng được thông báo chính thức; bài ghim luôn nằm trên cùng.'],
  },
  '/drive': {
    purpose: 'Lưu, sắp xếp, chia sẻ và soạn thảo tài liệu của bạn và được chia sẻ với bạn.',
    steps: [
      'Bấm "Mới" để tạo thư mục, tải tệp lên hoặc tạo văn bản mới.',
      'Kéo tệp thả vào danh sách để tải lên thư mục đang mở.',
      'Bấm vào thư mục để mở; dùng đường dẫn phía trên để quay lại.',
      'Dùng nút ở cuối mỗi dòng để tải về, chia sẻ, đổi tên, di chuyển hoặc xóa.',
    ],
    tips: [
      'Chia sẻ một thư mục thì mọi tệp bên trong cùng được chia sẻ.',
      'Tệp đã xóa nằm trong "Thùng rác" và khôi phục được.',
    ],
  },
  '/drive/:id/edit': {
    purpose: 'Soạn thảo trực tiếp văn bản, bảng tính, trình chiếu trong trình duyệt.',
    steps: [
      'Sửa nội dung như trên phần mềm văn phòng; nhiều người có thể sửa cùng lúc.',
      'Thay đổi được lưu tự động thành phiên bản mới của tệp.',
      'Đóng trình soạn thảo khi xong để các bản lưu được ghi nhận.',
    ],
    tips: ['Tài liệu đang mở soạn thảo thì chưa trình hồ sơ được; hãy đóng trình soạn thảo trước.'],
  },
  '/reports': {
    purpose: 'Số liệu công việc và hồ sơ trên dữ liệu bạn được phép xem.',
    steps: [
      'Chọn phạm vi (mọi việc bạn xem được, việc bạn giao, việc của bạn) và khoảng thời gian.',
      'Xem tình hình công việc, phân bổ theo người và tình hình hồ sơ.',
      'Xem bảng theo phòng ban để biết đơn vị nào nhiều việc hoặc hồ sơ quá hạn.',
      'Xuất danh sách hồ sơ ra tệp CSV khi cần.',
    ],
    tips: ['Mỗi chỉ số đều có định nghĩa; con số chỉ tính trên những gì bạn có quyền xem.'],
  },
  '/search': {
    purpose: 'Tìm công việc, hồ sơ, tài liệu, bài viết và tin nhắn trong toàn hệ thống.',
    steps: [
      'Gõ từ khóa và bấm "Tìm"; có thể tìm theo mã hồ sơ như HS-000012.',
      'Kết quả được nhóm theo loại; bấm để mở.',
    ],
    tips: ['Chỉ hiển thị những gì bạn được phép xem.'],
  },
  '/processes': {
    purpose: 'Thiết kế các luồng xử lý: đường đi của hồ sơ và những việc tự động khi có sự kiện.',
    steps: [
      'Bấm "Tạo luồng", chọn một mẫu có sẵn.',
      'Ở node đầu tiên, chọn khi nào luồng chạy; chọn biểu mẫu thì luồng là đường đi của hồ sơ biểu mẫu đó.',
      'Thêm, nối các bước trên canvas rồi bấm "Lưu".',
      'Bấm "Phát hành" để phân quyền, chạy kịch bản thử và đưa luồng vào áp dụng.',
    ],
    tips: [
      'Sửa canvas không ảnh hưởng ai cho đến lần phát hành sau.',
      'Hồ sơ đã tạo giữ phiên bản quy trình của mình.',
    ],
  },
  '/processes/:id': {
    purpose: 'Vẽ và cấu hình từng bước của một luồng.',
    steps: [
      'Kéo một loại bước từ cột trái vào canvas, hoặc bấm vào để thêm sau bước đang chọn.',
      'Nối các cổng ra (Duyệt, Trả lại, Đúng, Sai…) tới bước tiếp theo.',
      'Bấm vào một bước để cấu hình: người xử lý, hạn, kết quả phải nộp, quyền xem.',
      'Bấm "Chạy thử" để xem đường đi với dữ liệu mẫu mà không tác động thật.',
      'Bấm "Lưu" (Ctrl + S), rồi "Phát hành" khi đã sẵn sàng.',
    ],
    tips: [
      'Bước sau đọc được kết quả của bước trước, ví dụ {tham_dinh.ket_luan}.',
      'Chỉ cổng "Trả lại" được nối ngược về bước trước.',
      'Cổng của bước Duyệt không nối thì hồ sơ kết thúc đúng theo tên cổng.',
    ],
  },
  '/assistant': {
    purpose: 'Cài đặt trợ lý AI và các tính năng AI trong phần mềm.',
    steps: [
      'Tab "Dịch vụ AI": thêm dịch vụ (Claude, OpenAI, Gemini, Ollama, vLLM…) và lấy danh sách model.',
      'Tab "Tính năng AI": bật từng tính năng, chọn dịch vụ và model, rồi "Lưu cấu hình".',
      'Tab "Kiến thức": viết hoặc nhập bài hướng dẫn để trợ lý trả lời đúng quy trình.',
      'Bấm "Thử hỏi trợ lý" để kiểm tra câu trả lời.',
    ],
    tips: ['Mọi tính năng AI mặc định tắt; chỉ người có quyền quản lý trợ lý mới bật được.'],
  },
  '/plugins': {
    purpose: 'Plugin kết nối: ứng dụng chạy ở máy chủ riêng, nhận sự kiện, thêm bước quy trình và khung giao diện.',
    steps: [
      '"Cài plugin (manifest)": chọn tệp desktiny-plugin.json (hoặc .zip), xem plugin xin gì rồi "Cài plugin".',
      '"Duyệt quyền": chỉ chọn quyền và sự kiện plugin thật sự cần, rồi "Duyệt và bật".',
      'Sao chép khoá ký và token vừa cấp (chỉ hiện một lần) vào cấu hình máy chủ plugin.',
      '"Nhật ký" xem sự kiện đã gửi, bước đã gọi, dữ liệu plugin đã đọc; gửi lại sự kiện bị lỗi.',
      '"Cấu hình" điền giá trị riêng của cơ quan (ô bí mật không hiện lại); "Kiểm tra" hỏi sức khoẻ máy chủ plugin.',
    ],
    tips: [
      'Tắt plugin thì mọi token của nó hết hiệu lực ngay.',
      'Máy chủ plugin phải có trong danh sách được phép của triển khai (PLUGIN_ALLOWED_HOSTS).',
      'Mất khoá thì bấm "Đổi khoá"; khoá cũ hết hiệu lực.',
    ],
  },
  '/plugins/:pluginId/admin/:index': {
    purpose: 'Trang quản trị của một plugin kết nối: cấu hình nghiệp vụ của plugin (ca làm, bậc lương, mẫu giấy tờ…).',
    steps: ['Thao tác trong khung của plugin; plugin chỉ làm được những gì quản trị viên đã duyệt cho nó.'],
    tips: ['Chỉ người quản lý tổ chức mở được trang này.'],
  },
  '/apps/:pluginId/:index': {
    purpose: 'Trang riêng của một plugin kết nối, hiện trong khung cách ly ngay trong phần mềm.',
    steps: ['Dùng như một trang bình thường; plugin chỉ đọc được dữ liệu trong phạm vi quyền của bạn.'],
    tips: ['Nội dung trang do plugin cung cấp; liên hệ quản trị nếu trang không tải được.'],
  },
  '/packs': {
    purpose: 'Gói giao diện: giao diện (tên, logo, màu, trang đăng nhập, từ ngữ, menu) và quy trình mẫu theo ngành, cài và gỡ được.',
    steps: [
      'Gói có sẵn: bấm "Xem và cài", đọc phần xem trước (sẽ thêm gì, đổi gì) rồi "Cài gói".',
      'Gói từ cơ quan khác: "Tải gói lên (.zip)", xem trước rồi cài.',
      '"Tạo gói của cơ quan": chỉnh giao diện có xem trước sáng/tối, chọn quy trình đưa vào gói, rồi "Lưu gói".',
      'Bấm "Dùng giao diện này" để áp dụng cho mọi người; "Về giao diện mặc định" để trở lại như cũ.',
    ],
    tips: [
      'Màu khó đọc (tương phản dưới 4,5:1) bị từ chối, ở cả giao diện sáng và tối.',
      'Gỡ gói không xoá quy trình đã có hồ sơ; quy trình đó chỉ ngừng phát hành.',
      '"Xuất" tạo tệp .zip để cài ở cơ quan khác.',
    ],
  },
  '/profile': {
    purpose: 'Ảnh đại diện và thông tin liên hệ mà đồng nghiệp nhìn thấy.',
    steps: [
      'Bấm "Tải ảnh lên" để chọn ảnh PNG, JPEG hoặc WebP (tối đa 2 MB).',
      'Sửa họ tên, chức danh, số điện thoại, email liên hệ và giới thiệu ngắn.',
      'Bấm "Lưu thay đổi". "Hoàn tác" đưa các ô về như trước khi sửa.',
    ],
    tips: [
      'Ảnh hiện ở thanh trên cùng, trong Nhắn tin và Bảng tin.',
      'Vai trò và phòng ban do quản trị viên thay đổi trong Thiết lập.',
    ],
  },
  '/settings': {
    purpose: 'Cơ cấu tổ chức, vai trò và quyền, nhật ký và giao diện.',
    steps: [
      'Cơ cấu tổ chức: thêm phòng ban, người dùng, chọn lãnh đạo phòng.',
      'Vai trò và quyền: xem và chỉnh những gì mỗi vai trò được làm.',
      'Nhật ký: tra cứu ai đã làm gì, lúc nào.',
    ],
    tips: ['Biểu mẫu và bước duyệt được thiết kế trong Quy trình nghiệp vụ.'],
  },
}
