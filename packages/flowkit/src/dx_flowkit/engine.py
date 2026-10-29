# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Validation and side-effect-free simulation of small JSON workflow graphs.

A graph is ``{"nodes": [...], "edges": [...]}``. Node types are ``start``, ``map``,
``if``, ``human_task`` and ``end``. Conditions are data (a path, an operator, a value),
never code: nothing in this module calls ``eval`` or ``exec``.
"""

from collections import deque
from types import SimpleNamespace

from .errors import FlowError

NODE_TYPES = {"start", "map", "if", "human_task", "end"}
OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "exists"}
SETTLED = {"succeeded", "skipped", "cancelled"}


def path_value(context, path):
    """Read a dotted path such as ``$.input.amount`` from ``context``.

    Missing keys give ``None``. Keys that start with an underscore are never read.
    """
    if not isinstance(path, str) or len(path) > 300:
        raise FlowError("invalid_path", "Data path must be a string of at most 300 characters.")
    path = path.removeprefix("${").removesuffix("}").removeprefix("$.")
    result = context
    for key in path.split("."):
        if not key or key.startswith("_") or not isinstance(result, dict) or key not in result:
            return None
        result = result[key]
    return result


def resolve(value, context):
    """Replace ``$.path`` / ``${path}`` strings inside ``value`` with data from ``context``."""
    if isinstance(value, str) and (value.startswith("$.") or value.startswith("${")):
        return path_value(context, value)
    if isinstance(value, dict):
        return {k: resolve(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, context) for v in value]
    return value


def evaluate(condition, context):
    """Evaluate ``{"path", "operator", "value"}`` against ``context`` and return a bool."""
    operator = condition.get("operator", "eq")
    if not isinstance(operator, str) or operator not in OPERATORS:
        raise FlowError("invalid_operator", "Condition operator is not supported.")
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
        raise FlowError("condition_type_error", "Condition operands have incompatible types.") from None


def validate_graph(graph: dict, max_steps=100):
    """Check a graph and return its node ids in topological order.

    Raises ``FlowError`` for: wrong shape or size, duplicate or oversized ids, unknown
    node types, bad or duplicate edges, anything other than exactly one ``start``
    reaching every node, missing ``end``, cycles, and malformed node configuration.
    """
    if not isinstance(graph, dict):
        raise FlowError("invalid_graph", "A graph must be an object.")
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
        raise FlowError("invalid_graph", "A graph needs valid nodes and edges within the size limits.")
    ids = [n.get("id") for n in nodes]
    if any(not isinstance(i, str) or not i or len(i) > 80 for i in ids) or len(set(ids)) != len(ids):
        raise FlowError("invalid_node_ids", "Node ids must be unique strings of at most 80 characters.")
    if any(not isinstance(n.get("type"), str) or n["type"] not in NODE_TYPES for n in nodes):
        raise FlowError("unsupported_node", "A node has an unsupported type.")
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
            raise FlowError("invalid_edge", "An edge or its condition is invalid or duplicated.")
        seen.add((source, target))
        targets[source].append(target)
        degree[target] += 1
    starts = [n for n in nodes if n["type"] == "start"]
    roots = [i for i, d in degree.items() if d == 0]
    if len(starts) != 1 or roots != [starts[0]["id"]] or not any(n["type"] == "end" for n in nodes):
        raise FlowError(
            "invalid_roots", "A graph needs exactly one start and an end; every node must be reachable from start."
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
        raise FlowError("graph_cycle", "The graph has a cycle or an unreachable node.")
    for node in nodes:
        config = node.get("config", {})
        if not isinstance(config, dict):
            raise FlowError("invalid_node_config", "Node config must be an object.")
        if node["type"] == "if":
            operator = config.get("operator", "eq")
            if not isinstance(operator, str) or operator not in OPERATORS:
                raise FlowError("invalid_operator", "Operator is not supported.")
            if not isinstance(config.get("path"), str) or not config["path"] or len(config["path"]) > 300:
                raise FlowError("invalid_path", "An if node needs a valid data path.")
        if node["type"] == "map" and not isinstance(config.get("values", {}), dict):
            raise FlowError("invalid_mapping", "A map node's values must be an object.")
        if node["type"] == "human_task" and (
            not isinstance(config.get("assigned_subject"), str)
            or not config["assigned_subject"]
            or len(config["assigned_subject"]) > 255
        ):
            raise FlowError("assignee_required", "A human_task needs a valid assigned_subject.")
        if (
            node["type"] == "human_task"
            and config.get("external_business_ref") is not None
            and (
                not isinstance(config["external_business_ref"], str)
                or len(config["external_business_ref"]) > 255
            )
        ):
            raise FlowError("invalid_business_reference", "A human_task reference is invalid.")
        if node["type"] == "end" and targets[node["id"]]:
            raise FlowError("end_has_edges", "An end node cannot have outgoing edges.")
        if node["type"] != "end" and not targets[node["id"]]:
            raise FlowError("missing_end", "Every branch must finish at an end node.")
    return ordered


def edge_selected(edge, parent):
    """Whether ``edge`` is taken after ``parent`` (a node with ``state`` and ``output``) finished."""
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
    """Run a graph in memory and report the path taken. Nothing outside the arguments is touched.

    ``decisions`` maps a ``human_task`` node id to the output a person would give. A
    human task without a decision leaves the run ``waiting``. The report always has
    ``effects_performed: False`` and ``actions: []``.
    """
    order = validate_graph(graph)
    definitions = {node["id"]: node for node in graph["nodes"]}
    states = {node_id: SimpleNamespace(state="pending", output={}) for node_id in order}
    context = {"input": input_data, "nodes": {node_id: {"output": row.output} for node_id, row in states.items()}}
    traces, people = [], []
    decisions = decisions or {}
    for node_id in order:
        row, node = states[node_id], definitions[node_id]
        incoming = [edge for edge in graph["edges"] if edge["to"] == node_id]
        if any(states[edge["from"]].state not in SETTLED for edge in incoming):
            continue
        if incoming and not any(edge_selected(edge, states[edge["from"]]) for edge in incoming):
            row.state = "skipped"
            continue
        config = node.get("config", {})
        if node["type"] == "human_task":
            subject = resolve(config["assigned_subject"], context)
            if not isinstance(subject, str) or not subject:
                raise FlowError("assignee_unresolved", f"Step '{node_id}' has no resolvable assignee.")
            decision = decisions.get(node_id)
            people.append({"node_id": node_id, "subject": subject, "source": "fixture"})
            if decision is None:
                row.state = "waiting"
                continue
            if not isinstance(decision, dict):
                raise FlowError("invalid_fixture", "A simulated decision must be an object.")
            row.output, row.state = decision, "succeeded"
        elif node["type"] == "if":
            result = evaluate(config, context)
            row.output, row.state = {"result": result}, "succeeded"
            traces.append({
                "node_id": node_id,
                "expression": {key: config.get(key) for key in ("path", "operator", "value")},
                "evaluated_inputs": {config["path"]: path_value(context, config["path"])},
                "result": result,
                "selected_edges": [
                    edge["to"] for edge in graph["edges"] if edge["from"] == node_id and edge_selected(edge, row)
                ],
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
        "nodes": [
            {"node_id": node_id, "state": states[node_id].state, "output": states[node_id].output}
            for node_id in order
        ],
        "decision_traces": traces,
        "assignees": people,
        "actions": [],
        "effects_performed": False,
    }
