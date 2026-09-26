# GitHub Issues for AI Coding Harness Implementation

---

## Issue #1: Foundation & Infrastructure Setup
**Priority**: CRITICAL - Must be completed first  
**Estimated Time**: 2-3 days  
**Assignee**: Both team members (pair programming recommended)  
**Labels**: `foundation`, `infrastructure`, `setup`, `critical`

### Description

Set up the foundational infrastructure that both team members will build upon. This establishes the project structure, core interfaces, and shared services that enable parallel development without conflicts.

### Tasks

#### 1.1 Project Setup
- [ ] Initialize Python project with poetry/pip requirements
- [ ] Set up project structure:
  ```
  ai-coding-harness/
  ├── src/
  │   ├── agents/          # Agent implementations
  │   ├── orchestration/   # Orchestration layer
  │   ├── infrastructure/  # Shared services
  │   ├── tools/          # Tool implementations
  │   ├── verification/   # Verification pipeline
  │   └── ui/             # User interface
  ├── tests/              # Test suite
  ├── config/             # Configuration files
  ├── docs/               # Documentation
  └── scripts/            # Utility scripts
  ```
- [ ] Configure linting (black, flake8, mypy)
- [ ] Set up pre-commit hooks
- [ ] Initialize Git repository with .gitignore

#### 1.2 Core Interfaces & Abstract Classes
- [ ] Define `BaseAgent` abstract class:
  - Properties: `agent_id`, `model_config`, `tools`, `context_window`
  - Methods: `execute_task()`, `handle_error()`, `report_status()`
- [ ] Define `BaseManager` abstract class (extends BaseAgent)
  - Additional methods: `assign_task()`, `monitor_progress()`, `handle_escalation()`
- [ ] Define `Tool` interface:
  - Properties: `name`, `tier`, `description`, `parameters`
  - Methods: `execute()`, `validate_input()`, `check_permissions()`
- [ ] Define message protocol dataclasses:
  - `CommandMessage`, `StatusUpdate`, `ErrorEscalation`, `CoordinationMessage`

#### 1.3 Configuration System
- [ ] Create configuration schema (YAML/JSON):
  - Model configurations (providers, API keys, parameters)
  - Agent definitions (architect, managers, specialists)
  - Tool permissions matrix
  - Budget allocation settings
- [ ] Implement configuration loader with validation
- [ ] Add environment variable support for secrets
- [ ] Create example configuration templates

#### 1.4 Context Store Infrastructure
- [ ] Choose and set up database (PostgreSQL recommended)
- [ ] Design database schema:
  - `global_context` table (repo metadata, tasks, agents, rules)
  - `agent_contexts` table (per-agent conversation windows)
  - `context_windows` table (compressed history)
  - `token_usage` table (tracking and logging)
- [ ] Implement `ContextStore` class:
  - Methods: `save_global()`, `load_global()`, `save_agent_context()`, `load_agent_context()`
  - Implement time-windowed compression
- [ ] Add context retrieval with neighbor window support

#### 1.5 Model API Abstraction Layer
- [ ] Create `ModelProvider` interface
- [ ] Implement providers:
  - `OpenAIProvider` (GPT-4, GPT-4-mini, GPT-3.5)
  - `AnthropicProvider` (Claude Opus, Sonnet, Haiku)
  - `GoogleProvider` (Gemini Pro, Flash)
- [ ] Implement unified `generate_response()` method
- [ ] Add tool calling format translation per provider
- [ ] Implement retry logic with exponential backoff
- [ ] Add rate limit handling

#### 1.6 GitHub Integration
- [ ] Set up GitHub API client (PyGithub or gh CLI wrapper)
- [ ] Implement `GitHubService` class:
  - `create_issue()`, `create_pull_request()`, `merge_pr()`
  - `add_comment()`, `request_changes()`, `list_issues()`
- [ ] Add repository cloning and branch management
- [ ] Implement PR status checking

#### 1.7 Logging & Monitoring Infrastructure
- [ ] Set up structured logging (loguru or structlog)
- [ ] Create log levels: DEBUG, INFO, WARN, ERROR, CRITICAL
- [ ] Implement log aggregation to database
- [ ] Add correlation IDs for tracing requests across agents

