# Adversarial Technical Audit
## MRiARC / ai-coding-harness

**Repository:** https://github.com/MRiARC/ai-coding-harness  
**Audited branch:** `main`  
**Main snapshot reviewed:** `d72b75e7a5196ff688ef9c435b0af417f27cbf63`  
**Date:** September 26, 2026

---

# 1. Executive Verdict

The repository currently looks substantially more capable than it actually is.

It has clean Python, respectable abstractions, aggressive test coverage, provider adapters, context persistence, agent classes, recovery abstractions, budget accounting, Git/GitHub utilities, and extensive architecture documentation.

But the thing that matters most is still missing:

> **The repository cannot currently perform the software-engineering job it claims to perform through its standard interface.**

`make run` does not run an autonomous coding harness. It runs:

```text
python -m harness doctor
```

The CLI has no `run` command.

There is no concrete repository tool runtime.

There is no operational repository indexer.

There is no top-level orchestration engine connecting:

```text
issue
 → repository analysis
 → localization
 → implementation
 → verification
 → recovery
 → final review
 → evidence pack
```

So the current project is better described as:

> **A well-structured and heavily unit-tested framework for a future coding harness, not yet the coding harness itself.**

Worse, several Milestone 2 features are not merely unfinished. They are implemented in ways that make the documentation materially stronger than the runtime behavior.

The largest risk is therefore not ugly code.

The code is generally clean.

The largest risk is **false confidence**.

The repository contains enough abstractions, diagrams, roles, metrics, tests, and “100% coverage” language to make a reviewer believe the hard engineering problem has been solved.

It has not.

---

# 2. Current Assessment

| Area | Assessment |
|---|---:|
| Code hygiene | **8/10** |
| Static architecture organization | **7/10** |
| Documentation consistency | **2/10** |
| Runtime integration | **2/10** |
| Agent correctness guarantees | **2/10** |
| Real-model readiness | **2/10** |
| Verification rigor | **2/10** |
| Evaluation-interface readiness | **1/10** |
| Test-suite usefulness as readiness evidence | **4/10** |
| Current autonomous coding capability | **1/10** |

The project is not bad because it is messy.

It is dangerous because it is tidy while still being functionally incomplete.

---

# 3. The Biggest Problem: `make run` Does Not Run the Product

The Foreman design states that the evaluation flow is roughly:

```text
git clone ...
export AI_API_KEY=...
make setup
make run
<issue text>
```

The actual Makefile currently does this:

```text
run:
    python -m harness doctor
```

And the CLI only registers:

```text
doctor
```

There is no:

```text
harness run
```

There is no issue intake.

There is no target-repository argument.

There is no stdin issue pipeline.

There is no execution engine.

There is no patch generation.

There is no verification cycle.

There is no evidence-pack production.

This should be treated as **P0 / release-blocking**.

Everything else is secondary until this works.

Sources:

- https://github.com/MRiARC/ai-coding-harness/blob/main/Makefile
- https://github.com/MRiARC/ai-coding-harness/blob/main/src/harness/cli.py
- https://github.com/MRiARC/ai-coding-harness/blob/main/docs/specs/foreman-eval-mode-design.md

---

# 4. Critical: The Harness Has Agents but Almost No Actual Coding Tools

The repository currently has:

```text
src/harness/tools/
├── __init__.py
└── base.py
```

That is an interface, not a tool runtime.

The Foreman architecture depends on approximately:

```text
read_file
list_dir
search_text
search_symbols
repo_map
apply_edit
run_tests
run_cmd
git operations
token meter
```

None of those operational coding tools are present on `main`.

Consequently, you currently have the unusual architecture:

```text
Architect
Manager
Locator
Implementer
Verifier
Recovery system
Budget governor
Provider system
Context system
       │
       ▼
   No hands
```

The system has been given an organization chart before it has been given a keyboard.

This is backwards prioritization.

For an AI coding harness, the most valuable early proof is:

```text
read repository
      ↓
find bug
      ↓
edit file
      ↓
run test
      ↓
observe failure
      ↓
repair
      ↓
produce patch
```

You built sophisticated coordination concepts before proving that elementary loop.

---

# 5. Critical: Real Native Tool Calling Is Structurally Broken Across Turns

This is one of the most serious technical problems in the repository.

The provider layer itself supports structured native tool calls.

For example, `ModelResponse` preserves:

```text
tool call ID
tool name
arguments
```

