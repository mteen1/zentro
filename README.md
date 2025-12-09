# zentro - agentic task management system

![LangChain](https://img.shields.io/badge/langchain-%231C3C3C.svg?style=for-the-badge&logo=langchain&logoColor=white) ![LangGraph](https://img.shields.io/badge/langgraph-%231C3C3C.svg?style=for-the-badge&logo=langgraph&logoColor=white) ![Langfuse](https://img.shields.io/badge/LANGFUSE-8A2BE2) ![DeepSeek](https://custom-icon-badges.demolab.com/badge/Deepseek-4D6BFF?logo=deepseek&logoColor=fff)
![Nvidia](https://img.shields.io/badge/NVIDIA-76B900?logo=nvidia&logoColor=fff)

Tired of Jira's complexity? zentro is a smaller, easier-to-use task management system built with FastAPI and SQLAlchemy. It focuses on straightforward task and project workflows and includes optional integrations for background processing and observability.

Maintained by an engineer who has worked with real-world stacks (message brokers, tracing, reverse proxies). The README keeps things practical and focused — no marketing fluff.

### List of features

Basic task and project management:
- CRUD operations for tasks
- Task assignment to users
- Due dates, sprints, epics and projects
- User management and permissions

Background processing:
- Optional Redis integration for caching and simple pub/sub
- Optional RabbitMQ integration for background jobs

Monitoring and tracing:
- Optional OpenTelemetry support (can be run with the provided OTLP docker-compose)
- Optional Prometheus and Jaeger support for metrics and traces
- Optional Langfuse support for detailed agent traces

Agent capabilities
- Project agent: a programmatic agent that can read and change project data using a small set of tools
- Persistent async checkpointer: keeps a connection open to store agent conversations and state
- Optional Langfuse callback handler for agent traces when configured
- Streaming and non-streaming agent APIs: `run_agent`, `stream_agent`, `get_chat_history`, `shutdown_agent`
- Supported tools include project and task operations such as: `project_get`, `project_list`, `project_members_list`, `task_create`, `task_get`, `task_update`, `task_delete`, `task_assign`, `task_unassign`, `task_list_my`, `task_search`, `task_stats_by_status`, `epic_list`, `epic_get`, `sprint_list`, `sprint_get_active`

Notes about the agent:
- The agent uses a configurable model client and an AsyncPostgresSaver checkpointer opened in the background to persist conversation state.
- Langfuse integration and the model endpoint are optional and enabled by environment variables.
 - The agent uses a configurable model client and an AsyncPostgresSaver checkpointer opened in the background to persist conversation state.
 - By default the project is set up to use NVIDIA as a model provider (DeepSeek) via the configured API endpoint; this is configurable through environment variables.
 - Langfuse integration and the model endpoint are optional and enabled by environment variables.
 - Traefik is used as the reverse proxy in the included deployment compose files.








## Development

This repo includes a `Justfile` as a convenience for common development commands.

Install `just` from https://github.com/casey/just and run the app in development with:

```bash
just dev # for development
just install # for local installation using poetry
just test # for running tessts inside docker
```


## Project structure

The `zentro` package contains the application code. Key directories and files:

```bash
zentro/
- auth/           # auth endpoints and dependencies
- db/             # database setup, models and migrations
- intelligence_manager/  # project agent, prompts, tools and services
- project_manager/ # project-related business logic
- services/       # redis, rabbit and other integrations
- web/            # FastAPI application and API router
__main__.py       # start the app with uvicorn
settings.py       # configuration (uses pydantic BaseSettings)
tests/            # unit and integration tests
```

## Configuration

Configure the application with environment variables. By default, settings use the `ZENTRO_` prefix.

Create a `.env` file in the project root and set values such as database URL, API keys and other flags. For example:

```bash
ZENTRO_RELOAD=True
ZENTRO_PORT=8000
ZENTRO_ENVIRONMENT=dev
ZENTRO_DB_URL=postgresql+asyncpg://zentro:zentro@localhost:5432/zentro
ZENTRO_NVIDIA_API_KEY=<your-key>
```

See `zentro/settings.py` for available settings and the `env_prefix` if you need to change the prefix.
## OpenTelemetry

To run the OpenTelemetry collector and Jaeger alongside the app, add the OTLP compose file:

```bash
docker-compose -f docker-compose.yml -f deploy/docker-compose.otlp.yml --project-directory . up
```

Tracing UI is available at Jaeger (typically http://localhost:16686). This compose setup is intended for development and demos.

## Demo

### Soon...

 For now, see the `zentro/intelligence_manager/project_agent/agent.py` file for the agent behavior and available tools. or run locally and start chatting with the agent!

## Pre-commit
If you like to be sure your code is consistently formatted and checked before committing, you can use pre-commit hooks.

Install the project's pre-commit hooks with:

```bash
pre-commit install
```

Hooks include formatters and linters such as `black`, `mypy`, and `ruff`.

## Migrations

Use `alembic` for database migrations. Examples:

```bash
# Apply migrations up to a specific revision
alembic upgrade "<revision_id>"

# Apply all pending migrations
alembic upgrade head
```

To revert:

```bash
alembic downgrade <revision_id>
alembic downgrade base
```

To generate a revision:

```bash
alembic revision --autogenerate
alembic revision
```

