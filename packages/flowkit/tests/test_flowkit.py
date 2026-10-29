# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
import ast
import copy
from pathlib import Path

import pytest
from dx_flowkit import (
    FlowError,
    evaluate,
    path_value,
    resolve,
    simulate_graph,
    validate_graph,
)


def node(node_id, kind, **config):
    return {"id": node_id, "type": kind, "config": config}


def edge(source, target, when=None):
    return {"from": source, "to": target, **({} if when is None else {"when": when})}


def approval_graph():
    return {
        "nodes": [
            node("start", "start"),
            node("check", "if", path="$.input.amount", operator="gt", value=1000),
            node("manager", "human_task", assigned_subject="$.input.manager"),
            node("auto", "map", values={"approved": True, "by": "system"}),
            node("end", "end"),
        ],
        "edges": [
            edge("start", "check"),
            edge("check", "manager", True),
            edge("check", "auto", False),
            edge("manager", "end"),
            edge("auto", "end"),
        ],
    }


def code(graph):
    with pytest.raises(FlowError) as raised:
        validate_graph(graph)
    return raised.value.code


# ---- path_value / resolve ----------------------------------------------------------


def test_path_value_reads_nested_and_missing_keys():
    context = {"input": {"a": {"b": 3}}}
    assert path_value(context, "$.input.a.b") == 3
    assert path_value(context, "${input.a.b}") == 3
    assert path_value(context, "$.input.a.missing") is None
    assert path_value(context, "$.input.a.b.c") is None


@pytest.mark.parametrize("path", ["$.input._secret", "$._hidden", "$.input..x", "$."])
def test_path_value_never_reads_private_or_empty_keys(path):
    assert path_value({"input": {"_secret": 1}, "_hidden": 2}, path) is None


@pytest.mark.parametrize("path", [None, 5, ["a"], "x" * 301])
def test_path_value_rejects_bad_paths(path):
    with pytest.raises(FlowError) as raised:
        path_value({}, path)
    assert raised.value.code == "invalid_path"


def test_resolve_walks_dicts_and_lists_and_leaves_plain_values():
    context = {"input": {"n": 7, "who": "ann"}}
    value = {"a": "$.input.n", "b": ["${input.who}", "literal", 3], "c": {"d": "$.input.missing"}}
    assert resolve(value, context) == {"a": 7, "b": ["ann", "literal", 3], "c": {"d": None}}


# ---- evaluate ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("operator", "left", "right", "expected"),
    [
        ("eq", 5, 5, True),
        ("eq", 5, 6, False),
        ("ne", 5, 6, True),
        ("gt", 5, 4, True),
        ("gt", 5, 5, False),
        ("gte", 5, 5, True),
        ("lt", 4, 5, True),
        ("lte", 5, 5, True),
        ("in", "a", ["a", "b"], True),
        ("in", "z", ["a", "b"], False),
    ],
)
def test_evaluate_operators(operator, left, right, expected):
    context = {"input": {"x": left}}
    assert evaluate({"path": "$.input.x", "operator": operator, "value": right}, context) is expected


def test_evaluate_exists_and_value_from_context():
    context = {"input": {"x": 1, "limit": 1}}
    assert evaluate({"path": "$.input.x", "operator": "exists"}, context) is True
    assert evaluate({"path": "$.input.y", "operator": "exists"}, context) is False
    assert evaluate({"path": "$.input.x", "value": "$.input.limit"}, context) is True


def test_evaluate_rejects_unknown_operator_and_type_mismatch():
    with pytest.raises(FlowError) as raised:
        evaluate({"path": "$.input.x", "operator": "regex", "value": "a"}, {"input": {"x": "a"}})
    assert raised.value.code == "invalid_operator"
    with pytest.raises(FlowError) as raised:
        evaluate({"path": "$.input.x", "operator": "gt", "value": 3}, {"input": {"x": "text"}})
    assert raised.value.code == "condition_type_error"
    with pytest.raises(FlowError) as raised:
        evaluate({"path": "$.input.x", "operator": "in", "value": 5}, {"input": {"x": 1}})
    assert raised.value.code == "condition_type_error"


