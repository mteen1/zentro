#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ApiClient:
    base_url: str
    token: str | None = None
    opener: urllib.request.OpenerDirector = field(
        default_factory=lambda: urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
        ),
    )

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        form: dict[str, str] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        url = f"{self.base_url}{path}"
        headers: dict[str, str] = {}
        data = None
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if form is not None:
            data = urllib.parse.urlencode(form).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=10) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8")
            raise RuntimeError(f"{method} {path} failed: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach {self.base_url}. Start the API first.",
            ) from exc

        if not raw:
            return {}
        return json.loads(raw)


def print_step(title: str, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    print(f"\n== {title} ==")
    print(json.dumps(payload, indent=2, sort_keys=True))


def as_dict(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("Expected an object response")
    return payload


def as_list(payload: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise TypeError("Expected a list response")
    return payload


def run_demo(base_url: str) -> None:
    client = ApiClient(base_url=base_url.rstrip("/"))
    suffix = str(int(time.time()))
    email = f"a2a-demo-{suffix}@example.com"
    password = "demo-password-123"

    print(f"Running Zentro A2A demo against {client.base_url}")

    agent_card = client.request("GET", "/.well-known/agent-card.json")
    print_step("Public agent card", agent_card)

    client.request(
        "POST",
        "/api/users/register",
        body={
            "email": email,
            "password": password,
            "full_name": "A2A Demo Reviewer",
            "active": True,
        },
    )
    token = as_dict(
        client.request(
            "POST",
            "/api/token",
            form={"username": email, "password": password},
        ),
    )
    client.token = token["access_token"]
    print_step("Authenticated demo user", {"email": email})

    project = as_dict(
        client.request(
            "POST",
            "/api/projects",
            body={
                "name": f"A2A Demo Project {suffix}",
                "key": f"A2A{suffix[-6:]}",
                "description": "Demo project for agent-to-agent task delivery.",
            },
        ),
    )
    print_step("Created project", project)

    task = as_dict(
        client.request(
            "POST",
            "/api/projects/tasks",
            body={
                "project_id": project["id"],
                "title": "Implement board CRUD with tests",
                "description": (
                    "Planner delegates backend work, backend accepts it, "
                    "then publishes a test report artifact."
                ),
                "status": "todo",
                "priority": "high",
            },
        ),
    )
    print_step("Created canonical Zentro task", task)

    planner = as_dict(
        client.request(
            "POST",
            "/api/agents",
            body={
                "slug": f"planner-{suffix}",
                "display_name": "Planner Agent",
                "description": "Breaks project objectives into executable handoffs.",
                "provider": "local-demo",
                "capabilities": {"delegation": True, "planning": True},
                "skills": [
                    {
                        "name": "planning",
                        "description": "Turns goals into tasks and delegation context.",
                        "input_modes": ["text", "data"],
                        "output_modes": ["data"],
                        "tags": ["planning", "handoff"],
                    },
                ],
            },
        ),
    )
    backend = as_dict(
        client.request(
            "POST",
            "/api/agents",
            body={
                "slug": f"backend-engineer-{suffix}",
                "display_name": "Backend Engineer Agent",
                "description": "Implements backend APIs, migrations, and tests.",
                "provider": "local-demo",
                "capabilities": {"python": True, "fastapi": True, "testing": True},
                "skills": [
                    {
                        "name": "backend-implementation",
                        "description": "Builds FastAPI services and test coverage.",
                        "input_modes": ["text", "data"],
                        "output_modes": ["text", "data", "file"],
                        "tags": ["fastapi", "sqlalchemy", "pytest"],
                    },
                ],
            },
        ),
    )
    print_step(
        "Registered agents",
        {
            "planner": {"id": planner["id"], "slug": planner["slug"]},
            "backend": {"id": backend["id"], "slug": backend["slug"]},
        },
    )

    agent_task = as_dict(
        client.request(
            "POST",
            f"/api/projects/{project['id']}/agent-tasks",
            body={
                "task_id": task["id"],
                "active_agent_id": planner["id"],
                "requires_human_approval": True,
                "message": {
                    "message_id": f"msg-demo-{suffix}",
                    "role": "user",
                    "parts": [
                        {
                            "kind": "data",
                            "data": {
                                "objective": "Implement board CRUD",
                                "constraints": ["keep auth intact", "add tests"],
                                "definition_of_done": [
                                    "migration exists",
                                    "API tests pass",
                                    "artifact is attached",
                                ],
                            },
                        },
                    ],
                },
            },
        ),
    )
    print_step("Created agent task link", agent_task)

    delegated = client.request(
        "POST",
        f"/api/agent-tasks/{agent_task['id']}/delegate",
        body={
            "target_agent_id": backend["id"],
            "source_agent_id": planner["id"],
            "reason": "Backend implementation required",
            "handoff_summary": "Create the API, migration, and focused tests.",
        },
    )
    accepted = client.request("POST", f"/api/agent-tasks/{agent_task['id']}/accept")
    print_step("Delegated and accepted", {"delegated": delegated, "accepted": accepted})

    message = client.request(
        "POST",
        f"/api/agent-tasks/{agent_task['id']}/messages",
        body={
            "role": "agent",
            "sender_agent_id": backend["id"],
            "parts": [
                {
                    "kind": "data",
                    "data": {
                        "status": "working",
                        "summary": "API and migration implemented; tests are running.",
                    },
                },
            ],
        },
    )
    artifact = client.request(
        "POST",
        f"/api/agent-tasks/{agent_task['id']}/artifacts",
        body={
            "name": "pytest-report",
            "mime_type": "application/json",
            "created_by_agent_id": backend["id"],
            "parts": [
                {
                    "kind": "data",
                    "data": {
                        "command": "pytest tests/test_agent_manager.py -q",
                        "result": "passed",
                    },
                },
            ],
        },
    )
    print_step("Message and artifact", {"message": message, "artifact": artifact})

    messages = as_list(
        client.request("GET", f"/api/agent-tasks/{agent_task['id']}/messages"),
    )
    artifacts = as_list(
        client.request("GET", f"/api/agent-tasks/{agent_task['id']}/artifacts"),
    )
    events = as_list(client.request("GET", f"/api/agent-tasks/{agent_task['id']}/events"))
    activity = client.request("GET", f"/api/projects/{project['id']}/agent-activity")

    print_step(
        "Demo read model",
        {
            "message_count": len(messages),
            "artifact_count": len(artifacts),
            "event_types": [event["type"] for event in events],
            "activity": activity,
        },
    )

    print("\nDemo complete. Useful URLs:")
    print(f"- OpenAPI docs: {client.base_url}/api/docs")
    print(f"- Agent card: {client.base_url}/.well-known/agent-card.json")
    print(f"- Agent task: {client.base_url}/api/agent-tasks/{agent_task['id']}")
    print(f"- Event timeline: {client.base_url}/api/agent-tasks/{agent_task['id']}/events")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Zentro A2A API demo.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL for the running Zentro API.",
    )
    args = parser.parse_args()

    try:
        run_demo(args.base_url)
    except Exception as exc:
        print(f"Demo failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
