# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
from functools import wraps

import dx_flowkit
from dx_flowkit import FlowError
from dx_platform.database import utcnow
from dx_platform.errors import AppError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DecisionTrace, HumanTask, NodeRun, Run, Workflow

# Graph validation, conditions and dry runs come from dx-flowkit, the same code published
# for other projects; this module adds Vietnamese messages and the persisted live run.
NODE_TYPES = dx_flowkit.NODE_TYPES
OPERATORS = dx_flowkit.OPERATORS
MESSAGES = {
    "invalid_path": "Đường dẫn dữ liệu không hợp lệ.",
    "invalid_operator": "Toán tử điều kiện không được hỗ trợ.",
    "condition_type_error": "Kiểu dữ liệu điều kiện không tương thích.",
    "invalid_graph": "Luồng cần nodes/edges hợp lệ và số node/cạnh trong giới hạn.",
    "invalid_node_ids": "ID node phải duy nhất và tối đa 80 ký tự.",
    "unsupported_node": "Loại node chưa được hỗ trợ trong bản pilot.",
    "invalid_edge": "Cạnh hoặc điều kiện cạnh không hợp lệ hoặc trùng.",
    "invalid_roots": "Luồng cần đúng một start và có end; mọi node phải nối từ start.",
    "graph_cycle": "Luồng có chu trình hoặc node không thể tới.",
    "invalid_node_config": "Config node phải là object.",
    "invalid_mapping": "Kết quả map phải là object.",
    "assignee_required": "Human task cần assigned_subject hợp lệ.",
    "invalid_business_reference": "Tham chiếu human task không hợp lệ.",
    "end_has_edges": "Node end không được có cạnh đi ra.",
    "missing_end": "Nhánh cần kết thúc tại node end.",
    "invalid_fixture": "Quyết định giả lập phải là object.",
}


def app_error(exc: FlowError) -> AppError:
    if exc.code == "assignee_unresolved":
        return AppError(422, exc.code, f"Bước '{exc.node_id}' thiếu người nhận.")
    return AppError(422, exc.code, MESSAGES.get(exc.code, exc.message))


def _translated(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except FlowError as exc:
            raise app_error(exc) from None

    return call


path_value = _translated(dx_flowkit.path_value)
resolve = _translated(dx_flowkit.resolve)
evaluate = _translated(dx_flowkit.evaluate)
validate_graph = _translated(dx_flowkit.validate_graph)
simulate_graph = _translated(dx_flowkit.simulate_graph)
edge_selected = dx_flowkit.edge_selected


def advance(db: Session, run_id: str):
    """One bounded transaction locks the run; a crash rolls back all unfinished node work."""
    run = db.scalar(
        select(Run).where(Run.id == run_id).with_for_update().execution_options(populate_existing=True)
    )
    if not run or run.state not in {"queued", "running", "waiting"}:
        return run
    workflow = db.get(Workflow, run.workflow_id)
    graph = workflow.graph
    order = validate_graph(graph)
    definitions = {n["id"]: n for n in graph["nodes"]}
    rows = {n.node_id: n for n in db.scalars(select(NodeRun).where(NodeRun.run_id == run.id))}
    for key in order:
        if key not in rows:
            rows[key] = NodeRun(run_id=run.id, node_id=key, state="pending", output={})
            db.add(rows[key])
    db.flush()
    run.state = "running"
    context = {"input": run.input, "nodes": {i: {"output": r.output} for i, r in rows.items()}}
    try:
        for key in order:
            row, node = rows[key], definitions[key]
            if row.state in {"succeeded", "skipped", "failed", "cancelled"}:
                continue
            incoming = [e for e in graph["edges"] if e["to"] == key]
            if any(rows[e["from"]].state not in {"succeeded", "skipped", "cancelled"} for e in incoming):
                continue
            if incoming and not any(edge_selected(e, rows[e["from"]]) for e in incoming):
                row.state = "skipped"
                continue
            config = node.get("config", {})
            row.attempts += 1
            if node["type"] == "human_task":
                task = db.scalar(
                    select(HumanTask).where(HumanTask.run_id == run.id, HumanTask.node_id == key)
                )
                if task is None:
                    assignee = resolve(config["assigned_subject"], context)
                    if not isinstance(assignee, str) or not assignee or len(assignee) > 255:
                        raise AppError(
                            422, "assignee_unresolved", "Không phân giải được principal human task."
                        )
                    business_ref = resolve(config.get("external_business_ref"), context)
                    if business_ref is not None and (
                        not isinstance(business_ref, str) or len(business_ref) > 255
                    ):
                        raise AppError(
                            422, "invalid_business_reference", "Tham chiếu human task không hợp lệ."
                        )
                    task = HumanTask(
                        run_id=run.id,
                        node_id=key,
                        assigned_subject=assignee,
                        external_business_ref=business_ref,
                    )
                    db.add(task)
                    db.flush()
                if task.state != "completed":
                    row.state = "waiting"
                    continue
                row.output, row.state = task.result, "succeeded"
            elif node["type"] == "if":
                row.output, row.state = {"result": evaluate(config, context)}, "succeeded"
                db.add(DecisionTrace(
                    run_id=run.id,
                    node_id=key,
                    expression={field: config.get(field) for field in ("path", "operator", "value")},
                    evaluated_inputs={config["path"]: path_value(context, config["path"])},
                    result=row.output["result"],
                    selected_edges=[edge["to"] for edge in graph["edges"] if edge["from"] == key and edge_selected(edge, row)],
                ))
            elif node["type"] == "map":
                row.output, row.state = resolve(config.get("values", {}), context), "succeeded"
            else:
                row.output, row.state = {}, "succeeded"
            context["nodes"][key] = {"output": row.output}
        if all(r.state in {"succeeded", "skipped"} for r in rows.values()):
            run.state = "succeeded"
        elif any(r.state == "waiting" for r in rows.values()):
            run.state = "waiting"
    except AppError as exc:
        run.state, run.error = "failed", exc.code + ": " + exc.detail
    run.revision += 1
    run.updated_at = utcnow()
    db.flush()
    return run