Anthropic translation expects `tool_use_id`.

OpenAI requires a later `tool` message to correspond to the earlier assistant `tool_call`.

Gemini similarly has structured `functionCall` / `functionResponse` semantics.

But `LLMAgent` destroys that structure.

After a model makes a tool call, `_assistant_transcript()` converts the call into ordinary text such as conceptually:

```text
[calls: read_file({...})]
```

Then the context store persists it as plain assistant text.

The tool result is stored as:

```text
role = tool
content = ...
```

but without the original structured `tool_call_id`.

`StoreWindow.as_messages()` only returns:

```text
role
content
```

Therefore the model conversation cannot faithfully round-trip the native tool-call protocol.

For OpenAI-compatible models, the second request after a native tool call normally needs the original structured assistant tool call and a corresponding tool result ID.

For Anthropic, the tool result needs its corresponding `tool_use_id`.

Your Anthropic adapter even contains code to support this structure — but the agent layer throws the required data away before the adapter sees the next turn.

This means the provider unit tests and agent unit tests are testing two pieces independently while missing the broken connection between them.

The `FakeProvider` hides this problem because it does not validate API conversation semantics.

This is exactly the kind of bug that produces:

```text
199 tests pass
100% coverage
real API run fails on tool turn #2
```

I would consider this **release-blocking before any live model evaluation**.

Relevant files:

- `src/harness/agents/llm_agent.py`
- `src/harness/infrastructure/model_providers/openai_compatible.py`
- `src/harness/infrastructure/model_providers/anthropic.py`
- `src/harness/infrastructure/model_providers/google.py`

---

# 6. Critical: “Task Complete” Is Not Actually Required

The system defines:

```text
TASK_COMPLETE:
```

and prompts the agent to use it.

But `_loop()` effectively treats this as success:

```text
model stops calling tools
        ↓
success = True
```

It does not require the completion marker.

It does not require evidence.

It does not require a test result.

It does not require a verified diff.

It does not even require the model to claim it succeeded.

A response conceptually equivalent to:

```text
I cannot solve this problem.
```

can terminate the loop as:

```text
success=True
```

Even worse, the test suite explicitly normalizes this behavior.

The unit tests include scenarios where:

```text
unknown tool
      ↓
tool error
      ↓
model says "done"
      ↓
success
```

and:

```text
tool crashes
      ↓
model says "done"
      ↓
success
```

So this is not an accidental uncovered bug.

The tests currently institutionalize the wrong completion semantics.

A coding harness should distinguish at minimum:

```text
CONTINUE
DONE_PENDING_VERIFICATION
BLOCKED
FAILED
ABORTED
```

and only the Verifier/engine should promote work into:

```text
VERIFIED_SUCCESS
```

An Implementer's decision to stop talking should never itself equal success.

---

# 7. Critical: Your “Verifier” Is Mostly a Prompt

The architecture gives the impression of an independent verification layer:

```text
Implementer
    ↓
Verifier
    ↓
evidence-backed verdict
```

But there is no special enforced verifier protocol.

`verifier` is a role preset over the same generic `LLMAgent`.

The prompt says things like:

```text
run relevant tests
judge the diff
report evidence
```

but the runtime does not enforce any of them.

The verifier can return ordinary prose without running anything and the generic loop can mark it successful.

There is no mandatory structure such as:

```json
{
  "verdict": "pass",
  "commands_run": [],
  "tests": [],
  "baseline_regressions": [],
  "acceptance_criteria": []
}
```

There is no requirement that at least one verification method execute.

There is no programmatic transition:

```text
Implementer output
        ↓
must pass Verifier
        ↓
TaskResult.success = true
```

Therefore “Verifier” currently means:

> an LLM was told to behave like a verifier.

That is not the same thing as a verification system.

---

# 8. Critical: The Recovery Ladder Does Not Do What Its Names Claim

The recovery architecture sounds good:

```text
L1 self repair
L2 manager re-route
L3 architect re-plan
L4 graceful failure
```

The implementation is much weaker.

## L1 is mostly “try the same executor again”

At L1, the recovery ladder executes the task repeatedly.

It obtains an escalation after failure, but the failure evidence is not necessarily injected into the next task attempt.

So the documented concept:

```text
failure
  ↓
evidence
  ↓
same specialist receives evidence
  ↓
targeted repair
```

can degrade into:

