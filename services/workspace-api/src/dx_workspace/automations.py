# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Business automation flows drawn as a node graph: trigger → conditions → actions.

This is the visual configurator Workspace offers business users. Flows run inside the
Workspace worker against Workspace events; it is not the generic Core workflow engine.

A flow is a DAG of nodes and edges. The trigger node names the event; an `if` node routes
to its `true` or `false` branch; action nodes run and pass on to whatever they connect to;
a `wait` node resumes its successors later through the outbox. Each run pins the graph it
started with, so editing a flow never changes a run already under way.

The same canvas draws *process flows* (kind "process"): the route a form's dossiers follow
once submitted. They add step nodes that wait for people (approval, opinions, a task to be
done) and nodes that settle the dossier. Their live execution is in `processes`; this
module validates them and dry-runs them like any other flow.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any, Literal
from urllib.parse import urljoin, urlsplit

import httpx
from dx_flowkit import FlowError, compare
from dx_platform.auth import Actor
from dx_platform.errors import AppError
from dx_platform.security import SecretBox
from fastapi import APIRouter, Depends, Query
from pydantic import Field, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import ai_core
from . import models as m
from . import schemas as s
from .feed import can_see as can_see_post
from .feed import visibility_filter as post_visibility
from .policies import case_filter, current_user, get_case, require
from .services import audit, cas, case_event, enqueue, notify, page, serial
from .tasks import TaskCreate, TaskSource, create_task, event_data, get_task, log, manages, visible
from .text import matches

TRIGGERS = {
    "task.created": "Công việc được tạo",
    "task.assigned": "Công việc được giao lại",
    "task.submitted": "Công việc được nộp kết quả",
    "task.completed": "Công việc được nghiệm thu",
    "task.returned": "Công việc bị trả lại",
    "task.blocked": "Công việc bị vướng mắc",
    "case.submitted": "Hồ sơ được trình",
    "case.approved": "Hồ sơ được duyệt",
    "case.rejected": "Hồ sơ bị từ chối",
    "case.needs_revision": "Hồ sơ bị trả lại",
    "post.created": "Bài viết mới trên bảng tin",
}
TASK_FIELDS = {
    "title": "Tiêu đề",
    "status": "Trạng thái",
    "priority": "Mức ưu tiên",
    "labels": "Nhãn",
    "department_id": "Đơn vị",
    "assignee_id": "Người phụ trách",
    "creator_id": "Người giao",
}
CASE_FIELDS = {
    "title": "Tên hồ sơ",
    "status": "Trạng thái",
    "priority": "Mức ưu tiên",
    "department_id": "Đơn vị",
    "owner_id": "Người tạo",
    "form_id": "Mẫu hồ sơ",
}
POST_FIELDS = {
    "audience": "Phạm vi",
    "official": "Thông báo chính thức",
    "department_id": "Phòng ban",
    "author_id": "Người đăng",
}
SAMPLES = {
    "task": {
        "title": "Tổng hợp báo cáo tháng",
        "status": "submitted",
        "priority": "urgent",
        "labels": ["báo cáo"],
    },
    "case": {"title": "Đề xuất mua sắm thiết bị", "status": "approved", "priority": "high"},
    "post": {"audience": "organization", "official": True},
}
PROCESS_FIELDS = {
    "title": "Tên hồ sơ",
    "priority": "Mức ưu tiên",
    "department_id": "Đơn vị",
    "owner_id": "Người tạo",
    "file_count": "Số tài liệu đính kèm",
    "file_names": "Tên tài liệu đính kèm",
    "submission_no": "Lần trình",
}
PROCESS_SAMPLE = {
    "title": "Đề xuất mua sắm thiết bị",
    "status": "processing",
    "priority": "high",
    "file_count": 1,
    "file_names": ["To-trinh.docx"],
    "submission_no": 1,
    "form": {},
    # Dry runs only: the decision each step takes, by node id; approval is assumed otherwise.
    "decisions": {},
}
KINDS = ("automation", "process")
# Steps that only make sense inside a dossier's process.
PROCESS_NODES = {"approval", "consult", "assign_task", "request_info", "finish"}
NODE_TYPES = {"trigger", "if", "notify", "create_task", "webhook", "wait", "ai", *PROCESS_NODES}
# Nodes that leave through named branches, and the branches each one has.
BRANCHES = {
    "if": {"true", "false"},
    "approval": {"approve", "return", "reject"},
    "consult": {"approve", "reject"},
    "assign_task": {"completed", "cancelled"},
}
BRANCH_LABELS = {
    "true": "Đúng",
    "false": "Sai",
    "approve": "Duyệt",
    "return": "Trả lại",
    "reject": "Từ chối",
    "completed": "Hoàn thành",
    "cancelled": "Bị hủy",
}
# An approval branch left unconnected settles the dossier the obvious way, so a one-step
# process is just trigger → approval.
IMPLICIT_OUTCOME = {"approve": "approved", "return": "needs_revision", "reject": "rejected"}
TERMINAL = {"request_info", "finish"}
OUTCOMES = {"approved": "Đã duyệt", "rejected": "Từ chối", "needs_revision": "Yêu cầu bổ sung"}
ROLE_RECIPIENTS = {"assignee", "creator", "owner", "author", "department_manager"}
MAX_CHAIN = 3
MAX_NODES = 40
OPERATORS = Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains", "in", "empty", "not_empty"]


def trigger_family(event: str) -> str:
    return event.split(".", 1)[0]


def fields_for(event: str) -> dict:
    return {"task": TASK_FIELDS, "case": CASE_FIELDS, "post": POST_FIELDS}.get(trigger_family(event), {})


class Condition(s.Input):
    # `form.<key>` reads a field of the submitted form in process flows.
    field: str = Field(pattern=r"^[a-z_]{1,40}(\.[A-Za-z][A-Za-z0-9_]{0,63})?$")
    operator: OPERATORS
    value: Any = None


class TriggerData(s.Input):
    event: str = ""
    # Process flows: the form whose dossiers follow this process.
    form_id: str | None = None


class IfData(s.Input):
    mode: Literal["all", "any"] = "all"
    conditions: list[Condition] = Field(default_factory=list, max_length=10)


class NotifyData(s.Input):
    recipients: list[str] = Field(default_factory=list, max_length=20)
    title: str = Field(default="", max_length=250)


class CreateTaskData(s.Input):
    title: str = Field(default="", max_length=250)
    description: str = Field(default="", max_length=5000)
    assignee_id: str | None = None
    department_id: str | None = None
    due_in_days: int | None = Field(default=None, ge=0, le=365)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"


class WebhookData(s.Input):
    connection_id: str | None = None
    path: str = Field(default="", max_length=300)


class WaitData(s.Input):
    minutes: int = Field(default=60, ge=1, le=60 * 24 * 7)


class AiData(s.Input):
    """Ask AI to put the event in one of a few groups; a later condition branches on the answer."""

    question: str = Field(default="", max_length=500)
    choices: list[str] = Field(default_factory=list, max_length=8)
    # The answer is stored under this name, so an "if" node can test e.g. ai_label eq "Gấp".
    output: str = Field(default="ai_label", pattern=r"^[a-z_]{1,40}$")


