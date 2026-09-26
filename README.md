# LCC x DevClub AI Coding Harness - Architecture Diagrams

## 1. Complete System Architecture (5-Layer View)

```mermaid
graph TB
    subgraph UI["🖥️ USER INTERFACE LAYER"]
        Dashboard["📊 Web Dashboard<br/>Task Board | Agent Status<br/>Token Usage | GitHub Feed"]
        ConfigUI["⚙️ Configuration UI<br/>Drag-Drop Builder<br/>Model Selection | Tools"]
        TestWindow["🧪 Testing Window<br/>Terminal | API Tester<br/>Browser Preview"]
        Monitoring["📈 Monitoring<br/>Metrics | Costs<br/>Alerts | Health"]
        API["🔌 REST API<br/>Task Creation<br/>Status | Metrics"]
    end
    
    subgraph ORCH["👑 ORCHESTRATION LAYER"]
        Architect["<b>ARCHITECT AGENT</b><br/>━━━━━━━━━━━━━━<br/>Model: GPT-4/Claude Opus<br/>━━━━━━━━━━━━━━<br/>✓ Analyze repository<br/>✓ Extract global rules<br/>✓ Decompose tasks<br/>✓ Create GitHub issues<br/>✓ Final PR review & merge"]
    end
    
    subgraph COORD["🎯 COORDINATION LAYER"]
        Mgr1["<b>MANAGER 1: Backend</b><br/>━━━━━━━━━━━━<br/>Model: Claude Sonnet<br/>━━━━━━━━━━━━<br/>Max Specialists: 8<br/>━━━━━━━━━━━━<br/>Multi-Factor Assignment:<br/>• Specialty (40%)<br/>• Availability (20%)<br/>• Load Balance (20%)<br/>• Capability (20%)"]
        
        Mgr2["<b>MANAGER 2: Frontend</b><br/>━━━━━━━━━━━━<br/>Model: GPT-4-mini<br/>━━━━━━━━━━━━<br/>Max Specialists: 6<br/>━━━━━━━━━━━━<br/>Coordinates:<br/>• React/Vue specialists<br/>• Styling specialists<br/>• Frontend testing"]
        
        Mgr3["<b>MANAGER 3: DevOps</b><br/>━━━━━━━━━━━━<br/>Model: Gemini Flash<br/>━━━━━━━━━━━━<br/>Max Specialists: 4<br/>━━━━━━━━━━━━<br/>Handles:<br/>• CI/CD pipelines<br/>• Infrastructure<br/>• Security scans"]
    end
    
    subgraph EXEC["⚡ EXECUTION LAYER"]
        SD1["SD-Backend-API<br/>(Tier 2)"]
        SD2["SD-Database<br/>(Tier 3)"]
        SD3["SD-React<br/>(Tier 2)"]
        SD4["SD-Styling<br/>(Tier 2)"]
        SD5["SD-DevOps<br/>(Tier 2)"]
        SD6["SD-Security<br/>(Tier 3)"]
        SD7["SD-Testing<br/>(Tier 3)"]
        SD8["SD-Reviewer<br/>(Tier 4)"]
    end
    
    subgraph INFRA["🏗️ INFRASTRUCTURE LAYER"]
        Context["📊 Context Store<br/>PostgreSQL/MongoDB<br/>━━━━━━━━━━<br/>• Global context<br/>• Per-agent contexts<br/>• Time-windowed compression"]
        
        Tools["🔧 Tool Runtime<br/>23+ Tools<br/>━━━━━━━━━━<br/>Tier 1: Read ops<br/>Tier 2: Write/Test<br/>Tier 3: DB/Security"]
        
        Models["🤖 Model APIs<br/>Multi-Provider<br/>━━━━━━━━━━<br/>• OpenAI<br/>• Anthropic<br/>• Google<br/>• Open-Source"]
        
        GitHub["🐙 GitHub<br/>Integration<br/>━━━━━━━━━━<br/>• Issues<br/>• Pull Requests<br/>• CI/CD<br/>• Branch Protection"]
    end
    
    UI --> Architect
    Architect -->|Backend Tasks| Mgr1
    Architect -->|Frontend Tasks| Mgr2
    Architect -->|DevOps Tasks| Mgr3
    
    Mgr1 --> SD1
    Mgr1 --> SD2
    Mgr1 --> SD7
    
    Mgr2 --> SD3
    Mgr2 --> SD4
    Mgr2 --> SD8
    
    Mgr3 --> SD5
    Mgr3 --> SD6
    
    EXEC -.->|Uses| INFRA
    
    style UI fill:#E3F2FD,stroke:#1976D2,stroke-width:3px
    style ORCH fill:#FFF3E0,stroke:#F57C00,stroke-width:3px
    style COORD fill:#F3E5F5,stroke:#7B1FA2,stroke-width:3px
    style EXEC fill:#E8F5E9,stroke:#388E3C,stroke-width:3px
    style INFRA fill:#ECEFF1,stroke:#455A64,stroke-width:3px
    
    style Architect fill:#FFE082,stroke:#F57C00,stroke-width:3px
    style Mgr1 fill:#CE93D8,stroke:#7B1FA2,stroke-width:2px
    style Mgr2 fill:#CE93D8,stroke:#7B1FA2,stroke-width:2px
    style Mgr3 fill:#CE93D8,stroke:#7B1FA2,stroke-width:2px
```

