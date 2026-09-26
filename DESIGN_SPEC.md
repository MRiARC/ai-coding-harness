# LCC x DevClub AI Coding Harness — Design Specification

## Table of Contents

**Part I: Initial Design Overview**
1. System Architecture Overview
2. Context Management & Memory
3. Task Assignment & Coordination
4. Git Workflow & Conflict Resolution
5. Error Recovery & Escalation
6. Model & Tool Configuration
7. Verification & Quality Assurance
8. User Interface & Configuration
9. System Flow & Implementation
10. Resource Management & Optimization

**Part II: Complete Expanded Design Specification**
1. System Architecture & Agent Hierarchy (Expanded)
2. Agent Specifications (Detailed)
3. Tool Ecosystem (Expanded)
4. Context Management System (Expanded)
5. Task Assignment & Routing (Expanded)
6. Git Workflow & Conflict Resolution (Expanded)
7. Error Recovery & Escalation (Expanded)
8. Model Configuration & API Integration (Expanded)
9. Verification & Quality Assurance (Expanded)
10. User Interface & Configuration (Expanded)
11. Resource Management & Optimization (Expanded)
12. Monitoring & Observability (Expanded)
13. Security & Permissions (Expanded)
14. Extensibility & Plugin System (Expanded)
15. Testing Strategy & Deployment (Expanded)
16. Summary & Next Steps

---

## Part I: Initial Design Overview

### Section 1: System Architecture Overview

#### Core Components

**1. Agent Hierarchy (3 Tiers)**

```
User Prompt
    ↓
[Architect Agent]
    ↓
[Manager Agents (2-3 per team)]
    ↓
[Specialist Developer Agents (SD1, SD2, ...)]
    ↓
GitHub Repository (branches → PRs → merge)
```

**2. Agent Roles & Responsibilities**

**Architect Agent:**
- **Training**: Production-grade architectures, design patterns, system decomposition
- **Model Recommendation**: Highest-tier model (e.g., GPT-4, Claude Opus, Gemini Pro)
- **Responsibilities**:
  - Clone and analyze target repository
  - Decompose user prompts into structured tasks
  - Create GitHub Issues for each task
  - Assign context windows to specialist agents (via managers)
  - Review and merge PRs from specialists
  - Final quality gate before integration

**Manager Agents (2-3 per team):**
- **Training**: Task coordination, resource allocation, error recovery
- **Model Recommendation**: Mid-tier models (e.g., GPT-4-mini, Claude Sonnet)
- **Responsibilities**:
  - Receive task assignments from architect
  - Route tasks to specialists using multi-factor assignment (specialty, availability, load, capability)
  - Monitor specialist progress and token consumption
  - Handle error escalations from specialists
  - Coordinate multi-agent collaboration on complex tasks
  - Manage merge conflicts when specialists' branches converge
  - Report status back to architect

**Specialist Developer Agents (SD1, SD2, ...):**
- **Training**: Domain-specific (frontend, backend, testing, database, DevOps, etc.)
- **Model Recommendation**: Configurable by user, restricted by capability
- **Tool Access**: Capability-based (grep, sed, filesystem, git) — low-tier models restricted
- **Responsibilities**:
  - Work on assigned GitHub Issues in isolated branches
  - Read assigned context windows
  - Write code, tests, documentation
  - Self-recover from errors (2-3 attempts)
  - Escalate to manager if stuck
  - Raise PRs when task complete
  - Respond to review feedback

**3. Communication Flow**

```
User Prompt → Architect (analyzes intent)
    ↓
Creates Issues + Context Windows
    ↓
Manager receives task cluster → Analyzes multi-factor assignment
    ↓
Routes to Specialists
    ↓
Specialist works on branch → Raises PR
    ↓
Manager coordinates review → Resolves conflicts
    ↓
Architect reviews PR → Merges to main
```

---

### Section 2: Context Management & Memory

#### Hierarchical Context System

**1. Global Context Store**
- **Location**: Centralized database/store accessible to all agents
- **Contents**:
  - Repository structure & metadata
  - All active tasks and their status
  - Agent assignments and availability
  - Global rules extracted from user intents
  - Token usage logs per agent
  - Task dependency graph

**2. Per-Agent Context Windows**
- **Location**: Agent-local storage
- **Contents**:
  - Assigned task details
  - Relevant code files and diffs
  - Agent's own execution log
  - Time-windowed conversation history (compressed)
  
**3. Time-Windowed Compression Strategy**

```
[Window 1: Recent]← Agent reads first (uncompressed, last N interactions)
[Window 2: Mid-term] ← Compressed summaries (key decisions, actions)
[Window 3: Historical] ← High-level summaries (outcomes only)
```

**Algorithm**:
1. Agent receives task → checks Window 1 (recent uncompressed)
2. If insufficient context → expands to Window 2 (compressed mid-term)
3. If still insufficient → checks neighbor windows (related tasks)
4. If critical context needed → retrieves specific historical window

**4. Global Rule Extraction**
- When architect detects user intent with global implications (coding standards, architecture decisions, constraints)
- Extract as "hard rule" and persist to global context
- All agents inherit these rules in their system prompts

---

### Section 3: Task Assignment & Coordination

#### Multi-Factor Task Assignment

**Manager's Assignment Algorithm**:

```python
def assign_task(task, available_specialists):
    scores = []
    for specialist in available_specialists:
        score = (
            specialty_match(task, specialist) * 0.4+
            availability_score(specialist) * 0.2 +
            load_balance_score(specialist) * 0.2 +
            capability_match(task, specialist.model_tier) * 0.2
        )
        scores.append((specialist, score))
    
    # For complex tasks, assign top2-3 specialists
    if task.complexity > threshold:
        return sorted(scores, reverse=True)[:3]
    else:
        return [max(scores, key=lambda x: x[1])[0]]
```

**Factors**:
1. **Specialty Match**: Task domain vs agent training (frontend, backend, DB, etc.)
2. **Availability**: Is agent currently working? Queue length?
3. **Load Balance**: Total tokens consumed, tasks completed ratio
4. **Capability**: Does agent's model tier support required tools/complexity?

#### Concurrent Task Handling

**When new user prompt arrives**:
1. Architect receives prompt
2. Architect analyzes intent and extracts global rules
3. Architect + available Manager discuss assignment strategy
4. Check for conflicts with in-progress tasks:
   - File/module overlap detection
   - Dependency analysis
5. If conflict detected → sequence tasks or assign to different team
6. If independent → parallel assignment to separate manager teams

---

### Section 4: Git Workflow & Conflict Resolution

#### Branch-Per-Agent Strategy

**1. Branch Naming Convention**
```
agent/<agent-id>/<issue-number>-<short-description>
Example: agent/sd1/42-add-auth-endpoint
```

**2. Work Isolation**
- Each specialist clones repo and creates dedicated branch
- Works independently without awareness of other agents' branches
- Commits incrementally with descriptive messages

**3. Merge Coordination**

**Manager's Merge Protocol**:
```
1. Specialist completes work → raises PR to main
2. Manager reviews PR assignment
3. Run automated checks:
   - CI/CD pipeline (tests, lint, format)
   - Diff analysis (flag large changes, security-sensitive files)
4. If checks pass → assign optional reviewer agent (code quality specialist)
5. Reviewer creates low-priority issues for quality improvements
6. Manager checks for merge conflicts:
   - If no conflicts → approve for architect review
   - If conflicts → assign conflict resolution to:
     a) Original specialist (if simple)
     b) Multiple specialists involved (if complex)
     c) Escalate to architect (if critical)
7. Manager coordinates resolution and re-runs checks
```

**4. Architect's Final Review**
- Reviews PR against original intent
- Validates against global rules
- Checks test coverage and documentation
- Merges to main if approved
- Updates global context with changes

---

### Section 5: Error Recovery & Escalation

#### Three-Level Recovery Hierarchy

**Level 1: Self-Recovery (Specialist)**
- Agent encounters error (test failure, API timeout, invalid output)
- Attempts self-diagnosis and fix
- Max 2-3 retry attempts
- If resolved → continues work
- If unresolved after retries → escalate to manager

**Level 2: Manager Intervention**
- Receives error report from specialist with context
- Analyzes error type:
  - **Simple**: Reframe task, send back to same specialist
  - **Skill gap**: Reassign to different specialist with relevant expertise
  - **Complex**: Assign2-3 specialists to collaborate- **Tool/capability**: Check if specialist's model tier is insufficient, suggest upgrade
- Manager monitors token consumption vs progress- If agent consuming excessive tokens without progress → intervene early
  - Can add additional agents to assist
- If manager's strategies fail after attempts → escalate to architect

**Level 3: Architect Escalation**
- Receives escalation with full error context and attempted solutions
- Higher-level analysis:
  - Is task specification unclear? → reformulate and reassign
  - Is task too complex? → decompose into subtasks
  - Is repository context missing? → provide additional analysis
- Architect can reassign to different manager team
- Final fallback → human-in-the-loop notification

#### Proactive Monitoring

**Manager's Progress Tracking**:
- Polls specialist status at intervals
- Checks token consumption vs deliverables
- Flags: `token_used > expected_threshold AND progress < min_threshold`
- Early intervention before complete failure

---

### Section 6: Model & Tool Configuration

#### Multi-Layer API Support

**1. Model Configuration Schema**
```yaml
agents:
  architect:
    model_provider: "openai"# or anthropic, google, etc.
    model_id: "gpt-4"
    api_key_env: "OPENAI_API_KEY"
    temperature: 0.2
    max_tokens: 4000
    
  managers:
    - id: "manager-1"
      model_provider: "anthropic"
      model_id: "claude-sonnet-3-5"
      team: "backend"
      specialists:
    - id: "sd1"
      specialty: "frontend"
      model_provider: "openai"
      model_id: "gpt-4-mini"
      tools: ["filesystem", "git", "npm"]
      
    - id: "sd2"
      specialty: "backend"
      model_provider: "google"
      model_id: "gemini-1.5-pro"
      tools: ["filesystem", "git", "grep", "database"]
```

**2. Capability-Based Tool Access**

```python
TOOL_REQUIREMENTS = {
    "filesystem": {"min_model_tier": 1},
    "git": {"min_model_tier": 1},
    "grep": {"min_model_tier": 2},  # Prevents hallucination
    "sed": {"min_model_tier": 2},
    "database": {"min_model_tier": 3},
    "api_calls": {"min_model_tier": 3}
}

MODEL_TIERS = {
    "gpt-4": 4,
    "claude-opus": 4,
    "gpt-4-mini": 2,
    "claude-sonnet": 3,
    "gemini-flash": 1
}

def can_use_tool(agent, tool):
    agent_tier = MODEL_TIERS.get(agent.model_id, 0)
    required_tier = TOOL_REQUIREMENTS[tool]["min_model_tier"]
    return agent_tier >= required_tier
```

**3. Recommendations**
- System provides default configuration with best practices
- UI highlights recommended models per role
- Warnings when user selects low-tier model for architect
- Allow overrides but log warnings

---

### Section 7: Verification & Quality Assurance

#### Multi-Stage Verification Pipeline

**Stage 1: Agent Self-Check**
- Specialist runs tests locally before raising PR
- Validates against task acceptance criteria
- Checks code formatting

**Stage 2: Automated CI/CD**
```yaml
pr_checks:
  - name: "Lint"
    tools: ["eslint", "pylint", "rustfmt"]
    blocking: true
    
  - name: "Tests"
    command: "npm test"  # or pytest, cargo test, etc.
    blocking: true
    
  - name: "Coverage"
    threshold: 80%
    blocking: false
  - name: "Security Scan"
    tools: ["snyk", "bandit"]
    blocking: true
```

**Stage 3: Optional Reviewer Agent**
- Specialist agent trained on code quality patterns
- Reviews PR for:
  - Code smells
  - Pattern consistency with repo
  - Documentation completeness
  - Test adequacy
- Creates low-priority issues for improvements (non-blocking)

**Stage 4: Manager Coordination Review**
- Validates PR against original task assignment
- Checks for unintended side effects
- Ensures merge safety

**Stage 5: Architect Final Gate**
- Reviews against system architecture
- Validates global rules compliance
- Final approval before merge

---

### Section 8: User Interface & Configuration

#### Interactive Configuration UI

**1. Notion-Style Drag-and-Drop Builder**

**UI Components**:
- **Agent Blocks**: Draggable cards for Architect, Manager, Specialist
- **Connection Lines**: Visual links showing hierarchy (Architect → Managers → Specialists)
- **Property Panels**: Click agent to configure:
  - Model provider dropdown
  - Model ID selection
  - Tool permissions checkboxes
  - Specialty tags (for specialists)
  - Team assignment (for managers)

**Workflow**:
```
1. User drags "Architect" block to canvas → auto-configured with recommendations
2. User drags 2-3 "Manager" blocks → connects to Architect
3. User drags multiple "Specialist" blocks → assigns to Managers
4. User clicks each block to customize model, tools, specialty
5. UI generates YAML/JSON config file in real-time
6. User can export config or directly start harness
```

**2. Configuration File Format**
```yaml
harness_config:
  version: "1.0"
  
  repository:
    url: "https://github.com/user/repo"
    branch: "main"
    
  github_integration:
    token_env: "GITHUB_TOKEN"
    create_issues: true
    auto_merge: false# Require human approval
    
  architect:
    model:
      provider: "openai"
      id: "gpt-4"skills:
      - "production-architectures"
      - "system-design"
      - "code-review"
      
  managers:
    - id: "mgr-backend"
      team: "backend"
      model:
        provider: "anthropic"
        id: "claude-sonnet-3-5"max_specialists: 5- id: "mgr-frontend"
      team: "frontend"
      model:
        provider: "openai"
        id: "gpt-4-mini"
      max_specialists: 5specialists:
    - id: "sd-backend-1"
      specialty: "backend-api"
      manager: "mgr-backend"
      model:
        provider: "google"
        id: "gemini-1.5-pro"
      tools: ["filesystem", "git", "grep", "database"]
      
    - id: "sd-frontend-1"
      specialty: "react"
      manager: "mgr-frontend"
      model:
        provider: "openai"
        id: "gpt-4-mini"
      tools: ["filesystem", "git", "npm"]
  resource_management:
    global_token_budget: 1000000
    per_agent_budget: 50000
    budget_strategy: "dynamic"  # or "fixed", "priority"
    
  monitoring:
    dashboard: true
    live_github_link: true
    progress_notifications: true
```

**3. Progress Monitoring UI**

**Dashboard Components**:
- **Task Board**: Kanban-style (To Do → In Progress → Review → Done)
- **Agent Status Panel**: Live view of what each agent is working on
- **Token Usage Chart**: Real-time consumption per agent
- **GitHub Integration**: Embedded view of Issues, PRs, commits
- **Test Window**: Popup terminal for users to test intermediate features
- **Log Stream**: Filterable by agent, severity, timestamp

---

### Section 9: System Flow & Implementation

#### End-to-End Workflow

**Phase 1: Initialization**
```
1. User configures harness via UI or config file
2. System validates configuration (API keys, model availability, tool permissions)
3. Architect agent initializes
4. Manager agents spawn based on config
5. Specialist agents spawn and register with managers
6. System connects to GitHub repository
```

**Phase 2: Repository Analysis**
```
1. Architect clones repository
2. Analyzes structure:
   - File tree and module organization
   - Dependencies and build system
   - Test framework and commands
   - Documentation and README
   - Recent commits and patterns
3. Creates initial context map
4. Stores in global context
```

**Phase 3: Task Decomposition**
```
1. User submits prompt: "Add authentication to API"
2. Architect analyzes intent:
   - What: JWT-based authentication
   - Where: Express API endpoints
   - Success: Protected routes, login/logout, tests
3. Extracts global rules: "Use bcrypt for passwords", "JWT expiry24h"
4. Decomposes into GitHub Issues:
   - Issue #1: "Implement user model and password hashing"
   - Issue #2: "Create JWT generation and validation middleware"
   - Issue #3: "Add login/logout endpoints"
   - Issue #4: "Protect existing routes with auth middleware"
   - Issue #5: "Write integration tests for auth flow"
5. Creates context windows for each issue
6. Posts issues to GitHub
```

**Phase 4: Task Assignment**
```
1. Architect assigns issue clusters to managers:
   - Manager-1 (backend): Issues #1, #2, #3, #4
   - Manager-2 (testing): Issue #5
2. Manager-1 analyzes issues:
   - Issue #1: Assign to sd-backend-1 (database specialist)
   - Issue #2, #3: Assign to sd-backend-2 (API specialist)
   - Issue #4: Wait for #2, #3 completion, then assign
3. Manager provides context windows to specialists
```

**Phase 5: Specialist Execution**
```
For each specialist:
1. Receives task assignment from manager
2. Creates branch: agent/sd-backend-1/1-user-model
3. Reads context window
4. Pulls relevant code from repository
5. Implements feature:
   - Writes code
   - Writes tests
   - Runs tests locally
   - Self-verifies
6. If error → self-recover (2-3 attempts)
7. If still blocked → escalate to manager
8. If successful → commits and raises PR
9. Reports completion to manager
```

**Phase 6: Review & Merge**
```
1. Manager receives PR notification
2. Triggers automated CI/CD checks
3. If optional reviewer enabled:
   - Assigns reviewer agent
   - Reviewer analyzes code quality
   - Creates low-priority improvement issues
4. Manager checks for conflicts with other PRs
5. If conflicts:
   - Assigns conflict resolution to relevant specialists
   - Coordinates resolution
6. If clean:
   - Approves PR
   - Forwards to architect for final review
7. Architect reviews:
   - Validates against original intent
   - Checks global rules compliance
   - Merges to main
8. Updates global context with changes
9. Notifies user of completion
```

**Phase 7: Monitoring & User Feedback**
```
1. UI displays progress at each stage
2. User can test intermediate features via test window
3. User can view live GitHub activity
4. System logs token usage and performance metrics
5. User can intervene at any stage if needed
```

---

### Section 10: Resource Management & Optimization

#### Token Budget Allocation

**Strategy1: Per-Agent Fixed Budget**
```python
BUDGET_ALLOCATION = {
    "architect": "unlimited",  # Critical path
    "manager": 100000,  # Per manager
    "specialist": 50000  # Per specialist
}

def check_budget(agent):
    if agent.tokens_used > agent.budget:
        notify_manager(agent, "Budget exceeded")
        if agent.productivity_score < threshold:
            flag_for_human_review()
```

**Strategy 2: Dynamic Allocation**
```python
def reallocate_budget(team):
    total_consumed = sum(agent.tokens_used for agent in team)
    total_output = sum(agent.tasks_completed for agent in team)
    
    for agent in team:
        efficiency = agent.tasks_completed / agent.tokens_used
        if efficiency > team_avg:
            agent.budget += bonus_tokenselif efficiency < team_avg * 0.5:
            agent.budget -= penalty_tokens
```

**Strategy 3: Priority-Based**
```python
PRIORITY_MULTIPLIERS = {
    "critical": 2.0,
    "high": 1.5,
    "normal": 1.0,
    "low": 0.5
}

def allocate_for_task(task, agent):
    base_budget = 50000
    return base_budget * PRIORITY_MULTIPLIERS[task.priority]
```

#### Performance Tracking

**Metrics Collected**:
```python
agent_metrics = {
    "tokens_consumed": int,
    "tasks_completed": int,
    "tasks_failed": int,
    "average_task_time": float,
    "error_escalations": int,
    "self_recovery_rate": float,
    "code_quality_score": float,# From reviewer
    "test_coverage": float,
    "merge_conflicts_caused": int
}
```

**Reports Generated**:
1. **Real-time Dashboard**: Live agent status, token burn rate
2. **Post-Task Summary**: Per-task breakdown of agents involved, tokens used, time taken
3. **Agent Performance Profile**: Historical efficiency, specialty success rates
4. **Cost Optimization Suggestions**: "Consider using gpt-4-mini for sd-backend-2" based on performance data

---

## Part II: Complete Expanded Design Specification

