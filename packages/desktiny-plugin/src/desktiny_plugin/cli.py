# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""`desktiny-plugin`: start, check, pack and try out a connected plugin without a Desktiny at hand.

    desktiny-plugin init thu-nghiem --id vn.co-quan.thu-nghiem --name "Thử nghiệm"
    desktiny-plugin check thu-nghiem/desktiny-plugin.json
    desktiny-plugin pack thu-nghiem -o thu-nghiem.zip
    desktiny-plugin dev event case.submitted --subject case:HS1 --secret <khoá> --url http://localhost:9100
    desktiny-plugin dev step tra_cuu_mst --config ma_so=0101 --secret <khoá> --manifest thu-nghiem/desktiny-plugin.json

`check` repeats the rules Desktiny applies when the manifest is uploaded (the server stays the judge);
given the plugin's folder it also checks a packaged plugin's pages and its sector pack are there.
`dev` plays Desktiny's side: it signs and sends an event, a step call or an assistant tool call.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

from . import sign

API_VERSION = 2
SCOPES = {
    "cases.read", "tasks.read", "people.read", "cases.comment", "cases.fields.write", "tasks.write",
    "notifications.send", "files.read", "cases.attach", "cases.list", "departments.read", "people.list",
}  # fmt: skip
EVENTS = {
    "task.created", "task.assigned", "task.submitted", "task.completed", "task.returned", "task.blocked",
    "case.submitted", "case.approved", "case.rejected", "case.needs_revision", "case.step_entered",
    "case.file_added", "case.overdue", "case.closed", "task.overdue", "post.created",
}  # fmt: skip
SLOTS = {"case.side", "case.tab", "case.action", "task.side", "task.action", "home.widget", "page", "admin.page"}
FRAME_PERMISSIONS = {"geolocation", "camera", "clipboard-write"}
EMIT_KINDS = {"string", "number", "date", "person", "case"}
PATH = re.compile(r"^/([A-Za-z0-9._~!$&'()*+,;=:@%-][A-Za-z0-9._~!$&'()*+,;=:@%/-]{0,198})?$")
KEY = re.compile(r"^[a-z][a-z0-9_]{0,39}$")


PACKAGED = "desktiny-plugin/2"


