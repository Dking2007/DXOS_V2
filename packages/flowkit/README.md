<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: 2026 Desktiny contributors
-->

# dx-flowkit

Validate small JSON workflow graphs and dry-run them in memory. No dependencies, no
database, no network, no `eval`.

Extracted from the workflow engine of [Desktiny (DXOS V2)](../../README.md). The logic is
the same code the platform uses to check and preview workflows before they run for real.

*(Tiếng Việt: kiểm tra và chạy thử đồ thị quy trình dạng JSON ngay trong bộ nhớ, không cần
thư viện ngoài, không chạm vào dữ liệu thật.)*

## What it does

- `validate_graph(graph)` checks shape and size limits, unique ids, known node types,
  well-formed edges, exactly one `start` that reaches every node, an `end` on every
  branch, no cycles, and per-node configuration. It returns the node ids in
  topological order.
- `simulate_graph(graph, input, decisions)` walks the graph with the **same**
  condition and edge-selection functions a live run would use, and returns the path
  taken, each node's output and state, a decision trace for every `if` node, and the
  people a `human_task` would be assigned to. Human tasks wait unless you supply a
  decision for them.
- `evaluate`, `resolve`, `path_value`, `edge_selected` are the building blocks.

Every report has `execution_mode: "simulation"`, `actions: []` and
`effects_performed: False`.

## Example

```python
from dx_flowkit import simulate_graph

graph = {
    "nodes": [
        {"id": "start", "type": "start"},
        {"id": "check", "type": "if",
         "config": {"path": "$.input.amount", "operator": "gt", "value": 1000}},
        {"id": "manager", "type": "human_task",
         "config": {"assigned_subject": "$.input.manager"}},
        {"id": "auto", "type": "map", "config": {"values": {"approved": True}}},
        {"id": "end", "type": "end"},
    ],
    "edges": [
        {"from": "start", "to": "check"},
        {"from": "check", "to": "manager", "when": True},
        {"from": "check", "to": "auto", "when": False},
        {"from": "manager", "to": "end"},
        {"from": "auto", "to": "end"},
    ],
}

report = simulate_graph(graph, {"amount": 5000, "manager": "u-lead"})
report["state"]            # "waiting" (a person has to decide)
report["decision_traces"]  # why the amount check went to "manager"

done = simulate_graph(graph, {"amount": 5000, "manager": "u-lead"},
                      decisions={"manager": {"decision": "approved"}})
done["path"]               # ["start", "check", "manager", "end"]
```

Invalid input raises `FlowError` with a stable `code` such as `graph_cycle`,
`invalid_operator` or `assignee_unresolved`. Messages are English; map `code` if you need
another language.

## Node types and conditions

| Node | Purpose |
|---|---|
| `start` / `end` | Exactly one start; every branch ends at an end. |
| `if` | Compares `config.path` with `config.value` using `eq ne gt gte lt lte in exists`. Edges leaving it use `when: true/false` (or a string). |
| `map` | Builds output from `config.values`, resolving `$.path` / `${path}` references. |
| `human_task` | Needs `config.assigned_subject`. Waits for a decision in simulation. |

Paths read from `{"input": ..., "nodes": {<id>: {"output": ...}}}`. Keys starting with
`_` are never readable, and paths are limited to 300 characters.

## Limits (read before relying on it)

- This is a deliberately small engine: no parallel branches, loops, timers, or
  quorum rules. A graph is a DAG with one start.
- Simulation shows the logic path. It does **not** call external systems, so it cannot
  tell you whether an action would succeed.
- It does not run live workflows. Persistence, retries and locking are the host
  application's job (Desktiny does this in `dx_core.workflow.advance`).
- Conditions compare Python values: `"10" > 5` raises `condition_type_error`, it does
  not coerce.
- Version `0.1.0`, not yet published to PyPI.

## Development

```bash
pip install pytest .
python -m pytest
```

56 tests cover each operator, each validation error code, the simulation paths, and a
check that the package imports nothing outside the standard library and never calls
`eval`/`exec`.

## License

Apache-2.0.