### Table of Contents
1. System Architecture & Agent Hierarchy
2. Agent Specifications (Detailed)
3. Tool Ecosystem
4. Context Management System
5. Task Assignment & Routing
6. Git Workflow & Conflict Resolution
7. Error Recovery & Escalation
8. Model Configuration & API Integration
9. Verification & Quality Assurance
10. User Interface & Configuration
11. Resource Management & Optimization
12. Monitoring & Observability
13. Security & Permissions
14. Extensibility & Plugin System
15. Testing Strategy
16. Deployment & Operations

---

### Section 1: System Architecture & Agent Hierarchy (Expanded)

#### 1.1 Overall System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface Layer│
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Web Dashboard│  │  Config UI│  │  Test Window │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                │
┌─────────────────────────────────────────────────────────────┐
│                   Orchestration Layer                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Architect Agent                         │   │
│  │  - Intent Analysis- Task Decomposition          │   │
│  │  - Repo Analysis      - Final Review & Merge        │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                │
┌─────────────────────────────────────────────────────────────┐
│                   Coordination Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Manager-1   │  │  Manager-2   │  │  Manager-3   │     │
│  │  (Backend)   │  │  (Frontend)  │  │  (DevOps)    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                    Execution Layer                           │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ │
│  │SD1 │ │SD2 │ │SD3 │ │SD4 │ │SD5 │ │SD6 │ │SD7 │ │SD8 │ │
│  └────┘ └────┘ └────┘ └────┘ └────┘ └────┘ └────┘ └────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │  GitHub  │ │ Context  │ │  Tool    │ │  Model│      │
│  │Integration│ │  Store   │ │ Runtime│ │  APIs    │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└─────────────────────────────────────────────────────────────┘
```

#### 1.2 Communication Patterns

**Message Flow Types**:

1. **Command Messages** (Top-down)
```json
{
  "type": "command",
  "from": "architect",
  "to": "manager-1",
  "payload": {
    "action": "assign_tasks",
    "tasks": [
      {
        "issue_id": "42",
        "title": "Implement user authentication",
        "context_window_id": "ctx-42",
        "priority": "high",
        "estimated_complexity": 8
      }
    ]
  },
  "timestamp": "2026-09-26T15:00:00Z"
}
```

2. **Status Updates** (Bottom-up)
```json
{
  "type": "status_update",
  "from": "sd-backend-1",
  "to": "manager-1",
  "payload": {
    "task_id": "42",
    "status": "in_progress",
    "progress_percentage": 60,
    "tokens_consumed": 15000,
    "estimated_completion": "2026-09-26T16:30:00Z",
    "blockers": []
  },
  "timestamp": "2026-09-26T15:30:00Z"
}
```

3. **Error Escalations**
```json
{
  "type": "escalation",
  "from": "sd-backend-1",
  "to": "manager-1",
  "payload": {
    "task_id": "42",
    "error_type": "test_failure",
    "attempts": 3,
    "error_details": {
      "test": "test_user_login",
      "error": "AssertionError: Expected 200, got 401",
      "stacktrace": "..."
    },
    "context_summary": "Implemented JWT validation but tokens not being accepted"
  },
  "severity": "medium",
  "timestamp": "2026-09-26T15:45:00Z"
}
```

4. **Coordination Messages** (Peer-to-peer via Manager)
```json
{
  "type": "coordination",
  "from": "manager-1",
  "to": ["sd-backend-1", "sd-backend-2"],
  "payload": {
    "action": "collaborate",
    "task_id": "42",
    "reason": "Complex task requiring multiple specialties",
    "roles": {
      "sd-backend-1": "Implement auth logic",
      "sd-backend-2": "Write integration tests"
    },
    "shared_context": "ctx-42-shared"
  },
  "timestamp": "2026-09-26T15:50:00Z"
}
```

#### 1.3 Data Flow Architecture

```
User Prompt↓
[Intent Analyzer] → Extracts: intent, constraints, success criteria
    ↓
[Global Rule Extractor] → Identifies: coding standards, arch decisions
    ↓
[Task Decomposer] → Creates: GitHub Issues + Context Windows
    ↓
[Task Router] → Assigns: Issues to Manager teams
    ↓
[Manager Assignment Engine] → Multi-factor routing to Specialists
    ↓
[Specialist Executor] → Works in isolated branch
    ↓
[Self-Verification] → Runs tests, lint, format
    ↓
[PR Creation] → Raises PR to main
    ↓
[Automated Checks] → CI/CD pipeline
    ↓
[Optional Review] → Reviewer agent (code quality)
    ↓
[Manager Coordination] → Conflict detection & resolution
    ↓
[Architect Review] → Final validation
    ↓
[Merge to Main] → Integration complete↓
[Context Update] → Global state refreshed↓
[User Notification] → Task complete with metrics
```

---

### Section 2: Agent Specifications (Detailed)

#### 2.1 Architect Agent

**Role**: System orchestrator and quality gatekeeper

**Training Data / System Prompt Focus**:
- Production-grade software architectures (microservices, monoliths, serverless)
- Design patterns (Gang of Four, Enterprise patterns)
- System design principles (SOLID, DRY, KISS, YAGNI)
- Code review best practices
- Repository analysis techniques
- Task decomposition strategies
- GitHub workflow management

**Recommended Models**:
- Primary: GPT-4, Claude Opus, Gemini 1.5 Pro
- Fallback: GPT-4-turbo, Claude Sonnet

**Configuration**:
```yaml
architect:
  model:
    provider: "openai"
    id: "gpt-4"
    temperature: 0.2# Low for consistency
    max_tokens: 8000
    top_p: 0.95
  
  capabilities:
    - intent_analysis
    - task_decomposition
    - repository_analysis
    - code_review
    - merge_coordination
    - global_rule_extraction
  
  tools:
    - github_api
    - repository_clone
    - file_system_read
    - context_store_read_write
    - agent_messaging
  behavioral_parameters:
    task_complexity_threshold: 7# Above this, recommend multi-agent
    review_strictness: "high"
    auto_merge: false# Require human approval for merges
    escalation_timeout: 3600  # 1 hour before escalating stuck tasks
  
  knowledge_bases:
    - "production_architectures"
    - "design_patterns"
    - "code_review_guidelines"
    - "common_antipatterns"
```

**Key Responsibilities Detailed**:

1. **Repository Analysis**
   - Clone target repository
   - Analyze file structure: `src/`, `tests/`, `docs/`, `config/`
   - Identify tech stack: `package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`
   - Parse build system: `Makefile`, `webpack.config.js`, `tsconfig.json`
   - Detect test framework: Jest, Pytest, JUnit, Cargo test
   - Extract coding patterns: naming conventions, module organization
   - Identify dependencies and their versions
   - Map existing features and components
   - Create repository knowledge graph

2. **Intent Analysis**
   - Parse user prompt for primary intent
   - Extract explicit requirements
   - Infer implicit constraints
   - Identify success criteria
   - Detect global rules (e.g., "use TypeScript for all new code")
   - Classify task complexity (1-10 scale)
   - Estimate effort and timeline

3. **Task Decomposition**
   - Break down user intent into atomic tasks
   - Create dependency graph between tasks
   - Generate GitHub Issues with:
     - Clear titles
     - Detailed descriptions
     - Acceptance criteria
     - Labels (frontend, backend, testing, etc.)
     - Assignable to specialist types
   - Create context windows for each task:
     - Relevant files to examine
     - Related existing code
     - Design constraints
     - Testing requirements

4. **Final Review & Merge**
   - Review PRs from specialists (via managers)
   - Validate against original user intent
   - Check global rules compliance
   - Verify test coverage
   - Ensure documentation updated
   - Check for unintended side effects
   - Approve or request changes
   - Merge to main branch
   - Update global context with changes

#### 2.2 Manager Agents (2-3 per deployment)

**Role**: Team coordinators and middle management

**Specialization Types**:
1. **Backend Manager**: Coordinates API, database, server-side specialists
2. **Frontend Manager**: Coordinates UI, UX, client-side specialists
3. **DevOps Manager**: Coordinates infrastructure, CI/CD, deployment specialists

**Training Data / System Prompt Focus**:
- Task routing and load balancing
- Team coordination strategies
- Error diagnosis and recovery
- Conflict resolution techniques
- Progress monitoring and reporting
- Resource allocation optimization

**Recommended Models**:
- Primary: Claude Sonnet 3.5, GPT-4-mini, Gemini 1.5 Flash
- Fallback: GPT-3.5-turbo, Claude Haiku

**Configuration Example (Backend Manager)**:
```yaml
managers:
  - id: "mgr-backend"
    team: "backend"
    model:
      provider: "anthropic"
      id: "claude-sonnet-3-5"
      temperature: 0.3
      max_tokens: 4000
    
    specialties_managed:
      - backend-api
      - database
      - authentication
      - caching
      - message-queues
    
    max_specialists: 8
    concurrent_task_limit: 5
    
    tools:
      - github_api
      - agent_messaging
      - context_store_read_write
      - conflict_detector- token_monitor
    
    behavioral_parameters:
      assignment_algorithm: "multi_factor"  # vs "round_robin", "least_loaded"
      collaboration_threshold: 7# Complexity above which assign multiple agents
      progress_check_interval: 300  # 5 minutestoken_warning_threshold: 0.8  # 80% of agent budget
      escalation_retry_count: 2# Attempts before escalating to architect
    performance_tracking:
      track_tokens_per_task: true
      track_time_per_task: true
      track_error_rates: true
      generate_efficiency_reports: true
```

**Key Responsibilities Detailed**:

1. **Task Reception & Analysis**
   - Receive task cluster from architect
   - Analyze each task's requirements:
     - Required specialty
     - Estimated complexity
     - Dependencies on other tasks
     - Time sensitivity- Group related tasks for potential collaboration
   - Prioritize based on dependencies and urgency

2. **Multi-Factor Task Assignment**
   ```python
   def assign_task_detailed(self, task, available_specialists):
       scores = {}
       
       for specialist in available_specialists:
           # Factor1: Specialty Match (40% weight)
           specialty_score = self.calculate_specialty_match(
               task.required_specialty,
               specialist.specialties,
               specialist.past_performance_in_specialty
           )
           
           # Factor 2: Availability (20% weight)
           availability_score = self.calculate_availability(
               specialist.current_tasks,
               specialist.queue_length,
               specialist.last_task_completion_time
           )
           
           # Factor 3: Load Balance (20% weight)
           load_score = self.calculate_load_balance(
               specialist.tokens_used_today,
               specialist.tasks_completed_today,
               team_average_load
           )
           
           # Factor 4: Capability Match (20% weight)
           capability_score = self.calculate_capability(
               task.required_tools,
               specialist.available_tools,
               task.complexity,
               specialist.model_tier
           )
           
           total_score = (
               specialty_score * 0.4 +
               availability_score * 0.2 +
               load_score * 0.2 +
               capability_score * 0.2
           )
           
           scores[specialist] = total_score
       
       # For complex tasks (complexity > threshold), assign top N specialists
       if task.complexity > self.collaboration_threshold:
           sorted_specialists = sorted(scores.items(), key=lambda x: x[1], reverse=True)
           return [s[0] for s in sorted_specialists[:3]]
       else:
           return [max(scores.items(), key=lambda x: x[1])[0]]
   ```

3. **Progress Monitoring**
   - Poll specialist status at intervals
   - Track metrics:
     - Task progress percentage
     - Tokens consumed vs expected
     - Time elapsed vs estimated
     - Blockers or errors encountered
   - Proactive intervention:
     - If token burn high but progress low → investigate
     - If time elapsed > 2x estimated → offer assistance
     - If errors repeated → prepare escalation

4. **Error Handling & Recovery**
   ```python
   def handle_escalation(self, escalation_message):
       specialist = escalation_message.from
       task = escalation_message.task_id
       error = escalation_message.error_details
       
       # Analyze error type
       error_category = self.categorize_error(error)
       
       if error_category == "skill_gap":
           # Reassign to specialist with relevant expertise
           better_specialist = self.find_specialist_with_skill(error.required_skill)
           self.reassign_task(task, specialist, better_specialist)
           
       elif error_category == "tool_limitation":
           # Check if specialist's model tier is insufficient
           if specialist.model_tier < error.required_tier:
               self.suggest_model_upgrade(specialist)
           else:
               self.provide_tool_guidance(specialist, error.tool_name)
       
       elif error_category == "complex_task":
           # Assign additional specialists to collaborate
           collaborators = self.select_collaborators(task, specialist,count=2)
           self.create_collaboration_team(task, [specialist] + collaborators)
       
       elif error_category == "unclear_requirements":
           # Reframe task with clearer instructions
           clarified_task = self.clarify_task_requirements(task, error.confusion_point)
           self.update_specialist_task(specialist, clarified_task)
       else:
           # Unknown error type - escalate to architect
           self.escalate_to_architect(escalation_message)
   ```

5. **Merge Coordination**
   - Detect potential merge conflicts before they occur
   - When multiple specialists' PRs touch related code:
     - Sequence merges (merge A, then B)
     - Or coordinate simultaneous resolution
   - Assign conflict resolution:
     - Simple conflicts → original specialist
     - Complex conflicts → multiple specialists coordinate- Critical conflicts → escalate to architect
   - Re-run automated checks after resolution

#### 2.3 Specialist Developer Agents (8-15 per deployment)

**Role**: Code implementation and feature development

**Specialist Types & Configurations**:

##### 2.3.1 Backend API Specialist
```yaml
specialists:
  - id: "sd-backend-api-1"
    type: "specialist_developer"
    specialty: "backend-api"
    manager: "mgr-backend"
    model:
      provider: "openai"
      id: "gpt-4-mini"
      temperature: 0.4
      max_tokens: 4000
    
    training_focus:
      - RESTful API design
      - Express.js / FastAPI / Spring Boot patterns
      - API authentication (JWT, OAuth)
      - Request validation
      - Error handling middleware- API documentation (OpenAPI/Swagger)
      - Rate limiting
      - CORS configuration
    
    tools:
      - filesystem_read_write
      - git_operations
      - grep_search
      - code_execution
      - test_runner
      - api_testing (curl, Postman)
    
    file_patterns:
      - "src/routes/**/*.js"
      - "src/controllers/**/*.js"
      - "src/middleware/**/*.js"
      - "src/api/**/*.ts"
      - "tests/integration/**/*.test.js"
    
    common_tasks:
      - "Create REST endpoint"
      - "Add authentication middleware"
      - "Implement rate limiting"
      - "Write API integration tests"
```

##### 2.3.2 Database Specialist
```yaml
  - id: "sd-database-1"
    type: "specialist_developer"
    specialty: "database"
    manager: "mgr-backend"
    
    model:
      provider: "google"
      id: "gemini-1.5-pro"
      temperature: 0.3
      max_tokens: 4000
    
    training_focus:
      - Database schema design
      - SQL query optimization
      - ORM usage (Sequelize, SQLAlchemy, Prisma)
      - Migration management
      - Indexing strategies
      - Database transactions
      - Connection pooling
      - NoSQL patterns (MongoDB, Redis)
    
    tools:
      - filesystem_read_write
      - git_operations
      - database_client
      - migration_tools
      - query_analyzer
      - test_runner
    
    file_patterns:
      - "src/models/**/*.js"
      - "src/schemas/**/*.ts"
      - "migrations/**/*.sql"
      - "prisma/schema.prisma"
      - "src/database/**/*.py"
    
    common_tasks:
      - "Create database model"
      - "Write migration"
      - "Optimize query"
      - "Add indexes"
      - "Implement caching layer"
```

##### 2.3.3 Frontend React Specialist
```yaml
  - id: "sd-frontend-react-1"
    type: "specialist_developer"
    specialty: "frontend-react"
    manager: "mgr-frontend"
    
    model:
      provider: "openai"
      id: "gpt-4-mini"
      temperature: 0.5# Slightly higher for creative UI work
      max_tokens: 4000
    
    training_focus:
      - React component patterns (functional, hooks)
      - State management (Redux, Zustand, Context API)
      - React Router
      - Form handling and validation
      - API integration (fetch, axios)
      - Performance optimization (memo, useMemo, useCallback)
      - Accessibility (ARIA, semantic HTML)- CSS-in-JS (styled-components, emotion)
    
    tools:
      - filesystem_read_write
      - git_operations
      - npm_commands
      - browser_testing
      - test_runner (Jest, React Testing Library)
      - linting (eslint)
    
    file_patterns:
      - "src/components/**/*.jsx"
      - "src/pages/**/*.tsx"
      - "src/hooks/**/*.js"
      - "src/store/**/*.js"
      - "src/styles/**/*.css"
    
    common_tasks:
      - "Create React component"
      - "Add form validation"
      - "Implement state management"
      - "Write component tests"
      - "Optimize rendering performance"
```

##### 2.3.4 Frontend Styling Specialist
```yaml
  - id: "sd-frontend-styling-1"
    type: "specialist_developer"
    specialty: "frontend-styling"
    manager: "mgr-frontend"
    
    model:
      provider: "anthropic"
      id: "claude-sonnet-3-5"
      temperature: 0.6# Higher for creative design work
      max_tokens: 3000
    
    training_focus:
      - CSS architecture (BEM, SMACSS)
      - Responsive design
      - CSS Grid and Flexbox
      - Animations and transitions
      - Tailwind CSS
      - CSS preprocessors (Sass, Less)
      - Design systems
      - Cross-browser compatibility
    
    tools:
      - filesystem_read_write
      - git_operations
      - browser_testing
      - css_linting
      - design_token_management
    file_patterns:
      - "src/styles/**/*.css"
      - "src/styles/**/*.scss"
      - "tailwind.config.js"
      - "src/theme/**/*.ts"
    
    common_tasks:
      - "Implement responsive layout"
      - "Create animation"
      - "Build design system component"
      - "Optimize CSS bundle size"
```

##### 2.3.5 Testing Specialist
```yaml
  - id: "sd-testing-1"
    type: "specialist_developer"
    specialty: "testing"
    manager: "mgr-backend"  # Can be assigned to any manager
    
    model:
      provider: "openai"
      id: "gpt-4"
      temperature: 0.3
      max_tokens: 4000
    
    training_focus:
      - Unit testing patterns
      - Integration testing
      - E2E testing (Playwright, Cypress)
      - Test-driven development (TDD)
      - Mocking and stubbing
      - Test coverage analysis
      - Performance testing
      - Security testing basics
    
    tools:
      - filesystem_read_write
      - git_operations
      - test_runner
      - coverage_analyzer
      - e2e_browser
      - mocking_tools
    
    file_patterns:
      - "tests/**/*.test.js"
      - "tests/**/*.spec.ts"
      - "__tests__/**/*.js"
      - "e2e/**/*.test.js"
      - "cypress/**/*.cy.js"
    
    common_tasks:
      - "Write unit tests"
      - "Create integration test suite"
      - "Add E2E tests"
      - "Improve test coverage"
      - "Mock external dependencies"
```

##### 2.3.6 DevOps Specialist
```yaml
  - id: "sd-devops-1"
    type: "specialist_developer"
    specialty: "devops"
    manager: "mgr-devops"
    
    model:
      provider: "google"
      id: "gemini-1.5-pro"
      temperature: 0.2# Low for infrastructure consistency
      max_tokens: 4000
    
    training_focus:
      - CI/CD pipeline configuration
      - Docker and containerization
      - Kubernetes basics
      - Infrastructure as Code (Terraform, CloudFormation)
      - GitHub Actions / GitLab CI
      - Environment configuration
      - Deployment strategies (blue-green, canary)
      - Monitoring and logging setup
    
    tools:
      - filesystem_read_write
      - git_operations
      - docker_commands
      - kubectl_commands
      - terraform_commands
      - cloud_cli (aws, gcp, azure)
    
    file_patterns:
      - ".github/workflows/**/*.yml"
      - "Dockerfile"
      - "docker-compose.yml"
      - "terraform/**/*.tf"
      - "k8s/**/*.yaml"
      - ".env.example"
    
    common_tasks:
      - "Create CI/CD pipeline"
      - "Write Dockerfile"
      - "Configure deployment"
      - "Set up monitoring"
      - "Manage environment variables"
