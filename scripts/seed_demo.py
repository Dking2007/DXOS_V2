# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Fill a running development deployment with fictional demo content through the public API.

Run `scripts/seed.py` first (organization and users), then:
    python scripts/seed_demo.py --confirm-demo [--base-url http://localhost:8080]
Safe to re-run: every demo item carries a "[Demo]" marker and is skipped when it already exists.
"""

from __future__ import annotations

import argparse
import html
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREDENTIALS = ROOT / "infra/identity/generated/demo-credentials.txt"
TAG = "[Demo]"
API = "/workspace/v1"


def env_base_url() -> str:
    env = ROOT / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("PUBLIC_BASE_URL="):
                return line.split("=", 1)[1].strip()
    return "http://localhost:8080"


def multipart(filename: str, data: bytes, mime: str, folder_id: str | None = None) -> tuple[bytes, str]:
    b = uuid.uuid4().hex
    parts = (
        [(f'--{b}\r\nContent-Disposition: form-data; name="folder_id"\r\n\r\n{folder_id}\r\n').encode()]
        if folder_id
        else []
    )
    head = f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n'
    body = b"".join(parts) + head.encode() + data + f"\r\n--{b}--\r\n".encode()
    return body, f"multipart/form-data; boundary={b}"


def tiny_pdf(text: str) -> bytes:
    """A valid one-page PDF; text must be ASCII without parentheses."""
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = "%PDF-1.4\n", []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


class Session:
    """One logged-in demo user: Keycloak form login, then the BFF cookie + CSRF header."""

    def __init__(self, base: str, username: str, password: str):
        self.base = base.rstrip("/")
        # Keycloak marks cookies Secure even on plain-http dev stacks; browsers allow that on localhost.
        self.jar = http.cookiejar.CookieJar(
            http.cookiejar.DefaultCookiePolicy(secure_protocols=("http", "https"))
        )
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        page = self.opener.open(f"{self.base}{API}/auth/login", timeout=30)
        text = page.read().decode("utf-8")
        form = re.search(r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"', text) or re.search(
            r'<form[^>]*action="([^"]+)"[^>]*id="kc-form-login"', text
        )
        if not form:
            raise SystemExit(f"Keycloak login form not found for {username}")
        action = urllib.parse.urljoin(page.geturl(), html.unescape(form.group(1)))
        data = urllib.parse.urlencode({"username": username, "password": password}).encode()
        self.opener.open(action, data, timeout=30).read()
        self.csrf = ""
        self.me = self.get("/me")
        self.csrf = self.me["csrf_token"]

    def call(self, method: str, path: str, body=None, raw: tuple[bytes, str] | None = None):
        headers = {"X-CSRF-Token": self.csrf, "Idempotency-Key": uuid.uuid4().hex}
        data = None
        if raw:
            data, headers["Content-Type"] = raw
        elif body is not None:
            data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
        req = urllib.request.Request(f"{self.base}{API}{path}", data=data, method=method, headers=headers)
        try:
            with self.opener.open(req, timeout=60) as res:
                payload = res.read()
        except urllib.error.HTTPError as exc:
            raise SystemExit(
                f"{method} {path} -> {exc.code}: {exc.read()[:300].decode('utf-8', 'replace')}"
            ) from None
        return json.loads(payload) if payload else None

    def get(self, path: str):
        return self.call("GET", path)

    def items(self, path: str):
        res = self.get(path)
        return res["items"] if isinstance(res, dict) and "items" in res else res


def credentials(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        name, _, pw = line.partition(": ")
        if name and pw and " " not in name and name != "Login":
            out[name] = pw
    return out


def when(days: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def absent(rows, key: str, value: str) -> bool:
    """Idempotency check: true when no existing row carries `value` under `key`."""
    return all(r.get(key) != value for r in rows)


FORM = f"{TAG} Đề nghị mua sắm văn phòng phẩm"
# (owner, title, amount, priority, due in days, outcome); outcome None = draft, "" = waiting for approval.
CASES = [
    ("staff", "Mua giấy in A4 quý IV", 2400000, "normal", 7, "approve"),
    ("staff", "Thay mực máy in phòng họp", 1800000, "high", -3, ""),
    ("staff", "Mua bàn phím và chuột cho nhân viên mới", 3500000, "normal", 10, ""),
    ("staff", "Sắm tủ hồ sơ cho kho lưu trữ", 12000000, "low", 20, None),
    ("staff", "Mua thiết bị chiếu cho phòng đào tạo", 28000000, "normal", 5, "reject"),
    ("staff", "Đặt in danh thiếp lãnh đạo", 900000, "low", 12, "return"),
    ("staff-b", "Mua cáp mạng và đầu nối", 1500000, "urgent", 2, ""),
    ("staff-b", "Gia hạn bản quyền phần mềm vẽ kỹ thuật", 18500000, "high", -6, ""),
    ("staff-b", "Mua ghế công thái học cho phòng Kỹ thuật", 9600000, "normal", 14, "approve"),
    ("staff-b", "Mua bộ dụng cụ sửa chữa thiết bị", 4200000, "normal", 9, "return"),
]
# (creator, title, assignee user or None for the whole department, priority, due in days, steps taken, description)
TASKS = [
    (
        "manager",
        "Rà soát danh mục tài liệu lưu trữ",
        "staff",
        "normal",
        2,
        [],
        "Đối chiếu danh mục với kho lưu trữ.",
    ),
    (
        "manager",
        "Chuẩn bị báo cáo tuần",
        "staff",
        "urgent",
        -2,
        ["accept", "start"],
        "Tổng hợp số liệu cho họp giao ban.",
    ),
    (
        "manager",
        "Cập nhật lịch trực tuần tới",
        "staff",
        "low",
        -4,
        ["accept", "start", "submit", "complete"],
        "Gửi lịch cho toàn phòng.",
    ),
    ("manager", "Soạn thông báo nghỉ lễ", None, "normal", 4, [], "Giao cho cả phòng Hành chính nhận việc."),
    (
        "director",
        "Duyệt kế hoạch công tác quý IV",
        "manager",
        "high",
        6,
        [],
        "Gửi trình ban giám đốc trước hạn.",
    ),
    (
        "manager-b",
        "Kiểm tra hệ thống mạng nội bộ",
        "staff-b",
        "high",
        7,
        ["accept", "start"],
        "Kiểm tra thiết bị chuyển mạch từng tầng.",
    ),
    (
        "manager-b",
        "Bàn giao thiết bị cho nhân viên mới",
        "staff-b",
        "normal",
        -1,
        ["accept"],
        "Lập biên bản bàn giao.",
    ),
]
# (author, kind, text)
POSTS = [
    (
        "director",
        "official",
        "Thông báo: họp giao ban toàn cơ quan sáng thứ Hai hằng tuần, bắt đầu 8 giờ 30.",
    ),
    (
        "manager",
        "organization",
        "Phòng Hành chính đã cập nhật quy trình đề nghị mua sắm; mọi người gửi hồ sơ trên hệ thống nhé.",
    ),
    (
        "manager-b",
        "department",
        "Phòng Kỹ thuật bảo trì mạng chiều thứ Sáu, mong mọi người lưu việc trước 16 giờ.",
    ),
    ("staff", "organization", "Mẫu báo cáo tuần mới đã có trong kho tài liệu, mọi người dùng thử và góp ý."),
]
CHAT = [
    ("manager", "Chào cả nhóm, tuần này mình ưu tiên báo cáo tuần và lịch trực."),
    ("staff", "Dạ, báo cáo tuần em gửi trước chiều mai."),
    ("staff-b", "Bên Kỹ thuật bảo trì mạng chiều thứ Sáu, nhờ mọi người lưu ý."),
    ("manager", "Cảm ơn, mình đã ghi vào lịch chung."),
]
FILES = [
    ("Kế hoạch quý IV.pdf", "application/pdf", tiny_pdf("Ke hoach quy IV - du lieu demo")),
    ("Biên bản họp giao ban.txt", "text/plain", "Biên bản họp giao ban (dữ liệu minh họa).\n".encode()),
    ("Danh mục thiết bị.txt", "text/plain", "Danh mục thiết bị văn phòng (dữ liệu minh họa).\n".encode()),
]


def ensure_form(mgr: Session) -> str:
    for f in mgr.items("/forms"):
        if f["name"] == FORM:
            return f["id"]
    body = {
        "name": FORM,
        "description": "Biểu mẫu minh họa cho dữ liệu demo.",
        "fields": [
            {"key": "noi_dung", "label": "Nội dung đề nghị", "type": "textarea", "required": True},
            {"key": "so_tien", "label": "Dự toán (đồng)", "type": "number", "required": True},
        ],
        "approval_steps": [{"label": "Lãnh đạo phòng duyệt", "resolver": "department_manager"}],
    }
    return mgr.call("POST", "/forms", body)["id"]


def seed_cases(users: dict[str, Session], form_id: str) -> int:
    made = 0
    for owner, name, amount, priority, due, outcome in CASES:
        s, title = users[owner], f"{TAG} {name}"
        if not absent(s.items("/cases?limit=200"), "title", title):
            continue
        case = s.call(
            "POST",
            "/cases",
            {
                "title": title,
                "form_id": form_id,
                "priority": priority,
                "due_at": when(due),
                "payload": {"noi_dung": name, "so_tien": amount},
            },
        )
        made += 1
        if outcome is None:
            continue
        case = s.call("POST", f"/cases/{case['id']}/submit", {"expected_revision": case["revision"]})
        if outcome == "":
            continue
        manager = users["manager-b" if owner == "staff-b" else "manager"]
        task = wait_for_task(manager, case["id"])
        manager.call(
            "POST",
            f"/approval-tasks/{task['id']}/decisions",
            {
                "expected_revision": task["revision"],
                "decision": outcome,
                "reason": "" if outcome == "approve" else "Ý kiến minh họa của lãnh đạo phòng.",
            },
        )
    return made


def wait_for_task(manager: Session, case_id: str, seconds: int = 30) -> dict:
    """The approval task appears once the worker has processed the submission, which is asynchronous."""
    for _ in range(seconds):
        task = next((t for t in manager.items("/approval-tasks?limit=200") if t["case_id"] == case_id), None)
        if task:
            return task
        time.sleep(1)
    raise SystemExit(f"Không thấy việc duyệt của hồ sơ {case_id} sau {seconds} giây.")


def seed_tasks(users: dict[str, Session]) -> int:
    made = 0
    for creator, name, assignee, priority, due, steps, desc in TASKS:
        s, title = users[creator], f"{TAG} {name}"
        if not absent(s.items("/tasks?limit=200"), "title", title):
            continue
        body = {"title": title, "description": desc, "priority": priority, "due_at": when(due)}
        if assignee:
            body["assignee_id"] = users[assignee].me["id"]
        else:
            body["department_id"] = s.me["department_id"]
        task = s.call("POST", "/tasks", body)
        made += 1
        for action in steps:
            actor = s if action == "complete" else users[assignee]
            task = actor.call(
                "POST",
                f"/tasks/{task['id']}/transitions",
                {
                    "expected_revision": task["revision"],
                    "action": action,
                    "result": "Hoàn thành đúng yêu cầu." if action == "submit" else None,
                },
            )
    return made


def seed_posts(users: dict[str, Session]) -> int:
    made = 0
    for author, kind, text in POSTS:
        s, body = users[author], f"{TAG} {text}"
        if not absent(s.items("/posts?limit=100"), "body", body):
            continue
        payload = {
            "body": body,
            "audience": "department" if kind == "department" else "organization",
            "official": kind == "official",
        }
        if kind == "department":
            payload["department_id"] = s.me["department_id"]
        s.call("POST", "/posts", payload)
        made += 1
    return made


def seed_chat(users: dict[str, Session]) -> int:
    mgr, made = users["manager"], 0
    title = f"{TAG} Điều phối công việc tuần"
    conv = next((c for c in mgr.items("/conversations?limit=100") if c.get("title") == title), None)
    if not conv:
        conv = mgr.call(
            "POST",
            "/conversations",
            {
                "kind": "group",
                "title": title,
                "member_ids": [users[n].me["id"] for n in ("staff", "staff-b")],
            },
        )
        made = 1
    sent = {m.get("client_message_id") for m in mgr.items(f"/conversations/{conv['id']}/messages?limit=100")}
    for i, (author, text) in enumerate(CHAT):
        key = f"demo-seed-{i}"
        if key not in sent:
            users[author].call(
                "POST", f"/conversations/{conv['id']}/messages", {"client_message_id": key, "body": text}
            )
            made += 1
    return made


def seed_drive(users: dict[str, Session]) -> int:
    s, made = users["staff"], 0
    name = f"{TAG} Hồ sơ năm 2026"
    folder = next((f for f in s.items("/drive/folders") if f["name"] == name), None)
    if not folder:
        folder, made = s.call("POST", "/drive/folders", {"name": name}), 1
    existing = s.items(f"/drive/files?folder_id={urllib.parse.quote(folder['id'])}&limit=200")
    for fname, mime, data in FILES:
        if absent(existing, "name", f"{TAG} {fname}"):
            s.call("POST", "/drive/files", raw=multipart(f"{TAG} {fname}", data, mime, folder["id"]))
            made += 1
    return made


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base-url", default=env_base_url())
    parser.add_argument(
        "--credentials", type=Path, default=CREDENTIALS, help="demo-credentials.txt from bootstrap"
    )
    parser.add_argument(
        "--confirm-demo", action="store_true", help="Confirm the target is a development/demo deployment"
    )
    args = parser.parse_args()
    if not args.confirm_demo:
        parser.error("Pass --confirm-demo; this command creates synthetic demo data.")
    if not args.credentials.is_file():
        parser.error("Run python scripts/bootstrap.py and scripts/seed.py first.")
    pw = credentials(args.credentials)
    users = {
        n: Session(args.base_url, n, pw[n]) for n in ("director", "manager", "staff", "manager-b", "staff-b")
    }
    form_id = ensure_form(users["manager"])
    for label, made in (
        ("cases", seed_cases(users, form_id)),
        ("tasks", seed_tasks(users)),
        ("posts", seed_posts(users)),
        ("chat", seed_chat(users)),
        ("drive", seed_drive(users)),
    ):
        print(f"{label}: {made} created")
    return 0


if __name__ == "__main__":
    sys.exit(main())