# ---- validate_graph ----------------------------------------------------------------


def test_valid_graph_returns_topological_order_starting_at_start():
    order = validate_graph(approval_graph())
    assert order[0] == "start" and order[-1] == "end"
    assert order.index("check") < order.index("manager")
    assert sorted(order) == sorted(["start", "check", "manager", "auto", "end"])


@pytest.mark.parametrize("graph", [None, [], "x", {}, {"nodes": [], "edges": []}, {"nodes": [1], "edges": []}])
def test_malformed_shapes_are_validation_errors(graph):
    assert code(graph) in {"invalid_graph"}


def test_size_limits():
    graph = approval_graph()
    with pytest.raises(FlowError) as raised:
        validate_graph(graph, max_steps=3)
    assert raised.value.code == "invalid_graph"


def test_duplicate_and_oversized_ids():
    graph = approval_graph()
    graph["nodes"][1]["id"] = "start"
    assert code(graph) == "invalid_node_ids"
    graph = approval_graph()
    graph["nodes"][1]["id"] = "n" * 81
    assert code(graph) == "invalid_node_ids"


def test_unknown_node_type():
    graph = approval_graph()
    graph["nodes"][3]["type"] = "script"
    assert code(graph) == "unsupported_node"


@pytest.mark.parametrize(
    "bad_edge",
    [
        edge("start", "start"),
        edge("start", "ghost"),
        edge("start", "check"),
        {"from": "start", "to": "check", "when": 3},
    ],
)
def test_bad_edges(bad_edge):
    graph = approval_graph()
    graph["edges"].append(bad_edge)
    assert code(graph) == "invalid_edge"


def test_cycle_is_rejected():
    graph = {
        "nodes": [
            node("start", "start"),
            node("a", "map"),
            node("b", "map"),
            node("end", "end"),
        ],
        "edges": [edge("start", "a"), edge("a", "b"), edge("b", "a"), edge("b", "end")],
    }
    assert code(graph) in {"graph_cycle", "invalid_roots"}


def test_needs_exactly_one_start_and_an_end():
    graph = approval_graph()
    graph["nodes"].append(node("second", "start"))
    graph["edges"].append(edge("second", "end"))
    assert code(graph) == "invalid_roots"
    graph = approval_graph()
    graph["nodes"][-1]["type"] = "map"
    assert code(graph) == "invalid_roots"


def test_orphan_node_is_rejected():
    graph = approval_graph()
    graph["nodes"].append(node("orphan", "map"))
    graph["edges"].append(edge("orphan", "end"))
    assert code(graph) == "invalid_roots"


def test_branch_must_finish_and_end_has_no_exit():
    graph = approval_graph()
    graph["edges"] = [e for e in graph["edges"] if e["from"] != "auto"]
    assert code(graph) == "missing_end"
    graph = approval_graph()
    graph["nodes"].append(node("tail", "end"))
    graph["edges"].append(edge("end", "tail"))
    assert code(graph) == "end_has_edges"


@pytest.mark.parametrize(
    ("index", "config", "expected"),
    [
        (1, {"path": "$.input.a", "operator": "regex"}, "invalid_operator"),
        (1, {"operator": "eq"}, "invalid_path"),
        (1, {"path": "", "operator": "eq"}, "invalid_path"),
        (3, {"values": []}, "invalid_mapping"),
        (2, {}, "assignee_required"),
        (2, {"assigned_subject": "x" * 256}, "assignee_required"),
        (2, {"assigned_subject": "a", "external_business_ref": 5}, "invalid_business_reference"),
    ],
)
def test_node_config_checks(index, config, expected):
    graph = approval_graph()
    graph["nodes"][index]["config"] = config
    assert code(graph) == expected


def test_non_object_config_is_rejected():
    graph = approval_graph()
    graph["nodes"][3]["config"] = "text"
    assert code(graph) == "invalid_node_config"


