# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import random
from datetime import date

from dx_piivn import find_pii, fold, mask, redact, valid_cccd, valid_mobile

TODAY = date(2026, 10, 31)


def kinds(text):
    return [(f.kind, text[f.start : f.end]) for f in find_pii(text, today=TODAY)]


def test_valid_cccd_structure():
    assert valid_cccd("079203012345", TODAY)  # HCMC, born 2003
    assert valid_cccd("001085123456", TODAY)  # Hanoi, born 1985
    assert not valid_cccd("097203012345", TODAY)  # no province 097
    assert not valid_cccd("079803012345", TODAY)  # century digit 8 -> year 2303
    assert not valid_cccd("079227012345", TODAY)  # born 2027
    assert not valid_cccd("07920301234", TODAY)  # 11 digits


def test_cccd_is_found_with_and_without_keyword():
    assert kinds("CCCD số 079203012345 cấp tại Hà Nội") == [("CCCD", "079203012345")]
    found = find_pii("mã 079203012345", today=TODAY)
    assert [(f.kind, f.confidence) for f in found] == [("CCCD", "medium")]
    assert find_pii("CCCD số 079203012345", today=TODAY)[0].confidence == "high"


def test_random_twelve_digit_numbers_rarely_pass():
    rng = random.Random(7)
    hits = sum(valid_cccd(f"{rng.randrange(10**12):012d}", TODAY) for _ in range(100_000))
    assert hits / 100_000 < 0.03  # a bare 001..096 prefix check would pass about 9.6%


def test_phone_numbers():
    assert valid_mobile("0912345678")
    assert not valid_mobile("0123456789")  # old 012x prefixes are gone
    assert kinds("Gọi 0912 345 678 hoặc 091.234.5678") == [("PHONE", "0912 345 678"), ("PHONE", "091.234.5678")]
    assert kinds("ĐT: +84 912 345 678") == [("PHONE", "+84 912 345 678")]
    assert kinds("ĐT: (+84) 912345678") == [("PHONE", "(+84) 912345678")]
    assert kinds("mã đơn 0123456789") == []


def test_bank_account_and_tax_code_need_a_keyword():
    assert kinds("STK: 1903 1234 5678 90") == [("BANK_ACCOUNT", "1903 1234 5678 90")]
    assert kinds("Số tài khoản 0123456789012") == [("BANK_ACCOUNT", "0123456789012")]
    assert kinds("mã 1903123456789") == []
    assert kinds("MST 0912345678") == [("TAX_CODE", "0912345678")]  # not read as a phone number
    assert kinds("Mã số thuế: 0312345678901") == [("TAX_CODE", "0312345678901")]


def test_keyword_must_sit_right_before_the_number():
    assert kinds("tài khoản 55 và 0912345678") == [("PHONE", "0912345678")]


def test_old_cmnd_needs_keyword():
    assert kinds("CMND: 123456789") == [("CMND", "123456789")]
    assert kinds("số 123456789") == []


def test_dates_and_plain_numbers_are_ignored():
    assert kinds("Ngày 12 03 2026, tổng 1.250.000 đồng, 150 trang") == []


def test_email_and_redaction():
    text = "Liên hệ an.nguyen@example.vn hoặc 0912345678 (CCCD 079203012345)"
    assert redact(text, today=TODAY) == "Liên hệ [EMAIL] hoặc [PHONE] (CCCD [CCCD])"


def test_findings_hold_positions_not_values():
    finding = find_pii("SĐT 0912345678", today=TODAY)[0]
    assert set(vars(finding)) == {"kind", "start", "end", "confidence"}


def test_mask_keeps_only_the_ends():
    assert mask("CCCD", "079203012345") == "07********45"
    assert mask("EMAIL", "an.nguyen@example.vn") == "a***@example.vn"
    assert mask("PHONE", "0912 345 678") == "09******78"


def test_fold_preserves_length():
    text = "Đặng Thị Ánh Nguyệt — Số tài khoản"
    assert len(fold(text)) == len(text)
    assert fold("Số tài khoản") == "so tai khoan"