```text
failure
  ↓
call same executor again
```

That is retrying, not reasoning-based self-repair.

## L2 does not really re-route

The Manager generates guidance.

Then RecoveryLadder writes that guidance into:

```text
task.metadata
```

and invokes the same `executor` again.

It does not:

```text
select a different agent
reassign the task
change model
change tools
add collaborator
rerun Locator
```

The method is called re-route, but no real routing occurs.

That is a naming/behavior discrepancy.

## Worse: the specialist may never see the guidance

`LLMAgent.execute_task()` sends essentially:

```text
TASK: <title>
<description>
```

The specialist prompt does not include the task metadata.

Therefore:

```text
metadata["guidance"] = "..."
```

may never reach the model at all.

So the current L2 path can effectively be:

```text
Manager produces advice
        ↓
advice saved somewhere
        ↓
same model retries
        ↓
model never sees advice
```

That is a serious integration flaw.

---

# 9. Critical: The Rich Task Object Is Mostly Disconnected from Agent Execution

`Task` contains useful fields:

```text
acceptance_criteria
specialty
complexity
required_tools
files
metadata
dependencies
```

But when an agent executes a task, most of that disappears.

The basic task prompt only includes:

```text
title
description
```

The Implementer is therefore not guaranteed to receive the acceptance criteria that the Architect spent tokens creating.

Manager guidance can disappear.

Expected files can disappear.

Dependencies can disappear.

Required tools can disappear.

This makes the architecture internally self-defeating:

```text
Architect generates rich planning information
             ↓
        Task object
             ↓
generic agent receives only a fraction of it
```

Before introducing more planning intelligence, wire the planning output into execution.

---

# 10. Critical: Agent Context Can Be Written Into Two Different Task IDs

`build_agent()` constructs a `StoreWindow` using a fixed `task_id`, defaulting to:

```text
ad-hoc
```

But later `execute_task(task)` receives an actual `task.id`.

Inside execution:

```text
initial user task
```

is appended directly under the actual task ID.

But subsequent assistant/tool messages are appended through the preconstructed `context_window`, which can still point to `ad-hoc` or another task.

That means a reusable agent can create:

```text
task-123 context
    └── initial task message

ad-hoc context
    ├── assistant reasoning
    ├── tool calls
    └── tool results
```

Then `_loop()` may load summary information from one task while building the message history from another.

The tests hide this because their `StoreWindow` task ID and `Task.id` are deliberately identical.

This should be redesigned so the context window is created or rebound per execution, not permanently attached to an arbitrary task ID when the agent object is constructed.

---

# 11. High: Your Parallelism Safety Gate Is Not Safe

The Foreman spec contains a genuinely good idea:

> localize first, then calculate file overlap, then parallelize only independent work.

The current implementation deviates from that.

The Architect asks the LLM to guess each subtask's files.

Those guesses feed `execution_batches()`.

So currently the data flow is closer to:

```text
LLM guesses files
      ↓
parallelism decision
```

instead of:

```text
Locator searches repository
      ↓
observed file set
      ↓
parallelism decision
```

That defeats the reason for having a Locator.

There is another major bug: `execution_batches()` ignores `depends_on`.

For example:

```text
A: implement API
   files = api.py

B: add consumer
   files = client.py
   depends_on = A
```

Because there is no file overlap, A and B can land in the same parallel batch.

Explicit dependency information exists and is ignored.

Another unsafe edge case:

```text
subtask.files = []
```

An empty set conflicts with nothing.

Therefore uncertain or failed localization can paradoxically make the scheduler conclude that everything is safe to run simultaneously.

The correct scheduler needs:

```text
dependency DAG
      +
Locator-derived file overlap
      +
unknown-file conservative fallback
      +
cost/benefit threshold
```

Currently it has only one weak part of that.

---

# 12. High: The Manager Is More Simulated Than Operational

The Manager contains a clean-looking multi-factor formula:

```text
40% specialty
20% availability
20% load
20% capability
```

But the inputs are largely artificial.

`performance` is passed into `specialty_match()` and ignored.

`tokens_used` is a field in `SpecialistSlot`; it is not automatically synchronized with the actual token ledger.

`current_tasks` increments on assignment.

I found no normal task-completion lifecycle that decrements it.

`monitor_progress()` does not really poll running agents. It infers:

```text
current_tasks > 0 → WORKING
```

This means “progress monitoring” is more accurately:

> report whatever counters currently say.

The scheduler can also choose the top three agents for a complex task even if the candidate scores are poor, the specialty is wrong, or capability is inadequate.

A sophisticated assignment formula is premature when the underlying operational state is not trustworthy.

---

# 13. High: Budget Modes Are Labels, Not Control Policies

You have:

```text
NORMAL
SURGICAL
FINALIZE
```

The design says these modes should change runtime behavior.

For example:

```text
SURGICAL
→ less exploration
→ no expensive replanning
→ narrow context

FINALIZE
→ stop exploring
→ verify
→ only targeted repairs
```

But the implementation mainly calculates the mode.

The agent loop calls:

```text
governor.check()
```

which becomes meaningful only when the total token budget is exhausted.

I did not find the Agent/Manager/Recovery engine using `GovernorMode` to substantially alter policy at 70% or 90%.

Therefore today:

```text
70% reached
```

mostly means:

```text
mode() would return SURGICAL if somebody asked
```

That is accounting, not governance.

Also, a model call is allowed if the budget is below the cap before the call.

A large final request can therefore overshoot the total limit because usage is recorded only after completion.

A stronger governor would reserve predicted request + completion capacity before dispatch.

---

# 14. High: “Three-Window Context” Is Much Less Intelligent Than the Documentation Suggests

The context architecture sounds sophisticated:

```text
recent
compressed
historical milestones
fact ledger
```

But compression currently takes approximately the first meaningful line of selected conversation turns.

Tool messages are dropped by the default summarizer.

That means some of the most valuable information in a coding task can disappear:

```text
test traceback
exact compiler error
grep result
file discovery
command result
failed approach
```

The system celebrates “>60% compression,” but byte reduction is not the right success metric.

You can achieve excellent compression by deleting important information.

The correct metric is closer to:

```text
Can the agent still answer:
- what failed?
- which files matter?
- what approaches were tried?
- what exact test remains red?
- which constraints must not be violated?
```

The current tests check compression ratio, not semantic preservation.

The term “fact ledger” is therefore stronger than the implementation warrants.

---

# 15. High: PostgreSQL Is Presented as Supported but Core Methods Are Unimplemented

Configuration allows:

```yaml
storage:
  backend: postgres
```

The project exposes a `postgres` optional dependency.

`PostgresContextStore` exists.

But core methods still raise `NotImplementedError`, including important agent-context operations.

That makes “Postgres backend” a trap.

If a user selects an advertised configuration option, normal harness behavior can fail immediately.

There are two honest options:

```text
A. finish PostgreSQL
```

or:

```text
B. remove it from user-facing configuration until finished
```

For hackathon eval mode, I would choose B.

You do not need PostgreSQL.

---

# 16. High: Reproducibility Claims Are Incorrect

The documentation repeatedly talks about pinned or reproducible dependencies.

`pyproject.toml` uses constraints such as:

```text
pydantic>=2.7
httpx>=0.27
pytest>=8.2
mypy>=1.10
```

Those are not pinned versions.

There is no lockfile.

`make setup` also upgrades pip and installs the development dependency set.

The actual GitHub Actions run downloaded whatever current versions were available, including versions substantially newer than the minimum constraints.

Therefore two evaluations performed months apart can resolve different dependency graphs.

If reproducibility matters, use an actual lock strategy or exact compatible pins.

This is especially important for:

```text
pydantic
httpx
pytest
pytest-asyncio
mypy
```

where behavioral changes between major/minor versions can absolutely affect execution.

---

# 17. High: The Documentation Is Actively Sabotaging the Project

This is one of the most damaging repository-level problems.

The approved Foreman design says the runtime direction is approximately:

```text
Python
single prescribed model
local execution
SQLite
TUI/headless
small tool runtime
Architect → Manager → Locator/Implementer/Verifier
```

But `CONTEXT_FOR_AI.md` tells AI contributors:

```text
Go API server
Python + LangGraph
PostgreSQL
Redis
React + Vite
multi-service architecture
10+ specialists
```

`TECHNICAL_IMPLEMENTATION.md` describes the same obsolete multi-service architecture.

The README prominently shows:

```text
Web Dashboard
REST API
PostgreSQL
three manager teams
many specialist agents
GitHub PR workflows
```

The approved Foreman design explicitly classifies several of those as out of scope for evaluation.

This is particularly bad because the repository is being developed with AI coding tools.