```

##### 2.3.7 Security Specialist
```yaml
  - id: "sd-security-1"
    type: "specialist_developer"
    specialty: "security"
    manager: "mgr-backend"
    
    model:
      provider: "openai"
      id: "gpt-4"
      temperature: 0.1  # Very low for security rigor
      max_tokens: 4000
    
    training_focus:
      - OWASP Top 10
      - Input validation and sanitization
      - Authentication and authorization
      - Cryptography basics
      - Security headers
      - Dependency vulnerability scanning
      - SQL injection prevention
      - XSS and CSRF protection
    
    tools:
      - filesystem_read_write
      - git_operations
      - security_scanners (snyk, bandit, semgrep)
      - dependency_audit
      - static_analysis
    
    file_patterns:
      - "src/auth/**/*.js"
      - "src/middleware/security/**/*.js"
      - "package.json"  # For dependency audits
      - "requirements.txt"
    common_tasks:
      - "Audit authentication flow"
      - "Fix security vulnerabilities"
      - "Add input validation"
      - "Review dependency security"
      - "Implement security headers"
```

##### 2.3.8 Documentation Specialist
```yaml
  - id: "sd-docs-1"
    type: "specialist_developer"
    specialty: "documentation"
    manager: "mgr-frontend"  # Or any manager
    
    model:
      provider: "anthropic"
      id: "claude-sonnet-3-5"
      temperature: 0.5
      max_tokens: 4000
    
    training_focus:
      - Technical writing
      - API documentation (OpenAPI, JSDoc)
      - README best practices
      - Inline code comments
      - Architecture diagrams
      - User guides
      - Changelog management
    tools:
      - filesystem_read_write
      - git_operations
      - markdown_formatting
      - diagram_generation (mermaid)
      - api_doc_tools (swagger)
    
    file_patterns:
      - "README.md"
      - "docs/**/*.md"
      - "CHANGELOG.md"
      - "CONTRIBUTING.md"
      - "src/**/*.md"
      - "openapi.yaml"
    
    common_tasks:
      - "Write README"
      - "Document API endpoints"
      - "Create architecture diagrams"
      - "Update changelog"
      - "Write inline documentation"
```

##### 2.3.9 Performance Optimization Specialist
```yaml
  - id: "sd-performance-1"
    type: "specialist_developer"
    specialty: "performance"
    manager: "mgr-backend"
    
    model:
      provider: "openai"
      id: "gpt-4"
      temperature: 0.3
      max_tokens: 4000
    
    training_focus:
      - Performance profiling
      - Query optimization
      - Caching strategies (Redis, CDN)
      - Code optimization
      - Bundle size reduction
      - Lazy loading
      - Database indexing
      - Algorithm complexity analysis
    
    tools:
      - filesystem_read_write
      - git_operations
      - profiling_tools
      - performance_testing
      - bundle_analyzer
      - query_analyzer
    
    file_patterns:
      - "src/**/*.js"  # Can work acrosscodebase
      - "webpack.config.js"
      - "vite.config.ts"
    
    common_tasks:
      - "Profile application performance"
      - "Optimize database queries"
      - "Reduce bundle size"
      - "Implement caching"
      - "Fix memory leaks"
```

##### 2.3.10 Code Review Specialist
```yaml
  - id: "sd-reviewer-1"
    type: "specialist_developer"
    specialty: "code-review"
    manager: null  # Can be assigned to any manager dynamically
    
    model:
      provider: "openai"
      id: "gpt-4"
      temperature: 0.2
      max_tokens: 4000
    
    training_focus:
      - Code quality standards
      - Design patterns recognition
      - Code smells detection
      - Best practices across languages
      - Refactoring techniques
      - Testing adequacy assessment
      - Performance implications- Security review
    
    tools:
      - filesystem_read
      - git_operations
      - diff_analysis
      - static_analysis_tools
      - linting_tools
    
    review_checklist:
      - "Code follows repository patterns"
      - "Adequate test coverage (>80%)"
      - "No obvious security issues"
      - "Error handling present"
      - "Documentation updated"
      - "No code smells (long functions, deep nesting)"
      - "Performance considerations addressed"
      - "Accessibility standards met (for frontend)"
    
    common_tasks:
      - "Review pull requests"
      - "Create code quality issues"
      - "Suggest refactoring opportunities"
      - "Verify test coverage"
```

#### 2.4 Specialist Agent Behavioral Patterns

**All Specialists Follow This Workflow**:

```python
classSpecialistAgent:
    def execute_task(self, task):
        # 1. Receive task from manager
        self.log(f"Received task: {task.title}")
        self.load_context_window(task.context_window_id)
        
        # 2. Create isolated branch
        branch_name = f"agent/{self.id}/{task.issue_id}-{task.slug}"
        self.git_create_branch(branch_name)
        
        # 3. Analyze task requirements
        requirements = self.parse_task_requirements(task)
        files_to_modify = self.identify_files(requirements)
        
        # 4. Implement solution
        try:
            for attempt in range(3):  # Self-recovery: max 3 attempts
                self.implement_solution(requirements, files_to_modify)
                
                # 5. Self-verification
                verification_result = self.verify_implementation()
                
                if verification_result.success:
                    break
                else:
                    self.log(f"Attempt {attempt + 1} failed: {verification_result.error}")
                    if attempt < 2:
                        self.self_recover(verification_result)
                    else:
                        # Escalate to manager
                        self.escalate_to_manager(task, verification_result)
                        return
            # 6. Commit and raise PR
            self.git_commit(f"Implement {task.title}")
            pr = self.create_pull_request(task)
            
            # 7. Report completion to manager
            self.report_completion(task, pr)
            
        except Exception as e:
            self.escalate_to_manager(task, error=e)
    
    def verify_implementation(self):
        # Run tests
        test_result = self.run_tests()
        if not test_result.passed:
            return VerificationResult(success=False, error=test_result.failures)
        # Run linting
        lint_result = self.run_linter()
        if not lint_result.clean:
            self.auto_fix_lint_issues()
        
        # Check formatting
        format_result = self.run_formatter()
        
        return VerificationResult(success=True)
    def self_recover(self, verification_result):
        # Analyze what went wrong
        error_type = self.classify_error(verification_result.error)
        
        if error_type == "syntax_error":
            self.fix_syntax_error(verification_result.error)
        elif error_type == "test_failure":
            self.debug_test_failure(verification_result.error)
        elif error_type == "import_error":
            self.resolve_import_error(verification_result.error)
        else:
            # Unknown error, prepare for escalation
            pass
```

---

### Section 3: Tool Ecosystem (Expanded)

#### 3.1 Tool Categories

**Core Tools (Available to All Agents)**:
1. `agent_messaging` - Inter-agent communication
2. `context_store_read` - Read global/local context
3. `logging` - Structured logging

**Tier 1 Tools (Low Model Threshold)**:
4. `filesystem_read` - Read files
5. `filesystem_list` - List directory contents
6. `git_status` - Check git status
7. `git_log` - View commit history

**Tier 2 Tools (Medium Model Threshold - Prevents Hallucination)**:
8. `filesystem_write` - Write/modify files
9. `git_operations` - Create branches, commit, push
10. `grep_search` - Search code patterns
11. `sed_replace` - Pattern-based replacement
12. `npm_commands` - Package manager operations
13. `test_runner` - Execute test suites
14. `linting` - Code quality checks
15. `formatting` - Code formatting (prettier, black)

**Tier 3 Tools (High Model Threshold - Complex Operations)**:
16. `database_client` - Database operations
17. `api_testing` - API request testing
18. `code_execution` - Execute arbitrary code (sandboxed)
19. `migration_tools` - Database migrations
20. `docker_commands` - Container operations
21. `security_scanners` - Vulnerability scanning
22. `performance_profiling` - Performance analysis
23. `github_api` - GitHub API interactions

#### 3.2 Detailed Tool Specifications

##### Tool 1: `filesystem_read`
```yaml
name: filesystem_read
tier: 1
description: "Read contents of a file"
min_model_tier: 1

parameters:
  - name: path
    type: string
    required: true
    description: "Absolute or relative path to file"
  
  - name: start_line
    type: integer
    required: false
    description: "Starting line number (1-indexed)"
  
  - name: end_line
    type: integer
    required: false
    description: "Ending line number (inclusive)"

returns:
  type: object
  properties:
    content: string
    line_count: integer
    file_size_bytes: integer

error_codes:
  - FILE_NOT_FOUND
  - PERMISSION_DENIED
  - INVALID_PATH

example:
  input:
    path: "src/auth/login.js"
    start_line: 10
    end_line: 30
  output:
    content: "function validateUser(username, password) {...}"
    line_count: 21
    file_size_bytes: 1024
```

##### Tool 2: `filesystem_write`
```yaml
name: filesystem_write
tier: 2
description: "Write or modify file contents"
min_model_tier: 2

parameters:
  - name: path
    type: string
    required: true
  
  - name: content
    type: string
    required: true
  
  - name: mode
    type: enum
    values: ["overwrite", "append", "insert"]
    default: "overwrite"
  
  - name: insert_at_line
    type: integer
    required: false
    description: "Line number for insert mode"

safety_checks:
  - prevent_overwrite_without_backup: true
  - max_file_size: 10MB
  - blocked_paths:
      - "/.git/**"
      - "/node_modules/**"
      - "**/.env"

returns:
  type: object
  properties:
    success: boolean
    bytes_written: integer
    backup_path: string  # If backup created

example:
  input:
    path: "src/auth/login.js"
    content: "function validateUser(username, password) {\n  // Implementation\n}"
    mode: "overwrite"
  output:
    success: true
    bytes_written: 75
    backup_path: ".backups/login.js.1695739200"
```

##### Tool 3: `git_operations`
```yaml
name: git_operations
tier: 2
description: "Perform git operations (branch, commit, push)"
min_model_tier: 2

operations:
  - name: create_branch
    parameters:
      - branch_name: string
      - base_branch: string (default: "main")
    returns:
      success: boolean
      branch_name: string
  
  - name: commit
    parameters:
      - message: string- files: array[string] (default: all staged)
      - author: string (optional)
    returns:
      success: boolean
      commit_hash: string
      files_committed: array[string]
  
  - name: push
    parameters:
      - remote: string (default: "origin")
      - branch: string
      - force: boolean (default: false)
    returns:
      success: boolean
      pushed_commits: integer
  
  - name: pull
    parameters:
      - remote: string (default: "origin")
      - branch: string
    returns:
      success: boolean
      changes_pulled: integer
  
  - name: merge
    parameters:
      - source_branch: string
      - target_branch: string
      - strategy: enum["merge", "squash", "rebase"]
    returns:
      success: boolean
      conflicts: array[string]

safety_checks:
  - never_force_push_to_main: true
  - require_commit_message: true
  - prevent_empty_commits: true

example:
  operation: commit
  input:
    message: "Add user authentication endpoint"
    files: ["src/auth/login.js", "tests/auth.test.js"]output:
    success: true
    commit_hash: "a1b2c3d4"
    files_committed: ["src/auth/login.js", "tests/auth.test.js"]
```

##### Tool 4: `grep_search`
```yaml
name: grep_search
tier: 2
description: "Search for patterns in code"
min_model_tier: 2

parameters:
  - name: pattern
    type: string
    required: truedescription: "Search pattern (regex or literal)"
  
  - name: path
    type: string
    default: "."
    description: "Directory or file to search"
  
  - name: case_sensitive
    type: boolean
    default: false
  - name: whole_word
    type: boolean
    default: false
  
  - name: file_pattern
    type: string
    description: "File glob pattern (e.g., '*.js')"
  
  - name: max_results
    type: integer
    default: 100

returns:
  type: object
  properties:
    matches: array[object]
      - file: string
      - line_number: integer
      - line_content: string
      - match_start: integer
      - match_end: integer
    total_matches: integer
    searched_files: integer

example:
  input:
    pattern: "function.*login"
    path: "src/"
    file_pattern: "*.js"output:
    matches:
      - file: "src/auth/login.js"
        line_number: 15
        line_content: "function handleLogin(username, password) {"
        match_start: 0
        match_end: 19total_matches: 1
    searched_files: 47
```

##### Tool 5: `test_runner`
```yaml
name: test_runner
tier: 2
description: "Execute test suites"
min_model_tier: 2

parameters:
  - name: test_framework
    type: enum
    values: ["jest", "pytest", "mocha", "cargo", "go-test", "junit"]
    required: false# Auto-detect if not specified
  
  - name: test_path
    type: string
    description: "Specific test file or directory"
    default: "."  # Run all tests
  
  - name: test_pattern
    type: string
    description: "Filter tests by name pattern"
  
  - name: coverage
    type: boolean
    default: truedescription: "Generate coverage report"
  
  - name: timeout
    type: integer
    default: 300
    description: "Timeout in seconds"

returns:
  type: object
  properties:
    success: boolean
    total_tests: integer
    passed: integer
    failed: integer
    skipped: integer
    duration_seconds: float
    failures: array[object]
      - test_name: string
      - error_message: string
      - stacktrace: stringcoverage: object
      - line_coverage: float
      - branch_coverage: float
      - uncovered_lines: array[string]

example:
  input:
    test_framework: "jest"
    test_path: "tests/auth.test.js"
    coverage: true
  output:
    success: true
    total_tests: 12
    passed: 12
    failed: 0
    skipped: 0
    duration_seconds: 2.4
    failures: []
    coverage:
      line_coverage: 85.5
      branch_coverage: 78.2
      uncovered_lines: ["src/auth/login.js:45-47"]
```

##### Tool 6: `github_api`
```yaml
name: github_api
tier: 3
description: "Interact with GitHub API"
min_model_tier: 3

operations:
  - name: create_issue
    parameters:
      - title: string
      - body: string
      - labels: array[string]
      - assignees: array[string]- milestone: integer
    returns:
      issue_number: integer
      url: string
  
  - name: create_pull_request
    parameters:
      - title: string
      - body: string
      - head_branch: string
      - base_branch: string
      - labels: array[string]
      - reviewers: array[string]
    returns:
      pr_number: integer
      url: string
  
  - name: comment_on_pr
    parameters:
      - pr_number: integer
      - body: string
    returns:
      comment_id: integer
  
  - name: merge_pr
    parameters:
      - pr_number: integer
      - merge_method: enum["merge", "squash", "rebase"]- commit_message: string
    returns:
      success: boolean
      merge_commit_sha: string
  
  - name: request_changes
    parameters:
      - pr_number: integer
      - body: string
      - comments: array[object]
        - path: string
        - line: integer
        - body: string
    returns:
      review_id: integer
  
  - name: list_issues
    parameters:
      - state: enum["open", "closed", "all"]
      - labels: array[string]
      - assignee: string
    returns:
      issues: array[object]

example:
  operation: create_pull_request
  input:
    title: "Add user authentication"
    body: "Implements JWT-based authentication\n\nFixes #42"
    head_branch: "agent/sd1/42-add-auth"
    base_branch: "main"
    labels: ["backend", "authentication"]
  output:
    pr_number: 123
    url: "https://github.com/user/repo/pull/123"
```

##### Tool 7: `database_client`
```yaml
name: database_client
tier: 3
description: "Execute database operations"
min_model_tier: 3

parameters:
  - name: operation
    type: enum
    values: ["query", "execute", "transaction"]
  - name: sql
    type: string
    description: "SQL query or command"
  
  - name: parameters
    type: object
    description: "Parameterized query values"
  
  - name: database
    type: string
    default: "default"

safety_checks:
  - prevent_drop_commands: true
  - require_where_clause_for_updates: true
  - max_affected_rows: 1000
  - read_only_mode: false# Configurable

returns:
  type: object
  properties:
    success: boolean
    rows_affected: integer
    result_set: array[object]
    execution_time_ms: float

example:
  input:
    operation: "query"
    sql: "SELECT * FROM users WHERE id = ?"
    parameters: [42]
  output:
    success: true
    rows_affected: 1
    result_set:
      - id: 42
        username: "john_doe"
        email: "john@example.com"
    execution_time_ms: 15.2
```

##### Tool 8: `code_execution`
```yaml
name: code_execution
tier: 3
description: "Execute code in sandboxed environment"
min_model_tier: 3

parameters:
  - name: language
    type: enum
    values: ["javascript", "python", "bash", "typescript"]
  
  - name: code
    type: string
  
  - name: timeout
    type: integer
    default: 30
  
  - name: environment
    type: object
    description: "Environment variables"

sandbox_constraints:
  - network_access: false
  - filesystem_access: "temp_only"
  - max_memory_mb: 512
  - max_cpu_seconds: 30

returns:
  type: object
  properties:
    success: boolean
    stdout: string
    stderr: string
    exit_code: integer
    execution_time_seconds: float

example:
  input:
    language: "python"
    code: |
      def add(a, b):
          return a + b
      print(add(2, 3))
    timeout: 5output:
    success: true
    stdout: "5\n"
    stderr: ""
    exit_code: 0
    execution_time_seconds: 0.12
```

#### 3.3 Tool Access Control Matrix

```yaml
tool_access_matrix:
  architect:
    - agent_messaging
    - context_store_read_write
    - logging
    - filesystem_read
    - filesystem_list
    - git_status
    - git_log
    - github_api
    - grep_search
  manager:
    - agent_messaging
    - context_store_read_write
    - logging
    - filesystem_read
    - git_status
    - git_log
    - github_api
    - grep_search
    - conflict_detector- token_monitor
  
  specialist_tier_1_model:
    - agent_messaging
    - context_store_read
    - logging
    - filesystem_read
    - filesystem_list
    - git_status
    - git_log
  
  specialist_tier_2_model:
    - [all tier 1 tools]
    - filesystem_write
    - git_operations
    - grep_search
    - sed_replace
    - npm_commands
    - test_runner
    - linting
    - formatting
  
  specialist_tier_3_model:
    - [all tier 2 tools]
    - database_client
    - api_testing
    - code_execution
    - migration_tools
    - docker_commands
    - security_scanners
    - performance_profiling
  
  reviewer_specialist:
    - filesystem_read
    - git_operations (read-only)
    - grep_search
    - static_analysis_tools
    - linting_tools
    - diff_analysis
```

---

### Section 4: Context Management System (Expanded)

#### 4.1 Context Store Architecture

```
Context Store (Database: PostgreSQL / MongoDB)
│
├── Global Context
│   ├── Repository Metadata
│   │   ├── name, url, branch, language, framework
│   │   ├── file_structure (tree)
│   │   ├── dependencies
│   │   ├── build_commands
│   │   └── test_commands
│   │
│   ├── Active Tasks
│   │   ├── task_id, issue_number, title, status
│   │   ├── assigned_agents, manager
│   │   ├── priority, estimated_complexity
│   │   ├── dependencies (task graph)
│   │   └── created_at, updated_at
│   │
│   ├── Agent Registry
│   │   ├── agent_id, type, specialty, model
│   │   ├── status (active, busy, idle)
│   │   ├── current_task
│   │   ├── tokens_consumed, tasks_completed
│   │   └── availability_score
│   │
│   ├── Global Rules
│   │   ├── rule_id, description, scope
│   │   ├── created_by (architect), created_at
│   │   └── applies_to (all, backend, frontend, etc.)
│   │
│   └── Token Usage Logs
│       ├── agent_id, task_id, tokens_consumed
│       ├── timestamp, operation
│       └── productivity_score
│
├── Per-Agent Context Windows
│   ├── Agent ID: sd-backend-1
│   │   ├── Current Task
│   │   │   ├── task_details
│   │   │   ├── relevant_files
│   │   │   └── design_constraints
│   │   │
│   │   ├── Conversation History (Time-Windowed)
│   │   │   ├── Window 1: Recent (uncompressed, last 20 messages)
│   │   │   ├── Window 2: Mid-term (compressed, last 100 messages)
│   │   │   └── Window 3: Historical (summaries, older messages)
│   │   │
│   │   ├── Execution Log
│   │   │   ├── actions_taken
│   │   │   ├── files_modified
│   │   │   ├── commands_executed
│   │   │   └── errors_encountered
│   │   │
│   │   └── Performance Metrics
│   │       ├── tokens_used_this_task
│   │       ├── time_elapsed
│   │       └── progress_percentage
│   │
│   └── [Additional agents...]
│
└── Shared Context (for collaborating agents)
    ├── Collaboration ID: collab-42
    │   ├── participating_agents
    │   ├── shared_task_details
    │   ├── coordination_messages
    │   └── shared_files
    └── [Additional collaborations...]