def problems(manifest: dict, folder: Path | None = None) -> list[str]:
    """What Desktiny would refuse in this manifest (and, given the folder, in the package); empty if none."""
    found: list[str] = []

    def need(ok: bool, message: str):
        if not ok:
            found.append(message)

    schema = manifest.get("schema")
    need(schema in {"desktiny-plugin/1", PACKAGED}, f"`schema` phải là desktiny-plugin/1 hoặc {PACKAGED}.")
    packaged = schema == PACKAGED and not manifest.get("base_url")
    need(bool(re.fullmatch(r"[a-z][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)+", str(manifest.get("id", "")))),
         "`id` dạng tên miền đảo ngược, ví dụ vn.co-quan.ten-plugin.")  # fmt: skip
    need(bool(re.fullmatch(r"\d+\.\d+\.\d+", str(manifest.get("version", "")))), "`version` dạng 1.0.0.")
    for key in ("name", "license") if packaged else ("name", "license", "base_url"):
        need(bool(manifest.get(key)), f"Thiếu `{key}`.")
    if packaged:
        server = [key for key in ("nodes", "events", "emits", "assistant_tools", "health_endpoint") if manifest.get(key)]
        server += ["settings_schema"] if (manifest.get("settings_schema") or {}).get("properties") else []
        need(not server, "Plugin đóng gói chưa có máy chủ nên chưa dùng được: " + ", ".join(server) + ".")
        need(bool(manifest.get("ui") or manifest.get("pack")), "Plugin đóng gói cần `ui` hoặc `pack`.")
    else:
        need(str(manifest.get("base_url", "")).startswith(("http://", "https://")), "`base_url` phải là http(s).")
    need(not manifest.get("pack") or schema == PACKAGED, f"`pack` cần `schema` là {PACKAGED}.")
    required = str((manifest.get("requires") or {}).get("desktiny", ">=1"))
    need(bool(re.fullmatch(r">=\d{1,3}", required)) and int(required[2:]) <= API_VERSION,
         f"`requires.desktiny` không hợp lệ hoặc cần API mới hơn bản {API_VERSION}.")  # fmt: skip
    permissions = manifest.get("permissions", [])
    need(not set(permissions) - SCOPES, "Quyền không có: " + ", ".join(sorted(set(permissions) - SCOPES)))
    need(not set(manifest.get("events", [])) - EVENTS, "Sự kiện không có trong danh sách của Desktiny.")
    fields = (manifest.get("writes") or {}).get("fields", [])
    need(bool(fields) == ("cases.fields.write" in permissions), "`writes.fields` đi cùng quyền cases.fields.write.")
    need(PATH.match(manifest.get("events_endpoint", "/events")) is not None, "`events_endpoint` phải là đường dẫn /…")
    if manifest.get("health_endpoint") is not None:
        need(PATH.match(manifest["health_endpoint"]) is not None, "`health_endpoint` phải là đường dẫn /…")
    kinds = [node.get("kind") for node in manifest.get("nodes", [])]
    need(len(set(kinds)) == len(kinds), "Mỗi bước quy trình cần `kind` khác nhau.")
    for node in manifest.get("nodes", []):
        need(bool(re.fullmatch(r"[a-z][a-z0-9_]{1,39}", str(node.get("kind", "")))), f"Bước `{node.get('kind')}`: kind.")
        need(PATH.match(str(node.get("endpoint", ""))) is not None, f"Bước `{node.get('kind')}`: endpoint phải là /…")
        need(node.get("mode", "sync") in {"sync", "async"}, f"Bước `{node.get('kind')}`: mode là sync hoặc async.")
        if node.get("mode") == "async":
            need(1 <= int(node.get("timeout_days") or 0) <= 90, f"Bước chạy lâu `{node.get('kind')}` cần timeout_days 1–90.")
        schema = node.get("config_schema") or {}
        need(not any(f.get("secret") for f in (schema.get("properties") or {}).values()),
             f"Bước `{node.get('kind')}`: ô secret chỉ dùng trong settings_schema.")  # fmt: skip
    for ui in manifest.get("ui", []):
        need(ui.get("slot") in SLOTS, f"Khung `{ui.get('title')}`: vị trí chỉ gồm {', '.join(sorted(SLOTS))}.")
        need(PATH.match(str(ui.get("url", ""))) is not None, f"Khung `{ui.get('title')}`: url phải là /… trên base_url.")
        if packaged and folder is not None:
            page = folder / str(ui.get("url", "")).lstrip("/")
            need(page.is_file() and page.suffix.lower() in {".html", ".htm"},
                 f"Khung `{ui.get('title')}`: gói không có trang HTML {page.relative_to(folder).as_posix()}.")  # fmt: skip
    if manifest.get("pack") and folder is not None:
        need((folder / str(manifest["pack"]) / "desktiny-pack.json").is_file(),
             f"Thư mục `pack` ({manifest['pack']}) thiếu desktiny-pack.json.")  # fmt: skip
    need(not set(manifest.get("frame_permissions", [])) - FRAME_PERMISSIONS, "frame_permissions chỉ gồm "
         + ", ".join(sorted(FRAME_PERMISSIONS)) + ".")  # fmt: skip
    types = [event.get("type") for event in manifest.get("emits", [])]
    need(len(set(types)) == len(types), "Mỗi sự kiện trong `emits` cần `type` khác nhau.")
    for event in manifest.get("emits", []):
        bad = {k for k, v in (event.get("fields") or {}).items() if v not in EMIT_KINDS or not KEY.match(k)}
        need(not bad, f"Sự kiện `{event.get('type')}`: dữ liệu không hợp lệ: {', '.join(sorted(bad))}.")
    names = [tool.get("name") for tool in manifest.get("assistant_tools", [])]
    need(len(set(names)) == len(names), "Mỗi công cụ trợ lý cần `name` khác nhau.")
    for tool in manifest.get("assistant_tools", []):
        need(PATH.match(str(tool.get("endpoint", ""))) is not None, f"Công cụ `{tool.get('name')}`: endpoint phải là /…")
        need(len(str(tool.get("description", ""))) >= 10, f"Công cụ `{tool.get('name')}`: mô tả ít nhất 10 ký tự.")
    return found


def read(path: Path) -> dict:
    target = path / "desktiny-plugin.json" if path.is_dir() else path
    return json.loads(target.read_text(encoding="utf-8"))