You literally have a file called:

```text
CONTEXT_FOR_AI.md
```

whose instructions would cause an AI engineer to implement the wrong architecture.

This file should be treated as a defect, not stale documentation.

At minimum, the source-of-truth hierarchy should be brutally explicit:

```text
1. docs/specs/foreman-eval-mode-design.md
2. current code
3. current milestone implementation plan

Legacy:
DESIGN_SPEC.md
TECHNICAL_IMPLEMENTATION.md
old issue descriptions
```

Or archive the obsolete material outside the main contributor path.

---

# 18. High: The Project Is Overengineered in the Wrong Direction

This is the architectural criticism I would emphasize most strongly.

Before the harness can reliably:

```text
read file
search file
edit file
run test
```

you already implemented:

```text
OpenAI provider
Anthropic provider
Google provider
OpenAI-compatible provider
GitHub issue creation
GitHub PR creation
GitHub merging
PostgreSQL scaffold
13 role presets
specialist scoring
load balancing
recovery hierarchy
context compression
correlation messages
budget modes
large architectural documents
```

This is classic architecture-first overbuilding.

The competition does not reward the number of abstractions in the repository.

It rewards successful engineering tasks.

A much stronger development order would have been:

```text
single model
    ↓
read/search/edit/test
    ↓
one coding loop
    ↓
real fixture succeeds
    ↓
verification
    ↓
evidence pack
    ↓
localization
    ↓
recovery
    ↓
only then hierarchy/parallelism
```

Instead, the repo has partially inverted that order.

---

# 19. High: Thirteen “Agents” Are Mostly Prompt Personas

The runtime has role presets for:

```text
architect
manager
locator
implementer
verifier
backend-api
database
frontend
testing
devops
security
documentation
code-review
```

But most of these are not truly separate agent implementations.

They are configurations of the same generic `LLMAgent`.

That is not inherently wrong — prompt specialization can be useful.

But presenting them as a rich multi-agent organization risks overstating the architecture.

With one prescribed underlying model, the key differentiators should be:

```text
context
tools
authority
verification responsibilities
state transition rules
```

not simply role-flavored system prompts.

For eval mode, I would remove or freeze most classic personas until benchmark evidence shows they improve task completion.

Every extra role adds:

```text
routing complexity
prompt maintenance
test surface
token overhead
failure modes
```

without proven benefit.

---

# 20. High: The Architect Review Can Ignore Part of the Patch

`ArchitectAgent.review()` truncates the diff.

The implementation effectively reviews only the first portion of the diff.

A sufficiently large modification can therefore have:

```text
important changes near beginning → reviewed

dangerous changes near end → invisible
```

The final quality gate should never silently truncate the exact artifact it is judging.

Use structured per-file summaries plus targeted full diff retrieval, or reject oversized review inputs and inspect them in chunks.

Also, the Architect review currently focuses on acceptance criteria + diff.

It should consume verification evidence too:

```text
baseline test results
post-change test results
reproduction test
lint/typecheck
changed-file list
test-file integrity check
```

Otherwise the “final review” is another LLM opinion about code text.

---

# 21. Medium-High: Correlation IDs Do Not Automatically Correlate a Run

Protocol messages each default to their own newly generated correlation ID.

Unless the caller explicitly reuses one, two messages from the same task can end up with:

```text
correlation A
correlation B
correlation C
```

The Manager's helper constructs coordination messages without obviously threading the originating correlation ID.

Meanwhile logging has a separate context-variable correlation mechanism.

The design talks about correlation IDs “throughout,” but the system does not yet expose a single authoritative RunContext that every message, model call, tool call, log event, and evidence artifact inherits.

Build one.

Something like:

```text
RunContext
├── run_id
├── task_id
├── correlation_id
├── repo_id/path
└── budget
```

should flow everywhere.

---

# 22. Medium-High: The Tool Interface Will Fight Async Execution

`Tool.execute()` is synchronous.

`_call_tool()` is declared async but invokes the synchronous function directly.

That is harmless for an echo tool.

It is a poor abstraction for:

```text
run_tests
run_cmd
git
language-server queries
package-manager operations
```

Those are long-running operations.

If implemented naïvely under the current interface, they can block the event loop and undermine your future multi-agent concurrency.

The tool contract should either be natively async or explicitly distinguish sync CPU-light tools from async process/network tools.

---

# 23. Security Is Mostly Architectural Intent, Not Enforcement

