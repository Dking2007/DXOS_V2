# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Readable text out of the files people attach, page by page, for the AI features.

PDF text comes from pypdf. Word, Excel and PowerPoint files are zip archives of XML, read with
the standard library. A scanned PDF or a photo has no text layer: the caller then sends the
file itself to a service that can look at it, or tells the person it cannot be read.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree

from pypdf import PdfReader
from pypdf.errors import PdfReadError

# A page or slide is cut here; past this the text adds cost more than it adds facts.
MAX_PAGE_CHARS = 6000
MAX_PAGES = 60
# Word has no pages of its own; text is split into numbered parts of about this size instead.
WORD_PART_CHARS = 3000
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
TEXT_TYPES = {"text/plain", "text/markdown", "text/csv", "application/json"}
WORD = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SLIDES = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}


@dataclass
class Page:
    number: int
    text: str


@dataclass
class Document:
    name: str
    mime: str
    pages: list[Page]
    # What a page number means here: "trang" (PDF), "phần" (Word), "trang tính", "trang chiếu".
    unit: str = "trang"
    is_image: bool = False

    @property
    def has_text(self) -> bool:
        return any(page.text.strip() for page in self.pages)

    def as_prompt(self, limit: int = 40000) -> str:
        """The text with page markers the model can cite, cut at `limit` characters."""
        parts, used = [], 0
        for page in self.pages:
            block = f"[{self.unit} {page.number}]\n{page.text.strip()}\n"
            if used + len(block) > limit:
                parts.append("[…phần còn lại của tài liệu đã được lược bớt…]")
                break
            parts.append(block)
            used += len(block)
        return "\n".join(parts)


def kind_of(name: str, mime: str) -> str:
    suffix = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if mime == "application/pdf" or suffix == "pdf":
        return "pdf"
    if mime == WORD or suffix == "docx":
        return "docx"
    if mime == EXCEL or suffix == "xlsx":
        return "xlsx"
    if mime == SLIDES or suffix == "pptx":
        return "pptx"
    if mime in IMAGE_TYPES or suffix in {"png", "jpg", "jpeg", "webp", "gif"}:
        return "image"
    if mime in TEXT_TYPES or mime.startswith("text/") or suffix in {"txt", "md", "csv", "json"}:
        return "text"
    return "other"


def _clean(text: str) -> str:
    text = re.sub(r"[ \t ]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()[:MAX_PAGE_CHARS]


def read(name: str, mime: str, data: bytes) -> Document:
    """Split a file into numbered pages of text. Unknown or broken files give no pages."""
    kind = kind_of(name, mime)
    try:
        if kind == "pdf":
            reader = PdfReader(io.BytesIO(data))
            pages = [
                Page(i + 1, _clean(p.extract_text() or "")) for i, p in enumerate(reader.pages[:MAX_PAGES])
            ]
            return Document(name, "application/pdf", pages)
        if kind == "docx":
            return Document(name, mime, _word(data), unit="phần")
        if kind == "xlsx":
            return Document(name, mime, _excel(data), unit="trang tính")
        if kind == "pptx":
            return Document(name, mime, _slides(data), unit="trang chiếu")
        if kind == "text":
            return Document(name, mime, [Page(1, _clean(data.decode("utf-8", errors="replace")))])
        if kind == "image":
            return Document(name, mime if mime in IMAGE_TYPES else "image/png", [], is_image=True)
    except (PdfReadError, zipfile.BadZipFile, ElementTree.ParseError, KeyError, ValueError):
        pass
    return Document(name, mime, [])


def _word(data: bytes) -> list[Page]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    paragraphs = []
    for paragraph in root.iter(f"{{{NS['w']}}}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{{{NS['w']}}}t"))
        if text.strip():
            paragraphs.append(text)
    pages, current = [], ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) > WORD_PART_CHARS:
            pages.append(Page(len(pages) + 1, _clean(current)))
            current = ""
        current += paragraph + "\n"
    if current:
        pages.append(Page(len(pages) + 1, _clean(current)))
    return pages[:MAX_PAGES]


def _excel(data: bytes) -> list[Page]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [
                "".join(t.text or "" for t in item.iter(f"{{{NS['s']}}}t"))
                for item in root.iter(f"{{{NS['s']}}}si")
            ]
        sheets = sorted(
            (n for n in archive.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
            key=lambda n: int(re.search(r"(\d+)", n).group(1)),
        )
        pages = []
        for name in sheets[:MAX_PAGES]:
            root = ElementTree.fromstring(archive.read(name))
            rows = []
            for row in root.iter(f"{{{NS['s']}}}row"):
                cells = []
                for cell in row.iter(f"{{{NS['s']}}}c"):
                    value = cell.find("s:v", NS)
                    inline = cell.find("s:is", NS)
                    if cell.get("t") == "s" and value is not None and value.text and value.text.isdigit():
                        index = int(value.text)
                        cells.append(shared[index] if index < len(shared) else "")
                    elif inline is not None:
                        cells.append("".join(t.text or "" for t in inline.iter(f"{{{NS['s']}}}t")))
                    elif value is not None:
                        cells.append(value.text or "")
                if any(c.strip() for c in cells):
                    rows.append(" | ".join(cells))
            pages.append(Page(len(pages) + 1, _clean("\n".join(rows))))
    return pages


def _slides(data: bytes) -> list[Page]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = sorted(
            (n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
            key=lambda n: int(re.search(r"(\d+)", n).group(1)),
        )
        pages = []
        for name in names[:MAX_PAGES]:
            root = ElementTree.fromstring(archive.read(name))
            lines = [
                "".join(t.text or "" for t in p.iter(f"{{{NS['a']}}}t")) for p in root.iter(f"{{{NS['a']}}}p")
            ]
            pages.append(Page(len(pages) + 1, _clean("\n".join(line for line in lines if line.strip()))))
    return pages