class ApprovalData(s.Input):
    """One person decides: approve, return for changes or reject."""

    resolver: Literal["department_manager", "user"] = "department_manager"
    user_id: str | None = None
    allow_return: bool = True
    allow_reject: bool = True
    due_in_days: int | None = Field(default=None, ge=0, le=365)
    instructions: str = Field(default="", max_length=1000)


class ConsultData(s.Input):
    """Several people give their opinion at once; the flow goes on by how they answered."""

    user_ids: list[str] = Field(default_factory=list, max_length=10)
    include_department_manager: bool = False
    # "all": wait for everyone and agree only if all agree; "any": one agreement is enough.
    mode: Literal["all", "any"] = "all"
    due_in_days: int | None = Field(default=None, ge=0, le=365)
    instructions: str = Field(default="", max_length=1000)


class AssignTaskData(CreateTaskData):
    """Hand work to someone and wait until it is accepted as done (or cancelled)."""


class RequestInfoData(s.Input):
    message: str = Field(default="", max_length=1000)


class FinishData(s.Input):
    result: Literal["approved", "rejected"] = "approved"
    message: str = Field(default="", max_length=1000)


DATA_MODELS = {
    "approval": ApprovalData,
    "consult": ConsultData,
    "assign_task": AssignTaskData,
    "request_info": RequestInfoData,
    "finish": FinishData,
    "trigger": TriggerData,
    "if": IfData,
    "notify": NotifyData,
    "create_task": CreateTaskData,
    "webhook": WebhookData,
    "wait": WaitData,
    "ai": AiData,
}


class Position(s.Input):
    x: float = 0
    y: float = 0


class Node(s.Input):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    type: str
    label: str = Field(default="", max_length=120)
    position: Position = Field(default_factory=Position)
    data: dict = Field(default_factory=dict)


class Edge(s.Input):
    id: str = Field(min_length=1, max_length=90)
    source: str
    target: str
    branch: Literal["true", "false", "approve", "return", "reject", "completed", "cancelled"] | None = None


class Graph(s.Input):
    nodes: list[Node] = Field(default_factory=list, max_length=MAX_NODES)
    edges: list[Edge] = Field(default_factory=list, max_length=MAX_NODES * 3)


class RuleInput(s.Input):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    graph: Graph
    scope: Literal["all", "attached"] = "all"
    # Fixed at creation; an update keeps the kind the flow already has.
    kind: Literal["automation", "process"] = "automation"


class RulePatch(RuleInput, s.Revision):
    pass


class RuleToggle(s.Revision):
    enabled: bool


class RuleTest(s.Input):
    data: dict = Field(default_factory=dict)


class ManualRun(s.Input):
    ref_id: str = Field(min_length=1, max_length=36)


class GraphTest(s.Input):
    graph: Graph
    data: dict = Field(default_factory=dict)
    kind: Literal["automation", "process"] = "automation"


class ConnectionInput(s.Input):
    name: str = Field(min_length=1, max_length=200)
    base_url: str = Field(min_length=8, max_length=500)
    auth_type: Literal["none", "bearer", "header"] = "none"
    secret: str | None = Field(default=None, max_length=2000)
    secret_header: str = Field(default="Authorization", pattern=r"^[A-Za-z0-9-]{1,60}$")
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=10, ge=1, le=60)


def allowed_hosts(settings) -> set[str]:
    return {h.strip().lower() for h in settings.automation_allowed_hosts.split(",") if h.strip()}


def check_url(settings, url: str):
    parts = urlsplit(url)
    if parts.scheme not in {"https", "http"} or not parts.hostname:
        raise AppError(422, "connection_url_invalid", "Địa chỉ kết nối phải là URL http(s) hợp lệ.")
    if parts.hostname.lower() not in allowed_hosts(settings):
        raise AppError(
            422,
            "connection_host_denied",
            "Máy chủ đích chưa nằm trong AUTOMATION_ALLOWED_HOSTS của triển khai.",
        )


def value_of(data: dict, field: str):
    """`key` or `form.key`: one level of nesting, nothing else is reachable."""
    head, _, tail = field.partition(".")
    value = data.get(head)
    if not tail:
        return value
    return value.get(tail) if isinstance(value, dict) else None


def condition_holds(condition: dict, data: dict) -> bool:
    """One flow condition on event data; values of the wrong kind simply do not match."""
    try:
        return compare(condition["operator"], value_of(data, condition["field"]), condition.get("value"))
    except FlowError:
        return False


def render(template: str, data: dict) -> str:
    """Replace `{key}` / `{form.key}` with event values; no expressions are evaluated."""

    def value(match):
        found = value_of(data, match.group(1))
        return "" if found is None else str(found)

    return re.sub(r"\{([a-z_]{1,40}(?:\.[A-Za-z][A-Za-z0-9_]{0,63})?)\}", value, template)


def recipients(db: Session, names: list[str], data: dict) -> list[str]:
    result = []
    for name in names:
        if name in {"assignee", "creator", "owner", "author"}:
            user_id = data.get(
                {
                    "assignee": "assignee_id",
                    "creator": "creator_id",
                    "owner": "owner_id",
                    "author": "author_id",
                }[name]
            )
            if name == "assignee" and "case_id" in data and "task_id" not in data:
                # A dossier has no assignee; the person who carries it is its owner.
                user_id = data.get("owner_id")
        elif name == "department_manager":
            department = (
                db.get(m.Department, data.get("department_id")) if data.get("department_id") else None
            )
            user_id = department.manager_id if department else None
        else:
            user_id = name
        user = db.get(m.User, user_id) if user_id else None
        if user and user.active and user.id not in result:
            result.append(user.id)
    return result


def legacy_graph(trigger: str, conditions: list, actions: list) -> dict:
    """The graph form of a rule saved before flows existed: a straight line of nodes."""
    nodes = [
        {
            "id": "trigger",
            "type": "trigger",
            "label": "",
            "position": {"x": 0, "y": 120},
            "data": {"event": trigger},
        }
    ]
    edges = []
    previous, branch, x = "trigger", None, 300
    if conditions:
        nodes.append(
            {
                "id": "if_1",
                "type": "if",
                "label": "",
                "position": {"x": x, "y": 120},
                "data": {"mode": "all", "conditions": conditions},
            }
        )
        edges.append({"id": "e_trigger_if_1", "source": "trigger", "target": "if_1", "branch": None})
        previous, branch, x = "if_1", "true", x + 300
    for index, action in enumerate(actions, start=1):
        node_id = f"action_{index}"
        data = {k: v for k, v in action.items() if k != "type"}
        allowed = DATA_MODELS[action["type"]].model_fields
        nodes.append(
            {
                "id": node_id,
                "type": action["type"],
                "label": "",
                "position": {"x": x, "y": 120},
                "data": {k: v for k, v in data.items() if k in allowed},
            }
        )
        edges.append(
            {"id": f"e_{previous}_{node_id}", "source": previous, "target": node_id, "branch": branch}
        )
        previous, branch, x = node_id, None, x + 300
    return {"nodes": nodes, "edges": edges}


def graph_of(rule: m.AutomationRule) -> dict:
    return rule.graph or legacy_graph(rule.trigger, rule.conditions or [], rule.actions or [])


