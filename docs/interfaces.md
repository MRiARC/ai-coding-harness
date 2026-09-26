# Core Interfaces

Reference for the contracts introduced in foundation issue 1.2. Everything here
is interface-only: behavior lands in milestones 2 and 3.

## `BaseAgent` (`harness.agents.base`)

The contract every role in the hierarchy implements. Construct with an
`agent_id`, the raw `model_config` mapping (from the configuration system),
its `tools`, and a `ContextWindow`.

| Member | Kind | Purpose |
|---|---|---|
| `execute_task(task) -> TaskResult` | abstract | Run a task to completion, including the agent's internal loop |
| `handle_error(error, task) -> ErrorEscalation` | abstract | Classify a failure for the recovery ladder |
| `report_status() -> StatusUpdate` | abstract | Publish current lifecycle state |
| `permitted_tools(context) -> list[Tool]` | concrete | Filter this agent's tools through `Tool.check_permissions` |

## `BaseManager` (`harness.agents.base`)

Extends `BaseAgent` with coordination responsibilities: `assign_task()`,
`monitor_progress() -> list[StatusUpdate]`, `handle_escalation() -> StatusUpdate`.

## `ContextWindow` (Protocol)

Structural view over an agent's conversation context: `append(role, content)`
and `as_messages() -> list[dict]` (OpenAI chat format). Implemented by the
context-store infrastructure (issue 1.4); agents depend on the protocol only.

## `Tool` (`harness.tools.base`)

Abstract tool with `name`, `tier` (`ToolTier.BASIC/DEVELOPMENT/ADVANCED`),
`description`, and a JSON-schema `parameters` mapping. Methods:

- `validate_input(arguments) -> list[str]` — pure validation, empty list = valid
- `check_permissions(context) -> bool` — gate on caller capabilities (e.g. `model_tier`)
- `execute(**kwargs) -> ToolResult` — must return a failing `ToolResult`,
  never raise, so the recovery ladder can reason over outcomes

## Task value objects (`harness.agents.task`)

`Task` (immutable): `id`, `title`, `description`, `acceptance_criteria`,
`subtask_ids`, `metadata`. `TaskResult`: `task_id`, `success`, `summary`,
`artifacts` (evidence-pack paths), `error`.

## Protocol messages (`harness.orchestration.messages`)

All immutable pydantic models with `id`, `correlation_id`, `created_at`:

- `CommandMessage` — sender -> recipient instruction (`command`, `payload`)
- `StatusUpdate` — heartbeat (`AgentStatus`: idle/working/blocked/done/failed)
- `ErrorEscalation` — failure with `Severity` (transient/recoverable/fatal),
  `attempt`, optional `suggested_action`
- `CoordinationMessage` — Manager traffic (`CoordinationKind`: task_assign,
  task_result, context_share, broadcast, shutdown)

`correlation_id` stitches one task run's traffic together across agents and
into the evidence trace.
