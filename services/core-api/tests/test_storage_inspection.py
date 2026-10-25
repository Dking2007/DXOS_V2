# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Uploads are accepted by content signature, not by the name a client gives them."""

import io
import zipfile

import pytest
from dx_core.storage import inspect_content
from dx_platform.errors import AppError


def zipped(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("name", "data", "mime"),
    [
        ("anh.gif", b"GIF89a\x01\x00", "image/gif"),
        ("anh.webp", b"RIFF\x10\x00\x00\x00WEBPVP8 ", "image/webp"),
        ("clip.mp4", b"\x00\x00\x00\x18ftypmp42\x00\x00", "video/mp4"),
        ("clip.mov", b"\x00\x00\x00\x14ftypqt  \x00\x00", "video/quicktime"),
        ("clip.webm", b"\x1aE\xdf\xa3\x9fB\x86", "video/webm"),
        ("ghi-am.mp3", b"ID3\x04\x00\x00", "audio/mpeg"),
        ("ghi-am.ogg", b"OggS\x00\x02", "audio/ogg"),
        ("ghi-am.wav", b"RIFF\x24\x00\x00\x00WAVEfmt ", "audio/wav"),
        ("tai-lieu.zip", zipped({"a.txt": b"x"}), "application/zip"),
    ],
)
def test_media_and_archives_are_accepted_by_signature(name, data, mime):
    assert inspect_content(data, name, "application/octet-stream") == mime


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("gia.mp4", b"not a video"),
        ("gia.gif", b"\x89PNG\r\n\x1a\n"),
        ("gia.webp", b"RIFF\x10\x00\x00\x00WAVE"),
        ("gia.zip", b"PK but broken"),
        ("loi.zip", zipped({"../thoat.txt": b"x"})),
    ],
)
def test_content_must_match_the_extension(name, data):
    with pytest.raises(AppError):
        inspect_content(data, name, "application/octet-stream")


@pytest.mark.parametrize("name", ["anh.svg", "trang.html", "chay.exe", "script.js"])
def test_active_content_stays_refused(name):
    with pytest.raises(AppError) as refused:
        inspect_content(b"<svg/>", name, "text/plain")
    assert refused.value.code == "unsupported_file_type"