There is considerable security language throughout the docs.

Current runtime enforcement is not yet commensurate with those claims.

There is no concrete file tool runtime enforcing repository path confinement because the tools themselves do not exist.

There is no full sandbox.

There is no programmatic test-file integrity policy.

There is no secret scanner in the execution path.

There is no mandatory diff minimality guard.

There is also a future leakage issue to plan for:

tool calls and tool outputs are stored in context.

If an agent accidentally reads:

```text
.env
credentials
tokens
private config
```

those values could flow into:

```text
SQLite
logs
trace
model context
evidence artifacts
```

Secret redaction needs to happen at the tool/output boundary, not merely in prompts.

---

# 24. The 100% Coverage Number Is Creating the Wrong Incentive

The project has an objectively impressive:

```text
199 tests
100.00% statement coverage
```

The GitHub Actions run confirms that.

But this is a strong example of why statement coverage is not software correctness.

The suite achieves 100% while all of the following can still be true:

```text
make run cannot execute the product
native multi-turn tool protocol is broken
manager guidance can be invisible
bare prose is accepted as success
dependency scheduling is ignored
no real coding tools exist
no real verifier is enforced
Postgres contains NotImplementedError
```

Some tests actively verify undesirable behavior.

For example, tool failure followed by `"done"` is expected to succeed.

So increasing coverage from 90% to 100% did not protect you from the most important system-level problems.

I would stop treating 100% coverage as a headline metric.

Maintain reasonable coverage, but invest engineering time into behavioral evaluation.

The test that matters is closer to:

```text
Given broken fixture repository X
and issue Y

Harness:
1. localizes correct file
2. reproduces failure
3. edits correct implementation
4. does not weaken tests
5. makes reproduction pass
6. keeps baseline-green tests green
7. emits valid patch + evidence
8. stays under budget
```

You currently do not have that end-to-end test.

Your existing “integration” test manually constructs an evidence directory itself.

That tests file writing, not the harness pipeline.

---

# 25. PR / Review Process Criticism

PR #43 introduced thousands of lines of foundation work.

PR #44 introduced another approximately 2,200 additions.

Both have no GitHub review submissions or inline review threads in the connected repository history.

The repository contains committed “review reports” saying an automated reviewer approved the milestones.

That is useful internal documentation.

It should not be confused with adversarial independent review.

PR #44's CI genuinely passed on Python 3.11 and 3.12, and I verified the workflow logs.

But the CI checked:

```text
lint
format
mypy
unit/integration pytest
```

It did not check:

```text
make setup from a clean evaluation environment
make run with issue input
real harness execution
actual repository modification
actual tests on target repo
real model gateway
multi-turn native tool call
evidence pack replay
```

So “CI green” currently means:

> the scaffold behaves as its tests describe.

It does not mean:

> the coding harness works.

PR #44 also had a stacking/base-branch mistake that required a later direct merge of `feat/foundation` into `main`.

That was corrected, but it indicates the branch process is more complicated than this two-person hackathon project needs.

Simplify.

Sources:

- PR #43: https://github.com/MRiARC/ai-coding-harness/pull/43
- PR #44: https://github.com/MRiARC/ai-coding-harness/pull/44
- CI run: https://github.com/MRiARC/ai-coding-harness/actions/runs/36257235623

---

# 26. What I Would Freeze or Delete Right Now

I would stop further expansion of:

| Component | Recommendation |
|---|---|
| PostgreSQL backend | Freeze/remove from supported config until complete |
| GitHub PR/merge automation | Deprioritize for eval mode |
| Web dashboard | Do not build now |
| Go API | Archive the idea |
| Redis | Do not introduce |
| React frontend | Do not introduce |
| 13-role specialist organization | Freeze; keep only roles proven necessary |
| Advanced performance scoring | Defer |
| Fancy agent load balancing | Defer |
| Dynamic multi-provider strategy | Defer |
| More architecture documentation | Stop until runtime catches up |

Your project does not need more architecture.

It needs execution.

---

# 27. What I Would Build Next

The correct priority is not Milestone 3 as currently described by the old issue backlog.

It should be a ruthless vertical slice.

### P0 — Make One Issue Work End-to-End

Build:

```text
harness run
     ↓
issue intake
     ↓
target repo
     ↓
read/list/search tools
     ↓
apply edit
     ↓
run tests
     ↓
git diff
     ↓
verified outcome
     ↓
evidence pack
```

