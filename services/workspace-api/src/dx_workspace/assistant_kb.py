# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Finding the knowledge an assistant answer should rest on.

A pilot holds tens to a few hundred articles, so ranking happens in memory with BM25 over
accent-folded words: "quy trinh" finds "quy trình". No search index or extra service.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from itertools import pairwise

CHUNK_CHARS = 900
# Words so common in questions that they say nothing about the topic.
STOPWORDS = {
    "la", "va", "cua", "cho", "the", "nao", "gi", "co", "khong", "duoc", "toi", "ban", "mot",
    "cac", "nhung", "de", "trong", "voi", "khi", "thi", "se", "da", "dang", "ve", "nay", "do",
    "o", "tu", "den", "hay", "hoac", "neu", "bang", "nhu", "a", "ah", "oi", "minh", "em", "anh",
    "chi", "vay", "sao", "ra", "len", "vao", "lai", "nhe", "thoi",
}  # fmt: skip
CATEGORIES = {
    "process": "Quy trình nghiệp vụ",
    "guide": "Hướng dẫn sử dụng",
    "faq": "Hỏi đáp",
    "other": "Khác",
}


def fold(text: str) -> str:
    """Lower case without Vietnamese accents, so typing without marks still matches."""
    text = unicodedata.normalize("NFD", text.lower()).replace("đ", "d")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", fold(text)) if w not in STOPWORDS]


@dataclass
class Chunk:
    article_id: str
    title: str
    category: str
    text: str
    terms: list[str]


def chunk_article(article_id: str, title: str, category: str, body: str) -> list[Chunk]:
    """Split on blank lines and pack paragraphs into pieces of about CHUNK_CHARS."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    pieces: list[str] = []
    current = ""
    for paragraph in paragraphs:
        while len(paragraph) > CHUNK_CHARS:
            cut = paragraph.rfind(" ", 0, CHUNK_CHARS)
            cut = cut if cut > CHUNK_CHARS // 2 else CHUNK_CHARS
            if current:
                pieces.append(current)
                current = ""
            pieces.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()
        if current and len(current) + len(paragraph) + 2 > CHUNK_CHARS:
            pieces.append(current)
            current = ""
        current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        pieces.append(current)
    # The title counts twice: a question naming the topic should find its article.
    title_terms = words(title) * 2
    return [Chunk(article_id, title, category, text, title_terms + words(text)) for text in pieces]


def search(chunks: list[Chunk], query: str, limit: int = 6, budget: int = 6000) -> list[Chunk]:
    """Best-matching chunks, at most `limit` and about `budget` characters in total."""
    query_terms = list(dict.fromkeys(words(query)))
    if not query_terms or not chunks:
        return []
    count = len(chunks)
    average = sum(len(c.terms) for c in chunks) / count or 1
    frequency = Counter(term for c in chunks for term in set(c.terms))
    pairs = set(pairwise(query_terms))
    scored = []
    for chunk in chunks:
        tf = Counter(chunk.terms)
        score = 0.0
        for term in query_terms:
            if not tf[term]:
                continue
            idf = math.log(1 + (count - frequency[term] + 0.5) / (frequency[term] + 0.5))
            norm = tf[term] + 1.2 * (1 - 0.75 + 0.75 * len(chunk.terms) / average)
            score += idf * tf[term] * 2.2 / norm
        # Two question words next to each other in the text ("nghi phep") are a strong signal.
        if pairs:
            score += 0.6 * len(pairs & set(pairwise(chunk.terms)))
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    picked: list[Chunk] = []
    used = 0
    for _, chunk in scored:
        if len(picked) >= limit or (picked and used + len(chunk.text) > budget):
            break
        picked.append(chunk)
        used += len(chunk.text)
    return picked


OPERATORS = {"eq": "bằng", "ne": "khác", "gt": "lớn hơn", "gte": "từ", "lt": "nhỏ hơn", "lte": "không quá"}
FIELD_TYPES = {
    "text": "chữ",
    "textarea": "đoạn văn",
    "number": "số",
    "date": "ngày",
    "select": "chọn một giá trị",
    "checkbox": "xác nhận",
}


def package_article(package_name: str, description: str, form, steps: list, files: int, names: dict) -> str:
    """Describe a published business package as plain text the assistant can explain."""
    labels = {f.get("key"): f.get("label") or f.get("key") for f in form.fields or []}
    lines = [f"Quy trình “{package_name}” dùng mẫu hồ sơ “{form.name}”."]
    if description.strip():
        lines.append(description.strip())
    if form.description and form.description.strip():
        lines.append(f"Mô tả mẫu: {form.description.strip()}")
    lines.append("")
    lines.append("Thông tin cần điền khi lập hồ sơ:")
    for field in form.fields or []:
        kind = FIELD_TYPES.get(field.get("type"), field.get("type", ""))
        required = "bắt buộc" if field.get("required") else "không bắt buộc"
        options = f"; các lựa chọn: {', '.join(field['options'])}" if field.get("options") else ""
        lines.append(f"- {field.get('label') or field.get('key')} ({kind}, {required}{options})")
    lines.append("")
    lines.append(
        f"Cần đính kèm ít nhất {files} tài liệu từ kho tài liệu."
        if files
        else "Không bắt buộc đính kèm tài liệu."
    )
    lines.append("")
    lines.append("Các bước phê duyệt sau khi bấm “Chuyển duyệt”:")
    for number, step in enumerate(steps, 1):
        who = (
            "lãnh đạo phòng của người lập hồ sơ"
            if step.get("resolver") == "department_manager"
            else names.get(step.get("user_id"), "người được chỉ định")
        )
        condition = step.get("condition")
        when = ""
        if condition:
            label = labels.get(condition.get("field"), condition.get("field"))
            word = OPERATORS.get(condition.get("operator"), condition.get("operator"))
            when = f" (chỉ khi “{label}” {word} {condition.get('value')})"
        lines.append(f"{number}. {step.get('label')}: {who} duyệt{when}.")
    lines.append("")
    lines.append(
        "Mỗi người duyệt có thể phê duyệt, trả lại để sửa hoặc từ chối. Hồ sơ bị trả lại về trạng "
        "thái “Cần sửa”; người lập sửa rồi trình lại. Hồ sơ được phê duyệt khi đủ mọi bước."
    )
    return "\n".join(lines)