#### 1.8 Testing Framework
- [ ] Set up pytest with fixtures
- [ ] Create test utilities:
  - Mock model API responses
  - Mock GitHub API responses
  - Test database setup/teardown
- [ ] Write integration test examples

### Acceptance Criteria

- [ ] All core interfaces defined and documented
- [ ] Configuration system loads and validates correctly
- [ ] Context store can save/load data successfully
- [ ] Model API abstraction works for at least one provider (OpenAI)
- [ ] GitHub integration can create issues (tested)
- [ ] Project structure allows parallel development without conflicts
- [ ] Tests pass with >80% coverage on foundation code
- [ ] Documentation exists for all interfaces and configuration

### Technical Notes

**Database Schema Example**:
```sql
CREATE TABLE global_context (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE agent_contexts (
    agent_id VARCHAR(100),
    window_type VARCHAR(20), -- 'recent', 'midterm', 'historical'
    content JSONB,
    created_at TIMESTAMP,
    PRIMARY KEY (agent_id, window_type)
);
```

**Configuration Example**:
```yaml
architect:
  model:
    provider: openai
    id: gpt-4
    api_key_env: OPENAI_API_KEY
    temperature: 0.2
    max_tokens: 8000
```

### Dependencies

None - this is the foundation.

### Definition of Done

- All tasks checked off
- Tests written and passing
- Code reviewed and merged to main
- Documentation updated
- Both team members can start parallel work on Issues #2 and #3

---

## Issue #2: Core Agent System & Orchestration (Team Member 1)
**Priority**: HIGH  
**Estimated Time**: 5-7 days  
**Assignee**: Team Member 1  
**Labels**: `agents`, `orchestration`, `backend`, `core`  
**Depends On**: Issue #1

### Description

Implement the three-tier agent hierarchy (Architect → Managers → Specialists) with intelligent task routing, error recovery, and orchestration logic. This is the "brain" of the system.

### Tasks

#### 2.1 Architect Agent Implementation
- [ ] Implement `ArchitectAgent` class (extends `BaseAgent`):
  - `analyze_repository()` - Clone and analyze repo structure
  - `extract_global_rules()` - Parse user intent for coding standards
  - `decompose_task()` - Break user prompt into GitHub issues
  - `create_context_windows()` - Generate context for each task
  - `assign_to_managers()` - Route task clusters to manager teams
  - `review_pr()` - Final validation before merge
  - `merge_pr()` - Execute merge to main branch
- [ ] Implement repository analysis logic:
  - Parse file tree structure
  - Identify tech stack (package.json, requirements.txt, etc.)
  - Detect test framework
  - Extract existing patterns
- [ ] Implement task decomposition algorithm:
  - Use LLM to break down user prompt
  - Create dependency graph between tasks
  - Generate clear acceptance criteria per task
- [ ] Add global rule extraction with NLP patterns

#### 2.2 Manager Agent Implementation
- [ ] Implement `ManagerAgent` class (extends `BaseManager`):
  - `receive_tasks()` - Accept task cluster from architect
  - `assign_task()` - Use multi-factor algorithm to route
  - `monitor_specialists()` - Track progress and token usage
  - `handle_escalation()` - Receive and process errors
  - `coordinate_merge()` - Detect and resolve conflicts
- [ ] Implement multi-factor assignment algorithm:
  - Calculate specialty match score (40% weight)
  - Calculate availability score (20% weight)
  - Calculate load balance score (20% weight)
  - Calculate capability score (20% weight)
  - Select highest scorer or top 2-3 for complex tasks
- [ ] Add progress monitoring with proactive intervention:
  - Poll specialist status every 5 minutes
  - Calculate "stuck score" from tokens/progress ratio
  - Intervene early if excessive consumption detected
- [ ] Implement error handling logic:
  - Classify error type (skill gap, tool limitation, etc.)
  - Select recovery strategy (reassign, add agents, reframe)
  - Escalate to architect after 2 failed attempts
- [ ] Add conflict detection for merges:
  - Compare file changes across open PRs
  - Detect overlapping modifications
  - Coordinate resolution assignments

