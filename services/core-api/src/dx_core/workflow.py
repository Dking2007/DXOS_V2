from collections import deque
from types import SimpleNamespace

from dx_platform.database import utcnow
from dx_platform.errors import AppError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DecisionTrace, HumanTask, NodeRun, Run, Workflow

NODE_TYPES = {"start", "map", "if", "human_task", "end"}
OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "exists"}


def path_value(context, path):
    if not isinstance(path, str) or len(path) > 300:
        raise AppError(422, "invalid_path", "Đường dẫn dữ liệu không hợp lệ.")
    path = path.removeprefix("${").removesuffix("}").removeprefix("$.")
    result = context
    for key in path.split("."):
        if not key or key.startswith("_") or not isinstance(result, dict) or key not in result:
            return None
        result = result[key]
    return result


def resolve(value, context):
    if isinstance(value, str) and (value.startswith("$.") or value.startswith("${")):
        return path_value(context, value)
    if isinstance(value, dict):
        return {k: resolve(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, context) for v in value]
    return value


def evaluate(condition, context):
    operator = condition.get("operator", "eq")
    if not isinstance(operator, str) or operator not in OPERATORS:
        raise AppError(422, "invalid_operator", "Toán tử điều kiện không được hỗ trợ.")
    left = path_value(context, condition.get("path", ""))
    right = resolve(condition.get("value"), context)
    if operator == "exists":
        return left is not None
    if operator == "eq":
        return left == right
    if operator == "ne":
        return left != right
    try:
        if operator == "gt":
            return left > right
        if operator == "gte":
            return left >= right
        if operator == "lt":
            return left < right
        if operator == "lte":
            return left <= right
        return left in right
    except TypeError:
        raise AppError(422, "condition_type_error", "Kiểu dữ liệu điều kiện không tương thích.") from None


def validate_graph(graph: dict, max_steps=100):
    if not isinstance(graph, dict):
        raise AppError(422, "invalid_graph", "Định nghĩa luồng phải là object.")
    nodes, edges = graph.get("nodes"), graph.get("edges")
    if (
        not isinstance(nodes, list)
        or not nodes
        or len(nodes) > max_steps
        or not isinstance(edges, list)
        or len(edges) > max_steps * max_steps
        or not all(isinstance(node, dict) for node in nodes)
        or not all(isinstance(edge, dict) for edge in edges)
    ):
        raise AppError(422, "invalid_graph", "Luồng cần nodes/edges hợp lệ và số node/cạnh trong giới hạn.")
    ids = [n.get("id") for n in nodes]
    if any(not isinstance(i, str) or not i or len(i) > 80 for i in ids) or len(set(ids)) != len(ids):
        raise AppError(422, "invalid_node_ids", "ID node phải duy nhất và tối đa 80 ký tự.")
    if any(not isinstance(n.get("type"), str) or n["type"] not in NODE_TYPES for n in nodes):
        raise AppError(422, "unsupported_node", "Loại node chưa được hỗ trợ trong bản pilot.")
    degree, targets = dict.fromkeys(ids, 0), {i: [] for i in ids}
    seen = set()
    for edge in edges:
        source, target = edge.get("from"), edge.get("to")
        if (
            not isinstance(source, str)
            or not isinstance(target, str)
            or source not in targets
            or target not in targets
            or source == target
            or (source, target) in seen
            or (edge.get("when") is not None and not isinstance(edge["when"], (bool, str)))
        ):
            raise AppError(422, "invalid_edge", "Cạnh hoặc điều kiện cạnh không hợp lệ hoặc trùng.")
        seen.add((source, target))
        targets[source].append(target)
        degree[target] += 1
    starts = [n for n in nodes if n["type"] == "start"]
    roots = [i for i, d in degree.items() if d == 0]
    if len(starts) != 1 or roots != [starts[0]["id"]] or not any(n["type"] == "end" for n in nodes):
        raise AppError(
            422, "invalid_roots", "Luồng cần đúng một start và có end; mọi node phải nối từ start."
        )
    queue, ordered = deque(roots), []
    while queue:
        current = queue.popleft()
        ordered.append(current)
        for target in targets[current]:
            degree[target] -= 1
            if not degree[target]:
                queue.append(target)
    if len(ordered) != len(nodes):
        raise AppError(422, "graph_cycle", "Luồng có chu trình hoặc node không thể tới.")
    for node in nodes:
        config = node.get("config", {})
        if not isinstance(config, dict):
            raise AppError(422, "invalid_node_config", "Config node phải là object.")
        if node["type"] == "if":
            operator = config.get("operator", "eq")
            if not isinstance(operator, str) or operator not in OPERATORS:
                raise AppError(422, "invalid_operator", "Toán tử không hợp lệ.")
            if not isinstance(config.get("path"), str) or not config["path"] or len(config["path"]) > 300:
                raise AppError(422, "invalid_path", "Node if cần đường dẫn dữ liệu hợp lệ.")
        if node["type"] == "map" and not isinstance(config.get("values", {}), dict):
            raise AppError(422, "invalid_mapping", "Kết quả map phải là object.")
        if node["type"] == "human_task" and (
            not isinstance(config.get("assigned_subject"), str)
            or not config["assigned_subject"]
            or len(config["assigned_subject"]) > 255
        ):
            raise AppError(422, "assignee_required", "Human task cần assigned_subject hợp lệ.")
        if (
            node["type"] == "human_task"
            and config.get("external_business_ref") is not None
            and (
                not isinstance(config["external_business_ref"], str)
                or len(config["external_business_ref"]) > 255
            )
        ):
            raise AppError(422, "invalid_business_reference", "Tham chiếu human task không hợp lệ.")
        if node["type"] == "end" and targets[node["id"]]:
            raise AppError(422, "end_has_edges", "Node end không được có cạnh đi ra.")
        if node["type"] != "end" and not targets[node["id"]]:
            raise AppError(422, "missing_end", "Nhánh cần kết thúc tại node end.")
    return ordered


