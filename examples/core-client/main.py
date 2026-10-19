"""Exercise Core without importing or contacting Workspace."""

import argparse
import os
import uuid

import httpx


def main():
    parser = argparse.ArgumentParser(description="Minh chứng Core độc lập với Workspace")
    parser.add_argument("--base-url", default="http://localhost:8080/core/v1")
    parser.add_argument(
        "--token-env", default="DX_CORE_TOKEN", help="Biến môi trường chứa access token audience dx-core"
    )
    args = parser.parse_args()
    token = os.environ.get(args.token_env)
    if not token:
        parser.error(f"Cần access token trong biến {args.token_env}; không truyền token trên command line")
    with httpx.Client(
        base_url=args.base_url.rstrip("/") + "/", headers={"Authorization": "Bearer " + token}, timeout=30
    ) as client:

        def call(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        principal = call("GET", "principals/me")
        suffix = uuid.uuid4().hex[:8]
        schema = call(
            "POST",
            "schemas",
            json={
                "name": "equipment_check_" + suffix,
                "json_schema": {
                    "type": "object",
                    "properties": {"equipment": {"type": "string"}, "passed": {"type": "boolean"}},
                    "required": ["equipment", "passed"],
                    "additionalProperties": False,
                },
            },
        )
        call("POST", f"schemas/{schema['id']}/publish", json={"expected_revision": schema["revision"]})
        record = call(
            "POST",
            "records",
            json={
                "schema_id": schema["id"],
                "payload": {"equipment": "Máy in phòng tiếp nhận", "passed": True},
            },
            headers={"Idempotency-Key": "equipment-record-" + suffix},
        )
        data = "Phiếu kiểm tra thiết bị — dữ liệu demo".encode()
        upload = call(
            "POST", "storage/uploads", json={"name": "equipment.txt", "mime": "text/plain", "size": len(data)}
        )
        call("PUT", f"storage/uploads/{upload['id']}/content", content=data)
        file = call("POST", f"storage/uploads/{upload['id']}/complete")
        workflow = call(
            "POST",
            "workflows",
            json={
                "name": "Equipment check " + suffix,
                "graph": {
                    "nodes": [
                        {"id": "start", "type": "start"},
                        {
                            "id": "map",
                            "type": "map",
                            "config": {"values": {"equipment": "$.input.equipment", "reviewed": True}},
                        },
                        {"id": "end", "type": "end"},
                    ],
                    "edges": [{"from": "start", "to": "map"}, {"from": "map", "to": "end"}],
                },
            },
        )
        call("POST", f"workflows/{workflow['id']}/publish", json={"expected_revision": workflow["revision"]})
        run = call(
            "POST",
            f"workflows/{workflow['id']}/runs",
            json={"external_key": "equipment-run-" + suffix, "input": {"equipment": "Máy in"}},
            headers={"Idempotency-Key": "equipment-run-" + suffix},
        )
        assert run["state"] == "succeeded", run
        print(
            f"Core độc lập OK: namespace={principal['application']} schema={schema['id']} record={record['id']} file={file['id']} run={run['id']}"
        )


if __name__ == "__main__":
    main()