---

## 2. Specialist Workflow (11-Step Process)

```mermaid
graph LR
    S1["1️⃣ RECEIVE TASK<br/>━━━━━━━━━<br/>Manager assigns<br/>via multi-factor<br/>scoring"]
    
    S2["2️⃣ CREATE BRANCH<br/>━━━━━━━━━<br/>agent/id/issue-desc"]
    
    S3["3️⃣ IMPLEMENT<br/>━━━━━━━━━<br/>Write code<br/>Write tests<br/>Run linter"]
    
    S4["4️⃣ SELF-VERIFY<br/>━━━━━━━━━<br/>Run all tests<br/>Check coverage<br/>Review diffs"]
    
    S5["5️⃣ ERROR RECOVERY<br/>━━━━━━━━━<br/>Attempt 1: Fix syntax<br/>Attempt 2: Debug<br/>Attempt 3: Alt approach<br/>Failed? → Escalate"]
    
    S6["6️⃣ COMMIT & PR<br/>━━━━━━━━━<br/>Commit with<br/>type: desc<br/>Push & raise PR"]
    
    S7["7️⃣ CI/CD CHECKS<br/>━━━━━━━━━<br/>Lint ✓ Test ✓<br/>Build ✓ Coverage ✓<br/>Security ✓"]
    
    S8["8️⃣ REVIEW<br/>━━━━━━━━━<br/>Code quality<br/>agent reviews<br/>(optional)"]
    
    S9["9️⃣ MANAGER<br/>━━━━━━━━━<br/>Validates<br/>Checks conflicts<br/>Approves"]
    
    S10["🔟 ARCHITECT<br/>━━━━━━━━━<br/>Final validation<br/>Intent match ✓<br/>MERGE 🎉"]
    
    S11["✅ UPDATE<br/>━━━━━━━━━<br/>Global context<br/>Metrics logged<br/>User notified"]
    
    S1 --> S2 --> S3 --> S4
    S4 -.->|If Error| S5
    S5 --> S6
    S4 -->|Success| S6
    S6 --> S7 --> S8 --> S9 --> S10 --> S11
    
    style S1 fill:#A5D6A7,stroke:#388E3C,stroke-width:2px
    style S2 fill:#A5D6A7,stroke:#388E3C,stroke-width:2px
    style S3 fill:#A5D6A7,stroke:#388E3C,stroke-width:2px
    style S4 fill:#A5D6A7,stroke:#388E3C,stroke-width:2px
    style S5 fill:#FFE082,stroke:#F57C00,stroke-width:2px
    style S6 fill:#A5D6A7,stroke:#388E3C,stroke-width:2px
    style S7 fill:#BBDEFB,stroke:#1976D2,stroke-width:2px
    style S8 fill:#F8BBD0,stroke:#C2185B,stroke-width:2px
    style S9 fill:#CE93D8,stroke:#7B1FA2,stroke-width:2px
    style S10 fill:#FFE082,stroke:#F57C00,stroke-width:2px
    style S11 fill:#C8E6C9,stroke:#388E3C,stroke-width:2px
```