def edge_selected(edge, parent):
    if parent.state != "succeeded":
        return False
    when = edge.get("when")
    if when is None:
        return True
    if isinstance(when, bool):
        return parent.output.get("result") is when
    if isinstance(when, str):
        return (
            parent.output.get("decision") == when or str(parent.output.get("result")).lower() == when.lower()
        )
    return False


def simulate_graph(graph: dict, input_data: dict, decisions: dict | None = None) -> dict:
    """Evaluate a graph in memory using the same condition and edge functions as live runs."""
    order = validate_graph(graph)
    definitions = {node["id"]: node for node in graph["nodes"]}
    states = {node_id: SimpleNamespace(state="pending", output={}) for node_id in order}
    context = {"input": input_data, "nodes": {node_id: {"output": row.output} for node_id, row in states.items()}}
    traces, people = [], []
    decisions = decisions or {}
    for node_id in order:
        row, node = states[node_id], definitions[node_id]
        incoming = [edge for edge in graph["edges"] if edge["to"] == node_id]
        if any(states[edge["from"]].state not in {"succeeded", "skipped", "cancelled"} for edge in incoming):
            continue
        if incoming and not any(edge_selected(edge, states[edge["from"]]) for edge in incoming):
            row.state = "skipped"
            continue
        config = node.get("config", {})
        if node["type"] == "human_task":
            subject = resolve(config["assigned_subject"], context)
            if not isinstance(subject, str) or not subject:
                raise AppError(422, "assignee_unresolved", f"Bước '{node_id}' thiếu người nhận.")
            decision = decisions.get(node_id)
            people.append({"node_id": node_id, "subject": subject, "source": "fixture"})
            if decision is None:
                row.state = "waiting"
                continue
            if not isinstance(decision, dict):
                raise AppError(422, "invalid_fixture", "Quyết định giả lập phải là object.")
            row.output, row.state = decision, "succeeded"
        elif node["type"] == "if":
            result = evaluate(config, context)
            row.output, row.state = {"result": result}, "succeeded"
            traces.append({
                "node_id": node_id,
                "expression": {key: config.get(key) for key in ("path", "operator", "value")},
                "evaluated_inputs": {config["path"]: path_value(context, config["path"])},
                "result": result,
                "selected_edges": [edge["to"] for edge in graph["edges"] if edge["from"] == node_id and edge_selected(edge, row)],
            })
        elif node["type"] == "map":
            row.output, row.state = resolve(config.get("values", {}), context), "succeeded"
        else:
            row.output, row.state = {}, "succeeded"
        context["nodes"][node_id] = {"output": row.output}
    return {
        "execution_mode": "simulation",
        "state": "waiting" if any(row.state == "waiting" for row in states.values()) else "succeeded",
        "path": [node_id for node_id in order if states[node_id].state in {"succeeded", "waiting"}],
        "nodes": [{"node_id": node_id, "state": states[node_id].state, "output": states[node_id].output} for node_id in order],
        "decision_traces": traces,
        "assignees": people,
        "actions": [],
        "effects_performed": False,
    }


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