# ---- simulate_graph ----------------------------------------------------------------


def test_branch_taken_when_condition_true_waits_for_person():
    report = simulate_graph(approval_graph(), {"amount": 5000, "manager": "u-lead"})
    states = {n["node_id"]: n["state"] for n in report["nodes"]}
    assert states == {"start": "succeeded", "check": "succeeded", "manager": "waiting", "auto": "skipped", "end": "pending"}
    assert report["state"] == "waiting"
    assert report["assignees"] == [{"node_id": "manager", "subject": "u-lead", "source": "fixture"}]
    trace = report["decision_traces"][0]
    assert trace["result"] is True and trace["selected_edges"] == ["manager"]
    assert trace["evaluated_inputs"] == {"$.input.amount": 5000}


def test_decision_fixture_completes_the_run():
    report = simulate_graph(
        approval_graph(), {"amount": 5000, "manager": "u-lead"}, {"manager": {"decision": "approved"}}
    )
    states = {n["node_id"]: n["state"] for n in report["nodes"]}
    assert states["manager"] == "succeeded" and states["end"] == "succeeded"
    assert report["state"] == "succeeded"
    assert report["path"] == ["start", "check", "manager", "end"]


def test_other_branch_runs_map_without_people():
    report = simulate_graph(approval_graph(), {"amount": 10, "manager": "u-lead"})
    outputs = {n["node_id"]: n["output"] for n in report["nodes"]}
    assert outputs["auto"] == {"approved": True, "by": "system"}
    assert report["assignees"] == [] and report["state"] == "succeeded"
    assert report["path"] == ["start", "check", "auto", "end"]


def test_report_never_claims_side_effects_and_input_is_untouched():
    data = {"amount": 5000, "manager": "u-lead", "nested": {"k": [1, 2]}}
    snapshot = copy.deepcopy(data)
    report = simulate_graph(approval_graph(), data)
    assert report["execution_mode"] == "simulation"
    assert report["effects_performed"] is False and report["actions"] == []
    assert data == snapshot


def test_unresolvable_assignee_and_bad_fixture_are_errors():
    with pytest.raises(FlowError) as raised:
        simulate_graph(approval_graph(), {"amount": 5000})
    assert raised.value.code == "assignee_unresolved"
    with pytest.raises(FlowError) as raised:
        simulate_graph(approval_graph(), {"amount": 5000, "manager": "u"}, {"manager": "yes"})
    assert raised.value.code == "invalid_fixture"


def test_string_edge_matches_decision_or_result():
    graph = {
        "nodes": [
            node("start", "start"),
            node("review", "human_task", assigned_subject="u1"),
            node("ok", "end"),
            node("no", "end"),
        ],
        "edges": [edge("start", "review"), edge("review", "ok", "approved"), edge("review", "no", "rejected")],
    }
    report = simulate_graph(graph, {}, {"review": {"decision": "rejected"}})
    states = {n["node_id"]: n["state"] for n in report["nodes"]}
    assert states["no"] == "succeeded" and states["ok"] == "skipped"


def test_invalid_graph_is_rejected_before_any_simulation():
    graph = approval_graph()
    graph["nodes"][3]["type"] = "script"
    with pytest.raises(FlowError):
        simulate_graph(graph, {})


# ---- safety ------------------------------------------------------------------------


def test_package_never_executes_user_code_and_has_no_dependencies():
    source = Path(__file__).resolve().parents[1] / "src" / "dx_flowkit"
    for path in source.glob("*.py"):
        for found in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(found, ast.Call) and isinstance(found.func, ast.Name):
                assert found.func.id not in {"eval", "exec", "compile", "__import__"}, path
    imported = set()
    for path in source.glob("*.py"):
        for found in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(found, ast.Import):
                imported.update(a.name.split(".")[0] for a in found.names)
            elif isinstance(found, ast.ImportFrom) and found.level == 0:
                imported.add((found.module or "").split(".")[0])
    assert imported <= {"collections", "types"}