```

#### 4.2 Time-Windowed Compression Algorithm

```python
class ContextWindowManager:
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.window_1_size = 20  # Recent messages (uncompressed)
        self.window_2_size = 100  # Mid-term (compressed)
        self.window_3_size = 500  # Historical (high-level summaries)
    
    def add_message(self, message):
        """Add new message to agent's context"""
        # Add to Window 1 (recent)
        self.window_1.append(message)
        
        # If Window 1 exceeds size, compress and move to Window 2
        if len(self.window_1) > self.window_1_size:
            oldest_batch = self.window_1[:10]
            compressed = self.compress_messages(oldest_batch)
            self.window_2.append(compressed)
            self.window_1 = self.window_1[10:]
        
        # If Window 2 exceeds size, summarize and move to Window 3
        if len(self.window_2) > self.window_2_size:
            oldest_batch = self.window_2[:20]
            summary = self.summarize_messages(oldest_batch)
            self.window_3.append(summary)
            self.window_2 = self.window_2[20:]
    
    def compress_messages(self, messages):
        """Compress messages into concise summary"""
        # Extract key information:
        # - Actions taken
        # - Decisions made
        # - Errors encountered
        # - Files modified
        
        actions = [m for m in messages if m.type == "action"]
        decisions = [m for m in messages if m.type == "decision"]
        errors = [m for m in messages if m.type == "error"]
        
        return {
            "timeframe": {
                "start": messages[0].timestamp,
                "end": messages[-1].timestamp
            },
            "actions_summary": self.summarize_actions(actions),
            "decisions_made": [d.content for d in decisions],
            "errors": [{"type": e.error_type, "resolved": e.resolved} for e in errors],
            "files_modified": list(set([m.file for m in messages if hasattr(m, 'file')]))
        }
    
    def summarize_messages(self, compressed_batches):
        """Create high-level summary from compressed batches"""
        total_actions = sum(len(b["actions_summary"]) for b in compressed_batches)
        total_errors = sum(len(b["errors"]) for b in compressed_batches)
        all_files = set()
        for batch in compressed_batches:
            all_files.update(batch["files_modified"])
        
        return {
            "timeframe": {
                "start": compressed_batches[0]["timeframe"]["start"],
                "end": compressed_batches[-1]["timeframe"]["end"]
            },
            "total_actions": total_actions,
            "total_errors": total_errors,
            "errors_resolved": sum(1 for b in compressed_batches for e in b["errors"] if e["resolved"]),
            "files_modified": list(all_files),
            "major_milestones": self.extract_milestones(compressed_batches)
        }
    
    def get_context_for_task(self, task):
        """Retrieve relevant context for a task"""
        # Start with Window 1 (always included)
        context = {
            "recent": self.window_1,
            "mid_term": None,
            "historical": None,
            "neighbor_windows": []
        }
        
        # Check if Window 1 is sufficient
        if self.is_sufficient_context(context, task):
            return context
        
        # Expand to Window 2 if needed
        context["mid_term"] = self.window_2
        if self.is_sufficient_context(context, task):
            return context
        
        # Check neighbor context windows (related tasks)
        neighbor_windows = self.find_neighbor_windows(task)
        context["neighbor_windows"] = neighbor_windows
        if self.is_sufficient_context(context, task):
            return context
        
        # Full historical context
        context["historical"] = self.window_3
        return context
    
    def find_neighbor_windows(self, task):
        """Find context from related tasks"""
        # Find tasks that:
        # - Modified similar files
        # - Have similar requirements
        # - Are in the same domain
        
        related_tasks = self.find_related_tasks(task)
        neighbor_contexts = []
        
        for related_task in related_tasks:
            agent_id = related_task.assigned_agent
            neighbor_context = self.get_agent_context_summary(agent_id)
            neighbor_contexts.append(neighbor_context)
        
        return neighbor_contexts
```

#### 4.3 Global Rule Extraction

```python
class GlobalRuleExtractor:
    def __init__(self, architect_agent):
        self.architect = architect_agent
    
    def extract_rules_from_prompt(self, user_prompt):
        """Extract global rules from user prompts"""
        rules = []
        
        # Patterns that indicate global rules
        global_patterns = [
            r"always use(\w+)",
            r"never use (\w+)",
            r"all (\w+) should(\w+)",
            r"from now on",
            r"for all",
            r"every time",
            r"make sure to",
            r"remember to"
        ]
        
        for pattern in global_patterns:
            matches = re.findall(pattern, user_prompt, re.IGNORECASE)
            if matches:
                rule = self.formulate_rule(pattern, matches, user_prompt)
                rules.append(rule)
        
        # Use LLM to extract implicit rules
        implicit_rules = self.architect.analyze_for_implicit_rules(user_prompt)
        rules.extend(implicit_rules)
        
        return rules
    
    def formulate_rule(self, pattern, matches, context):
        """Formulate a clear rule from pattern matches"""
        # Example: "always use TypeScript" → Rule
        return {
            "id": generate_uuid(),
            "description": self.architect.formulate_rule_description(context),
            "scope": self.determine_scope(context),
            "priority": "high",
            "created_by": "architect",
            "created_at": datetime.now(),
            "applies_to": self.determine_applicable_agents(context)
        }
    
    def persist_rule(self, rule):
        """Save rule to global context"""
        global_context.rules.add(rule)
        
        # Notify all agents of new rule
        for agent in self.get_all_agents():
            self.notify_agent_of_rule(agent, rule)
    
    def notify_agent_of_rule(self, agent, rule):
        """Add rule to agent's system prompt"""
        if rule["applies_to"] == "all" or agent.specialty in rule["applies_to"]:
            agent.add_to_system_prompt(f"GLOBAL RULE: {rule['description']}")
```

##### 4.3.1 Refinement: LLM-Primary Extraction with User Confirmation & Versioning

**Problem**: Regex patterns (`"always use X"`, `"never use Y"`) are brittle — natural language rarely hits those exact phrasings, so the regex pass misses most real rules and the LLM fallback (`analyze_for_implicit_rules`) ends up doing almost all the work anyway. Worse, a misextracted rule silently becomes a "hard rule" every future agent inherits, with no way to tell which merged PRs were built under a rule that later turns out to be wrong.

**Revised extraction order**:
1. **LLM extraction is primary**, not a fallback. The architect analyzes the full prompt for both explicit and implicit rules directly — coding standards, architecture decisions, constraints — rather than waiting for regex to fail first.
2. The regex patterns in `extract_rules_from_prompt` are kept only as a **cheap pre-filter**: they flag prompts likely to contain a global rule so the (more expensive) LLM extraction pass can be skipped for prompts that obviously don't need it. They are no longer the source of truth for what the rule *is*.

**User confirmation gate**: Before `persist_rule` writes a newly extracted rule to global context, the architect surfaces it to the user for a quick confirm/reject:

```python
def propose_rule(self, rule):
    """Surface a newly extracted rule for user confirmation before persisting"""
    response = self.architect.ask_user_confirmation(
        f"Detected new global rule: \"{rule['description']}\". "
        f"Applies to: {rule['applies_to']}. Confirm, reject, or edit?"
    )
    if response.action == "confirm":
        self.persist_rule(rule)
    elif response.action == "edit":
        rule["description"] = response.edited_description
        self.persist_rule(rule)
    # "reject" → rule is discarded, never enters global context
```

**Rule versioning & rollback**: Every persisted rule is versioned, not just overwritten in place, so a bad rule can be identified and undone without guessing which agents inherited it:

```python
def persist_rule(self, rule):
    """Save a confirmed rule to global context with version tracking"""
    rule["version"] = 1
    rule["status"] = "active"
    global_context.rules.add(rule)

    for agent in self.get_all_agents():
        self.notify_agent_of_rule(agent, rule)

def revoke_rule(self, rule_id, reason):
    """Roll back a rule; does not delete it, marks it superseded"""
    rule = global_context.rules.get(rule_id)
    rule["status"] = "revoked"
    rule["revoked_reason"] = reason
    rule["revoked_at"] = datetime.now()

    # Tag which PRs were merged under this rule while it was active,
    # so they can be flagged for review after revocation
    affected_prs = global_context.find_prs_merged_under_rule(rule_id)
    return affected_prs
```

This turns rule extraction from a silent, irreversible side effect of task decomposition into a visible, auditable, and reversible step — at the cost of one extra confirmation round-trip per newly detected rule.

#### 4.4 Context Window Schema

```typescript
// TypeScript schema for context windows

interface ContextWindow {
  id: string;
  agent_id: string;
  created_at: Date;
  updated_at: Date;
  
  // Current task information
  current_task: {
    task_id: string;
    issue_number: number;
    title: string;
    description: string;
    acceptance_criteria: string[];
    priority: "critical" | "high" | "normal" | "low";
    estimated_complexity: number;  // 1-10
    assigned_at: Date;
  };
  
  // Relevant files for this task
  relevant_files: Array<{
    path: string;
    reason: string;  // Why this file is relevant
    content_summary: string;
    last_modified: Date;
  }>;
  
  // Design constraints
  constraints: {
    global_rules: string[];  // IDs of applicable global rules
    technical_constraints: string[];
    time_constraints?: Date;// Deadline if anydependency_tasks: string[];  // Must be completed first
  };
  
  // Conversation history (time-windowed)
  conversation: {
    window_1_recent: Message[];  // Last 20 messages
    window_2_midterm: CompressedBatch[];  // Compressed summaries
    window_3_historical: HistoricalSummary[];  // High-level summaries
  };
  
  // Execution log
  execution_log: Array<{
    timestamp: Date;
    action_type: "file_read" | "file_write" | "git_commit" | "test_run" | "error";
    details: any;
    success: boolean;
  }>;
  
  // Performance tracking
  performance: {
    tokens_consumed: number;
    time_elapsed_seconds: number;
    progress_percentage: number;
    estimated_completion: Date;
    blockers: Array<{
      description: string;
      severity: "low" | "medium" | "high";
      encountered_at: Date;
    }>;
  };
}

interface CompressedBatch {
  timeframe: {
    start: Date;
    end: Date;
  };
  actions_summary: string[];
  decisions_made: string[];
  errors: Array<{
    type: string;
    resolved: boolean;
  }>;
  files_modified: string[];
}

interface HistoricalSummary {
  timeframe: {
    start: Date;
    end: Date;
  };
  total_actions: number;
  total_errors: number;
  errors_resolved: number;
  files_modified: string[];
  major_milestones: string[];
}
```

---

### Section 5: Task Assignment & Routing (Expanded)

#### 5.1 Multi-Factor Assignment Algorithm

**Overview**: When a manager receives tasks from the architect, it must intelligently route them to the most suitable specialist(s). The assignment considers four primary factors, each weighted to balance different priorities.

**Factor 1: Specialty Match (40% weight)**
- **Primary Specialty Alignment**: Does the task's domain (backend-api, frontend-react, database, etc.) match the specialist's primary training focus?
- **Historical Performance**: Has this specialist successfully completed similar tasks in the past? Track success rate per specialty type.
- **Skill Confidence Score**: Each specialist maintains a confidence score (0-100) for each specialty area, updated based on task outcomes.
- **Example**: Task requires "Create REST API endpoint" → Backend-API specialist scores 95, Database specialist scores 30, Frontend specialist scores 10.

**Factor 2: Availability (20% weight)**
- **Current Task Load**: How many tasks is the specialist currently handling?
- **Queue Length**: How many pending tasks are already assigned?
- **Last Completion Time**: When did the specialist last finish a task? Recent completions indicate active availability.
- **Idle Time**: If a specialist has been idle too long, slightly prioritize them to keep workload balanced.
- **Example**: Specialist A has 0 active tasks (score: 100), Specialist B has 2 active tasks (score: 60), Specialist C has 4 tasks (score: 20).

**Factor 3: Load Balance (20% weight)**
- **Token Consumption Today**: Compare specialist's token usage to team average. If significantly above average, lower priority.
- **Tasks Completed vs Tokens Used**: Calculate efficiency ratio. Higher efficiency = higher score.
- **Fairness Metric**: Ensure all specialists get roughly equal opportunities over time.
- **Burnout Prevention**: If a specialist has been working continuously for extended periods, temporarily reduce assignment probability.
- **Example**: Team average is 50k tokens/day. Specialist A used 30k (score: 100), Specialist B used 70k (score: 60), Specialist C used 100k (score: 20).

**Factor 4: Capability Match (20% weight)**
- **Model Tier vs Task Complexity**: Does the specialist's model tier meet the task's complexity requirements?
- **Tool Requirements**: Does the specialist have access to all required tools (database client, docker, security scanners)?
- **Task Complexity Threshold**: Simple tasks (complexity1-3) can use any tier. Medium tasks (4-7) need tier2+. Complex tasks (8-10) need tier 3.
- **Example**: Task complexity is 8, requires database_client tool. Tier 1 specialist (score: 0), Tier 2 without database tool (score: 50), Tier 3 with database tool (score: 100).

**Assignment Decision Process**:
1. Calculate scores for all four factors for each available specialist.
2. Compute weighted total score: `(specialty * 0.4) + (availability * 0.2) + (load * 0.2) + (capability * 0.2)`.
3. If task complexity is above collaboration threshold (default: 7), select top 2-3 specialists and assign as a collaborative team.
4. If task complexity is below threshold, assign to the single highest-scoring specialist.
5. Log assignment decision with scores for future analysis and optimization.

#### 5.2 Concurrent Task Conflict Detection

**Intent Analysis Phase**:
When a new user prompt arrives while other tasks are in progress, the architect (potentially in coordination with an available manager) must determine if conflicts will occur.

**Conflict Detection Steps**:

**Step 1: File Overlap Detection**
- Extract all files that the new task will likely modify (using repository analysis and task description).
- Compare against files currently being modified by in-progress tasks.
- If exact file match found → potential conflict.
- If same directory/module → moderate conflict risk.
- If completely different areas → no conflict.

**Step 2: Dependency Graph Analysis**
- Check if the new task depends on features being implemented by current tasks.
- Check if current tasks depend on areas the new task will modify.
- Build a dependency graph: if new task creates a cycle or blocks current tasks → conflict.

**Step 3: Resource Contention Check**
- Will both tasks require the same database schemas, API endpoints, or shared infrastructure?
- If yes → sequencing required.

**Conflict Resolution Strategies**:

**Strategy A: Sequential Execution**
- If high conflict probability, queue the new task to start after conflicting task completes.
- Set up a trigger: when Task A finishes, automatically start Task B.
- Notify user of sequencing decision and estimated timeline.

**Strategy B: Parallel with Coordination**
- If moderate conflict (same module but different files), allow parallel execution but assign to same manager.
- Manager creates a "coordination context" shared between specialists.
- Specialists are instructed to coordinate on shared areas via manager.

**Strategy C: Task Decomposition**
- If the new prompt is complex and conflicts with multiple ongoing tasks, decompose it differently.
- Split the new task into sub-tasks that can execute in non-conflicting areas.
- Sequence the conflicting portions for later execution.

**Strategy D: Different Team Assignment**
- If conflict is isolated to one manager's team, assign new task to a different manager's team entirely.
- Example: Backend team busy with API work, new frontend task goes to frontend team with no conflicts.

#### 5.3 Dynamic Task Prioritization

**Priority Levels**:
- **Critical**: Blocking other tasks, security issues, production bugs
- **High**: User-requested features, important improvements
- **Normal**: Standard feature work, refactoring
- **Low**: Nice-to-have improvements, code quality enhancements

**Priority Adjustment Factors**:
- **Dependency Blocking**: If 3+ tasks are waiting for this task to complete, elevate priority to High.
- **Time Sensitivity**: If task has a deadline approaching, gradually increase priority.
- **Error Escalations**: If multiple specialists are blocked by the same issue, prioritize the blocker resolution.
- **User Intervention**: Users can manually adjust task priorities via the dashboard.

**Task Reassignment Triggers**:
- If a specialist is making poor progress (low token efficiency) on a task, manager can reassign after 2progress checks.
- If a specialist reports being stuck and manager's reframing doesn't help, reassign to a different specialist with different approach.
- If a specialist's model is upgraded mid-task (user config change), consider reassigning their current tasks to take advantage of the upgrade.

#### 5.4 Coordination Mode Selection (Simple / Full / Auto)

**Problem**: The full Architect → Manager → Specialist coordination loop (command message, status updates, escalation channel, merge coordination) adds several LLM round-trips before any code gets written. For low-complexity tasks, this overhead can exceed the cost of the task itself.

**Solution**: Coordination mode is a configuration knob, not a second parallel codebase. It reuses the existing `task.complexity` score (1–10, already computed during decomposition) to decide how much of the hierarchy actually participates, rather than building a separate lightweight pipeline from scratch.

```yaml
coordination:
  mode: "auto"        # simple | full | auto
  auto_thresholds:
    simple_below: 4    # architect assigns directly, no manager round-trip
    full_above: 7       # manager-coordinated, multi-specialist collaboration
    # complexity 4-7: manager routes to one specialist, no collaboration overhead
  user_override: null   # e.g. "full" to force full coordination regardless of score
                         # (recommended for security-sensitive or cross-cutting tasks)
