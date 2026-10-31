# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Word files laid out as Vietnamese administrative documents (Nghị định 30/2020/NĐ-CP).

The values follow Phụ lục I the same way plugins/vn-document-format checks them: A4, margins
20/20/30/15 mm, Times New Roman, national title 13 pt with motto 14 pt, body 14 pt. The AI only
writes the words; the layout is fixed here, so a draft opened in ONLYOFFICE passes the plugin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TWIPS_PER_MM = 1440 / 25.4
FONT = "Times New Roman"
# Document kinds with their heading: a công văn has no heading, its subject sits under the number.
KINDS = {
    "to_trinh": "TỜ TRÌNH",
    "cong_van": "",
    "thong_bao": "THÔNG BÁO",
    "ke_hoach": "KẾ HOẠCH",
    "bao_cao": "BÁO CÁO",
    "giay_moi": "GIẤY MỜI",
}
KIND_LABELS = {
    "to_trinh": "Tờ trình",
    "cong_van": "Công văn",
    "thong_bao": "Thông báo",
    "ke_hoach": "Kế hoạch",
    "bao_cao": "Báo cáo",
    "giay_moi": "Giấy mời",
}


@dataclass
class Draft:
    kind: str
    subject: str
    paragraphs: list[str]
    agency: str = "TÊN CƠ QUAN"
    parent_agency: str = ""
    number: str = "Số:      /"
    place_date: str = "......, ngày ... tháng ... năm ......"
    recipients: list[str] = field(default_factory=list)
    signer_title: str = "THỦ TRƯỞNG CƠ QUAN"
    signer_name: str = ""
    copies: list[str] = field(default_factory=list)


def _mm(value: float) -> int:
    return round(value * TWIPS_PER_MM)


def _run(text: str, size: float, bold=False, italic=False, underline=False, caps=False) -> str:
    props = f'<w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}" w:eastAsia="{FONT}"/>'
    props += "<w:b/>" if bold else ""
    props += "<w:i/>" if italic else ""
    props += "<w:caps/>" if caps else ""
    props += '<w:u w:val="single"/>' if underline else ""
    props += f'<w:color w:val="000000"/><w:sz w:val="{round(size * 2)}"/><w:szCs w:val="{round(size * 2)}"/>'
    return f'<w:r><w:rPr>{props}</w:rPr><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def _para(runs: str, align="left", indent_mm=0.0, before=0, after=0, line=None) -> str:
    spacing = (
        f'<w:spacing w:before="{before}" w:after="{after}"'
        + (f' w:line="{line}" w:lineRule="auto"' if line else "")
        + "/>"
    )
    indent = f'<w:ind w:firstLine="{_mm(indent_mm)}"/>' if indent_mm else ""
    return f'<w:p><w:pPr>{spacing}{indent}<w:jc w:val="{align}"/></w:pPr>{runs}</w:p>'


def _cell(width_mm: float, body: str) -> str:
    return f'<w:tc><w:tcPr><w:tcW w:w="{_mm(width_mm)}" w:type="dxa"/></w:tcPr>{body}</w:tc>'


def _table(columns: list[tuple[float, str]]) -> str:
    grid = "".join(f'<w:gridCol w:w="{_mm(w)}"/>' for w, _ in columns)
    borders = "".join(
        f'<w:{side} w:val="nil"/>' for side in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/><w:tblLayout w:type="fixed"/>'
        f"<w:tblBorders>{borders}</w:tblBorders></w:tblPr><w:tblGrid>{grid}</w:tblGrid>"
        "<w:tr>" + "".join(_cell(w, body) for w, body in columns) + "</w:tr></w:tbl>"
    )


def document_xml(draft: Draft) -> str:
    left = ""
    if draft.parent_agency:
        left += _para(_run(draft.parent_agency.upper(), 13), "center")
    left += _para(_run(draft.agency.upper(), 13, bold=True), "center")
    left += _para(_run("_______", 13), "center")
    left += _para(_run(draft.number, 13), "center", before=60)
    if draft.kind == "cong_van":
        left += _para(_run("V/v " + draft.subject, 12), "center")
    right = _para(_run("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", 13, bold=True), "center")
    right += _para(_run("Độc lập - Tự do - Hạnh phúc", 14, bold=True), "center")
    right += _para(_run("_______________________", 13), "center")
    right += _para(_run(draft.place_date, 14, italic=True), "center", before=120)
    body = _table([(70, left), (95, right)])
    heading = KINDS.get(draft.kind, "")
    if heading:
        body += _para(_run(heading, 14, bold=True), "center", before=360)
        body += _para(_run(draft.subject, 14, bold=True), "center", after=120)
    if draft.recipients:
        lines = draft.recipients
        if len(lines) == 1:
            body += _para(_run("Kính gửi: ", 14) + _run(lines[0], 14), "center", before=240, after=120)
        else:
            body += _para(_run("Kính gửi:", 14), "left", indent_mm=40, before=240)
            for item in lines:
                body += _para(_run("- " + item, 14), "left", indent_mm=55)
    for text in draft.paragraphs:
        if text.strip():
            body += _para(_run(text.strip(), 14), "both", indent_mm=12.7, before=120, line=300)
    copies = _para(_run("Nơi nhận:", 12, bold=True, italic=True), "left", before=240)
    for item in draft.copies or ["Như trên;", "Lưu: VT."]:
        copies += _para(_run("- " + item, 11), "left")
    sign = _para(_run(draft.signer_title.upper(), 14, bold=True), "center", before=240)
    sign += _para(_run("(Ký, ghi rõ họ tên và đóng dấu)", 14, italic=True), "center", after=1200)
    sign += _para(_run(draft.signer_name or "", 14, bold=True), "center")
    body += _table([(75, copies), (90, sign)])
    section = (
        f'<w:sectPr><w:pgSz w:w="{_mm(210)}" w:h="{_mm(297)}"/>'
        f'<w:pgMar w:top="{_mm(20)}" w:right="{_mm(15)}" w:bottom="{_mm(20)}" w:left="{_mm(30)}"'
        ' w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}{section}</w:body></w:document>"
    )


STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    f'<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}"'
    f' w:eastAsia="{FONT}"/><w:sz w:val="28"/><w:szCs w:val="28"/><w:lang w:val="vi-VN"/></w:rPr>'
    '</w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
    "</w:pPrDefault></w:docDefaults></w:styles>"
)


def build(draft: Draft) -> bytes:
    head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            head + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            head + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "word/_rels/document.xml.rels",
            head + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            "</Relationships>",
        )
        archive.writestr("word/document.xml", document_xml(draft))
        archive.writestr("word/styles.xml", STYLES)
    return stream.getvalue()