def form_fields(db: Session, form_id: str | None) -> dict:
    form = db.get(m.Form, form_id) if form_id else None
    return {f"form.{field['key']}": field["label"] for field in (form.fields if form else [])}


def approver(db: Session, data: dict, config: dict) -> tuple[m.User | None, str]:
    """Who decides an approval step for this dossier, or why nobody can."""
    if config.get("resolver") == "user":
        user = db.get(m.User, config.get("user_id")) if config.get("user_id") else None
    else:
        department = db.get(m.Department, data.get("department_id")) if data.get("department_id") else None
        user = db.get(m.User, department.manager_id) if department and department.manager_id else None
    if not user or not user.active:
        return None, "Bước duyệt chưa có người duyệt đang hoạt động."
    if user.id == data.get("owner_id"):
        return None, "Không được tự duyệt hồ sơ: người duyệt trùng người tạo."
    return user, ""


def consultees(db: Session, data: dict, config: dict) -> list[m.User]:
    """People asked for an opinion: those named, plus the unit's leader if chosen; never the owner."""
    ids = list(config.get("user_ids") or [])
    if config.get("include_department_manager") and data.get("department_id"):
        department = db.get(m.Department, data["department_id"])
        if department and department.manager_id:
            ids.append(department.manager_id)
    people = []
    for user_id in ids:
        user = db.get(m.User, user_id)
        if user and user.active and user.id != data.get("owner_id") and user not in people:
            people.append(user)
    return people


def offered(kind: str, data: dict) -> set[str]:
    """Branches a node can actually take with its configuration."""
    branches = set(BRANCHES.get(kind, set()))
    if kind == "approval":
        if not data.get("allow_return", True):
            branches.discard("return")
        if not data.get("allow_reject", True):
            branches.discard("reject")
    return branches


def validate_graph(db: Session, settings, graph: dict, kind: str = "automation") -> list[dict]:
    """Every problem in the flow, each tied to the node (or edge) it concerns."""
    errors: list[dict] = []
    process = kind == "process"

    def fail(node_id, message):
        errors.append({"node_id": node_id, "message": message})

    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    if len(nodes) != len(graph.get("nodes", [])):
        fail(None, "Mã node bị trùng.")
    triggers = [n for n in nodes.values() if n["type"] == "trigger"]
    if len(triggers) != 1:
        fail(None, "Luồng cần đúng một node kích hoạt.")
    outgoing: dict[str, list[dict]] = {node_id: [] for node_id in nodes}
    incoming: dict[str, int] = dict.fromkeys(nodes, 0)
    for edge in graph.get("edges", []):
        if edge["source"] not in nodes or edge["target"] not in nodes:
            fail(None, "Có đường nối tới node không tồn tại.")
            continue
        if edge["source"] == edge["target"]:
            fail(edge["source"], "Node không được nối vào chính nó.")
            continue
        source = nodes[edge["source"]]
        branches = BRANCHES.get(source["type"])
        if source["type"] in TERMINAL:
            fail(source["id"], "Node kết thúc quy trình không có bước tiếp theo.")
        elif branches and edge.get("branch") not in branches:
            labels = [BRANCH_LABELS[b] for b in sorted(branches, key=list(BRANCH_LABELS).index)]
            names = ", ".join(labels[:-1]) + " hoặc " + labels[-1]
            where = "node Điều kiện" if source["type"] == "if" else "node này"
            fail(source["id"], f"Đường ra từ {where} phải là nhánh {names}.")
        elif not branches and edge.get("branch"):
            fail(source["id"], "Node này không có nhánh; nối thẳng tới bước tiếp theo.")
        if nodes[edge["target"]]["type"] == "trigger":
            fail(edge["target"], "Không nối vào node kích hoạt.")
        outgoing[edge["source"]].append(edge)
        incoming[edge["target"]] += 1
    # Cycle check (Kahn): a flow must terminate, so it has to be a DAG.
    remaining = dict(incoming)
    ready = [node_id for node_id, count in remaining.items() if count == 0]
    visited = 0
    while ready:
        node_id = ready.pop()
        visited += 1
        for edge in outgoing.get(node_id, []):
            remaining[edge["target"]] -= 1
            if remaining[edge["target"]] == 0:
                ready.append(edge["target"])
    if visited != len(nodes):
        fail(None, "Luồng có vòng lặp; hãy bỏ đường nối quay ngược.")
    reachable = set()
    if len(triggers) == 1:
        stack = [triggers[0]["id"]]
        while stack:
            node_id = stack.pop()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            stack.extend(edge["target"] for edge in outgoing.get(node_id, []))
    form_id = (triggers[0].get("data") or {}).get("form_id") if len(triggers) == 1 else None
    known_fields = {**PROCESS_FIELDS, **form_fields(db, form_id)} if process else None
    for node in nodes.values():
        node_id, kind = node["id"], node["type"]
        if kind not in NODE_TYPES:
            fail(node_id, "Loại node chưa được hỗ trợ.")
            continue
        if kind in PROCESS_NODES and not process:
            fail(node_id, "Bước này chỉ dùng trong quy trình hồ sơ.")
            continue
        try:
            data = DATA_MODELS[kind].model_validate(node.get("data") or {})
        except ValidationError as exc:
            fail(node_id, "Cấu hình không hợp lệ: " + exc.errors()[0]["msg"])
            continue
        if kind != "trigger" and node_id not in reachable:
            fail(node_id, "Node chưa được nối từ node kích hoạt.")
        taken = {e.get("branch") for e in outgoing.get(node_id, [])} - {None}
        unused = taken - offered(kind, data.model_dump())
        if kind in BRANCHES and unused:
            fail(node_id, "Có nhánh đã tắt trong cấu hình nhưng vẫn được nối: " + ", ".join(
                BRANCH_LABELS.get(b, str(b)) for b in sorted(unused, key=str)
            ) + ".")
        if kind == "trigger":
            if process:
                if data.event != "case.submitted":
                    fail(node_id, "Quy trình bắt đầu khi hồ sơ được trình.")
                if not data.form_id or not db.get(m.Form, data.form_id):
                    fail(node_id, "Chọn biểu mẫu áp dụng quy trình.")
            elif data.event not in TRIGGERS:
                fail(node_id, "Chọn sự kiện kích hoạt.")
            if not outgoing.get(node_id):
                fail(node_id, "Nối node kích hoạt tới bước tiếp theo.")
        elif kind == "if":
            if not data.conditions:
                fail(node_id, "Thêm ít nhất một điều kiện.")
            if not outgoing.get(node_id):
                fail(node_id, "Nối ít nhất một nhánh Đúng hoặc Sai.")
            if known_fields is not None:
                for condition in data.conditions:
                    if condition.field not in known_fields:
                        fail(node_id, f"Trường “{condition.field}” không có trong hồ sơ hoặc biểu mẫu.")
        elif kind == "notify":
            if not data.recipients or not data.title.strip():
                fail(node_id, "Thông báo cần người nhận và nội dung.")
            for name in data.recipients:
                if name not in ROLE_RECIPIENTS and not db.get(m.User, name):
                    fail(node_id, "Người nhận thông báo không tồn tại.")
        elif kind in {"create_task", "assign_task"}:
            if not data.title.strip():
                fail(node_id, "Việc được tạo cần tiêu đề.")
            if data.assignee_id and not db.get(m.User, data.assignee_id):
                fail(node_id, "Người nhận việc không tồn tại.")
            if data.department_id and not db.get(m.Department, data.department_id):
                fail(node_id, "Đơn vị nhận việc không tồn tại.")
            if kind == "assign_task":
                if not data.assignee_id and not data.department_id:
                    fail(node_id, "Chọn người hoặc đơn vị nhận việc.")
                if not outgoing.get(node_id):
                    fail(node_id, "Nối bước sẽ chạy khi việc hoàn thành.")
        elif kind == "approval":
            if data.resolver == "user":
                user = db.get(m.User, data.user_id) if data.user_id else None
                if not user or not user.active:
                    fail(node_id, "Chọn người duyệt đang hoạt động.")
        elif kind == "consult":
            if not data.user_ids and not data.include_department_manager:
                fail(node_id, "Chọn ít nhất một người cho ý kiến.")
            for user_id in data.user_ids:
                user = db.get(m.User, user_id)
                if not user or not user.active:
                    fail(node_id, "Người cho ý kiến không tồn tại hoặc đã bị khóa.")
            if not outgoing.get(node_id):
                fail(node_id, "Nối bước tiếp theo cho nhánh Đồng ý hoặc Không đồng ý.")
        elif kind == "webhook":
            connection = db.get(m.Connection, data.connection_id) if data.connection_id else None
            if not connection:
                fail(node_id, "Chọn kết nối cho webhook.")
            else:
                try:
                    check_url(settings, urljoin(connection.base_url, data.path))
                except AppError as exc:
                    fail(node_id, exc.detail)
        elif kind == "ai":
            choices = [c.strip() for c in data.choices if c.strip()]
            if not data.question.strip() or len(choices) < 2 or len(set(choices)) != len(choices):
                fail(node_id, "Nhập câu hỏi và ít nhất hai lựa chọn khác nhau.")
            if "automation_ai" not in ai_core.enabled_features(db):
                fail(node_id, "Tính năng “Hỏi AI trong luồng” chưa được bật trong màn Trợ lý AI.")
            if not outgoing.get(node_id):
                fail(node_id, "Nối bước tiếp theo, thường là một node Điều kiện dùng kết quả AI.")
        elif kind == "wait" and not outgoing.get(node_id):
            fail(node_id, "Nối bước sẽ chạy sau khi chờ.")
    if process and not any(n["type"] in {"approval", "finish", "request_info"} for n in nodes.values()):
        fail(None, "Quy trình cần ít nhất một bước Duyệt hoặc node Kết thúc để hồ sơ có kết quả.")
    return errors


