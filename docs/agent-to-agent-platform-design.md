# Agent-To-Agent Project Platform Design

## Context

Zentro currently has the right foundation for human-to-agent project management:

- Projects, epics, sprints, tasks, task status, priority, users, and roles live in `zentro/project_manager`.
- The project agent already reads and changes project data through tool calls in `zentro/intelligence_manager/project_agent`.
- Streaming agent responses and Langfuse tracing already point toward long-running, observable work.

The next product direction is to make Zentro a coordination layer for agent-to-agent project delivery. Humans should still be able to manage projects, but the primary unit of work becomes a task that can be negotiated, delegated, executed, blocked, reviewed, and handed off between agents.

## Research Notes

### Agent2Agent Protocol

The current A2A specification describes an open protocol for independent agent systems to discover each other, negotiate modalities, manage collaborative tasks, and exchange information securely without sharing internal memory or tools.

Useful concepts for Zentro:

- `AgentCard`: public metadata for an agent's identity, endpoint, skills, capabilities, and auth requirements.
- `Task`: durable unit of work with status, history, messages, and artifacts.
- `Message`: conversational turn between client and remote agent.
- `Part`: typed content inside messages and artifacts, including text, files, and structured data.
- `Artifact`: output produced by an agent, potentially streamed incrementally.
- `message/send`, `message/stream`, `tasks/get`, `tasks/cancel`, push notification operations, and task resubscription provide a useful API shape.

Source: https://a2a-protocol.org/v0.3.0/specification/

### MCP Boundary

MCP is complementary, not a replacement for A2A. MCP standardizes how an agent application connects to tools, prompts, resources, and context servers. A2A standardizes how one agent delegates work to another agent. Zentro should expose project/task context as MCP resources/tools later, while using A2A-style concepts for cross-agent work ownership.

Source: https://modelcontextprotocol.io/specification/2025-06-18/architecture

### Event Model

Agent-to-agent task management needs evented status changes rather than only CRUD. CloudEvents gives a standard event envelope for routing, tracing, and integration. AsyncAPI can document broker channels if RabbitMQ becomes the default internal event bus.

Sources:

- https://github.com/cloudevents/spec
- https://www.asyncapi.com/docs/reference/specification/v3.1.0

### Multi-Agent Handoffs

LangChain/LangGraph handoff patterns are useful for internal implementation: persistent state controls which agent is active, and tool-based transitions move control between agents or workflow steps. Zentro should persist handoffs as first-class project events instead of leaving them only in the conversation graph.

Source: https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs

## Product Vision

Zentro becomes an agent project control plane:

- Humans create objectives, constraints, and approval policies.
- Agents advertise capabilities and availability.
- Agents claim, delegate, split, block, review, and complete tasks.
- Project state is visible as a live graph of work, dependencies, ownership, risk, and artifacts.
- Every handoff is auditable: who delegated what, why, with what context, and what changed.

The UI should shift from "chat with a project agent" to "watch and steer a project network":

- Project overview: health, blocked work, active agents, recent handoffs, risky tasks.
- Task board: human tasks and agent tasks together, with agent ownership and protocol state.
- Agent directory: cards, skills, trust level, recent success rate, current load.
- Handoff timeline: chronological stream of delegation, acceptance, rejection, questions, artifacts, and reviews.
- Artifact panel: generated specs, patches, test reports, research notes, and decision records linked to tasks.

## Domain Model

Keep Zentro's existing `Task` model as the canonical project-management object. Add protocol-facing objects around it rather than replacing it.

### AgentProfile

Represents a local or remote agent available to Zentro.

Suggested fields:

- `id`
- `slug`
- `display_name`
- `description`
- `provider`
- `endpoint_url`
- `agent_card`
- `capabilities`
- `auth_scheme`
- `trust_level`
- `is_active`
- `created_at`
- `updated_at`

### AgentSkill

Normalized searchable skills from an agent card.

Suggested fields:

- `id`
- `agent_profile_id`
- `name`
- `description`
- `input_modes`
- `output_modes`
- `tags`

### AgentTaskLink

Maps a Zentro task to agent protocol state.

Suggested fields:

- `id`
- `task_id`
- `context_id`
- `remote_task_id`
- `protocol`
- `state`
- `active_agent_id`
- `delegated_by_agent_id`
- `delegated_by_user_id`
- `requires_human_approval`
- `last_message_at`
- `created_at`
- `updated_at`

### AgentMessage

Durable task communication history.

Suggested fields:

- `id`
- `task_link_id`
- `message_id`
- `role`
- `sender_agent_id`
- `sender_user_id`
- `parts`
- `created_at`

### AgentArtifact

Outputs produced by agents and attached to project work.

Suggested fields:

- `id`
- `task_link_id`
- `artifact_id`
- `name`
- `mime_type`
- `parts`
- `uri`
- `created_by_agent_id`
- `created_at`

### AgentEvent

Append-only audit log and broker payload source.

Suggested fields:

- `id`
- `project_id`
- `task_id`
- `task_link_id`
- `type`
- `source_agent_id`
- `target_agent_id`
- `correlation_id`
- `causation_id`
- `payload`
- `created_at`

## State Mapping

Zentro task states should remain product-facing. Protocol states should be mapped explicitly.

| Zentro state | Agent protocol meaning |
| --- | --- |
| `draft` | Proposed work not yet eligible for autonomous execution |
| `todo` | Submitted and ready for agent claim/delegation |
| `in_progress` | Agent task is submitted, working, or streaming |
| `blocked` | Agent requires input, failed dependency, missing credential, or human decision |
| `in_review` | Artifact or result is waiting for validator agent or human approval |
| `done` | Agent task completed and accepted |