---

## 3. Error Recovery & Escalation (3-Level Hierarchy)

```mermaid
graph TD
    Error["❌ ERROR ENCOUNTERED<br/>━━━━━━━━━━━━━<br/>Test failure | API timeout<br/>Invalid output | Tool error"]
    
    Level1["<b>LEVEL 1: SELF-RECOVERY</b><br/>━━━━━━━━━━━━━━━━━<br/>Specialist Agent Attempts:<br/>━━━━━━━━━━━━━━━━━<br/>Attempt 1: Parse error, fix syntax<br/>Attempt 2: Debug logic, try fix<br/>Attempt 3: Alternative approach<br/>━━━━━━━━━━━━━━━━━<br/>Max 3 attempts or 30min"]
    
    Success1["✅ RESOLVED<br/>Continue task"]
    
    Level2["<b>LEVEL 2: MANAGER INTERVENTION</b><br/>━━━━━━━━━━━━━━━━━━━━━<br/>Manager Analyzes Error Type:<br/>━━━━━━━━━━━━━━━━━━━━━<br/>• Skill Gap → Reassign specialist<br/>• Tool Limitation → Grant access/upgrade model<br/>• Complex Task → Assign 2-3 specialists<br/>• Unclear Requirements → Reframe task<br/>━━━━━━━━━━━━━━━━━━━━━<br/>Monitors: token usage vs progress"]
    
    Success2["✅ RESOLVED<br/>Continue task"]
    
    Level3["<b>LEVEL 3: ARCHITECT ESCALATION</b><br/>━━━━━━━━━━━━━━━━━━━━━━━<br/>Architect Reviews:<br/>━━━━━━━━━━━━━━━━━━━━━━━<br/>• Task specification unclear → Reformulate<br/>• Task too complex → Decompose subtasks<br/>• Repository context missing → Deep analysis<br/>• Conflicting requirements → User decision<br/>━━━━━━━━━━━━━━━━━━━━━━━<br/>Can reassign to different manager team"]
    
    Success3["✅ RESOLVED<br/>Task reformulated"]
    
    Human["<b>LEVEL 4: HUMAN-IN-THE-LOOP</b><br/>━━━━━━━━━━━━━━━━━━━━<br/>User Intervention Required:<br/>━━━━━━━━━━━━━━━━━━━━<br/>• Architect cannot resolve<br/>• Infrastructure/external failures<br/>• User decision needed<br/>• Budget exceeded<br/>• Security judgment call<br/>━━━━━━━━━━━━━━━━━━━━<br/>Dashboard alert + optional email/Slack"]
    
    Error --> Level1
    Level1 -->|Success| Success1
    Level1 -->|Failed after 3 attempts| Level2
    Level2 -->|Success| Success2
    Level2 -->|Failed after 2 attempts| Level3
    Level3 -->|Success| Success3
    Level3 -->|Cannot resolve| Human
    
    style Error fill:#FFCDD2,stroke:#C62828,stroke-width:3px
    style Level1 fill:#C8E6C9,stroke:#388E3C,stroke-width:2px
    style Level2 fill:#CE93D8,stroke:#7B1FA2,stroke-width:2px
    style Level3 fill:#FFE082,stroke:#F57C00,stroke-width:2px
    style Human fill:#FFEBEE,stroke:#D32F2F,stroke-width:3px
    style Success1 fill:#A5D6A7,stroke:#388E3C,stroke-width:2px
    style Success2 fill:#A5D6A7,stroke:#388E3C,stroke-width:2px
    style Success3 fill:#A5D6A7,stroke:#388E3C,stroke-width:2px
```

---

## 4. Multi-Factor Task Assignment Algorithm