#### 2.3 Specialist Agent Base Implementation
- [ ] Implement `SpecialistAgent` class (extends `BaseAgent`):
  - `execute_task()` - Main workflow orchestrator
  - `create_branch()` - Git branch creation
  - `implement_solution()` - Use LLM to write code
  - `self_verify()` - Run tests and checks
  - `self_recover()` - Handle errors autonomously (3 attempts)
  - `create_pr()` - Raise pull request
  - `respond_to_review()` - Handle review feedback
- [ ] Implement 11-step workflow:
  1. Receive task and load context
  2. Create isolated branch
  3. Implement code and tests
  4. Run self-verification
  5. Attempt error recovery if needed
  6. Commit with conventional message
  7. Push and raise PR
  8. Wait for CI/CD
  9. Respond to reviewer if assigned
  10. Wait for manager approval
  11. Wait for architect merge
- [ ] Add self-recovery mechanisms:
  - Attempt 1: Parse error, fix syntax
  - Attempt 2: Debug logic, try alternative fix
  - Attempt 3: Completely different approach
  - Escalate to manager after 3 failures

#### 2.4 Specialist Type Implementations
Implement specialized agents with domain-specific prompts:

- [ ] `BackendAPISpecialist`:
  - System prompt focused on REST API, Express/FastAPI patterns
  - File patterns: `src/routes/`, `src/controllers/`
  - Tools: filesystem_write, git_operations, test_runner, api_testing
  
- [ ] `DatabaseSpecialist`:
  - System prompt focused on SQL, ORM, migrations
  - File patterns: `src/models/`, `migrations/`
  - Tools: filesystem_write, database_client, migration_tools
  
- [ ] `ReactSpecialist`:
  - System prompt focused on React, hooks, component patterns
  - File patterns: `src/components/`, `src/pages/`
  - Tools: filesystem_write, npm_commands, browser_testing
  
- [ ] `TestingSpecialist`:
  - System prompt focused on test writing, coverage analysis
  - File patterns: `tests/`, `__tests__/`
  - Tools: test_runner, coverage_analyzer, e2e_browser
  
- [ ] `DevOpsSpecialist`:
  - System prompt focused on CI/CD, Docker, deployment
  - File patterns: `.github/workflows/`, `Dockerfile`
  - Tools: docker_commands, terraform_commands

#### 2.5 Task Assignment & Routing
- [ ] Implement task queue per manager
- [ ] Add priority-based task ordering
- [ ] Implement concurrent task limits per specialist
- [ ] Add task dependency resolution
- [ ] Implement collaboration mode (2-3 agents on complex tasks)

#### 2.6 Error Recovery & Escalation
- [ ] Implement 4-level escalation hierarchy:
  - Level 1: Specialist self-recovery (max 3 attempts)
  - Level 2: Manager intervention (analysis and reassignment)
  - Level 3: Architect escalation (strategic review)
  - Level 4: Human notification (dashboard alert)
- [ ] Add escalation decision logic at each level
- [ ] Implement timeout-based escalation triggers
- [ ] Add escalation logging and tracking

#### 2.7 Context Management
- [ ] Implement context window loading per agent
- [ ] Add time-windowed compression:
  - Window 1: Last 20 messages uncompressed
  - Window 2: Compressed summaries (every 10 messages)
  - Window 3: High-level milestones (every 20 summaries)
- [ ] Implement neighbor window retrieval:
  - Find related tasks by file overlap
  - Share compressed contexts between agents
- [ ] Add global rule injection into agent prompts

#### 2.8 Resource Management
- [ ] Implement token tracking per agent
- [ ] Add budget allocation system (choose one strategy):
  - Fixed per-agent budgets
  - Dynamic reallocation based on efficiency
  - Priority-based allocation
  - Adaptive pool
- [ ] Implement budget monitoring and alerts
- [ ] Add usage logging to database

#### 2.9 Communication & Messaging
- [ ] Implement message passing between agents:
  - Command messages (top-down)
  - Status updates (bottom-up)
  - Error escalations (bottom-up)
  - Coordination messages (peer-to-peer via manager)