```

**Mode behaviors**:

- **Simple**: The architect calls the assignment function directly (specialty/availability/load/capability scoring still runs — it just skips the manager message hop). Roughly 2 round-trips instead of ~6. Suitable for isolated, low-complexity tasks with no dependents.
- **Full**: The original design — manager receives the task cluster, runs multi-factor assignment, monitors progress, handles escalation and merge coordination, reports back to the architect. Used for anything above the `full_above` threshold, or anything the user explicitly flags (e.g. auth, payments, schema changes).
- **Auto** (default): Complexity score decides per-task, using the thresholds above. Users can override per-project or per-prompt ("force full coordination on this one").

**Observability is preserved in simple mode**: even when the manager isn't in the decision loop, it still passively logs token usage and task status for that task, so the dashboard and performance-tracking systems (Section 11) don't lose visibility just because a task took the fast path.

---

### Section 6: Git Workflow & Conflict Resolution (Expanded)

#### 6.1 Branch Naming and Management

**Branch Naming Convention**:
- Format: `agent/<agent-id>/<issue-number>-<short-slug>`
- Examples:
  - `agent/sd-backend-1/42-add-user-auth`
  - `agent/sd-frontend-2/43-create-login-ui`
  - `agent/sd-testing-1/44-e2e-auth-tests`

**Branch Lifecycle**:
1. **Creation**: Specialist creates branch from latest `main` when task starts
2. **Development**: Specialist makes incremental commits with clear messages
3. **Self-Verification**: Before PR, specialist runs all checks locally
4. **PR Creation**: Specialist raises PR against `main` with detailed description
5. **Review Cycle**: Automated checks + optional reviewer + manager coordination
6. **Merge**: Architect performs final review and merges
7. **Cleanup**: Branch automatically deleted after successful merge

**Commit Message Standards**:
- Format: `<type>: <description>`
- Types: `feat`, `fix`, `test`, `docs`, `refactor`, `style`, `chore`
- Examples:
  - `feat: Add JWT authentication middleware`
  - `test: Add integration tests for auth endpoints`
  - `fix: Resolve token expiration bug`
  - `docs: Update API documentation for auth`

#### 6.2 Merge Coordination Protocol

**Phase 1: Pre-Merge Validation**

**Automated Checks** (all must pass):
- **Linting**: Code style matches repository standards (ESLint, Pylint, RustFmt, etc.)
- **Formatting**: Code properly formatted (Prettier, Black, gofmt)
- **Unit Tests**: All existing tests pass, new tests for new features
- **Integration Tests**: If applicable, integration test suite passes
- **Coverage**: Code coverage doesn't drop below threshold (default 80%)
- **Security Scan**: No new vulnerabilities introduced (Snyk, Bandit, Semgrep)
- **Build**: Code compiles/builds successfully
- **License Check**: No incompatible licenses introduced in dependencies

**Phase 2: Optional Code Review Agent**

If enabled in configuration, a reviewer specialist analyzes the PR for:
- **Code Quality**: No obvious code smells (long functions, deep nesting, duplicated code)
- **Pattern Consistency**: Follows existing repository patterns and conventions
- **Documentation**: Functions/classes documented, README updated if needed
- **Test Adequacy**: Tests cover edge cases, not just happy path
- **Performance Implications**: Flags potentially slow operations (N+1 queries, inefficient loops)
- **Security Concerns**: Looks for common vulnerabilities (SQL injection points, XSS risks, hardcoded secrets)

**Reviewer Output**: Creates low-priority GitHub issues for improvements (non-blocking) and/or comments directly on PR with suggestions.

**Phase 3: Conflict Detection**

Manager performs automatic conflict detection:
- **Git Merge Conflict**: Will this PR cause merge conflicts with `main`?
- **Semantic Conflict**: Are there other open PRs that modify related code that might cause runtime issues when both merged?
- **Test Conflict**: Will merging this break tests in other open PRs?

**If Conflicts Detected**:

**Simple Conflicts** (isolated to a few lines in one file):
- Manager assigns back to original specialist with specific conflict locations
- Specialist resolves conflicts and updates PR
- Manager re-triggers validation checks

**Complex Conflicts** (multiple files, overlapping logic):
- Manager identifies all specialists involved (original + those with conflicting PRs)
- Creates a "conflict resolution team" with 2-3 specialists
- Provides shared context with both sets of changes
- Specialists coordinate (via manager as intermediary) to resolve
- May require splitting work or refactoring approach

**Critical Conflicts** (core architecture changes, breaking API changes):
- Escalate to architect immediately
- Architect reviews both approaches
- Architect decides: merge one first and rebase other, or require redesign of one approach
- Architect may directly participate in resolution

**Phase 4: Manager Approval**

Manager validates:
- All automated checks passed
- Conflicts resolved (if any were present)
- Task acceptance criteria met (as defined in original GitHub issue)
- No unintended side effects visible
- Documentation and tests present

Manager approves and forwards PR to architect for final gate.

**Phase 5: Architect Final Review**

Architect performs high-level review:
- **Intent Validation**: Does this PR achieve what the user requested?
- **Architecture Consistency**: Does it fit the overall system design?
- **Global Rules Compliance**: Does it follow all global rules extracted from user prompts?
- **Quality Gate**: Is this production-ready code?
- **Integration Impact**: Will this affect other parts of the system?

**Architect Decision**:
- **Approve & Merge**: Merge to `main`, update global context, notify user
- **Request Changes**: Comment with specific changes needed, send back to specialist via manager
- **Reject & Redesign**: If fundamentally wrong approach, reject and create new task with corrected design

#### 6.3 Merge Strategies

**Standard Merge** (default):
- Preserves full commit history from specialist branch
- Creates merge commit in `main`
- Useful for tracking detailed development history

**Squash Merge**:
- Combines all specialist commits into single commit on `main`
- Cleaner history, easier to revert entire feature
- Recommended for tasks with many small incremental commits

**Rebase Merge**:
- Replays specialist commits on top of latest `main`
- Linear history, no merge commits
- Recommended for simple, clean changes

**Configuration**: User can set preferred merge strategy globally or per-task-type in config file.

#### 6.4 Rollback and Recovery

**If Merged PR Causes Issues**:

**Automatic Detection**:
- Post-merge CI/CD runs full test suite on `main`
- If tests fail after merge that passed before, flag automatically

**Rollback Protocol**:
1. Architect receives alert about failing tests on `main`
2. Architect reviews recent merges (last 1-3 PRs)
3. Identifies problematic merge using git bisect or manual review
4. Creates revert PR: `git revert <merge-commit-sha>`
5. Revert PR goes through expedited review (critical priority)
6. Once reverted, architect assigns specialist to fix issue in new branch
7. New PR undergoes full review cycle with extra scrutiny

#### 6.5 Contract-First Decomposition & Integration Branches

**Problem**: Parallel specialists working toward late integration (e.g. one building a user model, two others building JWT middleware and login endpoints against it) tend to only discover interface mismatches at merge time, when it's most expensive to fix. Post-hoc conflict resolution (Section 6.2) handles this, but by then two branches have already diverged.

**Solution**: Freeze shared interfaces *before* dependent specialists branch, instead of reconciling them *after*.

**Sequence**:
1. During task decomposition, the architect identifies **boundary artifacts** — any schema, type, or function signature that more than one issue will depend on (e.g. the `User` model shape needed by both the JWT middleware issue and the login-endpoint issue).
2. The issue that **owns** the boundary artifact is assigned and released first, alone.
3. That specialist implements just the **interface** (schema/types/function signatures with stub bodies — not the full feature) and pushes it to a dedicated **integration branch**.
4. Only once the interface has landed does the manager release the **dependent issues** to their specialists. Those specialists branch from the integration branch, not from stale `main`, so they code against a real, committed contract instead of a guess.
5. This release gate is enforced as a real dependency check in the manager's task queue (`wait_for: interface_landed(issue_id)`) — not a convention specialists are trusted to follow under time pressure, since an unenforced gate collapses back into the original race condition.

**Contract-change requests**: if a dependent specialist finds the frozen interface insufficient mid-task, it does not silently patch it. It raises a **contract-change request** through the manager — a visible, logged event — rather than quietly diverging in its own branch. The manager (or, for critical paths, the architect) approves the change and re-notifies any other specialist already building against that interface.

**What this does and doesn't solve**:
- ✅ Eliminates interface-mismatch conflicts (the most expensive kind — wrong field names, wrong signatures, wrong assumptions about shape).
- ✅ Turns silent divergence into a visible, logged event (the contract-change request) instead of a surprise at merge time.
- ⚠️ Does **not** eliminate same-file, different-function conflicts — two specialists can both respect the contract and still edit the same file. The file/module overlap detection in Section 5.2 remains active as a fallback safety net; contract-first reduces how often it fires, it doesn't replace it.
- ⚠️ Trades "occasional merge conflict" for "occasional pipeline stall" — dependent specialists are now blocked on the boundary-owner finishing its interface. This is usually the better trade, but it means boundary-artifact issues should be prioritized and assigned to reliable specialists, since a slow start on Issue #1 now delays everything downstream.

---

### Section 7: Error Recovery & Escalation (Expanded)

#### 7.1 Error Classification System

**Category 1: Syntax Errors**
- **Severity**: Low
- **Recovery**: Self-recoverable by specialist
- **Examples**: Missing semicolons, typos in keywords, incorrect indentation
- **Strategy**: Run linter, parse error message, apply fix, retry

**Category 2: Test Failures**
- **Severity**: Low to Medium (depending on test type)
- **Recovery**: Self-recoverable with debugging
- **Examples**: Assertion failures, unexpected behavior, edge case bugs
- **Strategy**: Analyze test output, identify cause, debug implementation, rerun tests

**Category 3: Import/Dependency Errors**
- **Severity**: Medium
- **Recovery**: Self-recoverable if dependency exists, escalate if missing
- **Examples**: Module not found, version incompatibility, circular dependencies
- **Strategy**: Check dependency installation, verify imports, update package manager, retry

**Category 4: Tool Limitation Errors**
- **Severity**: Medium
- **Recovery**: Escalate to manager for model upgrade or tool access grant
- **Examples**: Specialist tries to use tool not in their tier, model hallucinates tool usage
- **Strategy**: Manager checks if tool should be granted, or recommends model upgrade

**Category 5: Skill Gap Errors**
- **Severity**: Medium to High
- **Recovery**: Escalate to manager for reassignment
- **Examples**: Task requires expertise specialist doesn't have, unfamiliar framework
- **Strategy**: Manager reassigns to specialist with relevant expertise

**Category 6: Complex/Ambiguous Task Errors**
- **Severity**: High
- **Recovery**: Escalate to manager for task clarification or architect for redesign
- **Examples**: Unclear requirements, conflicting constraints, impossible requirements
- **Strategy**: Manager attempts to clarify, if unsuccessful escalates to architect for task reformulation

**Category 7: Infrastructure/External Errors**
- **Severity**: High
- **Recovery**: May require human intervention
- **Examples**: API rate limits, database connection failures, GitHub API errors, network issues
- **Strategy**: Retry with exponential backoff, if persistent escalate to human for infrastructure fix

**Category 8: Infinite Loop/Stuck State**
- **Severity**: Critical
- **Recovery**: Requires manager intervention
- **Examples**: Specialist repeating same failed approach, circular logic, consuming tokens without progress
- **Strategy**: Manager detects via progress monitoring, intervenes to break loop, reassigns or reformulates task

#### 7.2 Self-Recovery Process (Level 1)

**Specialist's Self-Recovery Workflow**:

**Attempt 1** (immediately after error):
- Parse error message to understand root cause
- Check if error is in known recoverable categories (syntax, import, test failure)
- Apply standard fix for that error type
- Rerun verification (tests, linter, etc.)
- If successful, continue task; if fails, proceed to Attempt 2

**Attempt 2** (with deeper analysis):
- Re-examine task requirements - did I misunderstand?
- Check context window for additional information I might have missed
- Look at similar code in repository - how do they handle this?
- Try alternative approach to same problem
- Rerun verification
- If successful, continue; if fails, proceed to Attempt 3

**Attempt 3** (with external context):
- Check neighbor context windows - has another specialist solved similar issue?
- Review mid-term compressed history - did I encounter this before?
- Try significantly different approach
- Rerun verification
- If successful, continue; if fails, escalate to manager with full error context

**Key Principle**: Self-recovery should be time-boxed. If specialist hasn't made progress after 3 attempts or30 minutes (whichever comes first), escalate rather than waste tokens.

#### 7.3 Manager Intervention (Level 2)

**Manager's Error Analysis Workflow**:

**Step 1: Classify Error**
- Review specialist's error report including all3 self-recovery attempts
- Classify into one of the error categories above
- Determine if this is a recurring pattern for this specialist

**Step 2: Select Intervention Strategy**

**For Tool Limitation Errors**:
- Check if specialist's model tier is insufficient for task complexity
- If yes, suggest user upgrade specialist's model (notify via dashboard)
- Or, check if tool should be granted based on actual need vs hallucination
- If legitimate need, temporarily grant tool access with monitoring

**For Skill Gap Errors**:
- Identify which specialist in the team has the required skill
- Reassign task to more suitable specialist
- Log this for future task assignment learning (update specialty match scoring)

**For Complex Task Errors**:
- Attempt to clarify task requirements using manager's broader context
- Reframe task description with more specific instructions
- Break task into smaller sub-tasks if original task too complex
- If manager can't clarify, escalate to architect

**For Test Failure Errors**:
- If specialist stuck on one specific test, assign second specialist to pair on debugging
- Create collaboration context for both specialists to coordinate
- Alternatively, assign testing specialist to write additional diagnostic tests

**For Infrastructure Errors**:
- Retry with exponential backoff (wait longer between attempts)
- Check if issue is temporary (API rate limit will reset) vs persistent
- If persistent, escalate to human via dashboard notification

**Step 3: Monitor Recovery**
- After intervention, set checkpoint for next progress review (e.g., 15 minutes)
- If specialist makes progress, continue monitoring
- If specialist still stuck after intervention, escalate to architect

**Manager's Proactive Monitoring**:
- Continuously track all specialists' progress metrics
- Calculate "stuck score": `(tokens_consumed / expected_tokens) * (time_elapsed / expected_time) * (1 - progress_percentage)`
- If stuck score exceeds threshold (e.g., 2.0), proactively intervene even without explicit escalation
- Early intervention prevents wasted resources

#### 7.4 Architect Escalation (Level 3)

**When Manager Escalates to Architect**:

**Scenario 1: Task Specification Issue**
- Manager and specialist both unclear on requirements
- Architect's action:
  - Review original user prompt for intent
  - Re-analyze what the task should accomplish
  - Rewrite task description with clearer acceptance criteria
  - Create additional context window with examples
  - Reassign (possibly to different specialist)

**Scenario 2: Task Complexity Underestimated**
- Task marked as complexity 5, but actually complexity 9
- Architect's action:
  - Decompose into multiple smaller sub-tasks
  - Create new GitHub issues for sub-tasks
  - Establish dependency order
  - Assign sub-tasks to multiple specialists potentially
  - Update complexity estimation model for future tasks

**Scenario 3: Repository Context Missing**
- Specialist needs information not available in their context window
- Architect's action:
  - Perform deeper repository analysis
  - Extract additional relevant files, patterns, or existing implementations
  - Create enriched context window
  - Provide specialist with additional background

**Scenario 4: Conflicting Requirements**
- Task has inherent conflicts (e.g., "make it fast and highly secure" but performance and security trade off)
- Architect's action:
  - Identify the conflict explicitly
  - Escalate to human user for decision on trade-off
  - Once user decides, update task requirements with chosen priority
  - Add global rule if decision applies to future tasks

**Scenario 5: Multiple Specialists Failing Same Task**
- Manager has reassigned task2-3 times, all specialists struggle
- Architect's action:
  - Recognize this might be architectural issue, not execution issue
  - Review if task is feasible given currentcodebase structure
  - May need to implement foundational changes first
  - Create prerequisite tasks
  - Reschedule original task for after prerequisites

**Scenario 6: Systemic Issue**
- Multiple tasks across different managers experiencing similar failures
- Architect's action:
  - Identify common pattern (e.g., all database tasks failing - maybe DB connection issue)
  - Escalate to human for infrastructure fix
  - Pause related tasks until issue resolved
  - Once resolved, resume tasks

#### 7.5 Human-in-the-Loop Escalation (Level 4)

**Triggers for Human Escalation**:
- Architect cannot resolve issue after 2 attempts
- Infrastructure/external system failures
- User decision required (conflicting requirements, security/performance trade-offs)
- Budget exceeded (token usage beyond allocation)
- Deadline approaching with tasks incomplete
- Security vulnerability requiring judgment call
- Unknown error pattern not classifiable by any agent

**Human Notification Methods**:
- Dashboard alert (red banner with details)
- Optional: Email/Slack notification if configured
- Provides context: what failed, what's been tried, recommended actions

**Human Actions Available**:
- Provide additional requirements/clarification
- Manually fix infrastructure issue
- Adjust task priorities
- Increase token budget
- Modify agent configuration
- Pause/resume harness
- Manual code review and merge

---

### Section 8: Model Configuration & API Integration (Expanded)

#### 8.1 Multi-Provider API Abstraction

**Supported Model Providers**:
- **OpenAI**: GPT-4, GPT-4-turbo, GPT-4-mini, GPT-3.5-turbo
- **Anthropic**: Claude Opus, Claude Sonnet, Claude Haiku
- **Google**: Gemini 1.5 Pro, Gemini 1.5 Flash
- **Open-Source**: Llama 3, Mistral, Codestral (via Ollama or self-hosted)

**Abstraction Layer Benefits**:
- Users can mix providers (e.g., OpenAI for architect, Anthropic for managers, Google for specialists)
- Fallback mechanisms: if primary provider API fails, automatically switch to configured fallback
- Cost optimization: route to cheapest model that meets requirements
- Provider-agnostic tool calling: harness translates tool calls to each provider's format

**API Request Flow**:
1. Agent needs to make model call (e.g., analyze task requirements)
2. Agent calls harness's unified `generate_response()` method with prompt and parameters
3. Harness checks agent's configured provider from config
4. Harness formats request in provider-specific format (OpenAI uses `messages` array, Anthropic uses different structure)
5. Harness adds tool definitions in provider-specific format
6. Harness makes API call with retry logic and error handling
7. Provider responds
8. Harness parses response to unified format
9. Harness logs token usage to context store
10. Returns result to agent

#### 8.2 Model Tier System

**Tier 1: Basic Models**
- **Examples**: GPT-3.5-turbo, Gemini Flash, Llama 3 8B, Claude Haiku
- **Characteristics**: Fast, cheap, good for simple tasks
- **Limitations**: Can hallucinate on complex tasks, limited context window, may struggle with multi-step reasoning
- **Use Cases**: Simple code reading, basic file operations, status reporting
- **Tool Access**: Tier 1 tools only (read operations, basic git)

**Tier 2: Intermediate Models**
- **Examples**: GPT-4-mini, Gemini 1.5 Flash, Mistral Medium
- **Characteristics**: Good balance of cost and capability
- **Strengths**: Reliable for most coding tasks, fewer hallucinations, decent reasoning
- **Use Cases**: Feature implementation, test writing, bug fixing
- **Tool Access**: Tier 1 + Tier 2 tools (write operations, testing, package management)

**Tier 3: Advanced Models**
- **Examples**: GPT-4, Claude Opus, Gemini 1.5 Pro, GPT-4-turbo
- **Characteristics**: Highest capability, best reasoning, most expensive
- **Strengths**: Complex problem-solving, architectural thinking, multi-step planning
- **Use Cases**: Architecture design, complex refactoring, critical code review
- **Tool Access**: All tools (including database, infrastructure, security scanning)

**Tier 4: Specialized Models** (future expansion)
- **Examples**: Codestral (code-specific), DeepSeek Coder, Code Llama
- **Characteristics**: Optimized for specific domains
- **Use Cases**: Domain-specific tasks where specialized models outperform general ones

**Automatic Tier Recommendation**:
- System analyzes task complexity, required tools, and budget
- Recommends minimum tier needed for reliable execution
- Warns if user configures specialist with tier below recommendation
- Allows user override with acknowledgment

#### 8.3 Dynamic Model Selection

**Adaptive Model Usage**:

**Scenario 1: Specialist Struggling**
- Specialist with Tier 2 model fails task twice
- Manager analyzes if task complexity exceeds specialist's model capability
- Manager suggests temporary model upgrade to Tier 3 for this specific task
- User can approve upgrade via dashboard or auto-approve if budget allows
- After task completion, specialist reverts to Tier 2 for next task

**Scenario 2: Simple Task Optimization**
- Task classified as low complexity (score 1-3)
- Specialist configured with Tier 3 model (overkill)
- System suggests downgrading to Tier 2 for this task to save costs
- If user enables "auto-optimize", system automatically uses lower tier when sufficient

**Scenario 3: Critical Path Acceleration**
- Multiple tasks waiting on one blocking task
- System identifies critical path
- Temporarily upgrades specialist working on blocker to highest tier
- Parallelizes with additional specialists if possible
- Goal: unblock critical path even at higher cost

#### 8.4 API Rate Limiting and Quotas

**Rate Limit Handling**:

**Detection**:
- Monitor API response headers for rate limit status
- Track requests per minute/hour/day per provider
- Predict when rate limit will be hit based on current usage pattern

**Prevention**:
- Queue requests if approaching rate limit
- Distribute requests across time to smooth out spikes
- If multiple API keys available, round-robin between them

**Response to Rate Limit Hit**:
- Immediate: Queue pending requests
- Short-term: Exponential backoff (wait 60s, then 120s, then 240s)
- If persistent: Switch to fallback provider if configured
- Notify user of rate limit issue via dashboard

**Cost Tracking**:
- Log every API call with token counts (prompt + completion)
- Calculate cost based on provider's pricing ($/1M tokens)
- Display cumulative cost per agent, per task, and globally
- Alert when approaching budget limits (80%, 90%, 100%)
- Provide cost breakdown: which agents/tasks consuming most budget

#### 8.5 Tool Calling Compatibility

**OpenAI Format** (function calling):
- Uses `tools` array with `function` objects
- Each function has `name`, `description`, `parameters` schema

**Anthropic Format**:
- Uses `tools` array with slightly different structure
- Requires explicit `tool_choice` parameter

**Google Format**:
- Uses `function_declarations` in `tools` array
- Different schema format for parameters

**Harness Translation Layer**:
- Maintains single internal tool definition format
- Translates to provider-specific format on each API call
- Parses provider-specific tool call responses back to unified format
- Handles differences in how providers signal tool usage

---

### Section 9: Verification & Quality Assurance (Expanded)

#### 9.1 Multi-Stage Verification Pipeline

**Stage 1: Agent Self-Check (Pre-PR)**

**When**: Before specialist raises PR

**Checks**:
- **Syntax Validation**: Run language-specific parser to catch syntax errors
- **Local Test Execution**: Run all relevant tests on specialist's branch
- **Linting**: Run configured linters (ESLint, Pylint, etc.)
- **Formatting**: Run formatters (Prettier, Black, rustfmt) and auto-fix
- **Acceptance Criteria Checklist**: Specialist reviews original task's acceptance criteria and confirms each met
- **File Diff Review**: Specialist reviews all changed files to ensure no accidental changes

**Self-Check Failures**:
- If any check fails, specialist must fix before PR creation
- Counts toward self-recovery attempts
- If can't fix after 3 attempts, escalate to manager

**Stage 2: Automated CI/CD Pipeline (Post-PR)**

**When**: Immediately after PR creation, runs on GitHub Actions/GitLab CI

**Checks**:

**Build Verification**:
- Compile code (if compiled language)
- Bundle application (if web app)
- Ensure no build errors
- Check bundle size hasn't increased dramatically (>10% growth flagged)

**Test Suites**:
- Unit tests: Test individual functions/classes
- Integration tests: Test interactions between modules
- E2E tests (if applicable): Test full user workflows
- Performance tests (if configured): Ensure no performance regressions
- All must pass (100% pass rate required)

**Code Quality**:
- Linting with blocking rules (errors fail build, warnings allowed)
- Code coverage report: Check if new code is tested
- Coverage threshold enforcement: Block if coverage drops below 80% (configurable)
- Cyclomatic complexity check: Flag functions with high complexity (>15)

**Security Scanning**:
- Dependency vulnerability scan (Snyk, npm audit, pip-audit)
- Static application security testing (SAST) - Semgrep, Bandit
- Check for hardcoded secrets (GitGuardian, TruffleHog)
- License compatibility check for new dependencies

**Documentation**:
- Check if README updated (if new features added)
- Check if API documentation generated (if API changes)
- Verify all public functions have docstrings/JSDoc

**CI/CD Failure Handling**:
- Comment on PR with detailed failure information
- Mark PR status as "failed"
- Specialist is automatically notified
- Specialist fixes issues and pushes new commits
- CI/CD re-runs automatically on new commits

**Stage 3: Optional Code Review Agent**

**When**: After CI/CD passes, if reviewer agent enabled in config

**Provider Diversity Requirement**: The reviewer agent's `model_provider` must differ from the specialist's that authored the PR. A same-provider review is prone to the same blind spots the author had, since correlated training tends to miss the same class of mistakes. This is enforced at config-validation time, not left as a convention: if a reviewer and its assigned specialist share a provider, the system either blocks startup with a config error or auto-selects a different-provider reviewer, per `coordination.reviewer_diversity_policy` (`block` | `auto_reassign`). This check re-runs whenever configs are edited, so provider diversity can't silently degrade as specialists or reviewers are swapped later.

**Review Focus**:

**Code Quality Deep Dive**:
- **Code Smells**: Long functions (>50 lines), deep nesting (>3 levels), duplicated code
- **Naming**: Variables, functions, classes use clear, descriptive names
- **Complexity**: Functions do one thing, classes have single responsibility
- **Error Handling**: Proper try-catch, error messages meaningful
- **Magic Numbers**: No unexplained constants, should be named variables

**Pattern Consistency**:
- **Repository Conventions**: Does code follow existing patterns in repo?
- **Framework Best Practices**: Using framework idioms correctly (React hooks, Express middleware, etc.)
- **Design Patterns**: Appropriate use of patterns (factory, singleton, observer, etc.)

**Test Quality**:
- **Coverage Gaps**: Identify specific edge cases not tested
- **Test Clarity**: Test names describe what they test
- **Test Independence**: Tests don't depend on execution order
- **Mock Appropriateness**: External dependencies properly mocked

**Performance Considerations**:
- **N+1 Queries**: Database queries in loops (should batch)
- **Inefficient Algorithms**: O(n²) where O(n log n) possible
- **Memory Leaks**: Event listeners not cleaned up, circular references
- **Unnecessary Re-renders**: React components re-rendering excessively

**Security Review**:
- **Input Validation**: User inputs validated and sanitized
- **SQL Injection**: Parameterized queries used
- **XSS Prevention**: Output properly escaped
- **Authentication**: Protected endpoints have auth checks
- **Authorization**: Users can only access their own resources

**Documentation**:
- **Inline Comments**: Complex logic explained
- **Function Documentation**: Parameters and return values documented
- **Architectural Decisions**: Significant design choices explained

**Reviewer Output**:
- **Non-Blocking Comments**: Suggestions for improvement as GitHub PR comments
- **Low-Priority Issues**: Creates follow-up GitHub issues for technical debt items
- **Score**: Gives PR a quality score (0-100) for tracking purposes

**Stage 4: Manager Coordination Review**

**When**: After automated checks and optional reviewer

**Manager's Checks**:

**Conflict Detection**:
- Compare PR file changes with other open PRs
- Identify potential merge conflicts (both git and semantic)
- Check if merging will break other in-progress work

**Task Completion Validation**:
- Review original GitHub issue acceptance criteria
- Verify PR actually addresses all criteria
- Check for scope creep (PR doing more than task asked)

**Integration Safety**:
- Will this PR break existing functionality?
- Are there adequate tests to prevent regressions?
- Does this require deployment coordination (database migrations, environment variables)?

**Manager's Actions**:
- **Approve**: Forward to architect if all looks good
- **Request Conflict Resolution**: Assign specialist(s) to resolve conflicts
- **Request Changes**: If acceptance criteria not met, send back to specialist with specific feedback
- **Reassign**: If specialist clearly went wrong direction, might reassign to different specialist

**Stage 5: Architect Final Gate**

**When**: After manager approval, before merge

**Architect's High-Level Review**:

**Intent Validation**:
- Does this PR achieve what the user originally requested?
- Is the approach architecturally sound?
- Could this have been done more simply (YAGNI principle)?

**System Impact**:
- How does this affect the overall system architecture?
- Does it introduce new dependencies on external systems?
- Is it backwards-compatible with existing features?

**Global Rules**:
- Check against all extracted global rules
- Ensure compliance with user's stated preferences
- Verify coding standards maintained

**Quality Gate**:
- Is this production-ready?
- Is it maintainable (will humans understand this in 6 months)?
- Does documentation exist for future developers?

**Architect's Decision**:
- **Approve & Merge**: Merge to main, task complete
- **Request Minor Changes**: Specific small fixes needed
- **Request Redesign**: Fundamental issue, needs different approach
- **Escalate to Human**: User input needed before merging

#### 9.2 Test Coverage Requirements

**Coverage Thresholds** (configurable):
- **Minimum Overall Coverage**: 80% (blocks merge if not met)
- **New Code Coverage**: 90% (new code should be well-tested)
- **Critical Paths**: 100% (authentication, payment, data integrity)

**Coverage Exemptions**:
- Configuration files
- Generated code
- Third-party code
- Explicitly marked as uncoverable (with justification)

**Coverage Enforcement**:
- CI/CD fails if threshold not met
- Coverage report posted as PR comment showing what's uncovered
- Specialist adds tests for uncovered lines
- Re-run CI/CD until threshold met

#### 9.3 Performance Benchmarking

**When Enabled** (optional, for performance-critical applications):

**Baseline Establishment**:
- Before changes, run performance benchmarks on main branch
- Measure: response times, throughput, memory usage, CPU usage
- Store baseline metrics

**PR Performance Testing**:
- Run same benchmarks on PR branch
- Compare against baseline
- Flag if regression detected:
  - Response time increase >10%
  - Memory usage increase >15%
  - Throughput decrease >10%

**Performance Regression Handling**:
- PR comment shows performance comparison
- If significant regression, block merge (unless explicitly overridden)
- Specialist must optimize or justify regression

---

### Section 10: User Interface & Configuration (Expanded)

#### 10.1 Interactive Configuration UI Design

**UI Framework**: Web-based dashboard (React/Vue/Svelte), responsive, modern design

**Main Configuration View**:

**Canvas Area** (drag-and-drop workspace):
- **Grid-based layout** for organizing agent blocks
- **Zoom and pan** controls for large configurations
- **Snap-to-grid** for clean alignment
- **Connection lines** auto-route between agents showing hierarchy

**Agent Block Components**:

**Architect Block** (single instance):
- **Icon**: Crown or blueprint symbol
- **Configurable Fields**:
  - Model provider dropdown (OpenAI, Anthropic, Google, Custom)
  - Model ID dropdown (filtered by provider)
  - Temperature slider (0.0 - 1.0)
  - Max tokens input
  - API key reference (environment variable name)
- **Visual Indicators**:
  - Green border if API key valid
  - Yellow warning if using sub-optimal model
  - Cost estimate per 1M tokens

**Manager Block** (2-3 instances):
- **Icon**: Organizational chart symbol
- **Configurable Fields**:
  - Manager ID (auto-generated or custom)
  - Team name (backend, frontend, devops)
  - Model configuration (same as architect)
  - Max specialists (slider1-15)
  - Assignment algorithm (dropdown)
- **Visual Indicators**:
  - Shows number of connected specialists
  - Cost estimate
- **Connection Points**:
  - Input from architect (top)
  - Output to specialists (bottom)

**Specialist Block** (8-15 instances):
- **Icon**: Code symbol, changes based on specialty
- **Configurable Fields**:
  - Specialist ID
  - Specialty dropdown (backend-api, frontend-react, database, testing, etc.)
  - Model configuration
  - Tool permissions (checkboxes)
  - Assigned manager (dropdown or drag connection)
- **Visual Indicators**:
  - Color-coded by specialty
  - Shows model tier (bronze/silver/gold/platinum)
  - Shows enabled tools count
  - Warns if low-tier model assigned to complex specialty
- **Connection Points**:
  - Input from manager (top)

**Interaction Features**:

**Drag to Create**:
- Sidebar with agent type buttons
- Drag button onto canvas to create instance
- Automatically positions near related agents

**Click to Configure**:
- Click any agent block to open property panel on right
- Property panel shows all configurable fields
- Changes save in real-time
- Validation errors show immediately

**Connect by Dragging**:
- Drag from connection point to another agent
- Line automatically routes between agents
- Validates connections (can't connect specialist directly to architect)
- Shows connection type on hover

**Real-Time Config Generation**:
- As user interacts, YAML/JSON config updates in bottom panel
- Syntax-highlighted, formatted
- Can toggle between YAML and JSON format
- Can copy config to clipboard
- Can export as file

**Templates**:
- Pre-configured templates for common setups:
  - "Budget Mode": Mostly tier 1-2 models, fewer agents
  - "Balanced Mode": Mix of tiers, moderate agent count
  - "Performance Mode": Mostly tier 3 models, many agents
  - "Full-Stack": Backend, frontend, and devops teams
- User can save custom templates

**Validation**:
- Real-time validation as user configures
- Red error indicators on invalid configurations
- Tooltip explains what's wrong
- Prevents starting harness with invalid config

**Cost Estimation**:
- Shows estimated monthly cost based on:
  - Number of agents
  - Model tiers selected
  - Assumed token usage per agent (configurable)
- Updates in real-time as configuration changes
- Breaks down cost by agent type and provider

#### 10.2 Dashboard Monitoring UI

**Layout**: Multi-panel dashboard with tabs

**Tab 1: Overview**

**Task Board** (Kanban view):
- **Columns**: To Do, In Progress, Review, Done
- **Cards**: Each GitHub issue as a card
- **Card Details**:
  - Issue number and title
  - Assigned specialist(s) with avatars
  - Priority indicator (color-coded)
  - Progress bar (0-100%)
  - Time elapsed / estimated
- **Drag-and-Drop**: Users can manually move tasks between columns (triggers reassignment)

**Active Agents Panel**:
- **List View**: All agents with current status
- **Per Agent**:
  - ID and specialty
  - Status: Idle, Working, Blocked, Error
  - Current task (if working)
  - Tokens consumed today
  - Efficiency score (tasks completed / tokens used)
- **Filters**: By status, by team, by specialty

**System Metrics**:
- **Total tasks**: Completed / In Progress / To Do
- **Overall progress**: Percentage complete
- **Token usage**: Today / This week / Total with graph
- **Cost**: Spent today / This week / Month-to-date
- **Average task completion time**
- **Success rate**: % of tasks completed without errors

**Tab 2: Agent Details**

**Agent Selection**:
- Dropdown or list to select specific agent
- Shows detailed view for that agent

**Agent Profile**:
- ID, type, specialty, model, tier
- Configuration summary
- Total tasks completed
- Success rate
- Average tokens per task

**Current Task Details** (if working):
- Task title and description
- Time elapsed with progress indicator
- Tokens consumed so far
- Real-time log stream (last 20 actions)
- Files currently being modified

**Performance History**:
- Graph: Tokens used over time
- Graph: Tasks completed over time
- Efficiency trend
- Errorcount trend

**Tab 3: GitHub Integration**

**Embedded GitHub View**:
- **Issues Tab**:
  - List of all open issues created by architect
  - Filter by label, assignee, status
  - Click to open in GitHub
- **Pull Requests Tab**:
  - List of all open PRs from specialists
  - Status indicators (checks passing/failing)
  - Reviewer comments count
  - Click to open in GitHub
- **Commits Tab**:
  - Recent commits from agents
  - Shows agent ID, commit message, timestamp
  - Diff viewer for quick inspection

**Live Activity Feed**:
- Real-time stream of GitHub events:
  - Issue created
  - PR opened
  - PR updated
  - Check suite passed/failed
  - PR merged- Comment added

**Tab 4: Logs & Debugging**

**Log Stream**:
- **Filterable by**:
  - Agent ID
  - Log level (DEBUG, INFO, WARN, ERROR)
  - Time range
  - Keyword search
- **Each Log Entry**:
  - Timestamp
  - Agent ID
  - Level (color-coded)
  - Message
  - Expandable for full details (stack trace, context)

**Error Dashboard**:
- List of all errors encountered
- Group by error type
- Shows recovery actions taken
- Can replay error context for debugging

**Token Usage Details**:
- Table showing all API calls
- Columns: Agent, Timestamp, Provider, Model, Prompt Tokens, Completion Tokens, Cost
- Export to CSV for analysis

**Tab 5: Testing Interface**

**Feature Testing Window**:
- When agents complete intermediate milestones, testing panel activates
- Shows available features to test
- **Terminal Emulator**: User can run commands to test
- **API Tester**: For backend features, provides curl command or HTTP client
- **Browser Preview**: For frontend features, embedded browser to interact with UI
- **Feedback Form**: User can report if feature works as expected or has issues

**Test Results**:
- History of user-tested features
- Pass/fail status
- User notes

#### 10.3 Configuration File Format (Detailed)

**YAML Structure**:

```yaml
harness_config:
  version: "1.0"
  created_at: "2026-09-26T15:00:00Z"
  last_modified: "2026-09-26T16:30:00Z"
  
  # Repository connection
  repository:
    url: "https://github.com/username/project"
    branch: "main"
    local_path: "./workspace"
    
  # GitHub API integration
  github:
    token_env: "GITHUB_TOKEN"
    auto_create_issues: true
    auto_comment_progress: true
    auto_merge: false# Require human approval
    merge_strategy: "squash"  # or "merge", "rebase"
    
  # Global resource limits
  resource_limits:
    total_token_budget: 1000000
    daily_token_limit: 100000
    per_agent_limit: 50000
    budget_strategy: "dynamic"  # or "fixed", "priority"
    cost_alert_threshold: 0.8# Alert at 80%
  # Architect configuration
  architect:
    model:
      provider: "openai"
      id: "gpt-4"
      api_key_env: "OPENAI_API_KEY"
      temperature: 0.2
      max_tokens: 8000
      fallback_provider: "anthropic"
      fallback_model: "claude-opus-3"
    
    behavioral_params:
      complexity_threshold: 7
      review_strictness: "high"
      auto_merge: false
      escalation_timeout_seconds: 3600
      
    knowledge_bases:
      - "production_architectures"
      - "design_patterns"
      - "code_review_guidelines"
  
  # Manager configurations
  managers:
    - id: "mgr-backend"
      team: "backend"
      model:
        provider: "anthropic"
        id: "claude-sonnet-3-5"
        api_key_env: "ANTHROPIC_API_KEY"
        temperature: 0.3
        max_tokens: 4000
      max_specialists: 8
      concurrent_task_limit: 5specialties_managed:
        - backend-api
        - database
        - authentication
        - caching
      behavioral_params:
        assignment_algorithm: "multi_factor"
        collaboration_threshold: 7
        progress_check_interval_seconds: 300
        token_warning_threshold: 0.8escalation_retry_count: 2
    - id: "mgr-frontend"
      team: "frontend"
      model:
        provider: "openai"
        id: "gpt-4-mini"
        api_key_env: "OPENAI_API_KEY"
        temperature: 0.4
        max_tokens: 4000
      
      max_specialists: 6
      concurrent_task_limit: 4
      
      specialties_managed:
        - frontend-react
        - frontend-styling
        - frontend-testing
    
    - id: "mgr-devops"
      team: "devops"
      model:
        provider: "google"
        id: "gemini-1.5-flash"
        api_key_env: "GOOGLE_API_KEY"
        temperature: 0.2
        max_tokens: 4000
      
      max_specialists: 4
      concurrent_task_limit: 3
      
      specialties_managed:
        - devops
        - infrastructure
        - ci-cd
  
  # Specialist configurations
  specialists:
    # Backend specialists
    - id: "sd-backend-api-1"
      specialty: "backend-api"
      manager: "mgr-backend"
      model:
        provider: "openai"
        id: "gpt-4-mini"
        api_key_env: "OPENAI_API_KEY"
        temperature: 0.4
        max_tokens: 4000
      
      tools:
        - filesystem_read_write
        - git_operations
        - grep_search
        - test_runner
        - api_testing
      
      file_patterns:
        - "src/routes/**/*.js"
        - "src/controllers/**/*.js"
        - "src/middleware/**/*.js"
      
      training_focus:
        - "RESTful API design"
        - "Express.js patterns"
        - "JWT authentication"
    
    - id: "sd-database-1"
      specialty: "database"
      manager: "mgr-backend"
      model:
        provider: "google"
        id: "gemini-1.5-pro"
        api_key_env: "GOOGLE_API_KEY"
        temperature: 0.3
        max_tokens: 4000
      
      tools:
        - filesystem_read_write
        - git_operations
        - database_client
        - migration_tools
        - query_analyzer
      
      file_patterns:
        - "src/models/**/*.js"
        - "migrations/**/*.sql"
        - "prisma/schema.prisma"
    
    # Frontend specialists
    - id: "sd-frontend-react-1"
      specialty: "frontend-react"
      manager: "mgr-frontend"
      model:
        provider: "openai"
        id: "gpt-4-mini"
        api_key_env: "OPENAI_API_KEY"
        temperature: 0.5
        max_tokens: 4000
      
      tools:
        - filesystem_read_write
        - git_operations
        - npm_commands
        - test_runner
        - browser_testing
      
      file_patterns:
        - "src/components/**/*.jsx"
        - "src/pages/**/*.tsx"
        - "src/hooks/**/*.js"
    
    # Testing specialist
    - id: "sd-testing-1"
      specialty: "testing"
      manager: "mgr-backend"  # Can work with any team
      model:
        provider: "openai"
        id: "gpt-4"
        api_key_env: "OPENAI_API_KEY"
        temperature: 0.3
        max_tokens: 4000
      
      tools:
        - filesystem_read_write
        - git_operations
        - test_runner
        - coverage_analyzer
        - e2e_browser
      
      file_patterns:
        - "tests/**/*.test.js"
        - "__tests__/**/*.js"
    
    # Code reviewer (optional)
    - id: "sd-reviewer-1"
      specialty: "code-review"
      manager: null  # Dynamically assigned
      model:
        provider: "openai"
        id: "gpt-4"
        api_key_env: "OPENAI_API_KEY"
        temperature: 0.2
        max_tokens: 4000
      
      enabled: true  # Set to false to disable reviewer
      
      tools:
        - filesystem_read
        - git_operations
        - diff_analysis
        - static_analysis_tools
  
  # Verification pipeline configuration
  verification:
    ci_cd:
      platform: "github_actions"  # or "gitlab_ci", "jenkins"
      config_file: ".github/workflows/test.yml"
      
      required_checks:
        - name: "lint"
          blocking: true
        - name: "test"
          blocking: true
        - name: "coverage"
          blocking: true
          threshold: 80
        - name: "security_scan"
          blocking: true- name: "build"
          blocking: true
    
    code_review:
      enable_reviewer_agent: true
      reviewer_creates_issues: true
      issue_priority: "low"
    
    performance_benchmarks:
      enabled: false  # Optional
      regression_threshold: 0.10# 10% regression blocks
  # Monitoring configuration
  monitoring:
    dashboard:
      enabled: true
      port: 3000
      host: "localhost"
    
    logging:
      level: "INFO"  # DEBUG, INFO, WARN, ERROR
      file: "./logs/harness.log"
      max_size_mb: 100
      retention_days: 30
    
    notifications:
      email:
        enabled: false
        smtp_host: ""
        recipients: []
      
      slack:
        enabled: false
        webhook_url_env: "SLACK_WEBHOOK"
  # Context management
  context:
    storage:
      type: "postgresql"  # or "mongodb", "sqlite"
      connection_string_env: "DATABASE_URL"
    compression:
      window_1_size: 20
      window_2_size: 100
      window_3_size: 500
      compression_algorithm: "summarization"  # or "deduplication"
  # Security settings
  security:
    sandbox_code_execution: true
    prevent_secret_logging: true
    require_code_review_for_security_files: true
    security_file_patterns:
      - "**/*.env"
      - "**/secrets/**"
      - "**/credentials/**"