```mermaid
graph LR
    Task["📋 TASK RECEIVED<br/>━━━━━━━━━<br/>Complexity: 7/10<br/>Specialty: Backend API<br/>Priority: High<br/>Tools: filesystem, git, database"]
    
    Factor1["<b>FACTOR 1</b><br/>Specialty Match<br/>(40% weight)<br/>━━━━━━━━<br/>Backend-API-1: 95<br/>Database-1: 30<br/>Frontend-1: 10"]
    
    Factor2["<b>FACTOR 2</b><br/>Availability<br/>(20% weight)<br/>━━━━━━━━<br/>Backend-API-1: 100<br/>(0 active tasks)<br/>Database-1: 60<br/>(2 active tasks)"]
    
    Factor3["<b>FACTOR 3</b><br/>Load Balance<br/>(20% weight)<br/>━━━━━━━━<br/>Backend-API-1: 100<br/>(30k tokens used)<br/>Database-1: 60<br/>(70k tokens used)"]
    
    Factor4["<b>FACTOR 4</b><br/>Capability<br/>(20% weight)<br/>━━━━━━━━<br/>Backend-API-1: 50<br/>(Tier 2, no DB tool)<br/>Database-1: 100<br/>(Tier 3, has DB tool)"]
    
    Calculate["🧮 CALCULATE<br/>━━━━━━━━<br/>Backend-API-1:<br/>95×0.4 + 100×0.2<br/>+ 100×0.2 + 50×0.2<br/>= 88 total<br/>━━━━━━━━<br/>Database-1:<br/>30×0.4 + 60×0.2<br/>+ 60×0.2 + 100×0.2<br/>= 56 total"]
    
    Decision["✅ ASSIGN<br/>━━━━━━━━<br/>Task → Database-1<br/>(Higher capability<br/>for database needs)<br/>━━━━━━━━<br/>If complexity > 7:<br/>Assign top 2-3"]
    
    Task --> Factor1
    Task --> Factor2
    Task --> Factor3
    Task --> Factor4
    
    Factor1 --> Calculate
    Factor2 --> Calculate
    Factor3 --> Calculate
    Factor4 --> Calculate
    
    Calculate --> Decision
    
    style Task fill:#E3F2FD,stroke:#1976D2,stroke-width:2px
    style Factor1 fill:#FFF9C4,stroke:#F57C00,stroke-width:2px
    style Factor2 fill:#FFF9C4,stroke:#F57C00,stroke-width:2px
    style Factor3 fill:#FFF9C4,stroke:#F57C00,stroke-width:2px
    style Factor4 fill:#FFF9C4,stroke:#F57C00,stroke-width:2px
    style Calculate fill:#BBDEFB,stroke:#1976D2,stroke-width:2px
    style Decision fill:#C8E6C9,stroke:#388E3C,stroke-width:3px
```

---

## 5. Context Management System

```mermaid
graph TB
    subgraph Global["🌍 GLOBAL CONTEXT STORE"]
        RepoMeta["📁 Repository Metadata<br/>• Name, URL, branch<br/>• File structure<br/>• Dependencies<br/>• Build/test commands"]
        
        Tasks["📋 Active Tasks<br/>• Task ID, status<br/>• Assigned agents<br/>• Priority, complexity<br/>• Dependency graph"]
        
        Agents["👥 Agent Registry<br/>• Agent ID, type, status<br/>• Current task<br/>• Tokens consumed<br/>• Availability score"]
        
        Rules["📜 Global Rules<br/>• Extracted from prompts<br/>• Coding standards<br/>• Architecture decisions<br/>• Applies to: all/team"]
    end
    
    subgraph Agent1["👤 AGENT 1: Context Windows"]
        W1_1["<b>Window 1: Recent</b><br/>Last 20 messages<br/>(Uncompressed)"]
        
        W2_1["<b>Window 2: Mid-term</b><br/>Compressed summaries<br/>Key decisions + actions"]
        
        W3_1["<b>Window 3: Historical</b><br/>High-level summaries<br/>Outcomes only"]
    end
    
    subgraph Agent2["👤 AGENT 2: Context Windows"]
        W1_2["<b>Window 1: Recent</b><br/>Last 20 messages<br/>(Uncompressed)"]
        
        W2_2["<b>Window 2: Mid-term</b><br/>Compressed summaries<br/>Key decisions + actions"]
        
        W3_2["<b>Window 3: Historical</b><br/>High-level summaries<br/>Outcomes only"]
    end
    
    Algo["🔍 RETRIEVAL ALGORITHM<br/>━━━━━━━━━━━━━━━<br/>1. Agent checks Window 1 first<br/>2. If insufficient → expand to Window 2<br/>3. Still insufficient → check neighbor windows<br/>4. Critical need → retrieve historical<br/>━━━━━━━━━━━━━━━<br/>Neighbor: Related tasks, similar files"]
    
    Global -.->|Provides| Agent1
    Global -.->|Provides| Agent2
    Agent1 -.->|Can access| Agent2
    Agent2 -.->|Can access| Agent1
    
    Agent1 --> Algo
    Agent2 --> Algo
    
    style Global fill:#E3F2FD,stroke:#1976D2,stroke-width:3px
    style Agent1 fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px
    style Agent2 fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px
    style Algo fill:#FFF9C4,stroke:#F57C00,stroke-width:2px
```