- [ ] Add message queue or pub/sub system
- [ ] Implement message logging and tracing

### Acceptance Criteria

- [ ] Architect can analyze a repository and decompose tasks
- [ ] Managers can assign tasks using multi-factor algorithm
- [ ] Specialists can complete full workflow from task to PR
- [ ] Error recovery works through all 4 levels
- [ ] Context compression reduces memory by >60%
- [ ] Budget tracking logs all token consumption
- [ ] At least 3 specialist types fully implemented
- [ ] End-to-end test: User prompt → Task decomposition → Specialist execution → PR creation
- [ ] Tests pass with >75% coverage
- [ ] No conflicts with Team Member 2's work (infrastructure, verification, UI)

### Implementation Guidelines

**Agent Communication Example**:
```python
class ManagerAgent(BaseManager):
    def assign_task(self, task: Task, specialists: List[SpecialistAgent]):
        scores = []
        for specialist in specialists:
            specialty_score = self._calculate_specialty_match(task, specialist)
            availability_score = self._calculate_availability(specialist)
            load_score = self._calculate_load_balance(specialist)
            capability_score = self._calculate_capability(task, specialist)
            
            total = (
                specialty_score * 0.4 +
                availability_score * 0.2 +
                load_score * 0.2 +
                capability_score * 0.2
            )
            scores.append((specialist, total))
        
        if task.complexity > 7:
            # Assign top 2-3 for complex tasks
            return [s for s, _ in sorted(scores, reverse=True)[:3]]
        else:
            return [max(scores, key=lambda x: x[1])[0]]
```

**Self-Recovery Example**:
```python
def self_recover(self, error: Exception, attempt: int) -> bool:
    if attempt == 1:
        # Parse error, fix syntax
        return self._fix_syntax_error(error)
    elif attempt == 2:
        # Debug logic, alternative fix
        return self._debug_and_fix(error)
    elif attempt == 3:
        # Try completely different approach
        return self._alternative_approach()
    else:
        # Escalate to manager
        self.escalate_to_manager(error)
        return False
```

### Testing Requirements

- Unit tests for each agent class
- Integration tests for agent communication
- E2E test with mock LLM responses
- Error recovery scenario tests
- Budget tracking accuracy tests

### Dependencies

- Issue #1 (Foundation) must be complete
- Model API abstraction must be working
- Context store must be functional
- GitHub integration must be available

### Definition of Done

- All agent types implemented and functional
- Task routing works correctly
- Error recovery handles all scenarios
- Tests pass and coverage >75%
- Code reviewed and documented
- Can run end-to-end from prompt to PR
- No merge conflicts with Issue #3 work

---

## Issue #3: Verification, Security & User Interface (Team Member 2)
**Priority**: HIGH  
**Estimated Time**: 5-7 days  
**Assignee**: Team Member 2  
**Labels**: `verification`, `security`, `ui`, `frontend`  
**Depends On**: Issue #1

### Description

Implement the verification pipeline, security controls, tool ecosystem, and user interface. This ensures code quality, system security, and provides user interaction capabilities.

### Tasks

#### 3.1 Tool Ecosystem Implementation

**Tier 1 Tools** (5 tools - basic operations):
- [ ] `filesystem_read`: Read file contents with line ranges
- [ ] `filesystem_list`: List directory contents
- [ ] `git_status`: Check git working directory status
- [ ] `git_log`: View commit history
- [ ] `logging`: Write structured logs

**Tier 2 Tools** (7 tools - development operations):
- [ ] `filesystem_write`: Modify files with backup creation
- [ ] `git_operations`: Branch, commit, push operations
- [ ] `grep_search`: Pattern search in codebase
- [ ] `npm_commands`: Package manager operations (npm, pip, cargo)
- [ ] `test_runner`: Execute test suites (Jest, Pytest, etc.)
- [ ] `linting`: Run linters (ESLint, Pylint, etc.)
- [ ] `formatting`: Code formatting (Prettier, Black, etc.)