Do not overload `TaskStatus` with every protocol state. Store detailed protocol state in `AgentTaskLink.state`, then derive project board status from policy.

## Protocol Shape

### Agent Card

Expose local Zentro-managed agents at:

```http
GET /.well-known/agent-card.json
GET /api/agents/{agent_id}/card
```

For remote agents, store fetched cards in `AgentProfile.agent_card` and periodically refresh them.

### Internal REST API

Suggested first endpoints:

```http
GET    /api/agents
POST   /api/agents
GET    /api/agents/{agent_id}
GET    /api/agents/{agent_id}/card
POST   /api/projects/{project_id}/agent-tasks
GET    /api/projects/{project_id}/agent-tasks
GET    /api/agent-tasks/{task_link_id}
POST   /api/agent-tasks/{task_link_id}/messages
POST   /api/agent-tasks/{task_link_id}/delegate
POST   /api/agent-tasks/{task_link_id}/accept
POST   /api/agent-tasks/{task_link_id}/reject
POST   /api/agent-tasks/{task_link_id}/cancel
GET    /api/agent-tasks/{task_link_id}/events
```

### Message Envelope

Use an A2A-compatible payload internally, even before full external compliance:

```json
{
  "message": {
    "role": "user",
    "parts": [
      {
        "kind": "data",
        "data": {
          "objective": "Implement board CRUD",
          "constraints": ["preserve current API auth", "add tests"],
          "definition_of_done": ["migration exists", "tests pass"]
        }
      }
    ],
    "contextId": "project-42",
    "taskId": "zentro-task-120",
    "messageId": "msg-01"
  },
  "configuration": {
    "blocking": false,
    "acceptedOutputModes": ["text", "data", "file"]
  }
}
```

### Event Envelope

Use CloudEvents-compatible metadata for internal event routing:

```json
{
  "specversion": "1.0",
  "type": "zentro.agent_task.delegated",
  "source": "/agents/planner",
  "id": "evt-01",
  "time": "2026-05-09T00:00:00Z",
  "subject": "projects/42/tasks/120",
  "datacontenttype": "application/json",
  "data": {
    "task_link_id": 10,
    "from_agent": "planner",
    "to_agent": "backend-engineer",
    "reason": "Backend implementation required",
    "handoff_summary": "Add board CRUD and tests."
  }
}
```

## Architecture

### MVP Components

- Agent registry: manages local/remote agent cards and skills.
- Task protocol adapter: maps Zentro tasks to A2A-style tasks, messages, states, and artifacts.
- Handoff service: validates delegation, acceptance, rejection, cancellation, and human approval rules.
- Event store: append-only `AgentEvent` records for audit and replay.
- Stream API: SSE endpoint for project and task event timelines.
- Policy layer: controls which agents can mutate project state, create tasks, assign work, or mark work done.

### Recommended Flow

1. Human or agent creates a normal Zentro task.
2. Planner agent converts the task into an `AgentTaskLink`.
3. Planner selects a target agent from registry skills and trust policy.
4. Handoff service emits `zentro.agent_task.delegated`.
5. Target agent accepts, rejects, asks for input, or delegates a subtask.
6. Agent messages and artifacts are persisted against the task link.
7. Validator agent or human reviews artifacts.
8. Task status changes to `done` only after acceptance policy passes.

## Implementation Plan

### Phase 1: Internal Agent Task Layer

- Add agent registry tables and schemas.
- Add task link, message, artifact, and event tables.
- Add service functions for create, delegate, accept, reject, message, artifact, and cancel.
- Add read endpoints for project-level agent activity.
- Add tests around state transitions and audit event creation.

### Phase 2: Live Project Overview

- Add SSE stream for project events.
- Add task state aggregation: active, blocked, waiting for input, waiting for review, completed.
- Add agent workload and handoff timeline endpoints.
- Keep UI/API read models separate from write models.

### Phase 3: External Protocol Compatibility

- Publish Zentro agent cards.
- Add A2A-compatible `message/send`, `message/stream`, `tasks/get`, and `tasks/cancel` adapters.
- Add remote agent discovery and card refresh.
- Add push notification webhook support for long-running remote tasks.

### Phase 4: MCP Integration

- Expose project summaries, tasks, artifacts, and workflow state as MCP resources.
- Expose safe project operations as MCP tools with explicit authorization.
- Use MCP for context access and A2A for delegation.

## Design Decisions

- Zentro tasks stay canonical because the project manager already owns permissions, boards, priorities, and project views.
- Protocol state is stored separately to avoid coupling UI task states to every external agent protocol revision.
- Agent events are append-only because auditability matters more than convenience in autonomous project mutation.
- Agent artifacts are first-class because project outcomes should be inspectable without replaying chat history.
- Handoffs are explicit domain actions, not just chat messages, because assignment and responsibility need durable semantics.

## Open Questions

- Should the first implementation support only local agents, or include one remote A2A-compatible agent from day one?
- Should `AgentProfile` reuse `User` identity, or should agents be separate principals with optional linked users?
- What actions require human approval: task creation, assignment, status change to done, artifact publication, or all project mutations?
- Should RabbitMQ be mandatory for agent events, or should the database event log be the source of truth with optional broker publishing?
- What is the minimum trust policy: static allowlist, per-project role, signed agent card, or token-bound agent identity?

## First Slice Recommendation

Build a local-only A2A-inspired layer first:

1. Add agent registry and agent task tables.
2. Implement explicit handoff state transitions.
3. Persist messages, artifacts, and audit events.
4. Add project overview endpoints for active agents, blocked tasks, and recent handoffs.
5. Add external A2A compatibility only after internal semantics are stable.

This avoids committing too early to protocol edge cases while still shaping the product around durable agent collaboration.
