# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""The client speaks the plugin API's wire format; the CLI checks, packs and plays Desktiny's side."""

import hashlib
import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from desktiny_plugin import Client, PluginError, read_delivery, verify
from desktiny_plugin.cli import main, problems

SECRET = "khoa-bi-mat"
EXAMPLE = Path(__file__).resolve().parents[3] / "examples/plugins/tra-cuu-mst/desktiny-plugin.json"


@pytest.fixture
def server():
    seen: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def handle_any(self):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            seen.append({"method": self.command, "path": self.path, "headers": dict(self.headers), "body": body})
            if self.path.startswith("/workspace/v1/plugin/v1/files/"):
                payload, kind = b"%PDF", "application/pdf"
                self.send_response(200)
                self.send_header("Content-Type", kind)
                good = hashlib.sha256(payload).hexdigest()
                self.send_header("X-Content-SHA256", "0" * 64 if "hong" in self.path else good)
                self.end_headers()
                self.wfile.write(payload)
                return
            status = 404 if self.path.endswith("/missing") else 200
            answer = json.dumps({"code": "case_not_found", "detail": "x"} if status == 404 else {"ok": True}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(answer)

        do_GET = do_POST = do_PATCH = handle_any

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}", seen
    httpd.shutdown()


def test_writes_carry_a_key_and_reports_are_signed(server):
    url, seen = server
    client = Client(url, "dkp_x", secret=SECRET)
    client.comment_case("c1", "Đã tra cứu", key="k1")
    assert seen[-1]["headers"]["Idempotency-Key"] == "k1" and json.loads(seen[-1]["body"]) == {"body": "Đã tra cứu"}
    client.write_fields("c1", {"amount": 1})
    assert seen[-1]["method"] == "PATCH" and seen[-1]["headers"]["Idempotency-Key"]
    client.attach("c1", "đơn đã ký.pdf", b"%PDF-1", "application/pdf", node_id="ky", role="result")
    assert b'name="node_id"' in seen[-1]["body"] and "multipart/form-data" in seen[-1]["headers"]["Content-Type"]
    client.complete_call("call-1", output={"so": "12"})
    report = seen[-1]
    assert report["headers"]["Idempotency-Key"] == "call-1"
    verify(SECRET, report["headers"]["X-Desktiny-Timestamp"], report["body"], report["headers"]["X-Desktiny-Signature"])
    client.cases(form_id="f1", limit=50)
    assert seen[-1]["path"].endswith("/cases?form_id=f1&limit=50") and "Idempotency-Key" not in seen[-1]["headers"]
    with pytest.raises(PluginError) as error:
        client.get("/cases/missing")
    assert error.value.status == 404 and error.value.code == "case_not_found"
    with pytest.raises(ValueError):
        Client(url, "dkp_x").call_progress("call-1", "Đang ký")
    assert client.file_content("c1", "f1") == b"%PDF"
    with pytest.raises(PluginError):  # the bytes do not match the SHA-256 sent with them
        client.file_content("c1", "hong")


def test_the_cli_checks_packs_and_starts_a_plugin(tmp_path, capsys):
    assert problems(json.loads(EXAMPLE.read_text(encoding="utf-8"))) == []
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "desktiny-plugin/1", "id": "x", "permissions": ["cases.write"],
                               "nodes": [{"kind": "ky", "endpoint": "//evil", "mode": "async"}]}))  # fmt: skip
    assert main(["check", str(bad)]) == 1
    out = capsys.readouterr().out
    assert "cases.write" in out and "timeout_days" in out and "endpoint" in out
    project = tmp_path / "thu-nghiem"
    assert main(["init", str(project), "--id", "vn.vi-du.thu-nghiem"]) == 0
    assert main(["check", str(project)]) == 0
    target = tmp_path / "goi.zip"
    assert main(["pack", str(project), "-o", str(target)]) == 0
    assert "desktiny-plugin.json" in zipfile.ZipFile(target).namelist()


def test_dev_plays_desktiny_and_signs_what_it_sends(server):
    url, seen = server
    assert main(["dev", "step", "tra_cuu_mst", "--secret", SECRET, "--manifest", str(EXAMPLE), "--url", url,
                 "--config", "ma_so=0101", "--subject", "case:c1"]) == 0  # fmt: skip
    call = read_delivery(SECRET, seen[-1]["headers"], seen[-1]["body"])
    assert seen[-1]["path"] == "/nodes/tra-cuu" and call["config"] == {"ma_so": "0101"}
    assert main(["dev", "event", "case.submitted", "--secret", SECRET, "--url", url, "--subject", "case:c1"]) == 0
    assert read_delivery(SECRET, seen[-1]["headers"], seen[-1]["body"])["subject"] == {"type": "case", "id": "c1"}


def test_check_reads_a_packaged_plugin_folder(tmp_path, capsys):
    example = Path(__file__).resolve().parents[3] / "examples" / "plugins" / "mot-cua-mau"
    assert main(["check", str(example)]) == 0
    folder = tmp_path / "dong-goi"
    (folder / "ui").mkdir(parents=True)
    manifest = {"schema": "desktiny-plugin/2", "id": "vn.vi-du.dong-goi", "name": "Đóng gói", "version": "1.0.0",
                "license": "Apache-2.0", "pack": "pack/", "events": ["case.submitted"],
                "ui": [{"slot": "page", "title": "Trang", "url": "/ui/trang.html"}]}  # fmt: skip
    (folder / "desktiny-plugin.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert main(["check", str(folder)]) == 1
    out = capsys.readouterr().out
    assert "events" in out and "ui/trang.html" in out and "desktiny-pack.json" in out