**Tier 3 Tools** (8 tools - advanced operations):
- [ ] `database_client`: Execute database queries with safety checks
- [ ] `api_testing`: Make HTTP requests for testing
- [ ] `code_execution`: Execute code in sandboxed environment
- [ ] `migration_tools`: Run database migrations
- [ ] `docker_commands`: Container operations
- [ ] `security_scanners`: Run Snyk, Bandit, Semgrep
- [ ] `performance_profiling`: Performance analysis tools
- [ ] `github_api`: Already in foundation, enhance for tool use

**Tool Infrastructure**:
- [ ] Implement `ToolRegistry` class to manage all tools
- [ ] Add permission checking based on agent model tier
- [ ] Implement tool execution with timeout and error handling
- [ ] Add tool usage logging
- [ ] Create sandboxed execution environment for `code_execution` tool

#### 3.2 Verification Pipeline (5 Stages)

**Stage 1: Agent Self-Check**:
- [ ] Implement `SelfCheckService`:
  - Run syntax validation
  - Execute tests locally
  - Run linter
  - Run formatter
  - Check acceptance criteria
- [ ] Add pre-PR validation gate

**Stage 2: Automated CI/CD**:
- [ ] Create GitHub Actions workflow (`.github/workflows/test.yml`):
  - Build verification
  - Full test suite
  - Code coverage check (>80% required)
  - Security scan (Snyk or Bandit)
  - License check
- [ ] Implement CI/CD result checker
- [ ] Add blocking logic for failed checks

**Stage 3: Code Review Agent** (Optional):
- [ ] Implement `CodeReviewerAgent`:
  - Detect code smells (long functions, deep nesting, duplication)
  - Check pattern consistency with repository
  - Verify documentation completeness
  - Assess test quality
  - Flag performance implications
- [ ] Output low-priority improvement issues (non-blocking)

**Stage 4: Manager Review**:
- [ ] Already in Issue #2 (Manager agent)
- [ ] Interface for verification pipeline to query manager approval

**Stage 5: Architect Review**:
- [ ] Already in Issue #2 (Architect agent)
- [ ] Interface for verification pipeline to query architect approval

**Pipeline Orchestration**:
- [ ] Implement `VerificationPipeline` class:
  - Coordinate all 5 stages
  - Handle stage failures and retries
  - Log verification results
  - Report to relevant agents

#### 3.3 Security Implementation

**Input Security**:
- [ ] Implement `PromptInjectionDetector`:
  - Pattern matching for injection attempts
  - Flag suspicious prompts
  - Require user confirmation for flagged inputs
- [ ] Add parameter validation in all tools:
  - Type checking
  - Range validation
  - Path sanitization (no ../ traversal)
- [ ] Implement command injection prevention:
  - Use parameterized execution
  - Block shell metacharacters
  - Whitelist allowed commands

**Execution Security**:
- [ ] Implement sandboxed code execution:
  - Use Docker containers for isolation
  - No network access
  - CPU time limit: 30 seconds
  - Memory limit: 512 MB
  - Temporary filesystem only
- [ ] Add tool permission gating:
  - Check model tier vs tool tier requirements
  - Deny access if tier insufficient
  - Log all permission checks

**Data Security**:
- [ ] Implement `SecretDetector`:
  - Pre-commit scan for API keys, passwords, private keys
  - Pattern matching for common secret formats
  - Block commits containing secrets
  - Alert specialist to remove secrets
- [ ] Add file-level permissions:
  - `.env` files: Read-only
  - `secrets/*`: Blocked entirely
  - `src/auth/*`: Require security review
  - `migrations/*`: Require specialist approval
- [ ] Implement API key management:
  - Load from environment variables only
  - Validate keys on startup
  - Support key rotation

**Access Control**:
- [ ] Configure GitHub branch protection (done via GitHub settings, document in README)
- [ ] Implement audit logging:
  - Log all agent actions
  - Append-only immutable log
  - Add cryptographic signatures
  - Support export for compliance

#### 3.4 Monitoring & Observability

**Dashboard Backend**:
- [ ] Implement REST API for dashboard:
  - `/api/tasks` - List all tasks with status
  - `/api/agents` - List all agents with current state
  - `/api/metrics` - Get token usage, costs, performance
  - `/api/logs` - Query logs with filters
  - `/api/github` - Get GitHub activity (issues, PRs, commits)
