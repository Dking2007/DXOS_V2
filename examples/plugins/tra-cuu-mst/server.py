# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Example connected plugin: look up a company by tax code (simulated data).

Run:  DESKTINY_SECRET=… DESKTINY_TOKEN=… DESKTINY_URL=http://localhost:8080 python server.py
It answers on http://localhost:9100 (PORT to change):

* POST /events          signed event from Desktiny; on case.submitted, reads the dossier with the token;
* POST /nodes/tra-cuu   signed flow-step call; returns {branch, output} for later steps;
* GET  /ui/case-card.html and /sdk/desktiny-plugin-sdk.js   the frame shown on a dossier;
* GET  /api/lookup?ma_so=…   the frame's own lookup (open CORS, no Desktiny data).
"""

from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from desktiny_plugin import Client, PluginError, SignatureError, read_delivery

HERE = Path(__file__).resolve().parent
SDK = HERE.parents[2] / "packages" / "plugin-sdk" / "desktiny-plugin-sdk.js"
# Simulated register: tax code → (company name, status). Not real companies.
REGISTER = {
    "0101234567": ("Công ty TNHH Mẫu Một", "Đang hoạt động"),
    "0309876543": ("Công ty Cổ phần Ví Dụ", "Tạm ngừng kinh doanh"),
}
log = logging.getLogger("tra-cuu-mst")


def lookup(tax_code: str) -> dict:
    code = "".join(ch for ch in str(tax_code) if ch.isdigit())
    if len(code) not in (10, 13):
        return {"found": False, "reason": "Mã số thuế cần 10 hoặc 13 chữ số."}
    name, status = REGISTER.get(code[:10], (None, None))
    if not name:
        return {"found": False, "reason": "Không có trong dữ liệu giả lập."}
    return {"found": True, "ma_so": code, "ten_dn": name, "trang_thai": status}


def handle_step(body: dict) -> dict:
    """The `tra_cuu_mst` step: success with the company's details, error when it is not found."""
    result = lookup((body.get("config") or {}).get("ma_so", ""))
    if not result["found"]:
        return {"branch": "error", "output": {"ten_dn": "", "trang_thai": ""}, "message": result["reason"]}
    return {"branch": "success", "output": {"ten_dn": result["ten_dn"], "trang_thai": result["trang_thai"]}}


def handle_event(body: dict, client: Client | None) -> str:
    """A delivered event; with a token, read the dossier it is about (ids only arrive in the event)."""
    subject = body.get("subject") or {}
    if body.get("type") != "case.submitted" or subject.get("type") != "case" or not client:
        return "ignored"
    try:
        dossier = client.case(subject["id"])
    except PluginError as exc:
        log.warning("cannot read dossier %s: %s", subject["id"], exc)
        return "unreadable"
    log.info("dossier submitted: %s %s", dossier["code"], dossier["title"])
    return "read"


class Handler(BaseHTTPRequestHandler):
    secret = os.environ.get("DESKTINY_SECRET", "")
    client = (
        Client(os.environ["DESKTINY_URL"], os.environ["DESKTINY_TOKEN"])
        if os.environ.get("DESKTINY_URL") and os.environ.get("DESKTINY_TOKEN")
        else None
    )

    def reply(self, status: int, body: bytes = b"", kind: str = "application/json", cors: bool = False):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if cors:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802 (http.server naming)
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        try:
            data = read_delivery(self.secret, self.headers, body)
        except (SignatureError, ValueError):
            self.reply(401, b'{"error": "bad signature"}')
            return
        path = urlsplit(self.path).path
        if path == "/events":
            self.reply(202, json.dumps({"result": handle_event(data, self.client)}).encode())
        elif path == "/nodes/tra-cuu":
            self.reply(200, json.dumps(handle_step(data), ensure_ascii=False).encode())
        else:
            self.reply(404)

    def do_GET(self):  # noqa: N802
        parts = urlsplit(self.path)
        if parts.path == "/api/lookup":
            code = parse_qs(parts.query).get("ma_so", [""])[0]
            self.reply(200, json.dumps(lookup(code), ensure_ascii=False).encode(), cors=True)
        elif parts.path == "/ui/case-card.html":
            self.reply(200, (HERE / "ui" / "case-card.html").read_bytes(), "text/html; charset=utf-8")
        elif parts.path == "/sdk/desktiny-plugin-sdk.js":
            self.reply(200, SDK.read_bytes(), "text/javascript; charset=utf-8")
        else:
            self.reply(404)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("PORT", "9100"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()  # noqa: S104 (example server)
