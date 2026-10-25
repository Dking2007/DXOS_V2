# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile


def new_document(kind: str) -> tuple[bytes, str]:
    common = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    content = {
        "docx": {
            "part": "word/document.xml",
            "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
            "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xml": '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Tài liệu mới</w:t></w:r></w:p><w:sectPr/></w:body></w:document>',
        },
        "xlsx": {
            "part": "xl/workbook.xml",
            "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
            "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xml": '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Trang 1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        },
        "pptx": {
            "part": "ppt/presentation.xml",
            "type": "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
            "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "xml": '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:sldSz cx="9144000" cy="6858000"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>',
        },
    }[kind]
    extra_types = ""
    if kind == "xlsx":
        extra_types = '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            common
            + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/'
            + content["part"]
            + '" ContentType="'
            + content["type"]
            + '"/>'
            + extra_types
            + "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            common
            + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="'
            + content["part"]
            + '"/></Relationships>',
        )
        archive.writestr(content["part"], common + content["xml"])
        if kind == "xlsx":
            archive.writestr(
                "xl/_rels/workbook.xml.rels",
                common
                + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
            )
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                common
                + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>',
            )
    return stream.getvalue(), content["mime"]