---

## 6. Git Workflow & Branch Strategy

```mermaid
gitGraph
    commit id: "main: Initial state"
    branch agent/sd1/42-add-auth
    checkout agent/sd1/42-add-auth
    commit id: "feat: Add user model"
    commit id: "feat: Add JWT middleware"
    commit id: "test: Add auth tests"
    
    checkout main
    branch agent/sd2/43-login-ui
    checkout agent/sd2/43-login-ui
    commit id: "feat: Create login component"
    commit id: "style: Add login styling"
    
    checkout main
    branch agent/sd3/44-e2e-tests
    checkout agent/sd3/44-e2e-tests
    commit id: "test: Add E2E auth flow"
    
    checkout main
    merge agent/sd1/42-add-auth tag: "PR #42: Merged by Architect"
    
    checkout main
    merge agent/sd2/43-login-ui tag: "PR #43: Merged by Architect"
    
    checkout main
    merge agent/sd3/44-e2e-tests tag: "PR #44: Merged by Architect"
    
    commit id: "main: All features integrated"
```

**Branch Protection Rules:**
- ✅ `main` branch: Protected, only Architect can merge
- ✅ `agent/*` branches: Specialists can push, managers can coordinate
- ❌ No force-push to `main`
- ✅ Auto-delete branches after merge
- ✅ All PRs require CI/CD to pass

---

## 7. Tool Ecosystem (23+ Tools by Tier)

```mermaid
graph TB
    subgraph Tier1["🟢 TIER 1: Basic Models (All Access)"]
        T1_1["filesystem_read<br/>Read file contents"]
        T1_2["filesystem_list<br/>List directories"]
        T1_3["git_status<br/>Check git status"]
        T1_4["git_log<br/>View commit history"]
        T1_5["logging<br/>Write logs"]
    end
    
    subgraph Tier2["🟡 TIER 2: Medium+ Models"]
        T2_1["filesystem_write<br/>Modify files"]
        T2_2["git_operations<br/>Branch, commit, push"]
        T2_3["grep_search<br/>Search patterns"]
        T2_4["npm_commands<br/>Package manager"]
        T2_5["test_runner<br/>Execute tests"]
        T2_6["linting<br/>Code quality"]
        T2_7["formatting<br/>Code formatting"]
    end
    
    subgraph Tier3["🔴 TIER 3: Advanced Models"]
        T3_1["database_client<br/>DB operations"]
        T3_2["api_testing<br/>HTTP requests"]
        T3_3["code_execution<br/>Run code (sandboxed)"]
        T3_4["migration_tools<br/>DB migrations"]
        T3_5["docker_commands<br/>Containers"]
        T3_6["security_scanners<br/>Vuln scanning"]
        T3_7["performance_profiling<br/>Performance analysis"]
        T3_8["github_api<br/>Issues, PRs, merge"]
    end
    
    Models["🤖 MODEL TIERS<br/>━━━━━━━━━━━<br/>Tier 1: GPT-3.5, Gemini Flash, Llama 3 8B<br/>Tier 2: GPT-4-mini, Gemini Flash, Mistral<br/>Tier 3: GPT-4, Claude Sonnet, Gemini Pro<br/>Tier 4: GPT-4, Claude Opus (Architect only)"]
    
    Sandbox["🔒 SANDBOX ENVIRONMENT<br/>━━━━━━━━━━━━━━━━<br/>• Isolated containers<br/>• No network access<br/>• CPU limit: 30s<br/>• Memory limit: 512MB<br/>• Temp filesystem only"]
    
    Models -.->|Can use| Tier1
    Models -.->|Tier 2+ can use| Tier2
    Models -.->|Tier 3+ can use| Tier3
    
    Tier3 --> Sandbox
    
    style Tier1 fill:#C8E6C9,stroke:#388E3C,stroke-width:2px
    style Tier2 fill:#FFF9C4,stroke:#F57C00,stroke-width:2px
    style Tier3 fill:#FFCDD2,stroke:#C62828,stroke-width:2px
    style Models fill:#E3F2FD,stroke:#1976D2,stroke-width:2px
    style Sandbox fill:#ECEFF1,stroke:#455A64,stroke-width:2px
```