def cmd_check(args) -> int:
    path = Path(args.path)
    issues = problems(read(path), path if path.is_dir() else None)
    for issue in issues:
        print("✗", issue)
    if not issues:
        print("✓ Manifest hợp lệ theo các quy tắc của Desktiny (máy chủ vẫn kiểm lại khi cài).")
    return 1 if issues else 0


def cmd_pack(args) -> int:
    folder = Path(args.path)
    if cmd_check(argparse.Namespace(path=str(folder))):
        return 1
    output = Path(args.output or f"{read(folder)['id']}.zip")
    skip = {"__pycache__", ".git", ".venv", "node_modules"}
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(folder.rglob("*")):
            relative = file.relative_to(folder)
            if file.is_file() and not skip & set(relative.parts) and file.resolve() != output.resolve():
                archive.write(file, relative.as_posix())
    print(f"✓ Đã đóng gói {output}")
    return 0


SERVER = '''# Máy chủ plugin tối thiểu: nhận sự kiện và bước quy trình đã ký, trả lời bằng JSON.
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from desktiny_plugin import SignatureError, read_delivery

SECRET = os.environ.get("DESKTINY_SECRET", "")


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            data = read_delivery(SECRET, self.headers, body)
        except SignatureError:
            return self.answer(401, {{"error": "signature"}})
        if self.path == "/events":
            return self.answer(202, {{}})
        if self.path == "/nodes/vi-du":
            return self.answer(200, {{"branch": "success", "output": {{"ket_qua": "Đã xử lý " + str(data["config"])}}}})
        return self.answer(404, {{}})

    def do_GET(self):
        self.answer(200, {{"ok": True}}) if self.path == "/health" else self.answer(404, {{}})

    def answer(self, status, body):
        payload = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", "{port}"))), Handler).serve_forever()
'''


def cmd_init(args) -> int:
    folder = Path(args.path)
    if folder.exists() and any(folder.iterdir()):
        print(f"✗ Thư mục {folder} đã có nội dung.")
        return 1
    plugin_id = args.id or f"vn.vi-du.{re.sub(r'[^a-z0-9-]+', '-', folder.name.lower()).strip('-') or 'plugin'}"
    manifest = {
        "schema": "desktiny-plugin/1",
        "id": plugin_id,
        "name": args.name or folder.name,
        "version": "0.1.0",
        "license": "Apache-2.0",
        "description": "",
        "base_url": f"http://localhost:{args.port}",
        "requires": {"desktiny": f">={API_VERSION}"},
        "permissions": ["cases.read"],
        "events": ["case.submitted"],
        "health_endpoint": "/health",
        "nodes": [{"kind": "vi_du", "title": "Bước ví dụ", "endpoint": "/nodes/vi-du",
                   "config_schema": {"type": "object", "properties": {"noi_dung": {"type": "string", "title": "Nội dung"}}},
                   "outputs": {"ket_qua": "Kết quả"}}],
        "ui": [{"slot": "case.side", "title": "Ví dụ", "url": "/ui/index.html", "height": 200}],
    }  # fmt: skip
    (folder / "ui").mkdir(parents=True, exist_ok=True)
    (folder / "desktiny-plugin.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8")
    (folder / "server.py").write_text(SERVER.format(port=args.port), "utf-8")
    (folder / "ui" / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><body><p id=out>Đang tải…</p><script type=module>\n"
        "import { connect } from './desktiny-plugin-sdk.js'\n"
        "const desktiny = connect()\nconst context = await desktiny.context\n"
        "document.getElementById('out').textContent = 'Hồ sơ ' + (context.record.case_id || '—')\n</script>\n",
        "utf-8",
    )
    print(f"✓ Đã tạo {folder}: desktiny-plugin.json, server.py, ui/index.html")
    print("  Chép packages/plugin-sdk/desktiny-plugin-sdk.js vào ui/ rồi chạy: DESKTINY_SECRET=… python server.py")
    return 0


