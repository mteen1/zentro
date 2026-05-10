[▶ Watch the Zentro demo video](https://drive.google.com/file/d/1Sg-xBoOBvoNZ5LwCoLAwT9rvtjgYMyaA/view?usp=sharing)

Powered by NotebookLM.

# Zentro

Zentro is a FastAPI backend for agentic project management. It keeps the normal
project-management model - projects, epics, sprints, tasks, users, roles, and
permissions - and adds an internal agent-to-agent coordination layer for
delegating and auditing task delivery.

The frontend lives in a separate repository. This repository is the API,
database, migrations, background worker, and agent coordination backend.

## Why It Exists

Most project tools assume a human is the primary worker. Zentro is designed for a
mixed team where humans define goals and constraints, while agents can claim,
delegate, execute, block, review, and hand off work with a durable audit trail.

The current A2A layer is intentionally internal-first. It borrows the useful
shape of the Agent2Agent protocol - agent cards, task state, messages, parts,
artifacts, and event history - without committing early to every external
protocol edge case.

## Highlights

- FastAPI API with SQLAlchemy async models and Alembic migrations.
- JWT auth, users, project roles, and project/task permissions.
- Project management primitives: projects, epics, sprints, tasks, priorities,
  task status, task assignment, and reporting endpoints.
- Project agent endpoints with streaming and non-streaming responses.
- Agent registry with searchable skills and public agent cards.
- Agent task links that map canonical Zentro tasks to A2A-style protocol state.
- Durable agent messages and artifacts linked to project tasks.
- Append-only CloudEvents-style audit events for handoffs and task activity.
- Redis, RabbitMQ, Taskiq, OpenTelemetry, Prometheus, Jaeger, and Langfuse
  integration points.
- Dockerized local development and GitLab CI image publishing.

## Architecture

```text
Client / Frontend
      |
      v
FastAPI application
      |
      +-- auth
      +-- project_manager
      |     projects, epics, sprints, tasks, roles, permissions
      |
      +-- intelligence_manager
      |     project agent, chat history, streaming responses, Langfuse hooks
      |
      +-- agent_manager
      |     agent registry, task links, messages, artifacts, handoffs, events
      |
      +-- services
            Redis, RabbitMQ, Taskiq worker integrations
```

Database migrations live in `zentro/db/migrations`. Models are loaded from the
configured app list in `zentro/settings.py`.

## Quickstart

Start the full local stack:

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.dev.yml up -d
```

Open the API docs:

```text
http://127.0.0.1:8000/api/docs
```

Run tests inside Docker:

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.dev.yml run --rm --no-deps api pytest -q
```

Run the A2A product demo against the local API:

```bash
python scripts/a2a_demo.py
```

Or with `just`:

```bash
just demo-a2a
```

The demo script registers a temporary user, creates a project and task, registers
planner/backend agents, creates an agent task link, delegates work, accepts the
handoff, writes an agent message, publishes a test-report artifact, and prints
the resulting event timeline/read model.

## A2A Demo Flow

The shortest reviewer path is:

1. Start the stack.
2. Run `python scripts/a2a_demo.py`.
3. Open `/api/docs`.
4. Inspect the printed agent task, messages, artifacts, and events.

Core endpoints:

```http
GET    /.well-known/agent-card.json
GET    /api/agents
POST   /api/agents
GET    /api/agents/{agent_id}/card
POST   /api/projects/{project_id}/agent-tasks
GET    /api/projects/{project_id}/agent-tasks
GET    /api/projects/{project_id}/agent-activity
GET    /api/agent-tasks/{task_link_id}
POST   /api/agent-tasks/{task_link_id}/delegate
POST   /api/agent-tasks/{task_link_id}/accept
POST   /api/agent-tasks/{task_link_id}/reject
POST   /api/agent-tasks/{task_link_id}/cancel
POST   /api/agent-tasks/{task_link_id}/messages
GET    /api/agent-tasks/{task_link_id}/messages
POST   /api/agent-tasks/{task_link_id}/artifacts
GET    /api/agent-tasks/{task_link_id}/artifacts
GET    /api/agent-tasks/{task_link_id}/events
```

More detail is in `docs/a2a-demo-flow.md`.

## CI/CD And Deployment

GitLab CI builds and pushes Docker images from `main`:

```text
registry.gitlab.com/m.moharami/zentro:sha-<commit>
registry.gitlab.com/m.moharami/zentro:prod
```

The deployment repository at `../zentro-deploy` consumes the `:prod` image as
`ZENTRO_API_IMAGE=registry.gitlab.com/m.moharami/zentro:prod` in
`env/apps.env`. Its compose setup runs the API, Taskiq worker, Postgres, Redis,
RabbitMQ, Traefik routing, and the separate frontend image.

## Development Commands

```bash
just install      # poetry install
just dev          # docker compose development stack with source mounted
just test         # dockerized test run
just demo-a2a     # run the A2A demo script against localhost:8000
```

Without `just`, use Poetry or Docker directly:

```bash
poetry install
poetry run pytest
docker compose -f docker-compose.yml -f deploy/docker-compose.dev.yml up -d
```

## Configuration

Settings use the `ZENTRO_` environment variable prefix. Common values:

```bash
ZENTRO_HOST=0.0.0.0
ZENTRO_PORT=8000
ZENTRO_ENVIRONMENT=dev
ZENTRO_DB_HOST=zentro-db
ZENTRO_DB_PORT=5432
ZENTRO_DB_USER=zentro
ZENTRO_DB_PASS=zentro
ZENTRO_DB_BASE=zentro
ZENTRO_REDIS_HOST=zentro-redis
ZENTRO_RABBIT_HOST=zentro-rmq
ZENTRO_NVIDIA_API_KEY=<optional-model-key>
ZENTRO_LANGFUSE_HOST=<optional-langfuse-host>
```

See `zentro/settings.py` for the full list.

## Migrations

```bash
alembic upgrade head
alembic downgrade <revision_id>
alembic revision --autogenerate -m "describe change"
```

The local Docker compose includes a migrator service for applying migrations in
the containerized stack.

## Observability

OpenTelemetry collector and Jaeger can run alongside the app:

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.otlp.yml up
```

Jaeger is typically available at:

```text
http://127.0.0.1:16686
```

Langfuse tracing is enabled when the Langfuse environment variables are
configured.

## Repository Map

```text
zentro/
  agent_manager/        A2A-inspired registry, task links, events, messages
  auth/                 JWT auth endpoints and dependencies
  db/                   SQLAlchemy base, migrations, models, DAO helpers
  intelligence_manager/ Project agent, prompts, tools, chat services
  project_manager/      Projects, epics, sprints, tasks, roles, permissions
  services/             Redis and RabbitMQ integrations
  web/                  FastAPI application and API routers
scripts/
  a2a_demo.py           End-to-end A2A API demo script
docs/
  agent-to-agent-platform-design.md
  a2a-demo-flow.md
tests/
  API and service tests
```