---

## 8. Resource Management & Budget Strategies

```mermaid
graph TD
    Budget["💰 GLOBAL TOKEN BUDGET<br/>━━━━━━━━━━━━━━<br/>Example: 1,000,000 tokens/day"]
    
    Strategy1["<b>Strategy 1: Fixed Per-Agent</b><br/>━━━━━━━━━━━━━━━━<br/>Architect: Unlimited<br/>Manager: 100k each<br/>Specialist: 50k each<br/>━━━━━━━━━━━━━━━━<br/>Pro: Predictable<br/>Con: Inflexible"]
    
    Strategy2["<b>Strategy 2: Dynamic</b><br/>━━━━━━━━━━━━━━━━<br/>Track efficiency:<br/>tasks_completed / tokens_used<br/>━━━━━━━━━━━━━━━━<br/>High efficiency: +20% budget<br/>Low efficiency: -10% budget<br/>━━━━━━━━━━━━━━━━<br/>Pro: Self-optimizing<br/>Con: Complex"]
    
    Strategy3["<b>Strategy 3: Priority-Based</b><br/>━━━━━━━━━━━━━━━━<br/>Critical: 100k tokens<br/>High: 50k tokens<br/>Normal: 30k tokens<br/>Low: 15k tokens<br/>━━━━━━━━━━━━━━━━<br/>Pro: Business-aligned<br/>Con: Hard to predict"]
    
    Strategy4["<b>Strategy 4: Adaptive Pool</b><br/>━━━━━━━━━━━━━━━━<br/>Shared pool, draw as needed<br/>━━━━━━━━━━━━━━━━<br/>80% used: Prioritize high-value<br/>90% used: Critical only<br/>100% used: Pause all<br/>━━━━━━━━━━━━━━━━<br/>Pro: Max flexibility<br/>Con: Unpredictable"]
    
    Monitoring["📊 MONITORING & OPTIMIZATION<br/>━━━━━━━━━━━━━━━━━━━<br/>Track per agent:<br/>• Tokens consumed<br/>• Tasks completed<br/>• Efficiency score<br/>• Cost ($)<br/>━━━━━━━━━━━━━━━━━━━<br/>Generate recommendations:<br/>• Downgrade models for simple tasks<br/>• Upgrade models for stuck agents<br/>• Reallocate budget to high performers"]
    
    Budget --> Strategy1
    Budget --> Strategy2
    Budget --> Strategy3
    Budget --> Strategy4
    
    Strategy1 --> Monitoring
    Strategy2 --> Monitoring
    Strategy3 --> Monitoring
    Strategy4 --> Monitoring
    
    style Budget fill:#FFF9C4,stroke:#F57C00,stroke-width:3px
    style Strategy1 fill:#BBDEFB,stroke:#1976D2,stroke-width:2px
    style Strategy2 fill:#C8E6C9,stroke:#388E3C,stroke-width:2px
    style Strategy3 fill:#F8BBD0,stroke:#C2185B,stroke-width:2px
    style Strategy4 fill:#CE93D8,stroke:#7B1FA2,stroke-width:2px
    style Monitoring fill:#FFE082,stroke:#F57C00,stroke-width:2px
```