def post(url: str, secret: str, body: dict, headers: dict) -> int:
    raw = json.dumps(body, ensure_ascii=False).encode()
    stamp = str(int(time.time()))
    request = urllib.request.Request(url, data=raw, method="POST", headers={
        "Content-Type": "application/json", "X-Desktiny-Timestamp": stamp,
        "X-Desktiny-Signature": sign(secret, stamp, raw), **headers})  # fmt: skip
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310 (the developer's own URL)
            status, content = response.status, response.read()
    except urllib.error.HTTPError as exc:
        status, content = exc.code, exc.read()
    except urllib.error.URLError as exc:
        print(f"✗ Không gọi được {url}: {exc.reason}")
        return 2
    print(f"→ {url}\n← {status}\n{content.decode('utf-8', 'replace')}")
    return 0 if status < 400 else 1


def pairs(values: list[str]) -> dict:
    result = {}
    for item in values or []:
        key, _, value = item.partition("=")
        try:
            result[key] = json.loads(value)
        except ValueError:
            result[key] = value
    return result


def cmd_dev(args) -> int:
    manifest = read(Path(args.manifest)) if args.manifest else {}
    base = (args.url or manifest.get("base_url", "")).rstrip("/")
    if not base:
        print("✗ Cần --url hoặc --manifest để biết địa chỉ máy chủ plugin.")
        return 2
    delivery = uuid.uuid4().hex
    if args.what == "event":
        kind, _, subject_id = (args.subject or "").partition(":")
        body = {"delivery_id": delivery, "event_id": uuid.uuid4().hex, "type": args.name,
                "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "subject": {"type": kind, "id": subject_id} if subject_id else None}  # fmt: skip
        path = manifest.get("events_endpoint", "/events")
        headers = {"X-Desktiny-Event": args.name, "X-Desktiny-Delivery": delivery, "Idempotency-Key": delivery}
    elif args.what == "step":
        node = next((n for n in manifest.get("nodes", []) if n.get("kind") == args.name), {"endpoint": args.path})
        kind, _, subject_id = (args.subject or "").partition(":")
        body = {"call_id": delivery, "run_id": "dev-run", "node_id": "dev-node", "step": args.name,
                "config": pairs(args.config), "subject": {"type": kind, "id": subject_id} if subject_id else None}  # fmt: skip
        path = node.get("endpoint") or args.path
        headers = {"X-Desktiny-Step": args.name, "X-Desktiny-Delivery": delivery, "Idempotency-Key": f"dev-run:{delivery}"}
    else:
        tool = next((t for t in manifest.get("assistant_tools", []) if t.get("name") == args.name), {"endpoint": args.path})
        body = {"call_id": delivery, "tool": args.name, "arguments": pairs(args.config),
                "user": {"id": "dev-user", "display_name": "Người thử"}, "token": "", "api_base": ""}  # fmt: skip
        path = tool.get("endpoint") or args.path
        headers = {"X-Desktiny-Tool": args.name, "X-Desktiny-Delivery": delivery}
    if not path:
        print("✗ Không biết đường dẫn: thêm --manifest hoặc --path.")
        return 2
    return post(base + path, args.secret, body, headers)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="desktiny-plugin", description="Công cụ cho người viết plugin Desktiny.")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Tạo khung dự án plugin.")
    init.add_argument("path")
    init.add_argument("--id")
    init.add_argument("--name")
    init.add_argument("--port", type=int, default=9100)
    init.set_defaults(run=cmd_init)
    check = commands.add_parser("check", help="Kiểm manifest theo quy tắc của Desktiny.")
    check.add_argument("path", nargs="?", default=".")
    check.set_defaults(run=cmd_check)
    pack = commands.add_parser("pack", help="Kiểm rồi đóng gói thư mục plugin thành .zip.")
    pack.add_argument("path", nargs="?", default=".")
    pack.add_argument("-o", "--output")
    pack.set_defaults(run=cmd_pack)
    dev = commands.add_parser("dev", help="Đóng vai Desktiny: gửi sự kiện, gọi bước hoặc công cụ, có ký.")
    dev.add_argument("what", choices=["event", "step", "tool"])
    dev.add_argument("name", help="Loại sự kiện, kind của bước hoặc tên công cụ.")
    dev.add_argument("--secret", required=True, help="Khoá ký (như Desktiny cấp khi duyệt).")
    dev.add_argument("--manifest", help="desktiny-plugin.json để lấy base_url và đường dẫn.")
    dev.add_argument("--url", help="Địa chỉ máy chủ plugin, thay cho base_url của manifest.")
    dev.add_argument("--path", help="Đường dẫn khi không có trong manifest.")
    dev.add_argument("--subject", help="Bản ghi liên quan, dạng case:<mã> hoặc task:<mã>.")
    dev.add_argument("--config", action="append", help="Giá trị cấu hình hoặc tham số, dạng khoa=gia_tri.")
    dev.set_defaults(run=cmd_dev)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
