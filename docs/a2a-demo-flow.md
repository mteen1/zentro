# A2A Demo Flow

This demo shows Zentro as a project control plane for agent-to-agent task
delivery. It uses the real HTTP API and creates temporary demo records.

## Start The API

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.dev.yml up -d
```

## Run The Demo

```bash
python scripts/a2a_demo.py
```

Optional:

```bash
python scripts/a2a_demo.py --base-url http://127.0.0.1:8000
```

## What The Script Does

1. Reads the public Zentro agent card from `/.well-known/agent-card.json`.
2. Registers and authenticates a temporary demo user.
3. Creates a project and a canonical Zentro task.
4. Registers a planner agent and backend engineer agent.
5. Creates an agent task link for the Zentro task.
6. Delegates the task from planner to backend engineer.
7. Accepts the task.
8. Adds an agent message.
9. Publishes a test-report artifact.
10. Reads back messages, artifacts, recent project activity, and the audit event
    timeline.

## Product Signals To Show

- Zentro tasks remain canonical project-management objects.
- Agent task protocol state lives beside the task instead of replacing task
  status.
- Handoffs are explicit actions, not only chat text.
- Messages and artifacts are durable task history.
- Audit events use a CloudEvents-style envelope for future broker routing.

## Manual API Walkthrough

After the script runs, open:

```text
http://127.0.0.1:8000/api/docs
```

Use the IDs printed by the script with these endpoints:

```http
GET /api/agent-tasks/{task_link_id}
GET /api/agent-tasks/{task_link_id}/messages
GET /api/agent-tasks/{task_link_id}/artifacts
GET /api/agent-tasks/{task_link_id}/events
GET /api/projects/{project_id}/agent-activity
```

The event timeline should include:

```text
zentro.agent_task.created
zentro.agent_task.delegated
zentro.agent_task.accepted
zentro.agent_task.message.created
zentro.agent_task.artifact.created
```

