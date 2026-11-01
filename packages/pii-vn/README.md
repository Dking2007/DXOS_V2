<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# dx-piivn

Tìm định danh cá nhân Việt Nam trong văn bản, không phụ thuộc thư viện ngoài.

```python
from dx_piivn import find_pii, redact

text = "Liên hệ an.nguyen@example.vn hoặc 0912 345 678 (CCCD 079203012345)"
find_pii(text)   # [Finding(kind='EMAIL', ...), Finding(kind='PHONE', ...), Finding(kind='CCCD', ...)]
redact(text)     # "Liên hệ [EMAIL] hoặc [PHONE] (CCCD [CCCD])"
```

| Loại | Quy tắc | Cần từ khóa? |
|---|---|---|
| `CCCD` | 12 số: mã tỉnh hợp lệ + chữ số thế kỷ/giới + năm sinh không ở tương lai | Không (có từ khóa thì `confidence="high"`) |
| `CMND` | 9 số | Có (`CMND`, `CMT`, `chứng minh`) |
| `PHONE` | đầu số di động đang dùng; hỗ trợ `+84` và `(+84)` | Không |
| `BANK_ACCOUNT` | 8–19 số | Có (`STK`, `số tài khoản`, `tài khoản`) |
| `TAX_CODE` | 10 hoặc 13 số | Có (`MST`, `mã số thuế`) |
| `EMAIL` | địa chỉ e-mail | Không |

`Finding` chỉ có `kind`, `start`, `end`, `confidence`; không giữ giá trị gốc, nên có thể lưu mà
không lưu dữ liệu cá nhân.

## Giới hạn

- CCCD không có chữ số kiểm tra. Số qua được kiểm tra chỉ là "đúng cấu trúc", không chứng minh đã
  được cấp. Số 12 chữ số ngẫu nhiên vẫn qua khoảng 1,6% (test đo trên 100.000 mẫu, ngưỡng 3%).
- Danh sách mã tỉnh và đầu số di động **chưa đối chiếu với văn bản chính thức** (`[ĐX]`); cần người
  đối chiếu trước khi dựa vào.
- Số tài khoản và mã số thuế không có checksum công khai nên chỉ báo khi có từ khóa ngay trước.
- Không có OCR: văn bản phải lấy được từ lớp chữ của tài liệu. Không dò tên người.
- Số điện thoại bàn (`02x`) không được báo vì thường là của cơ quan.
- Đây là heuristic hỗ trợ rà soát, không phải kiểm tra pháp lý.