def trigger_event(graph: dict) -> str:
    return next(n["data"].get("event", "") for n in graph["nodes"] if n["type"] == "trigger")


def trigger_form(graph: dict) -> str | None:
    return next((n["data"].get("form_id") for n in graph["nodes"] if n["type"] == "trigger"), None)


def kind_of(rule: m.AutomationRule) -> str:
    return rule.kind or "automation"


def require_valid(db: Session, settings, graph: dict, kind: str = "automation"):
    errors = validate_graph(db, settings, graph, kind)
    if errors:
        raise AppError(422, "flow_invalid", errors[0]["message"])


def attachable(trigger: str) -> bool:
    """Flows people may attach to a task: task events that can happen after it exists."""
    return trigger_family(trigger) == "task" and trigger != "task.created"


def check_scope(scope: str, trigger: str):
    if scope == "attached" and not attachable(trigger):
        raise AppError(
            422,
            "scope_invalid",
            "Chỉ luồng theo sự kiện công việc (trừ “Công việc được tạo”) mới để nhân viên tự gắn vào việc.",
        )


def applies(db: Session, rule: m.AutomationRule, data: dict) -> bool:
    if rule.scope != "attached":
        return True
    return bool(
        data.get("task_id")
        and db.scalar(
            select(m.TaskAutomation.id).where(
                m.TaskAutomation.rule_id == rule.id, m.TaskAutomation.task_id == data["task_id"]
            )
        )
    )