- [ ] Use Flask or FastAPI for API server
- [ ] Add WebSocket support for real-time updates

**Metrics Collection**:
- [ ] Implement `MetricsCollector`:
  - Track tokens consumed per agent
  - Track tasks completed per agent
  - Calculate efficiency scores
  - Track error rates and escalations
  - Track time per task
  - Track costs ($ per task)
- [ ] Store metrics in database (time-series if possible)
- [ ] Generate performance reports

**Health Monitoring**:
- [ ] Implement health check endpoints:
  - Liveness: Is system running?
  - Readiness: Can system accept work?
- [ ] Check component status (database, GitHub API, model APIs)
- [ ] Track API latency and errors

#### 3.5 User Interface

**Web Dashboard** (Choose: React, Vue, or simple HTML+JS):
- [ ] **Task Board View**:
  - Kanban columns: To Do, In Progress, Review, Done
  - Drag-and-drop to change status
  - Click card to see details
  - Real-time updates via WebSocket
- [ ] **Agent Status Panel**:
  - List all agents with current status
  - Show active task per agent
  - Display token consumption
  - Show efficiency scores
  - Color-coded by status (idle, working, blocked, error)
- [ ] **Metrics Dashboard**:
  - Token usage charts (line graph over time)
  - Cost tracking (cumulative and daily)
  - Task completion rate
  - Agent efficiency comparison (bar chart)
- [ ] **GitHub Integration View**:
  - List recent issues
  - List open pull requests with status
  - Show commit activity
  - Embed GitHub links
- [ ] **Logs Viewer**:
  - Filterable log stream (by agent, level, time)
  - Search functionality
  - Expandable entries for details
- [ ] **Configuration Interface**:
  - Form to edit agent configurations
  - Model selection dropdowns
  - Tool permission checkboxes
  - Save configuration to YAML file

**Testing Console** (Optional if time permits):
- [ ] Terminal emulator for running commands
- [ ] API tester for making HTTP requests
- [ ] Feature validation forms

#### 3.6 Configuration UI (Advanced - if time permits)

**Drag-and-Drop Agent Builder**:
- [ ] Canvas for visual agent layout
- [ ] Agent blocks (architect, manager, specialist)
- [ ] Connection lines showing hierarchy
- [ ] Property panels for configuration
- [ ] Real-time YAML generation
- [ ] Export configuration file

**Simpler Alternative** (if drag-drop too complex):
- [ ] Form-based configuration editor
- [ ] Add/remove agents with buttons
- [ ] Model dropdowns
- [ ] Tool checkboxes
- [ ] Preview generated YAML
- [ ] Save to file

### Acceptance Criteria

- [ ] All 20 tools implemented and functional
- [ ] Tool permission checking works correctly
- [ ] Verification pipeline runs all 5 stages
- [ ] CI/CD workflow blocks failing PRs
- [ ] Secret detection prevents leaks
- [ ] Sandbox prevents code execution escape
- [ ] Dashboard shows real-time system state
- [ ] Metrics track token usage and costs accurately
- [ ] Web UI is functional and user-friendly
- [ ] Tests pass with >75% coverage
- [ ] No conflicts with Team Member 1's work (agents, orchestration)

### Implementation Guidelines

**Tool Implementation Example**:
```python
class FilesystemReadTool(Tool):
    name = "filesystem_read"
    tier = 1
    description = "Read contents of a file"
    
    def execute(self, path: str, start_line: int = None, end_line: int = None):
        # Validate path (no ../ traversal)
        if ".." in path:
            raise SecurityError("Path traversal not allowed")
        
        with open(path, 'r') as f:
            if start_line and end_line:
                lines = f.readlines()[start_line-1:end_line]
                return "".join(lines)
            else:
                return f.read()
```