---

## 9. Security Architecture

```mermaid
graph TB
    subgraph Input["🔐 INPUT SECURITY"]
        PromptValidation["Prompt Injection Detection<br/>━━━━━━━━━━━━━━<br/>Flags: 'Ignore previous'<br/>'You are now...'<br/>'Print system prompt'"]
        
        ParamValidation["Parameter Validation<br/>━━━━━━━━━━━━━━<br/>• Type checking<br/>• Range validation<br/>• Path sanitization<br/>• No ../../ escapes"]
        
        CommandInjection["Command Injection Prevention<br/>━━━━━━━━━━━━━━<br/>• Parameterized execution<br/>• No string concatenation<br/>• Block: ; | & $ backticks"]
    end
    
    subgraph Execution["⚡ EXECUTION SECURITY"]
        Sandbox["Code Execution Sandbox<br/>━━━━━━━━━━━━━━<br/>• Isolated containers<br/>• No network access<br/>• CPU: 30s limit<br/>• Memory: 512MB limit<br/>• Temp filesystem only"]
        
        ToolGating["Tool Permission Gating<br/>━━━━━━━━━━━━━━<br/>• Tier-based access<br/>• Low-tier models restricted<br/>• Dangerous tools need Tier 3<br/>• Temporary escalation logged"]
    end
    
    subgraph Data["🗄️ DATA SECURITY"]
        SecretDetection["Secret Detection<br/>━━━━━━━━━━━━━━<br/>Pre-commit scanning:<br/>• API keys<br/>• Private keys<br/>• Passwords<br/>• Connection strings<br/>• JWT secrets<br/>━━━━━━━━━━━━━━<br/>Block commit if detected"]
        
        FilePermissions["File-Level Permissions<br/>━━━━━━━━━━━━━━<br/>Sensitive files:<br/>• .env → Read-only<br/>• secrets/* → Blocked<br/>• src/auth/* → Security review<br/>• migrations/* → Specialist only"]
        
        APIKeys["API Key Management<br/>━━━━━━━━━━━━━━<br/>• Environment variables<br/>• Never in config files<br/>• Rotation support<br/>• Validation on startup"]
    end
    
    subgraph Access["🚪 ACCESS CONTROL"]
        BranchProtection["Branch Protection<br/>━━━━━━━━━━━━━━<br/>• main: Architect only<br/>• No force-push<br/>• PR required<br/>• CI/CD must pass"]
        
        AuditLog["Audit Trail<br/>━━━━━━━━━━━━━━<br/>• All actions logged<br/>• Immutable append-only<br/>• Cryptographic signatures<br/>• Export for compliance"]
    end
    
    Input --> Execution
    Execution --> Data
    Data --> Access
    
    style Input fill:#FFEBEE,stroke:#C62828,stroke-width:2px
    style Execution fill:#FFF3E0,stroke:#F57C00,stroke-width:2px
    style Data fill:#E8F5E9,stroke:#388E3C,stroke-width:2px
    style Access fill:#E3F2FD,stroke:#1976D2,stroke-width:2px
```

---

## 10. Verification Pipeline (5 Stages)