class Execution:
    """Walks a flow from given nodes. With `dry_run` it only reports what would happen."""

    def __init__(
        self,
        db: Session,
        graph: dict,
        data: dict,
        *,
        dry_run: bool,
        run=None,
        rule=None,
        chain=None,
        event: dict | None = None,
    ):
        self.db, self.graph, self.data, self.dry_run = db, graph, data, dry_run
        self.run, self.rule, self.chain, self.event = run, rule, chain or [], event or {}
        self.nodes = {node["id"]: node for node in graph["nodes"]}
        self.steps: list[dict] = []
        # Process flows: set once the dossier is settled; nothing after that runs.
        self.outcome: str | None = None
        self.done = "would_run" if dry_run else "succeeded"

    def successors(self, node_id: str, branch: str | None = None) -> list[str]:
        return [
            e["target"]
            for e in self.graph["edges"]
            if e["source"] == node_id and (branch is None or e.get("branch") == branch)
        ]

    def walk(self, start: list[str]):
        queue, seen = list(start), set()
        while queue and self.outcome is None:
            node_id = queue.pop(0)
            if node_id in seen or node_id not in self.nodes:
                continue
            seen.add(node_id)
            queue.extend(self.step(self.nodes[node_id]))
        return self.steps

    def follow(self, node, branch: str) -> list[str]:
        """Where a step goes after taking `branch`; an unconnected approval branch settles the dossier."""
        following = self.successors(node["id"], branch)
        if not following and node["type"] == "approval":
            self.conclude(IMPLICIT_OUTCOME[branch], node)
        return following

    def conclude(self, outcome: str, node, message: str = ""):
        """Settle the dossier. A dry run only says so; `processes` applies it for real."""
        self.outcome = outcome
        self.steps.append(
            {
                "node_id": None,
                "type": "outcome",
                "state": self.done,
                "outcome": outcome,
                "source": node["id"],
                "message": message,
            }
        )

    def process_step(self, node, kind, data) -> list[str]:
        """Dry run of a process step: who would be asked, and the path a sample decision takes."""
        if kind == "finish":
            self.record(node, self.done, outcome=data.get("result", "approved"))
            self.conclude(data.get("result", "approved"), node, render(data.get("message", ""), self.data))
            return []
        if kind == "request_info":
            self.record(node, self.done, outcome="needs_revision")
            self.conclude("needs_revision", node, render(data.get("message", ""), self.data))
            return []
        detail: dict = {}
        if kind == "approval":
            person, problem = approver(self.db, self.data, data)
            if not person:
                self.record(node, "failed", error="approver_unresolved", message=problem)
                return []
            detail["people"] = [person.display_name]
        elif kind == "consult":
            people = consultees(self.db, self.data, data)
            if not people:
                self.record(node, "failed", error="consultees_missing", message="Không có ai để xin ý kiến.")
                return []
            detail["people"] = [person.display_name for person in people]
        elif kind == "assign_task":
            detail["title"] = render(data.get("title", ""), self.data)
        default = "completed" if kind == "assign_task" else "approve"
        branch = (self.data.get("decisions") or {}).get(node["id"], default)
        if branch not in offered(kind, data):
            branch = default
        self.record(node, "would_run", branch=branch, **detail)
        return self.follow(node, branch)

    def record(self, node, state, **extra):
        self.steps.append({"node_id": node["id"], "type": node["type"], "state": state, **extra})

    def step(self, node) -> list[str]:
        kind, data = node["type"], node.get("data") or {}
        if kind in PROCESS_NODES:
            return self.process_step(node, kind, data)
        if kind == "trigger":
            self.record(node, "succeeded")
            return self.successors(node["id"])
        if kind == "if":
            results = [condition_holds(c, self.data) for c in data.get("conditions", [])]
            passed = all(results) if data.get("mode", "all") == "all" else any(results)
            branch = "true" if passed else "false"
            self.record(node, "succeeded", branch=branch, results=results)
            return self.successors(node["id"], branch)
        if kind == "ai":
            choices = [c.strip() for c in data.get("choices", []) if c.strip()]
            try:
                label = ai_core.classify(self.db, ai_core.runtime_settings(), data.get("question", ""), choices, self.data)
            except AppError as exc:
                self.record(node, "failed", error=exc.code, message=exc.detail)
                return []
            self.data = {**self.data, data.get("output") or "ai_label": label}
            self.record(node, "succeeded", output=data.get("output") or "ai_label", value=label)
            return self.successors(node["id"])
        if kind == "wait":
            minutes = int(data.get("minutes", 60))
            following = self.successors(node["id"])
            if self.dry_run:
                self.record(node, "would_run", minutes=minutes)
                return following
            resume_at = m.utcnow() + timedelta(minutes=minutes)
            # The worker does not pick the job up before `available_at`, so no process sleeps.
            self.db.add(
                m.Outbox(
                    kind="automation.resume",
                    aggregate_id=self.run.id,
                    available_at=resume_at,
                    payload={
                        "run_id": self.run.id,
                        "wait_node": node["id"],
                        "nodes": following,
                        "data": self.data,
                        "event": self.event,
                        "chain": self.chain,
                    },
                )
            )
            self.record(node, "waiting", minutes=minutes, resume_at=resume_at.isoformat())
            return []
        try:
            detail = self.act(node, kind, data)
        except AppError as exc:
            # A failed action stops its own branch; parallel branches still run.
            self.record(node, "failed", error=exc.code, message=exc.detail)
            return []
        self.record(node, detail.pop("state", "would_run" if self.dry_run else "succeeded"), **detail)
        return self.successors(node["id"])

    def make_task(self, data) -> m.Task:
        owner = self.db.get(m.User, self.rule.created_by)
        if not owner or not owner.active:
            raise AppError(403, "rule_owner_inactive", "Người tạo luật đã bị khóa.")
        due = (
            m.utcnow() + timedelta(days=data["due_in_days"]) if data.get("due_in_days") is not None else None
        )
        # Runs as the flow's author, with that person's permissions at run time.
        with self.db.begin_nested():
            return create_task(
                self.db,
                owner,
                TaskCreate(
                    title=render(data.get("title", ""), self.data),
                    description=render(data.get("description", ""), self.data),
                    assignee_id=data.get("assignee_id") or None,
                    department_id=data.get("department_id") or None,
                    priority=data.get("priority", "normal"),
                    due_at=due,
                    case_id=self.data.get("case_id"),
                    source=TaskSource(type="automation", id=self.rule.id, label=self.rule.name),
                ),
                origin={"rules": [*self.chain, self.rule.id]},
            )

    def act(self, node, kind, data) -> dict:
        if kind == "notify":
            people = recipients(self.db, data.get("recipients", []), self.data)
            title = render(data.get("title", ""), self.data)
            if not self.dry_run:
                for user_id in people:
                    notify(
                        self.db,
                        user_id,
                        f"automation:{self.run.id}:{node['id']}:{user_id}",
                        title,
                        link=link_for(self.data),
                    )
            return {"recipients": people, "title": title}
        if kind == "create_task":
            title = render(data.get("title", ""), self.data)
            if self.dry_run:
                return {"title": title}

            task = self.make_task(data)
            return {"title": title, "task_id": task.id}
        # webhook
        if self.dry_run:
            return {"connection_id": data.get("connection_id"), "path": data.get("path", "")}
        enqueue(
            self.db,
            "automation.webhook",
            self.run.id,
            {
                "run_id": self.run.id,
                "node_id": node["id"],
                **self.event,
                "data": self.data,
            },
        )
        return {"state": "queued"}


def settle(run: m.AutomationRun):
    states = {step["state"] for step in run.steps}
    if run.submission_id:
        # A process run is done only when the dossier is settled (`processes.settle`); a late
        # webhook result never marks it succeeded on its own.
        if run.state not in {"succeeded", "cancelled", "failed"}:
            run.state = "waiting" if states & {"queued", "waiting"} else "failed"
        return
    if states & {"queued", "waiting"}:
        run.state = "waiting" if "waiting" in states else "running"
    elif "failed" in states or "unknown" in states:
        run.state = "failed"
    elif not states - {"succeeded"} and any(step["type"] not in {"trigger", "if"} for step in run.steps):
        run.state = "succeeded"
    else:
        # Only the trigger and conditions ran: the event did not match the flow.
        run.state = "not_matched"


def dispatch(db: Session, payload: dict):
    """Run every enabled flow listening to this event; the worker may deliver an event more than once."""
    event_type, data, origin = payload["event_type"], payload["data"], payload.get("origin") or {"rules": []}
    chain = origin.get("rules", [])
    for rule in db.scalars(
        select(m.AutomationRule).where(
            m.AutomationRule.trigger == event_type,
            m.AutomationRule.enabled.is_(True),
            or_(m.AutomationRule.kind.is_(None), m.AutomationRule.kind != "process"),
        )
    ):
        if db.scalar(
            select(m.AutomationRun.id).where(
                m.AutomationRun.rule_id == rule.id, m.AutomationRun.event_id == payload["event_id"]
            )
        ):
            continue
        # A flow limited to attached tasks stays silent for every other task.
        if not applies(db, rule, data):
            continue
        run_rule(db, rule, payload["event_id"], event_type, data, chain)


def run_rule(
    db: Session, rule: m.AutomationRule, event_id: str, event_type: str, data: dict, chain: list
) -> m.AutomationRun:
    """Run one flow for one event, recording a run; shared by events and manual runs."""
    graph = graph_of(rule)
    run = m.AutomationRun(
        rule_id=rule.id,
        rule_revision=rule.revision,
        event_id=event_id,
        event_type=event_type,
        state="running",
        graph=graph,
        data=data,
    )
    db.add(run)
    db.flush()
    if rule.id in chain or len(chain) >= MAX_CHAIN:
        # The event was caused by this flow (or a long chain); acting again would loop.
        run.state, run.steps = (
            "skipped",
            [{"node_id": None, "type": "loop_guard", "state": "skipped", "chain": chain}],
        )
        return run
    trigger = next(n["id"] for n in graph["nodes"] if n["type"] == "trigger")
    execution = Execution(
        db,
        graph,
        data,
        dry_run=False,
        run=run,
        rule=rule,
        chain=chain,
        event={"event_type": event_type, "event_id": event_id},
    )
    run.steps = execution.walk([trigger])
    settle(run)
    return run