```

**User Actions**:
- **Export**: Download this config as file
- **Import**: Upload existing config to populate UI
- **Share**: Generate shareable link (without API keys)
- **Version**: Save multiple config versions, switch between them

---

### Section 11: Resource Management & Optimization (Expanded)

#### 11.1 Token Budget Allocation Strategies

**Strategy 1: Fixed Per-Agent Budget**

**Allocation Method**:
- Each agent receives a predetermined token allocation at the start of the day/week/month
- Budget is independent of task complexity or agent performance
- Simple and predictable, but inflexible

**Budget Distribution Example**:
- Architect: Unlimited (critical path, can't be constrained)
- Each Manager: 100,000 tokens per day
- Each Specialist: 50,000 tokens per day
- Total daily budget: 100k (managers) × 3+ 50k (specialists) × 10= 800k tokens

**Enforcement**:
- When agent reaches budget limit, it's marked as "budget exhausted"
- Cannot accept new tasks until budget resets
- Manager must reassign tasks to agents with remaining budget
- User receives notification when agents hit budget

**Pros**: Predictable costs, simple to understand, prevents runaway spending
**Cons**: Inflexible, some agents may sit idle while others need more budget

**Strategy 2: Dynamic Allocation Based on Performance**

**Initial Allocation**:
- All agents start with base budget (e.g., 50k tokens)

**Performance-Based Adjustment**:
- Track each agent's efficiency: `efficiency = tasks_completed / tokens_consumed`
- Calculate team average efficiency
- Every evaluation period (e.g., every 6 hours):
  - High performers (efficiency > team_avg × 1.2): Bonus +20% budget
  - Average performers: Budget maintained
  - Low performers (efficiency < team_avg × 0.8): Penalty -10% budget

**Reallocation**:
- Tokens saved from low performers are redistributed to high performers
- Ensures token budget flows to most productive agents
- Self-optimizing over time

**Safeguards**:
- Minimum budget per agent (e.g., 10k tokens) - never drop below
- Maximum budget per agent (e.g., 200k tokens) - prevent one agent from dominating
- New agents get 3-task grace period before performance evaluation kicks in

**Pros**: Rewards productivity, self-optimizing, maximizes output per token
**Cons**: More complex, can create feedback loops (struggling agents get less budget, struggle more)

**Strategy 3: Priority-Based Allocation**

**Task Priority Determines Budget**:
- Each task has priority level: Critical, High, Normal, Low
- Budget allocated per task based on priority:
  - Critical: 100k tokens
  - High: 50k tokens
  - Normal: 30k tokens
  - Low: 15k tokens

**Agent Receives Budget When Assigned Task**:
- No standing budget - agents only get tokens when assigned tasks
- If task consumes less than allocated budget, excess returns to pool
- If task needs more, manager can request budget increase (requires justification)

**Priority Escalation**:
- If task is blocked and blocking other tasks, priority auto-escalates
- Higher priority = more budget available
- Critical tasks never budget-constrained

**Pros**: Budget tied directly to business value, critical work never blocked
**Cons**: Hard to predict total spend, requires careful priority assignment

**Strategy 4: Adaptive Pool System**

**Global Token Pool**:
- Total budget goes into shared pool (e.g., 1M tokens/day)
- Agents draw from pool as needed
- No per-agent limits, but total pool is finite

**Draw Monitoring**:
- Real-time tracking of pool level
- When pool reaches warning thresholds:
  - 80% consumed: Start prioritizing high-value tasks
  - 90% consumed: Only critical tasks proceed
  - 100% consumed: All work pauses until reset

**Intelligent Rationing**:
- As pool depletes, system becomes more selective about task assignment
- Lower-priority tasks deferred
- System suggests using lower-tier models to conserve tokens
- May batch multiple tasks together to minimize overhead

**Pool Refill**:
- Daily/weekly reset based on configured period
- Optional: User can manually add tokens to pool mid-period if needed

**Pros**: Maximum flexibility, agents never artificially blocked, naturally prioritizes high-value work
**Cons**: Unpredictable consumption patterns, risk of exhausting pool early in period

**Recommendation for Hackathon**: Use **Strategy 2 (Dynamic Allocation)** or **Strategy 4 (Adaptive Pool)** to demonstrate intelligent resource management.

#### 11.2 Cost Optimization Techniques

**Technique 1: Model Tier Downgrading for Simple Tasks**

**Detection**:
- System analyzes task complexity scoring
- Tasks with complexity≤ 3 flagged as "simple"

**Optimization**:
- If specialist assigned has Tier 3 model but task is simple, suggest Tier 2
- If user enables auto-optimization, system automatically uses lower tier
- Track success rate - if lower tier completes successfully, learn for future

**Savings**:
- Tier 3 to Tier 2: ~70% cost reduction
- Tier 2 to Tier 1: ~80% cost reduction
- Cumulative savings over many simple tasks is significant

**Technique 2: Caching Repeated Analyses**

**Cacheable Operations**:
- Repository structure analysis (changes infrequently)
- File dependency graphs
- Code pattern detection
- Similar task solutions

**Cache Implementation**:
- Store analysis results in context store with hash key
- Before performing expensive operation, check cache
- Cache invalidation: When files modified, invalidate related caches
- TTL: Cache expires after configurable time (e.g., 24 hours)

**Savings**:
- Avoid re-analyzing same code multiple times
- Particularly valuable for repository analysis (architect's initial scan)
- Can save 20-30% of architect's token usage

**Technique 3: Batching Similar Tasks**

**Detection**:
- When multiple tasks are similar (same file patterns, same specialty, similar acceptance criteria)
- Example: "Add authentication to endpoint A", "Add authentication to endpoint B", "Add authentication to endpoint C"

**Optimization**:
- Instead of assigning separately, create single combined task
- Specialist solves pattern once, applies to all instances
- Single PR with all changes

**Savings**:
- Reduces context-loading overhead (load repo context once, not three times)
- Pattern reuse within same execution
- Can save 30-40% tokens compared to separate execution

**Technique 4: Incremental Context Loading**

**Problem**:
- Loading full repository context every time is expensive
- Most tasks only need subset of files

**Solution**:
- Provide minimal context initially (task description + directly relevant files)
- Allow agent to request additional context on-demand
- Load files lazily as agent determines they're needed

**Implementation**:
- Initial context: ~5-10 most relevant files
- Agent has `request_additional_context()` tool
- Agent can explore repository structure and load files as needed
- Significantly reduces unused context in prompt

**Savings**:
- Reduce prompt tokencount by 50-70% for focused tasks
- Only load what's actually used

**Technique 5: Compression of Historical Context**

**Aggressive Compression**:
- Apply more aggressive compression to older context windows
- Window 1: Full detail (recent)
- Window 2: Moderate compression (mid-term)
- Window 3: Heavy compression (historical)
- Window 4: Ultra-compressed (only major milestones)

**Smart Retrieval**:
- Don't load historical windows unless explicitly needed
- Agent requests history only when current context insufficient
- Most tasks complete with Window 1 only

**Savings**:
- Reduces context size by 60-80% on average
- Especially valuable for long-running agents with extensive history

#### 11.3 Performance Tracking and Analytics

**Metrics Dashboard**:

**Agent-Level Metrics**:
- **Efficiency Score**: `tasks_completed / (tokens_consumed / 1000)`- Higher is better- Industry benchmark: 1.5-2.5tasks per 1k tokens
- **Success Rate**: `successful_tasks / total_tasks`
  - Target: >90%
- **Average Task Duration**: Time from assignment to completion
  - Track trend - should decrease as agent "learns"
- **Error Rate**: `errors_encountered / tasks_attempted`
  - Target: <10%
- **Self-Recovery Rate**: `errors_self_resolved / total_errors`
  - Target: >70%
- **Escalation Frequency**: `escalations / total_tasks`
  - Target: <5%

**Task-Level Metrics**:
- **Token Consumption**: Total tokens used for this task
- **Time to Completion**: Wall-clock time
- **Iteration Count**: How many attempts needed
- **Code Quality Score**: From reviewer agent (if enabled)
- **Test Coverage**: % of new code covered by tests
- **Merge Conflicts**: How many conflicts occurred during merge

**System-Level Metrics**:
- **Overall Throughput**: Tasks completed per day
- **Average Cost Per Task**: Total spend / tasks completed
- **Budget Utilization**: % of allocated budget consumed
- **Agent Utilization**: % of time agents actively working vs idle
- **Critical Path Efficiency**: How quickly blocking tasks are resolved
- **User Satisfaction**: If user provides feedback, track satisfaction ratings

**Trend Analysis**:
- Graph metrics over time (daily, weekly, monthly)
- Identify patterns:
  - Are certain specialists consistently underperforming?
  - Are certain task types consuming excessive tokens?
  - Are we getting more efficient over time (learning effect)?
- Provide actionable insights: "Consider upgrading sd-backend-2's model" or "Database tasks using 2x expected tokens - investigate"

**Cost Breakdown**:
- **By Agent**: Which agents consuming most budget?
- **By Task Type**: Which specialties most expensive?
- **By Provider**: How much spent on OpenAI vs Anthropic vs Google?
- **By Time Period**: Daily/weekly spend with trend line
- **Projected Monthly Cost**: Based on current usage pattern

**Optimization Recommendations**:
System generates automated suggestions:
- "Task complexity estimation too conservative - 80% of tasks use less than 50% allocated budget"
- "sd-frontend-1 has 95% success rate with Tier 2 model - consider downgrading from Tier 3"
- "Backend tasks show high cache hit rate - enable aggressive caching to save 25%"
- "Three specialists idle 60% of time - reduce specialist count or increase task load"

#### 11.4 Budget Alerts and Governance

**Alert Thresholds**:

**Warning Levels**:
- **Level 1 (Green)**: 0-70% budget consumed - normal operation
- **Level 2 (Yellow)**: 70-85% budget consumed - start monitoring closely
- **Level 3 (Orange)**: 85-95% budget consumed - begin conservation measures
- **Level 4 (Red)**: 95-100% budget consumed - critical, only essential work
- **Level 5 (Black)**: 100%+ budget consumed - all work paused

**Automated Responses by Level**:

**Level 2 (Yellow)**:
- Send notification to user dashboard
- Log warning in system logs
- Continue normal operation

**Level 3 (Orange)**:
- Send email/Slack alert if configured
- Display prominent warning in dashboard
- System suggests:
  - Downgrade models where possible
  - Defer low-priority tasks
  - Enable aggressive caching

**Level 4 (Red)**:
- Urgent notification to user
- System automatically:
  - Pauses all "Low" priority tasks
  - Defers new "Normal" priority tasks
  - Only "High" and "Critical" tasks proceed- Downgrades models automatically if auto-optimize enabled
- User must acknowledge alert

**Level 5 (Black)**:
- All work stops except critical path
- User must take action:
  - Increase budget allocation
  - Wait for budget reset (next day/week)
  - Manually approve which tasks can continue
- Dashboard shows clear "Budget Exhausted" message

**Budget Governance Controls**:

**User Approval Thresholds**:
- Configurable thresholds for actions requiring approval:
  - Task exceeds 10k tokens: Manager approval
  - Task exceeds 50k tokens: Architect approval
  - Task exceeds 100k tokens: Human approval
- Prevents runaway tasks from consuming budget

**Budget Rollover**:
- Option: Unused budget rolls over to next period (day/week/month)
- Incentivizes efficiency - savings accumulate
- Cap maximum rollover (e.g., 150% of base allocation)

**Emergency Budget Reserve**:
- 10-20% of budget held in reserve
- Only accessible for critical issues or escalations
- Prevents complete paralysis from budget exhaustion

---

### Section 12: Monitoring & Observability (Expanded)

#### 12.1 Real-Time Logging System

**Log Levels and Usage**:

**DEBUG**:
- Purpose: Detailed diagnostic information for development/troubleshooting
- Contains: Every tool call, every API request, context loading, cache hits/misses
- Volume: Very high (thousands of logs per task)
- Storage: Short retention (7 days)
- Usage: Disable in production, enable when debugging specific issues

**INFO**:
- Purpose: Normal operational messages
- Contains: Task assignments, task completions, PR creations, merges
- Volume: Moderate (hundreds of logs per day)
- Storage: Medium retention (30 days)
- Usage: Default log level for production

**WARN**:
- Purpose: Potentially problematic situations that don't stop operation
- Contains: Budget warnings, slow performance, retry attempts, deprecated features used
- Volume: Low (dozens per day)
- Storage: Long retention (90 days)
- Usage: Always enabled, review regularly

**ERROR**:
- Purpose: Errors that prevent task completion but don't crash system
- Contains: Task failures, escalations, API errors, validation failures
- Volume: Low (should be rare)
- Storage: Long retention (90 days)
- Usage: Always enabled, trigger alerts

**CRITICAL**:
- Purpose: System-level failures requiring immediate attention
- Contains: Database connection lost, GitHub API unreachable, all agents failing
- Volume: Very low (ideally zero)
- Storage: Permanent retention
- Usage: Always enabled, immediate notifications

**Log Structure**:

Each log entry contains:
- **Timestamp**: ISO8601 format with milliseconds
- **Level**: DEBUG/INFO/WARN/ERROR/CRITICAL
- **Agent ID**: Which agent generated this log
- **Task ID**: Which task being worked on (if applicable)
- **Message**: Human-readable description
- **Metadata**: Structured data (JSON) with additional context
- **Trace ID**: For correlating related logs across agents
- **User Session**: If user action triggered this

**Log Aggregation**:
- All agents log to centralized system (database or log aggregation service)
- Enables searching across all agents simultaneously
- Correlate logs by task ID or trace ID
- Full-text search capability

#### 12.2 Distributed Tracing

**Trace Concept**:
- Each user prompt generates a unique Trace ID
- As work flows through system, all operations tagged with this Trace ID
- Enables following complete execution path from prompt to merge

**Trace Spans**:

**Root Span**: User Prompt Received
- Duration: From prompt submission to final task completion
- Tags: User ID, prompt text, total tasks generated

**Child Span1**: Architect Analysis
- Duration: Intent analysis + task decomposition
- Tags: Tasks created, complexity scores, global rules extracted
- Parent: Root Span

**Child Span 2**: Manager Assignment (per manager)
- Duration: Task assignment algorithm execution
- Tags: Specialists selected, assignment scores, rationale
- Parent: Root Span

**Child Span 3**: Specialist Execution (per specialist)
- Duration: From task received to PR raised
- Tags: Files modified, tests run, errors encountered
- Parent: Child Span 2 (specific manager)

**Child Span 4**: Review Cycle
- Duration: From PR raised to merge
- Tags: Checks passed/failed, reviewer comments, conflicts
- Parent: Child Span 3 (specific specialist)

**Trace Visualization**:
- Dashboard shows trace as timeline
- Each span is a bar showing duration
- Hover for details
- Identify bottlenecks (longest spans)
- Identify failures (spans marked with error)

**Use Cases**:
- **Performance Analysis**: "Why did this task take so long?" - inspect trace, find slow span
- **Debugging**: "Why did this fail?" - follow trace to error point
- **Optimization**: "Where are we spending most time?" - aggregate traces, identify common slow operations

#### 12.3 Alerting and Notifications

**Alert Channels**:

**Dashboard Alerts** (always enabled):
- Banner at top of dashboard
- Color-coded by severity
- Dismissible but logged
- Click for full details

**Email Alerts** (optional):
- Configure SMTP settings
- Specify recipient list
- Configurable: which alert types trigger email
- Email includes summary + link to dashboard

**Slack/Discord Alerts** (optional):
- Webhook integration
- Post to configured channel
- Rich formatting with action buttons
- Thread replies for status updates

**Webhook Alerts** (advanced):
- POST to custom URL
- JSON payload with full alert details
- Enables integration with external monitoring systems

**Alert Types and Triggers**:

**Budget Alerts**:
- Trigger: Budget threshold reached (70%, 85%, 95%, 100%)
- Severity: WARN (70%), ERROR (95%), CRITICAL (100%)
- Channels: Dashboard + Email/Slack

**Task Failure Alerts**:
- Trigger: Task fails after all recovery attempts
- Severity: ERROR
- Channels: Dashboard
- Include: Task details, error summary, suggested actions

**System Health Alerts**:
- Trigger: Multiple agents failing, API unreachable, database issues
- Severity: CRITICAL
- Channels: All configured channels
- Requires user acknowledgment

**Performance Degradation Alerts**:
- Trigger: Average task duration increases >50% compared to baseline
- Severity: WARN
- Channels: Dashboard
- Suggests: "Investigate recent changes, check API latency"

**Security Alerts**:
- Trigger: Security scan finds vulnerability, suspicious activity detected
- Severity: ERROR
- Channels: Dashboard + Email
- Requires user review before proceeding

**Agent Stuck Alerts**:
- Trigger: Agent consuming tokens without progress for extended period
- Severity: WARN
- Channels: Dashboard
- Manager automatically intervenes

**Alert Suppression**:
- Prevent alert fatigue
- Same alert doesn't repeat within time window (e.g., don't alert about same budget threshold every minute)
- Group similar alerts (e.g., "5 agents experiencing API errors" instead of 5 separate alerts)

#### 12.4 Health Checks and Status Monitoring

**System Health Dashboard**:

**Component Status Indicators**:
- **Architect Agent**: Green (operational), Yellow (degraded), Red (down)
- **Manager Agents**: Status per manager
- **Specialist Agents**: Count of healthy/degraded/down specialists
- **GitHub API**: Connection status, rate limit remaining
- **Model APIs**: Per provider (OpenAI, Anthropic, Google)
- **Database**: Connection status, query performance
- **Context Store**: Storage space remaining, performance

**Health Check Probes**:

**Liveness Probes** (is system alive?):
- Every 30 seconds, check:
  - Can reach database?
  - Can agents respond to ping?
  - Is dashboard server running?
- If liveness fails: System is down, critical alert

**Readiness Probes** (is system ready to work?):
- Every 60 seconds, check:
  - Are API keys valid?
  - Is GitHub API accessible?
  - Do agents have budget remaining?
  - Are any agents blocked/stuck?
- If readiness fails: System up but can't accept new work, warn user

**Performance Metrics**:
- **API Latency**: Average response time from model providers (should be <5s)
- **Database Query Time**: Average (should be <100ms)
- **Context Load Time**: How long to load context window (should be <1s)
- **Git Operations Time**: Clone, commit, push durations

**Automatic Recovery**:

**Transient Failures**:
- Temporary API errors: Retry with exponential backoff
- Network blips: Retry after brief delay
- Rate limits: Queue requests, resume when limit resets

**Persistent Failures**:
- API key invalid: Alert user, pause system until fixed
- GitHub unreachable: Alert user, queue GitHub operations for later
- Database down: Critical alert, system cannot operate

**Degraded Mode**:
- If some components failing but system can still operate in limited capacity
- Example: One model provider down, automatically switch to fallback
- Dashboard shows "Degraded Mode" status with explanation

#### 12.5 Audit Trail and Compliance

**Audit Log**:

**Logged Events**:
- User actions: Config changes, manual task assignments, overrides
- Agent actions: Task assignments, code changes, PR merges
- System events: Budget allocations, model upgrades, error recoveries
- Security events: API key usage, permission grants, policy violations

**Audit Entry Structure**:
- **Event ID**: Unique identifier
- **Timestamp**: When event occurred
- **Actor**: Who/what performed action (user, agent ID, system)
- **Action Type**: What was done
- **Target**: What was affected (task, file, config)
- **Before State**: What it was before (for changes)
- **After State**: What it is now
- **Justification**: Why action was taken (if applicable)

**Immutable Audit Log**:
- Append-only, cannot be modified or deleted
- Cryptographic signatures to detect tampering
- Enables compliance with auditing requirements

**Audit Reports**:
- Generate reports for specific time periods
- Filter by actor, action type, target
- Export as CSV/JSON for external analysis
- Useful for:
  - "What changed in the last 24 hours?"
  - "Who modified this file?"
  - "Why was this task reassigned?"

**Compliance Features**:
- Data retention policies (configurable per log type)
- PII redaction (scrub sensitive data from logs)
- Export capabilities (for regulatory reporting)
- Access controls (who can view audit logs)

---

### Section 13: Security & Permissions (Expanded)

#### 13.1 API Key Management

**Secure Storage**:
- API keys never stored in config files directly
- Use environment variables: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.
- Config file references env var names, not actual keys
- Supports `.env` files for development, actual env vars for production

**Key Rotation**:
- Support multiple keys per provider with automatic rotation
- If one key hits rate limit, switch to next key in pool
- If key becomes invalid, mark as bad and notify user
- User can update keys without restarting system

**Key Validation**:
- On startup, validate all configured API keys
- Make test API call to each provider
- If invalid, mark provider as unavailable
- User receives immediate feedback about key issues

**Least Privilege**:
- Keys should have minimum necessary permissions
- Read-only keys where possible
- Separate keys for production vs development if supported

#### 13.2 Code Execution Sandboxing

**Sandbox Environment**:

**Isolation**:
- Code execution happens in isolated container/VM
- No access to host system
- Restricted filesystem (only temp directory)
- No network access (except explicitly allowed APIs)

**Resource Limits**:
- CPU: Max time limit (30 seconds default)
- Memory: Max allocation (512 MB default)
- Disk: Max temp storage (100 MB)
- Exceeding limits terminates execution

**Blocked Operations**:
- Cannot spawn child processes
- Cannot make network requests (prevents data exfiltration)
- Cannot access environment variables (prevents key exposure)
- Cannot modify files outside temp directory

**Allowed Operations**:
- Run tests
- Execute build scripts
- Run linters/formatters
- Analyze code statically

**Sandbox Escapes**:
- Monitor for attempted sandbox escapes
- Log suspicious activities
- Terminate and flag if escape attempt detected

#### 13.3 Secret Detection and Prevention

**Pre-Commit Scanning**:

**Before Allowing Commit**:
- Scan all modified files for potential secrets
- Patterns detected:
  - API keys (long alphanumeric strings)
  - Private keys (BEGIN PRIVATE KEY)
  - Passwords (password=, pwd=)
  - Tokens (token=, auth=)
  - Database connection strings
  - AWS access keys
  - JWT secrets

**Detection Tools**:
- Integrated tools: GitGuardian, TruffleHog, detect-secrets
- Custom regex patterns for project-specific secrets

**On Secret Detected**:
- Block commit immediately
- Alert specialist and manager
- Mark file for review
- Provide guidance: "Move secret to .env file, use environment variable"
- Only allow commit after secret removed

**False Positive Handling**:
- Specialists can mark false positives
- Requires justification
- Manager reviews and approves exception
- Adds to allow-list for future

**GitHub Secret Scanning**:
- Enable GitHub's built-in secret scanning
- If secret accidentally pushed, GitHub alerts immediately
- System pauses work until secret rotated

#### 13.4 Access Control and Permissions

**File-Level Permissions**:

**Sensitive File Patterns**:
- `.env`, `.env.*` files: Architects and managers can read, specialists cannot
- `config/secrets.*`: Read-only for all agents
- `src/auth/**`: Require security specialist review before changes
- `database/migrations/**`: Require database specialist + manager approval
- `.github/workflows/**`: Require DevOps specialist + architect approval

**Permission Matrix**:
- Define which agent types can read/write which file patterns
- Enforced by tool layer (filesystem_write checks permissions)
- Violations logged and blocked

**Branch Protection**:
- `main` branch: Protected, only architect can merge
- `develop` branch: Only managers can merge
- `agent/*` branches: Specialists can push, managers can merge
- No force-pushes allowed except by architects

**Tool Permission Gating**:
- Dangerous tools (database_client, docker_commands) restricted to Tier 3models
- Specialists must justify need for elevated permissions
- Manager grants temporary access with timeout

**Principle of Least Privilege**:
- Agents only get permissions needed for their role
- Temporary permission escalation possible with justification
- All escalations logged in audit trail

#### 13.5 Input Validation and Sanitization

**User Input Validation**:

**Prompt Injection Prevention**:
- User prompts analyzed for potential injection attacks
- Patterns flagged: "Ignore previous instructions", "You are now...", "Print your system prompt"
- Suspicious prompts require user confirmation: "This prompt looks unusual, proceed anyway?"

**Parameter Validation**:
- All tool parameters validated against schema
- Type checking: Ensure integers are integers, strings are strings
- Range checking: Ensure values within allowed ranges
- Path validation: Ensure file paths don't escape workspace (no `../../` exploits)

**Command Injection Prevention**:
- Never construct shell commands via string concatenation
- Use parameterized execution
- Sanitize all inputs before passing to shell
- Block dangerous characters:`;`, `|`, `&`, `$`, backticks

**SQL Injection Prevention**:
- Only use parameterized queries
- Never concatenate user input into SQL strings
- Use ORM where possible
- Validate all inputs against expected format

**XSS Prevention**:
- Dashboard escapes all user-generated content
- Agent messages sanitized before display
- No inline JavaScript in agent-generated content

---

### Section 14: Extensibility & Plugin System (Expanded)

#### 14.1 Custom Agent Types

**Plugin Architecture**:

**Agent Plugin Structure**:
Each custom agent type is defined in a plugin directory:

```
plugins/
  custom-mobile-specialist/
    plugin.yaml# Metadata and configuration
    system_prompt.txt    # Agent's system prompt
    tools.yaml           # Custom tools this agent can use
    file_patterns.yaml   # Which files this agent works with
    examples/            # Example tasks for training
```

**plugin.yaml Example**:
```yaml
name: "Mobile App Specialist"
type: "specialist"
version: "1.0.0"
specialty: "mobile-react-native"
description: "Specialist in React Native mobile app development"
recommended_model_tier: 2
compatible_managers: ["frontend", "mobile"]

training_focus:
  - "React Native component patterns"
  - "Mobile-specific considerations (gestures, navigation)"
  - "iOS and Android platform differences"
  - "Mobile performance optimization"
  - "Push notifications"

default_tools:
  - filesystem_read_write
  - git_operations
  - npm_commands
  - mobile_simulator
  - test_runner
```

**Loading Custom Agents**:
- User places plugin in `plugins/` directory
- System scans for plugins on startup
- Validates plugin structure and dependencies
- Loads agent type into available pool
- User can then configure instances of this agent type in UI

**Plugin Marketplace** (future feature):
- Community-contributed agent types
- Browse, install directly from dashboard
- Ratings and reviews
- Automatic updates

#### 14.2 Custom Tools

**Tool Plugin Structure**:

```
plugins/tools/
  custom-security-scanner/
    tool.yaml           # Tool metadata
    executor.py# Tool implementation
    requirements.txt    # Dependencies
    README.md           # Documentation
```

**tool.yaml Example**:
```yaml
name: "custom_security_scan"
description: "Run company-specific security checks"
tier: 3
parameters:
  - name: file_path
    type: string
    required: true
  - name: severity_threshold
    type: enum
    values: ["low", "medium", "high", "critical"]
    default: "medium"
returns:
  type: object
  properties:
    vulnerabilities_found: integer
    details: array
```

**Tool Execution**:
- System imports tool module dynamically
- Tool must implement standard interface: `execute(parameters) -> result`
- Sandboxed execution (can't access system outside tool scope)
- Result must match defined schema

**Tool Registration**:
- User installs tool plugin
- Tool becomes available in tool catalog
- User grants tool access to specific agents via config
- Agents can now call tool like built-in tools

#### 14.3 Custom Workflows

**Workflow Customization**:

**Hook Points**:
System provides hooks at key points where users can inject custom logic:

- **pre_task_assignment**: Before manager assigns task to specialist
- **post_task_completion**: After specialist completes task
- **pre_pr_merge**: Before architect merges PR
- **post_merge**: After successful merge
- **on_error**: When any error occurs
- **on_budget_threshold**: When budget threshold reached

**Hook Implementation**:

**hooks/custom_notification.py**:
```python
# Example: Send custom notification when task completes

def post_task_completion(task, specialist, result):
    """
    Called after specialist completes task
    Args:
        task: Task object with details
        specialist: Specialist agent that completed it
        result: Completion result
    Returns:
        None (or modified task/result to alter behavior)
    """
    # Custom logic: Send to company Slack
    send_slack_message(
        channel="#dev-updates",
        message=f"Task {task.title} completed by {specialist.id}"
    )
```

**Hook Registration**:
User registers hooks in config:
```yaml
hooks:
  post_task_completion:
    - custom_notification.post_task_completion
  pre_pr_merge:
    - require_jira_ticket.validate- notify_stakeholders.send_email
```

**Use Cases**:
- Custom notifications to external systems
- Additional validation before merge
- Integrate with JIRA/Linear for ticket updates
- Custom metrics collection
- Company-specific compliance checks

#### 14.4 Custom Model Providers

**Adding New Model Provider**:

**Provider Plugin Structure**:
```
plugins/providers/
  openrouter/
    provider.yaml       # Provider metadata
    client.py           # API client implementation
    pricing.yaml        # Cost per token
    models.yaml         # Available models
```

**Provider Implementation**:
Must implement standard interface:
- `initialize(api_key)`: Set up client
- `generate(prompt, params)`: Call model
- `format_tools(tools)`: Convert tools to provider format
- `parse_response(response)`: Parse provider response to standard format

**Once Implemented**:
- Provider shows up in model provider dropdown in UI
- Users can configure agents to use this provider
- System handles API calls transparently

**Example Use Cases**:
- Company uses self-hosted model server
- Want to use OpenRouter for access to many models
- Custom fine-tuned models on specific infrastructure

#### 14.5 Integration APIs

**Harness REST API**:

**Endpoints**:

**POST /api/tasks/create**:
- Programmatically create tasks
- Allows external systems to send work to harness
- Returns task ID for tracking

**GET /api/tasks/:id/status**:
- Check task status
- Returns: pending, in_progress, completed, failed
- Includes progress percentage and ETA

**GET /api/agents/status**:
- Get status of all agents
- Returns list with current activity and metrics

**POST /api/config/update**:
- Update configuration programmatically
- Add/remove agents, change model configurations
- Requires authentication

**GET /api/metrics**:
- Export metrics as JSON
- For feeding into external monitoring systems

**Webhook Support**:

**Outbound Webhooks**:
System can POST events to configured URLs:
- Task completed
- Task failed
- PR merged
- Budget threshold reached
- Error escalated

**Webhook Payload**:
Standard JSON format with event type, timestamp, and event-specific data

**Retry Logic**:
- If webhook delivery fails, retry with exponential backoff
- After 5 failures, mark webhook as problematic
- User notified of webhook failures

**Use Case**:
- Integrate harness into existing CI/CD pipeline
- Update project management tools when tasks complete
- Feed metrics into company dashboards
- Trigger downstream workflows

---

### Section 15: Testing Strategy & Deployment (Expanded)

#### 15.1 Testing the Harness Itself

**Unit Tests**:

**Components to Test**:
- **Context Management**: Window compression, neighbor retrieval, rule extraction
- **Task Assignment**: Multi-factor scoring algorithm produces expected results
- **Tool Execution**: Each tool executes correctly with valid inputs, errors appropriately on invalid inputs
- **Git Operations**: Branch creation, commits, PR creation work as expected
- **Model API Abstraction**: Requests formatted correctly for each provider, responses parsed correctly

**Testing Strategy**:
- Mock model API calls (don't spend tokens on testing)
- Mock GitHub API calls (don't create real issues/PRs)
- Test with sample repository (small test repo in test fixtures)
- Isolated tests (no dependencies between tests)
- Fast execution (<5 seconds per test)

**Integration Tests**:

**End-to-End Scenarios**:
- **Simple Task Flow**: User prompt → Architect creates task → Manager assigns → Specialist implements → PR merged
- **Error Recovery Flow**: Specialist encounters error → Self-recovers → Continues task
- **Escalation Flow**: Specialist stuck → Manager intervenes → Task reassigned → Completion
- **Collaboration Flow**: Complex task → Multiple specialists assigned → Coordinate → Single PR

**Test Environment**:
- Use real model APIs but with low-tier models (minimize cost)
- Use test GitHub repository (not production code)
- Use test database (isolated from production data)
- Automated tests run in CI/CD pipeline

**Performance Tests**:

**Load Testing**:
- Simulate 50+ concurrent tasks
- Ensure system remains responsive
- Measure: Task throughput, API latency, database query time
- Identify bottlenecks

**Token Efficiency Tests**:
- Run standardized task set
- Measure total tokens consumed
- Track over time - efficiency should improve with optimizations
- Benchmark against target (e.g., <10k tokens per simple task)

#### 15.2 Harness Validation Before Deployment

**Pre-Deployment Checklist**:

**Configuration Validation**:
- [ ] All API keys valid and tested
- [ ] GitHub token has required permissions (create issues, PRs, merge)
- [ ] Database connection successful
- [ ] All agents have valid model configurations
- [ ] Tool permissions correctly assigned
- [ ] Budget allocations sum correctly

**Health Checks**:
- [ ] All agents respond to ping
- [ ] Model APIs reachable and responding
- [ ] GitHub API reachable
- [ ] Dashboard accessible
- [ ] Logging system operational

**Smoke Tests**:
- [ ] Create simple test task manually
- [ ] Verify architect can decompose task
- [ ] Verify manager can assign task
- [ ] Verify specialist can execute task
- [ ] Verify PR can be created and merged
- [ ] Verify metrics are logged correctly

**Security Checks**:
- [ ] Secret scanning enabled
- [ ] Code execution sandboxed
- [ ] Branch protection rules configured
- [ ] Audit logging enabled
- [ ] API keys not exposed in logs

#### 15.3 Deployment Options

**Option 1: Local Development**:
- Run harness on developer's machine
- SQLite database for context store
- Suitable for:
  - Testing harness itself
  - Small personal projects
  - Hackathon development

**Setup**:
1. Clone harness repository
2. Install dependencies: `pip install -r requirements.txt` or `npm install`
3. Configure `.env` with API keys
4. Run: `python main.py` or `npm start`
5. Access dashboard at `http://localhost:3000`

**Option 2: Single Server Deployment**:
- Deploy to single VPS or cloud VM
- PostgreSQL database
- Suitable for:
  - Small teams (2-5 developers)
  - Medium-sized projects

**Setup**:
1. Provision server (e.g., AWS EC2,DigitalOcean Droplet)
2. Install dependencies
3. Configure environment variables
4. Set up PostgreSQL database
5. Run harness as systemd service (auto-restart on failure)
6. Configure reverse proxy (Nginx) for dashboard
7. Enable HTTPS with Let's Encrypt

**Option 3: Docker Deployment**:
- Containerized deployment
- Docker Compose for multi-container setup
- Suitable for:
  - Consistent environments
  - Easy scaling
  - CI/CD integration

**docker-compose.yml Structure**:
```yaml
services:
  harness:
    # Main harness applicationdashboard:
    # Web dashboard UI
  database:
    # PostgreSQL for context store
  redis:
    # For caching and message queue
```

**Setup**:
1. Install Docker and Docker Compose
2. Configure `.env` file
3. Run: `docker-compose up -d`
4. Access dashboard at configured port

**Option 4: Kubernetes Deployment** (advanced):
- Scalable, production-grade deployment
- Suitable for:
  - Large teams
  - High task volume
  - Mission-critical usage

**Architecture**:
- Harness core: Multiple replicas for redundancy
- Dashboard: Load balanced
- Database: Managed service (AWS RDS, Google Cloud SQL)
- Horizontal pod autoscaling based on task queue length

#### 15.4 Hackathon-Specific Deployment

**For Hackathon Submission**:

**Deliverables**:
1. **GitHub Repository**: Complete source code
2. **README.md**: Clear setup instructions
3. **Demo Video**: 3-5 minute walkthrough
4. **Live Demo**: Deployed instance judges can test
5. **Documentation**: Architecture overview, design decisions
6. **Metrics Report**: Performance data from test runs

**Demo Repository Setup**:
- Create sample project with intentional issues/features to implement
- Pre-configure harness for this demo project
- Document expected behavior
- Include comparison: "Without harness" vs "With harness"

**Live Demo Instance**:
- Deploy to cloud provider with public URL
- Judges can access dashboard (read-only or interactive)
- Pre-load with completed tasks to show history
- Have system actively working on tasks during judging

**Evaluation Criteria Alignment**:

**Correctness**:
- Demonstrate: Show PRs that pass all tests, merge successfully
- Evidence: Test coverage reports, successful merges

**Orchestration**:
- Demonstrate: Multi-agent coordination on complex task
- Evidence: Dashboard showing task flow through agents, decision logs

**Recovery**:
- Demonstrate: Agent encountering error and recovering
- Evidence: Logs showing error, recovery attempts, successful resolution

**Efficiency**:
- Demonstrate: Token usage per task, cost breakdown
- Evidence: Metrics dashboard, comparison to baseline

**Autonomy**:
- Demonstrate: System handling multiple tasks without human intervention
- Evidence: Time-lapse video of system working, minimal human actions needed

#### 15.5 Post-Hackathon Roadmap

**Phase 1: Core Stability** (Weeks 1-4after hackathon):
- Fix critical bugs found during judging
- Improve error handling robustness
- Add comprehensive logging
- Performance optimization
- Security hardening

**Phase 2: User Experience** (Weeks 5-8):
- Polish dashboard UI
- Add onboarding wizard
- Improve documentation
- Add video tutorials
- Community feedback integration

**Phase 3: Advanced Features** (Weeks 9-16):
- Plugin marketplace
- More specialist types
- Advanced coordination patterns
- Machine learning for task assignment optimization
- Cost prediction models

**Phase 4: Enterprise Features** (Weeks 17-24):
- SSO integration
- Role-based access control
- Compliance features (SOC 2, GDPR)
- Multi-tenant support
- Enterprise SLA

**Community Building**:
- Open-source release
- Discord/Slack community
- Monthly releases
- Contribution guidelines
- Example plugins and agents

---

### Summary & Next Steps

This comprehensive design covers every aspect of the autonomous coding harness for the LCC x DevClub Hackathon. The system features:

✅ **3-tier hierarchical architecture** (Architect → Managers → Specialists)
✅ **10+ specialist types** with detailed role definitions
✅ **23+ tools** with tiered access control
✅ **Intelligent task assignment** using multi-factor scoring
✅ **Robust error recovery** with 3-level escalation
✅ **Branch-per-agent git workflow** with conflict resolution
✅ **Multi-stage verification** pipeline (5 stages)
✅ **Interactive configuration UI** with drag-and-drop
✅ **Real-time monitoring** dashboard
✅ **Resource optimization** with dynamic budget allocation
✅ **Comprehensive security** (sandboxing, secret detection, audit logs)
✅ **Extensibility** via plugins and hooks