Do not parallelize.

Do not use multiple specialist personas.

Do not add a dashboard.

Prove one model can solve one deterministic fixture correctly.

### P0 — Fix Conversation Representation

Replace `dict[str, str]` message history with a structured message type that preserves:

```text
assistant tool_calls
tool_call_id
tool name
tool output
provider-neutral structured content
```

Then integration-test a two-tool-call conversation against mocked OpenAI, Anthropic, and Gemini HTTP endpoints.

### P0 — Define Real Terminal Semantics

An agent reply must not equal task success.

Use explicit state.

Example:

```text
agent_done
    ↓
verification_pending
    ↓
verifier_pass
    ↓
verified_success
```

### P0 — Make Verification Deterministic First

Before asking an LLM verifier for judgment, collect:

```text
baseline tests
reproduction test
changed files
syntax/lint
targeted tests
full regression tests when feasible
```

The LLM should interpret evidence, not replace evidence.

### P1 — Build Deterministic Localization

Then add:

```text
ripgrep
symbol extraction
repo map
BM25
```

Only after this works should the Architect be allowed to decompose complex tasks.

### P1 — Repair the Recovery System

Each retry must receive:

```text
previous attempt
failure reason
test evidence
changed diff
dead-end record
manager instruction
```

L2 must genuinely alter execution.

If the action says:

```text
reassign
```

then instantiate/use another specialist.

If it says:

```text
rerun locator
```

rerun localization.

If it says:

```text
add collaborator
```

actually add one.

### P2 — Restore Hierarchy Carefully

Once the single-agent baseline has benchmark results, measure whether:

```text
Architect + Locator + Implementer + Verifier
```

beats:

```text
single capable coding agent + verifier
```

on:

```text
success rate
tokens
wall time
regressions
```

If hierarchy does not improve the benchmark, remove it.

Architecture should earn its complexity.

### P2 — Parallelism Last

Only parallelize when all of these are true:

```text
dependency DAG says independent
Locator says files disjoint
repo state allows isolated worktrees
estimated speedup is meaningful
merge verification is available
```

Unknown file set should mean:

```text
sequential
```

not:

```text
safe to parallelize
```

---

# 28. Minimum Bar Before Calling This an “Autonomous Coding Harness”

I would not use that description publicly until a clean clone can demonstrate the following:

```text
make setup

make run --repo <fixture> --issue-file issue.md
```

and the harness automatically:

```text
reads repository
understands issue
finds relevant source
runs baseline
reproduces bug
edits implementation
runs verification
recovers from at least one failed attempt
produces final diff
produces test report
produces token report
produces trace
returns meaningful exit status
```

Then run exactly the same engine against the prescribed live model endpoint.

Until that works, the safest description is:

> “Foundation and orchestration framework for an autonomous coding harness.”

Not:

> “Autonomous coding harness.”

---

# 29. Final Assessment

The team has demonstrated that it can write clean, typed, testable Python.

That is not the problem.

The project currently suffers from **architecture inflation**: abstractions and documentation are ahead of executable capability.

The repository spends complexity on things that do not yet contribute to solving the core problem.

The most concerning examples are:

```text
multi-provider system before working tool loop
GitHub automation before local coding engine
PostgreSQL before reliable SQLite end-to-end flow
13 personas before one proven agent
parallelism logic before dependency-safe localization
100% coverage before behavioral end-to-end correctness
budget modes before modes actually change behavior
recovery terminology before recovery actually changes strategy
verification role before verification is enforced
```

The strongest move now is not to add more features.

It is to aggressively collapse the system into the smallest thing that can actually solve coding tasks, benchmark that, and then earn complexity one feature at a time.

If you do that, the existing foundation is useful.

If you continue implementing the old architecture issue-by-issue, you risk ending with a beautiful multi-agent platform that loses the hackathon because the basic coding loop is less reliable than a single well-tooled model.

## Bottom line

**Today, I would not approve this as evaluation-ready.**

I would approve the repository as a promising foundation.

I would block further architecture expansion until these are fixed:

```text
real `make run`
concrete coding tools
structured tool-call conversation state
real end-to-end engine
verification-gated success
manager/recovery instructions actually reaching execution
dependency-safe scheduling
clean source-of-truth documentation
real live-model integration test
```

The project needs fewer promises and more executable evidence.

That is the main criticism.