**Verification Pipeline Example**:
```python
class VerificationPipeline:
    def verify(self, pr: PullRequest) -> VerificationResult:
        # Stage 1: Self-check already done before PR
        
        # Stage 2: CI/CD
        cicd_result = self.wait_for_cicd(pr)
        if not cicd_result.passed:
            return VerificationResult(passed=False, stage=2, reason="CI/CD failed")
        
        # Stage 3: Optional code reviewer
        if self.config.enable_reviewer:
            review = self.code_reviewer.review(pr)
            self.create_improvement_issues(review.suggestions)
        
        # Stage 4: Manager review
        manager_approval = self.wait_for_manager_approval(pr)
        if not manager_approval:
            return VerificationResult(passed=False, stage=4, reason="Manager rejected")
        
        # Stage 5: Architect review
        architect_approval = self.wait_for_architect_approval(pr)
        if architect_approval:
            return VerificationResult(passed=True)
        else:
            return VerificationResult(passed=False, stage=5, reason="Architect rejected")
```

### Testing Requirements

- Unit tests for each tool
- Integration tests for verification pipeline
- Security tests for sandbox escape attempts
- API endpoint tests
- UI component tests (if using framework)
- E2E test: Tool execution → Verification → Dashboard display

### Dependencies

- Issue #1 (Foundation) must be complete
- GitHub integration must be functional
- Context store must be available
- Need to coordinate with Issue #2 for agent interfaces

### Definition of Done

- All tools implemented and tested
- Verification pipeline functional
- Security controls in place and tested
- Dashboard shows system state correctly
- Tests pass and coverage >75%
- Code reviewed and documented
- UI is usable and responsive
- No merge conflicts with Issue #2 work

---

## Coordination Notes

### Minimizing Conflicts

**Team Member 1** works primarily in:
- `src/agents/` - All agent implementations
- `src/orchestration/` - Task routing, error recovery
- Agent-related tests

**Team Member 2** works primarily in:
- `src/tools/` - All tool implementations
- `src/verification/` - Verification pipeline
- `src/security/` - Security controls
- `src/ui/` - User interface
- Tool/verification/UI tests

**Shared Areas** (coordinate via comments/communication):
- `src/infrastructure/` - Created in Issue #1, minimal changes needed
- Configuration files - Team Member 2 may add security config
- Documentation - Both update relevant sections

### Integration Points

1. **Agent → Tool**: Agents call tools via `ToolRegistry`
2. **Agent → Verification**: Specialists trigger verification pipeline
3. **Agents → Dashboard**: Agents report status via API endpoints
4. **Foundation → Everyone**: Both use interfaces from Issue #1

### Suggested Workflow

1. **Days 1-3**: Both work on Issue #1 (Foundation) together
2. **Days 4-10**: Parallel development:
   - TM1: Issue #2 (Agents & Orchestration)
   - TM2: Issue #3 (Verification, Security, UI)
3. **Daily**: 15-min sync to discuss integration points
4. **Days 11-12**: Integration testing and bug fixes together
5. **Day 13**: Demo preparation and documentation

### Communication Protocol

- Use GitHub issue comments for updates
- Tag each other when interface changes needed
- Create small PRs frequently (easier to review)
- Do code reviews for each other
- Pair program on tricky integration points

---

## Success Metrics

**After all issues complete, the system should**:
- [ ] Accept a user prompt and create GitHub issues
- [ ] Route tasks to appropriate specialists
- [ ] Have specialists create working PRs
- [ ] Pass all verification stages
- [ ] Merge to main without human intervention (for simple tasks)
- [ ] Display system status in dashboard
- [ ] Recover from errors gracefully
- [ ] Track token usage and costs accurately
- [ ] Maintain security (no secret leaks, sandbox violations)
- [ ] Handle at least 5 concurrent tasks

**Quality Targets**:
- Test coverage: >75% overall
- No critical security vulnerabilities
- API response time: <200ms (p95)
- Dashboard loads in <2 seconds
- Can handle 10 specialists simultaneously
- Token efficiency: >1.5 tasks per 1000 tokens

---

## Additional Resources

- [Design Specification](DESIGN_SPEC.md) - Complete 5,294-line spec
- [Architecture Diagrams](README.md) - Visual system architecture
- [GitHub API Docs](https://docs.github.com/en/rest)
- [OpenAI API Docs](https://platform.openai.com/docs/api-reference)
- [Anthropic API Docs](https://docs.anthropic.com/claude/reference)