def subject_of(data: dict) -> dict | None:
    """What a run was about, for the run history: the task, dossier or post in the event."""
    if data.get("task_id"):
        return {"type": "task", "id": data["task_id"], "title": data.get("title", ""), "link": link_for(data)}
    if data.get("case_id"):
        return {"type": "case", "id": data["case_id"], "title": data.get("title", ""), "link": link_for(data)}
    if data.get("post_id"):
        return {"type": "post", "id": data["post_id"], "title": "Bài viết trên bảng tin", "link": "/feed"}
    return None


def resume(db: Session, payload: dict):
    """Continue a flow after a wait node, against the graph the run started with."""
    run = db.scalar(select(m.AutomationRun).where(m.AutomationRun.id == payload["run_id"]).with_for_update())
    rule = db.get(m.AutomationRule, run.rule_id) if run else None
    if not run or not rule:
        return

    def waiting_here(step):
        return step["node_id"] == payload["wait_node"] and step["state"] == "waiting"

    if not any(waiting_here(step) for step in run.steps):
        return  # Already resumed by an earlier delivery of this job.
    steps = [dict(step, state="succeeded") if waiting_here(step) else step for step in run.steps]
    if not rule.enabled:
        run.steps = [
            *steps,
            {
                "node_id": None,
                "type": "resume",
                "state": "cancelled",
                "message": "Luồng đã tắt trong lúc chờ.",
            },
        ]
        run.state = "cancelled"
        return
    execution = Execution(
        db,
        run.graph,
        current_data(db, payload["data"]),
        dry_run=False,
        run=run,
        rule=rule,
        chain=payload.get("chain", []),
        event=payload.get("event", {}),
    )
    run.steps = steps + execution.walk(payload["nodes"])
    settle(run)


def current_data(db: Session, data: dict) -> dict:
    """Event data refreshed from the record, so steps after a wait see what is true now.

    That is what makes "wait a day, then remind if it is still returned" possible; the
    event's own facts (who triggered it, and so on) are kept when the record is gone.
    """
    if data.get("task_id"):
        task = db.get(m.Task, data["task_id"])
        return {**data, **event_data(task)} if task else data
    if data.get("case_id"):
        case = db.get(m.Case, data["case_id"])
        return {**data, **case_event(case)} if case else data
    return data


def link_for(data: dict) -> str | None:
    if data.get("task_id"):
        return f"/tasks/{data['task_id']}"
    if data.get("case_id"):
        return f"/cases/{data['case_id']}"
    if data.get("post_id"):
        return "/feed"
    return None


def send_webhook(url: str, headers: dict, body: dict, timeout: int) -> httpx.Response:
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        return client.post(url, json=body, headers=headers)


def deliver_webhook(db: Session, settings, payload: dict):
    run = db.scalar(select(m.AutomationRun).where(m.AutomationRun.id == payload["run_id"]).with_for_update())
    rule = db.get(m.AutomationRule, run.rule_id) if run else None
    if not run or not rule:
        return
    steps = list(run.steps)
    position = next(
        (
            i
            for i, step in enumerate(steps)
            if step.get("node_id") == payload["node_id"] and step["state"] == "queued"
        ),
        None,
    )
    if position is None:
        return
    node = next(n for n in run.graph["nodes"] if n["id"] == payload["node_id"])
    data = node.get("data") or {}
    connection = db.get(m.Connection, data.get("connection_id"))

    def finish(state, **extra):
        steps[position] = dict(steps[position], state=state, **extra)
        run.steps = steps
        settle(run)

    if not connection:
        finish("failed", error="connection_missing")
        return
    url = urljoin(connection.base_url, data.get("path", ""))
    try:
        check_url(settings, url)
    except AppError as exc:
        finish("failed", error=exc.code)
        return
    headers = {
        **connection.headers,
        "Idempotency-Key": f"{run.id}:{payload['node_id']}",
        "X-DX-Event-Type": payload["event_type"],
        "X-DX-Event-Id": payload["event_id"],
    }
    if connection.secret:
        secret = SecretBox(settings.credential_encryption_key).decrypt(connection.secret)
        name = secret.get("header", "Authorization")
        headers[name] = ("Bearer " if connection.auth_type == "bearer" else "") + secret["value"]
    body = {
        "event_id": payload["event_id"],
        "event_type": payload["event_type"],
        "rule_id": rule.id,
        "data": payload["data"],
    }
    try:
        response = send_webhook(url, headers, body, connection.timeout_seconds)
    except httpx.TimeoutException:
        # The receiver may already have acted; resending blindly could act twice.
        finish("unknown", error="timeout")
        return
    except httpx.TransportError as exc:
        raise AppError(503, "webhook_unreachable", "Không kết nối được máy chủ webhook.") from exc
    if response.status_code >= 500:
        raise AppError(503, "webhook_server_error", f"Webhook trả lỗi {response.status_code}.")
    if response.status_code >= 400:
        finish("failed", error=f"http_{response.status_code}")
        return
    finish("succeeded", status_code=response.status_code)


