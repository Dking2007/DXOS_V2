# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("seed_demo", ROOT / "scripts/seed_demo.py")
seed_demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed_demo)


def test_absent_detects_existing_demo_items():
    rows = [{"title": "[Demo] A"}, {"title": "khác"}]
    assert not seed_demo.absent(rows, "title", "[Demo] A")
    assert seed_demo.absent(rows, "title", "[Demo] B")


def test_multipart_carries_folder_and_file():
    body, ctype = seed_demo.multipart("a.txt", b"xyz", "text/plain", "f1")
    boundary = ctype.split("boundary=")[1].encode()
    assert body.count(b"--" + boundary) == 3 and b'name="folder_id"' in body and b"xyz" in body


def test_tiny_pdf_is_wellformed():
    pdf = seed_demo.tiny_pdf("Xin chao")
    assert pdf.startswith(b"%PDF-") and pdf.rstrip().endswith(b"%%EOF")


def test_demo_data_is_unique_and_covers_states():
    titles = [c[1] for c in seed_demo.CASES] + [t[1] for t in seed_demo.TASKS]
    assert len(titles) == len(set(titles))
    assert {c[5] for c in seed_demo.CASES} == {None, "", "approve", "return", "reject"}
    assert any(c[4] < 0 for c in seed_demo.CASES)