```mermaid
graph LR
    Stage1["<b>STAGE 1</b><br/>Agent Self-Check<br/>━━━━━━━━━<br/>• Syntax validation<br/>• Run tests locally<br/>• Lint check<br/>• Format code<br/>• Review acceptance criteria<br/>━━━━━━━━━<br/>Before raising PR"]
    
    Stage2["<b>STAGE 2</b><br/>Automated CI/CD<br/>━━━━━━━━━<br/>• Build verification<br/>• All test suites<br/>• Code coverage >80%<br/>• Security scan<br/>• License check<br/>━━━━━━━━━<br/>Blocks PR if fails"]
    
    Stage3["<b>STAGE 3</b><br/>Reviewer Agent<br/>━━━━━━━━━<br/>• Code smells<br/>• Pattern consistency<br/>• Documentation<br/>• Test quality<br/>• Performance implications<br/>━━━━━━━━━<br/>Creates improvement issues<br/>(Non-blocking)"]
    
    Stage4["<b>STAGE 4</b><br/>Manager Review<br/>━━━━━━━━━<br/>• Validates acceptance<br/>• Checks for conflicts<br/>• Ensures merge safety<br/>• Coordinates resolution<br/>━━━━━━━━━<br/>Approves for architect"]
    
    Stage5["<b>STAGE 5</b><br/>Architect Gate<br/>━━━━━━━━━<br/>• Reviews against intent<br/>• Validates global rules<br/>• Architecture fit<br/>• Quality gate<br/>━━━━━━━━━<br/>Final merge decision"]
    
    Success["✅ MERGED TO MAIN<br/>━━━━━━━━━<br/>• Context updated<br/>• Metrics logged<br/>• User notified<br/>• Branch deleted"]
    
    Stage1 --> Stage2
    Stage2 --> Stage3
    Stage3 --> Stage4
    Stage4 --> Stage5
    Stage5 --> Success
    
    Stage1 -.->|Fails| Stage1
    Stage2 -.->|Fails| Fix["🔧 Fix Required<br/>Specialist fixes<br/>and re-submits"]
    Stage4 -.->|Conflicts| Resolve["🔀 Resolve Conflicts<br/>Manager coordinates<br/>resolution"]
    Stage5 -.->|Changes Needed| Stage1
    
    Fix -.-> Stage1
    Resolve -.-> Stage4
    
    style Stage1 fill:#C8E6C9,stroke:#388E3C,stroke-width:2px
    style Stage2 fill:#BBDEFB,stroke:#1976D2,stroke-width:2px
    style Stage3 fill:#F8BBD0,stroke:#C2185B,stroke-width:2px
    style Stage4 fill:#CE93D8,stroke:#7B1FA2,stroke-width:2px
    style Stage5 fill:#FFE082,stroke:#F57C00,stroke-width:2px
    style Success fill:#A5D6A7,stroke:#388E3C,stroke-width:3px
    style Fix fill:#FFCDD2,stroke:#C62828,stroke-width:2px
    style Resolve fill:#FFF9C4,stroke:#F57C00,stroke-width:2px
```

---

## Legend

### Color Coding
- 🔵 **Blue**: User Interface Layer
- 🟠 **Orange**: Architect (Orchestration)
- 🟣 **Purple**: Managers (Coordination)
- 🟢 **Green**: Specialists (Execution) & Success states
- ⚫ **Gray**: Infrastructure Layer
- 🔴 **Red**: Errors & Security
- 🟡 **Yellow**: Warnings & Recovery

### Model Tiers
- **Tier 1**: Basic (GPT-3.5, Gemini Flash, Llama 3 8B) - Read-only tools
- **Tier 2**: Medium (GPT-4-mini, Gemini Flash, Mistral) - Write + Test tools
- **Tier 3**: Advanced (GPT-4, Claude Sonnet, Gemini Pro) - Database + Security tools
- **Tier 4**: Expert (GPT-4, Claude Opus) - All tools + Architecture (Architect only)

### Key Statistics
- **1** Architect Agent (Tier 4)
- **3** Manager Agents (Backend, Frontend, DevOps)
- **10+** Specialist Types
- **23+** Tools across 3 tiers
- **5** Verification stages
- **3** Error recovery levels
- **4** Budget allocation strategies

---

## 🏆 Hackathon Focus Areas

✅ **Correctness**: 5-stage verification pipeline ensures code quality  
✅ **Orchestration**: 3-tier hierarchy with intelligent task routing  
✅ **Recovery**: 3-level error handling (Self → Manager → Architect → Human)  
✅ **Efficiency**: Dynamic budget allocation, context compression, tool tier optimization  
✅ **Autonomy**: Minimal human intervention, self-recovering agents, automated workflows  

---

**Design Document**: 5,294 lines | **Created**: September 2026 | **Version**: 1.0  
**Ready for Implementation** 🚀