def build_router(app):
    router = APIRouter(prefix="/workspace/v1", tags=["automations"])
    db_dep = app.state.db_dependency
    actor_dep = app.state.auth.actor
    settings = app.state.settings

    def admin(db, actor):
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")
        user = current_user(db, actor)
        require(db, user, "automations.manage")
        return user

    def connection_data(value):
        data = serial(value)
        data.pop("secret")
        data["has_secret"] = bool(value.secret)
        return data

    def rule_data(db, rule):
        data = serial(rule)
        data["kind"] = kind_of(rule)
        data["graph"] = graph_of(rule)
        form = db.get(m.Form, rule.form_id) if rule.form_id else None
        data["form_name"] = form.name if form else None
        data.pop("conditions", None)
        data.pop("actions", None)
        last = db.scalar(
            select(m.AutomationRun)
            .where(m.AutomationRun.rule_id == rule.id)
            .order_by(m.AutomationRun.created_at.desc())
            .limit(1)
        )
        data["last_run"] = run_data(last) if last else None
        data["attached_count"] = db.scalar(
            select(func.count(m.TaskAutomation.id)).where(m.TaskAutomation.rule_id == rule.id)
        )
        return data

    def run_data(run):
        data = serial(run)
        data.pop("graph", None)
        data["subject"] = subject_of(run.data or {})
        data["manual_by"] = (run.data or {}).get("manual_by")
        return data

    def event_source(db, user, family: str, ref_id: str) -> dict:
        """Event data built from an existing record the user may see, as its real event would carry."""
        if family == "task":

            return event_data(get_task(db, user, ref_id))
        if family == "case":
            return case_event(get_case(db, user, ref_id))
        post = db.get(m.Post, ref_id)
        if not post or not can_see_post(db, user, post):
            raise AppError(404, "post_not_found", "Không tìm thấy bài viết.")
        return {
            "post_id": post.id,
            "author_id": post.author_id,
            "audience": post.audience,
            "department_id": post.department_id,
            "official": post.official,
        }

    def get_rule(db, rule_id):
        rule = db.get(m.AutomationRule, rule_id)
        if not rule:
            raise AppError(404, "rule_not_found", "Không tìm thấy luồng tự động.")
        return rule

    def check_single_process(db, rule_id: str | None, form_id: str | None):
        """A form follows one process at a time, or a dossier would not know which to take."""
        other = db.scalar(
            select(m.AutomationRule).where(
                m.AutomationRule.kind == "process",
                m.AutomationRule.form_id == form_id,
                m.AutomationRule.enabled.is_(True),
                m.AutomationRule.id != (rule_id or ""),
            )
        )
        if other:
            raise AppError(
                409,
                "process_already_enabled",
                f"Biểu mẫu này đang dùng quy trình “{other.name}”. Tắt quy trình đó trước khi bật quy trình khác.",
            )

    def not_process(rule):
        if kind_of(rule) == "process":
            raise AppError(
                422, "process_runs_on_submit", "Quy trình hồ sơ tự chạy khi hồ sơ được trình; không chạy tay."
            )

    @router.get("/automations/catalog")
    def catalog(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = admin(db, actor)
        return {
            "triggers": [
                {
                    "key": k,
                    "label": v,
                    "fields": fields_for(k),
                    "sample": SAMPLES[trigger_family(k)],
                    "attachable": attachable(k),
                }
                for k, v in TRIGGERS.items()
            ],
            "operators": ["eq", "ne", "gt", "gte", "lt", "lte", "contains", "in", "empty", "not_empty"],
            "recipients": sorted(ROLE_RECIPIENTS),
            "process": {
                "fields": PROCESS_FIELDS,
                # The drawer's own unit, so "leader of the unit" resolves to someone in a dry run.
                "sample": {**PROCESS_SAMPLE, "department_id": user.department_id, "owner_id": None},
                "forms": [
                    {"id": form.id, "name": form.name, "fields": form_fields(db, form.id)}
                    for form in db.scalars(
                        select(m.Form).where(m.Form.state == "published").order_by(m.Form.name)
                    )
                ],
                "outcomes": OUTCOMES,
            },
            "branch_labels": BRANCH_LABELS,
            "webhooks_enabled": bool(allowed_hosts(settings)),
            "allowed_hosts": sorted(allowed_hosts(settings)),
            "max_nodes": MAX_NODES,
        }

    @router.get("/automations")
    def rules(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        admin(db, actor)
        rows = list(db.scalars(select(m.AutomationRule).order_by(m.AutomationRule.created_at.desc())))
        return page(rows, 200, transform=lambda r: rule_data(db, r))

    @router.get("/automations/{rule_id}")
    def read_rule(rule_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        admin(db, actor)
        return rule_data(db, get_rule(db, rule_id))

    @router.post("/automations/validate")
    def validate(
        body: Graph,
        kind: Literal["automation", "process"] = "automation",
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        """Check a flow while it is being drawn; problems come back tied to their node."""
        admin(db, actor)
        errors = validate_graph(db, settings, body.model_dump(), kind)
        return {"valid": not errors, "errors": errors}

    @router.post("/automations/test")
    def test_graph(body: GraphTest, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        """Dry run of an unsaved flow: the path it would take; writes nothing and calls nothing."""
        admin(db, actor)
        graph = body.graph.model_dump()
        errors = validate_graph(db, settings, graph, body.kind)
        if errors:
            return {"valid": False, "errors": errors, "steps": []}
        trigger = next(n["id"] for n in graph["nodes"] if n["type"] == "trigger")
        execution = Execution(db, graph, body.data, dry_run=True)
        steps = execution.walk([trigger])
        return {
            "valid": True,
            "errors": [],
            "steps": steps,
            "matched": any(step["type"] not in {"trigger", "if"} for step in steps),
            "outcome": execution.outcome,
        }

    @router.post("/automations", status_code=201)
    def create_rule(body: RuleInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user = admin(db, actor)
        graph = body.graph.model_dump()
        require_valid(db, settings, graph, body.kind)
        if body.kind == "automation":
            check_scope(body.scope, trigger_event(graph))
        # New flows start disabled: they are tested before they act on real events.
        rule = m.AutomationRule(
            name=body.name,
            description=body.description,
            scope=body.scope if body.kind == "automation" else "all",
            kind=body.kind,
            form_id=trigger_form(graph) if body.kind == "process" else None,
            trigger=trigger_event(graph),
            conditions=[],
            actions=[],
            graph=graph,
            enabled=False,
            created_by=user.id,
        )
        db.add(rule)
        db.flush()
        audit(db, user, "automation.created", rule.id)
        db.commit()
        return rule_data(db, rule)

    @router.put("/automations/{rule_id}")
    def update_rule(
        rule_id: str, body: RulePatch, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = admin(db, actor)
        rule = get_rule(db, rule_id)
        kind = kind_of(rule)
        graph = body.graph.model_dump()
        require_valid(db, settings, graph, kind)
        values = {
            "name": body.name,
            "description": body.description,
            "trigger": trigger_event(graph),
            "scope": body.scope,
            "graph": graph,
            "updated_at": m.utcnow(),
        }
        if kind == "process":
            values.update(scope="all", form_id=trigger_form(graph))
            if rule.enabled:
                check_single_process(db, rule.id, values["form_id"])
        else:
            check_scope(body.scope, trigger_event(graph))
        # Dossiers already submitted keep the flow they started with; only new ones see the edit.
        cas(db, m.AutomationRule, rule_id, body.expected_revision, values)
        audit(db, user, "automation.updated", rule_id)
        db.commit()
        return rule_data(db, db.get(m.AutomationRule, rule_id))

    @router.post("/automations/{rule_id}/enabled")
    def toggle(
        rule_id: str, body: RuleToggle, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = admin(db, actor)
        rule = get_rule(db, rule_id)
        if body.enabled:
            require_valid(db, settings, graph_of(rule), kind_of(rule))
            if kind_of(rule) == "process":
                check_single_process(db, rule.id, rule.form_id)
        cas(
            db,
            m.AutomationRule,
            rule_id,
            body.expected_revision,
            {"enabled": body.enabled, "updated_at": m.utcnow()},
        )
        audit(db, user, "automation.enabled" if body.enabled else "automation.disabled", rule_id)
        db.commit()
        return rule_data(db, db.get(m.AutomationRule, rule_id))

    @router.post("/automations/{rule_id}/test")
    def test_rule(
        rule_id: str, body: RuleTest, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        """Dry run of the saved flow for a sample event."""
        admin(db, actor)
        graph = graph_of(get_rule(db, rule_id))
        trigger = next(n["id"] for n in graph["nodes"] if n["type"] == "trigger")
        execution = Execution(db, graph, body.data, dry_run=True)
        steps = execution.walk([trigger])
        return {
            "matched": any(step["type"] not in {"trigger", "if"} for step in steps),
            "steps": steps,
            "outcome": execution.outcome,
        }

    @router.get("/automations/{rule_id}/candidates")
    def candidates(
        rule_id: str,
        q: str | None = Query(None, max_length=200),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        """Records a manual run can use: those of the trigger's kind that the user may see."""
        user = admin(db, actor)
        rule = get_rule(db, rule_id)
        not_process(rule)
        family = trigger_family(rule.trigger)
        needle = (q or "").strip()
        items = []
        if family == "task":

            for task in db.scalars(select(m.Task).order_by(m.Task.updated_at.desc())):
                if matches(needle, task.title) and visible(db, user, task):
                    items.append({"id": task.id, "title": task.title, "status": task.status})
        elif family == "case":
            for case in db.scalars(
                select(m.Case).where(case_filter(db, user)).order_by(m.Case.updated_at.desc())
            ):
                if matches(needle, case.title, f"hs-{case.number:06d}"):
                    items.append(
                        {
                            "id": case.id,
                            "title": f"HS-{case.number:06d} · {case.title}",
                            "status": case.status,
                        }
                    )
        else:
            for post in db.scalars(
                select(m.Post).where(post_visibility(db, user)).order_by(m.Post.created_at.desc())
            ):
                if matches(needle, post.body):
                    items.append({"id": post.id, "title": post.body[:90], "status": None})
        return {"family": family, "items": items[:20]}

    @router.post("/automations/{rule_id}/run", status_code=201)
    def run_now(
        rule_id: str, body: ManualRun, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        """Run the saved flow now, for real, as if its event had just happened to that record.

        Works whether the flow is switched on or not: it is how a flow is tried on real data,
        or applied to a record that existed before the flow was made.
        """
        user = admin(db, actor)
        rule = get_rule(db, rule_id)
        not_process(rule)
        require_valid(db, settings, graph_of(rule))
        data = event_source(db, user, trigger_family(rule.trigger), body.ref_id)
        data["manual_by"] = user.display_name
        run = run_rule(db, rule, m.uid(), rule.trigger, data, [])
        audit(db, user, "automation.run_manual", rule.id, {"run_id": run.id, "ref_id": body.ref_id})
        db.commit()
        return run_data(run)

    def task_for(db, actor, task_id):
        if actor.application != "workspace" or actor.service:
            raise AppError(403, "workspace_user_required", "Cần phiên người dùng Workspace.")

        user = current_user(db, actor)
        task = get_task(db, user, task_id)
        # The people responsible for the task decide what runs on it; watchers only follow.
        can_manage = task.assignee_id == user.id or manages(db, user, task)
        return user, task, can_manage

    def task_automations(db, task, can_manage):
        attached = {
            row.rule_id: row
            for row in db.scalars(select(m.TaskAutomation).where(m.TaskAutomation.task_id == task.id))
        }
        rules = list(
            db.scalars(
                select(m.AutomationRule)
                .where(m.AutomationRule.trigger.like("task.%"))
                .order_by(m.AutomationRule.name)
            )
        )

        def item(rule):
            return {
                "id": rule.id,
                "name": rule.name,
                "description": rule.description,
                "trigger": rule.trigger,
                "trigger_label": TRIGGERS.get(rule.trigger, rule.trigger),
                "enabled": rule.enabled,
                "attached": rule.id in attached,
            }

        return {
            # Offered: switched-on flows limited to attached tasks, plus any already attached
            # (a flow switched off later stays listed so it can be detached).
            "available": [
                item(r)
                for r in rules
                if r.scope == "attached" and attachable(r.trigger) and (r.enabled or r.id in attached)
            ],
            "always": [item(r) for r in rules if r.scope == "all" and r.enabled],
            "can_manage": can_manage,
        }

    @router.get("/tasks/{task_id}/automations", tags=["tasks"])
    def list_task_automations(task_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        _, task, can_manage = task_for(db, actor, task_id)
        return task_automations(db, task, can_manage)

    @router.put("/tasks/{task_id}/automations/{rule_id}", tags=["tasks"])
    def attach(task_id: str, rule_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user, task, can_manage = task_for(db, actor, task_id)
        if not can_manage:
            raise AppError(
                403, "task_manager_required", "Chỉ người giao, người phụ trách hoặc điều phối được gắn luồng."
            )
        rule = db.get(m.AutomationRule, rule_id)
        if not rule or rule.scope != "attached" or not rule.enabled or not attachable(rule.trigger):
            raise AppError(
                422, "rule_not_attachable", "Luồng này không bật hoặc không cho gắn vào công việc."
            )
        if not db.scalar(
            select(m.TaskAutomation.id).where(
                m.TaskAutomation.task_id == task.id, m.TaskAutomation.rule_id == rule.id
            )
        ):

            db.add(m.TaskAutomation(task_id=task.id, rule_id=rule.id, attached_by=user.id))
            log(db, task, user.id, "automation_attached", {"rule_id": rule.id, "name": rule.name})
            audit(db, user, "automation.attached", task.id, {"rule_id": rule.id})
        db.commit()
        return task_automations(db, task, can_manage)

    @router.delete("/tasks/{task_id}/automations/{rule_id}", tags=["tasks"])
    def detach(task_id: str, rule_id: str, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        user, task, can_manage = task_for(db, actor, task_id)
        if not can_manage:
            raise AppError(
                403, "task_manager_required", "Chỉ người giao, người phụ trách hoặc điều phối được gỡ luồng."
            )
        row = db.scalar(
            select(m.TaskAutomation).where(
                m.TaskAutomation.task_id == task.id, m.TaskAutomation.rule_id == rule_id
            )
        )
        if row:

            rule = db.get(m.AutomationRule, rule_id)
            db.delete(row)
            log(
                db,
                task,
                user.id,
                "automation_detached",
                {"rule_id": rule_id, "name": rule.name if rule else ""},
            )
            audit(db, user, "automation.detached", task.id, {"rule_id": rule_id})
        db.commit()
        return task_automations(db, task, can_manage)

    @router.get("/automations/{rule_id}/runs")
    def runs(
        rule_id: str,
        limit: int = Query(50, ge=1, le=200),
        db: Session = Depends(db_dep),
        actor: Actor = Depends(actor_dep),
    ):
        admin(db, actor)
        rows = list(
            db.scalars(
                select(m.AutomationRun)
                .where(m.AutomationRun.rule_id == rule_id)
                .order_by(m.AutomationRun.created_at.desc())
                .limit(limit)
            )
        )
        return page(rows, limit, transform=run_data)

    @router.get("/connections")
    def connections(db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)):
        admin(db, actor)
        return page(
            list(db.scalars(select(m.Connection).order_by(m.Connection.name))), 200, transform=connection_data
        )

    @router.post("/connections", status_code=201)
    def create_connection(
        body: ConnectionInput, db: Session = Depends(db_dep), actor: Actor = Depends(actor_dep)
    ):
        user = admin(db, actor)
        check_url(settings, body.base_url)
        if body.auth_type != "none" and not body.secret:
            raise AppError(422, "secret_required", "Nhập khóa xác thực cho kết nối.")
        lowered = {k.lower() for k in body.headers}
        if lowered & {"authorization", "cookie", body.secret_header.lower()}:
            raise AppError(422, "secret_in_headers", "Không đặt thông tin bí mật trong header thường.")
        secret = None
        if body.auth_type != "none":
            header = "Authorization" if body.auth_type == "bearer" else body.secret_header
            secret = SecretBox(settings.credential_encryption_key).encrypt(
                {"header": header, "value": body.secret}
            )
        value = m.Connection(
            name=body.name,
            base_url=body.base_url,
            auth_type=body.auth_type,
            secret=secret,
            headers=body.headers,
            timeout_seconds=body.timeout_seconds,
            created_by=user.id,
        )
        db.add(value)
        db.flush()
        audit(db, user, "connection.created", value.id)
        db.commit()
        return connection_data(value)

    return router
