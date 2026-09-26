# Technical Implementation Guide

> **AI Coding Harness - Technology Stack & Implementation Strategy**  
> Mapping design specification to concrete technologies and implementation patterns

---

## Table of Contents

1. [Technology Stack Overview](#1-technology-stack-overview)
2. [System Architecture](#2-system-architecture)
3. [Service Communication](#3-service-communication)
4. [Database Design](#4-database-design)
5. [Component Implementation](#5-component-implementation)
6. [Deployment Strategy](#6-deployment-strategy)
7. [Development Workflow](#7-development-workflow)

---

## 1. Technology Stack Overview

### 1.1 Core Technologies

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **API Server** | Go 1.21+ | High performance, excellent concurrency, fast development |
| **Agent System** | Python 3.11+ | LLM ecosystem, LangGraph for workflows, rapid iteration |
| **Database** | PostgreSQL 15+ | JSONB support, reliability, ACID compliance |
| **Cache/Queue** | Redis 7+ | Fast pub/sub, caching, session storage |
| **Frontend** | React 18 + Vite | Fast development, component reusability, modern tooling |

### 1.2 Key Libraries & Frameworks

**Go Stack:**
```
- net/http (stdlib)          # HTTP server
- gorilla/websocket          # WebSocket support
- lib/pq                     # PostgreSQL driver
- go-redis/redis             # Redis client
- google/uuid                # UUID generation
- sirupsen/logrus            # Structured logging
```

**Python Stack:**
```
- langgraph                  # Agent workflow orchestration
- langchain                  # LLM abstractions (optional)
- openai                     # OpenAI API client
- anthropic                  # Anthropic API client
- google-generativeai        # Google Gemini client
- pygithub                   # GitHub API client
- sqlalchemy                 # ORM for database
- fastapi                    # HTTP API framework
- pydantic                   # Data validation
```

**Frontend Stack:**
```
- react                      # UI framework
- vite                       # Build tool
- @tanstack/react-query      # Data fetching
- recharts                   # Charts for metrics
- tailwindcss                # Styling (optional)
```

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                         │
│                     http://localhost:3000                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP/WebSocket
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   API GATEWAY (Go)                              │
│                  http://localhost:8080                          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   HTTP       │  │  WebSocket   │  │   Auth       │        │
│  │   Router     │  │   Server     │  │   Middleware │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP REST
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              AGENT ORCHESTRATOR (Python)                        │
│                  http://localhost:8000                          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  Architect   │  │   Managers   │  │ Specialists  │        │
│  │    Agent     │  │   (3 types)  │  │  (10+ types) │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐     │
│  │           LangGraph Workflow Engine                  │     │
│  └──────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                ↓             ↓             ↓
┌──────────────────┐  ┌──────────────┐  ┌──────────────┐
│   PostgreSQL     │  │    Redis     │  │   GitHub     │
│   (Context +     │  │  (Cache +    │  │     API      │
│    Metrics)      │  │   Pub/Sub)   │  │              │
└──────────────────┘  └──────────────┘  └──────────────┘
```

### 2.2 Service Breakdown

#### **Service 1: API Gateway (Go)**

**Port**: 8080  
**Responsibilities**:
- HTTP request routing
- WebSocket connection management
- Authentication/authorization
- Rate limiting
- Request validation
- Static file serving (frontend)
- Proxy to Python agent service

**Key Endpoints**:
```
GET  /api/health              # Health check
GET  /api/tasks               # List tasks
POST /api/tasks               # Create task
GET  /api/agents              # List agents
GET  /api/metrics             # Get metrics
GET  /api/logs                # Query logs
WS   /ws                      # WebSocket connection
```

#### **Service 2: Agent Orchestrator (Python)**

**Port**: 8000  
**Responsibilities**:
- Agent lifecycle management
- LLM API calls
- Task decomposition
- Error recovery
- Context management
- GitHub operations

**Key Endpoints**:
```
POST /agent/architect/analyze      # Analyze repository
POST /agent/architect/decompose    # Decompose task
POST /agent/manager/assign         # Assign task
POST /agent/specialist/execute     # Execute task
GET  /agent/status/:id             # Get agent status
```

---

## 3. Service Communication

### 3.1 Go ↔ Python Communication

**Pattern**: HTTP REST (synchronous) + Redis Pub/Sub (async events)

**Request Flow Example**:
```
1. User submits prompt via Frontend
2. Frontend → Go API Gateway (HTTP POST /api/tasks)
3. Go validates request, stores in DB
4. Go → Python Agent Service (HTTP POST /agent/architect/decompose)
5. Python processes, returns task breakdown
6. Go stores results, publishes event to Redis
7. WebSocket clients receive real-time update
8. Go returns response to Frontend
```

**Event Flow Example**:
```
1. Specialist completes task
2. Python publishes event to Redis: "task.completed"
3. Go subscribes to Redis, receives event
4. Go broadcasts to WebSocket clients
5. Frontend updates UI in real-time
```

### 3.2 Communication Protocols

**Synchronous (HTTP REST)**:
- Task creation
- Status queries
- Configuration updates
- Metrics retrieval

**Asynchronous (Redis Pub/Sub)**:
- Task status updates
- Agent state changes
- Error notifications
- Progress updates

**Real-time (WebSocket)**:
- Live dashboard updates
- Log streaming
- Metrics streaming

---

## 4. Database Design

### 4.1 PostgreSQL Schema

**Tables**:

```sql
-- Global context and repository metadata
CREATE TABLE repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL,
    name TEXT NOT NULL,
    branch TEXT DEFAULT 'main',
    tech_stack JSONB,
    structure JSONB,
    analyzed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Tasks and issues
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID REFERENCES repositories(id),
    github_issue_number INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL, -- 'pending', 'in_progress', 'review', 'done'
    priority TEXT, -- 'critical', 'high', 'normal', 'low'
    complexity INTEGER, -- 1-10
    assigned_agent_id UUID,
    context_window JSONB,
    dependencies JSONB, -- Array of task IDs
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Agents registry
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL, -- 'architect', 'manager', 'specialist'
    specialty TEXT, -- 'backend', 'frontend', 'devops', etc.
    model_provider TEXT NOT NULL,
    model_id TEXT NOT NULL,
    status TEXT NOT NULL, -- 'idle', 'working', 'blocked', 'error'
    current_task_id UUID REFERENCES tasks(id),
    tokens_consumed BIGINT DEFAULT 0,
    tasks_completed INTEGER DEFAULT 0,
    config JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Agent context windows (time-windowed)
CREATE TABLE agent_contexts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(id),
    window_type TEXT NOT NULL, -- 'recent', 'midterm', 'historical'
    content JSONB NOT NULL,
    compressed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Global rules extracted from user prompts
CREATE TABLE global_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID REFERENCES repositories(id),
    rule_type TEXT, -- 'coding_standard', 'architecture', 'constraint'
    description TEXT NOT NULL,
    applies_to TEXT, -- 'all', 'backend', 'frontend', etc.
    created_at TIMESTAMP DEFAULT NOW()
);

-- Token usage tracking
CREATE TABLE token_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID REFERENCES agents(id),
    task_id UUID REFERENCES tasks(id),
    tokens_consumed INTEGER NOT NULL,
    cost_usd DECIMAL(10, 6),
    model_provider TEXT,
    model_id TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Metrics and performance
CREATE TABLE metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_type TEXT NOT NULL, -- 'task_completion', 'error_rate', 'efficiency'
    agent_id UUID REFERENCES agents(id),
    value DECIMAL(10, 4),
    metadata JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Audit logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id UUID,
    details JSONB,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_assigned_agent ON tasks(assigned_agent_id);
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_token_usage_agent ON token_usage(agent_id);
CREATE INDEX idx_token_usage_timestamp ON token_usage(timestamp);
CREATE INDEX idx_metrics_timestamp ON metrics(timestamp);
CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
```

### 4.2 Redis Data Structures

**Keys**:
```
# Session storage
session:{session_id} → JSON (user session data)

# Agent status cache
agent:status:{agent_id} → JSON (current status, updated frequently)

# Task queue
queue:tasks:pending → LIST (task IDs waiting for assignment)

# Pub/Sub channels
channel:task.created
channel:task.updated
channel:task.completed
channel:agent.status
channel:error.escalated
```

---

## 5. Component Implementation

### 5.1 Go API Server Implementation

**Project Structure**:
```
api-server/
├── cmd/
│   └── server/
│       └── main.go              # Entry point
├── internal/
│   ├── handlers/
│   │   ├── tasks.go             # Task endpoints
│   │   ├── agents.go            # Agent endpoints
│   │   ├── metrics.go           # Metrics endpoints
│   │   └── websocket.go         # WebSocket handler
│   ├── middleware/
│   │   ├── auth.go              # Authentication
│   │   ├── logging.go           # Request logging
│   │   └── ratelimit.go         # Rate limiting
│   ├── models/
│   │   └── types.go             # Data structures
│   ├── database/
│   │   └── postgres.go          # DB connection
│   ├── redis/
│   │   └── client.go            # Redis client
│   └── proxy/
│       └── agent_client.go      # Python service client
├── go.mod
└── go.sum
```

**Key Implementation Patterns**:

**HTTP Server Setup**:
```go
// Stdlib HTTP server with graceful shutdown
server := &http.Server{
    Addr:         ":8080",
    Handler:      router,
    ReadTimeout:  15 * time.Second,
    WriteTimeout: 15 * time.Second,
    IdleTimeout:  60 * time.Second,
}
```

**WebSocket Hub Pattern**:
```go
// Central hub manages all WebSocket connections
type Hub struct {
    clients    map[*Client]bool
    broadcast  chan []byte
    register   chan *Client
    unregister chan *Client
}

// Broadcasts messages to all connected clients
func (h *Hub) run() {
    for {
        select {
        case client := <-h.register:
            h.clients[client] = true
        case client := <-h.unregister:
            delete(h.clients, client)
        case message := <-h.broadcast:
            for client := range h.clients {
                client.send <- message
            }
        }
    }
}
```

**Proxy to Python Service**:
```go
// HTTP client with timeout and retry
client := &http.Client{
    Timeout: 30 * time.Second,
}

// Call Python agent service
resp, err := client.Post(
    "http://localhost:8000/agent/architect/decompose",
    "application/json",
    bytes.NewBuffer(jsonData),
)
```

### 5.2 Python Agent Service Implementation

**Project Structure**:
```
agent-service/
├── main.py                      # FastAPI entry point
├── agents/
│   ├── __init__.py
│   ├── base.py                  # BaseAgent abstract class
│   ├── architect.py             # Architect agent
│   ├── manager.py               # Manager agent
│   └── specialist.py            # Specialist agent
├── workflows/
│   ├── __init__.py
│   ├── task_decomposition.py   # LangGraph workflow
│   ├── task_execution.py       # Specialist workflow
│   └── error_recovery.py       # Recovery workflow
├── models/
│   ├── __init__.py
│   ├── providers.py             # LLM provider abstraction
│   └── schemas.py               # Pydantic models
├── tools/
│   ├── __init__.py
│   ├── filesystem.py            # File operations
│   ├── git.py                   # Git operations
│   └── github.py                # GitHub API
├── database/
│   ├── __init__.py
│   └── connection.py            # SQLAlchemy setup
├── requirements.txt
└── pyproject.toml
```

**Key Implementation Patterns**:

**LangGraph Workflow Example**:
```python
from langgraph.graph import StateGraph, END

# Define workflow state
class TaskDecompositionState(TypedDict):
    user_prompt: str
    repository_analysis: dict
    tasks: list[dict]
    global_rules: list[str]

# Create workflow graph
workflow = StateGraph(TaskDecompositionState)

# Add nodes
workflow.add_node("analyze_intent", analyze_user_intent)
workflow.add_node("extract_rules", extract_global_rules)
workflow.add_node("decompose_tasks", decompose_into_tasks)
workflow.add_node("create_issues", create_github_issues)

# Define edges
workflow.set_entry_point("analyze_intent")
workflow.add_edge("analyze_intent", "extract_rules")
workflow.add_edge("extract_rules", "decompose_tasks")
workflow.add_edge("decompose_tasks", "create_issues")
workflow.add_edge("create_issues", END)

# Compile
app = workflow.compile()
```

**Agent Base Class**:
```python
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    def __init__(self, agent_id: str, model_config: dict):
        self.agent_id = agent_id
        self.model_config = model_config
        self.context_window = []
        self.tools = []
    
    @abstractmethod
    async def execute_task(self, task: Task) -> TaskResult:
        """Execute assigned task"""
        pass
    
    @abstractmethod
    async def handle_error(self, error: Exception) -> RecoveryAction:
        """Handle errors with recovery strategy"""
        pass
    
    async def report_status(self, status: AgentStatus):
        """Report status to orchestrator"""
        await self.db.update_agent_status(self.agent_id, status)
```

**Model Provider Abstraction**:
```python
class ModelProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, tools: list = None) -> str:
        pass

class OpenAIProvider(ModelProvider):
    async def generate(self, prompt: str, tools: list = None) -> str:
        response = await self.client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
        )
        return response.choices[0].message.content
```


### 5.3 Frontend Implementation

**Project Structure**:
```
frontend/
├── src/
│   ├── components/
│   │   ├── TaskBoard.tsx        # Kanban board
│   │   ├── AgentPanel.tsx       # Agent status
│   │   ├── MetricsChart.tsx     # Charts
│   │   └── LogViewer.tsx        # Log stream
│   ├── hooks/
│   │   ├── useWebSocket.ts      # WebSocket hook
│   │   └── useApi.ts            # API calls
│   ├── services/
│   │   └── api.ts               # API client
│   ├── App.tsx
│   └── main.tsx
├── package.json
└── vite.config.ts
```

**WebSocket Hook**:
```typescript
function useWebSocket(url: string) {
  const [messages, setMessages] = useState<any[]>([]);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    ws.current = new WebSocket(url);
    
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setMessages(prev => [...prev, data]);
    };

    return () => ws.current?.close();
  }, [url]);

  return messages;
}
```

---

## 6. Deployment Strategy

### 6.1 Development Environment

**Docker Compose Setup**:
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ai_harness
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api-server:
    build: ./api-server
    ports:
      - "8080:8080"
    environment:
      DATABASE_URL: postgres://dev:dev@postgres:5432/ai_harness
      REDIS_URL: redis://redis:6379
      AGENT_SERVICE_URL: http://agent-service:8000
    depends_on:
      - postgres
      - redis

  agent-service:
    build: ./agent-service
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgres://dev:dev@postgres:5432/ai_harness
      REDIS_URL: redis://redis:6379
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    depends_on:
      - postgres
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      VITE_API_URL: http://localhost:8080

volumes:
  postgres_data:
```

### 6.2 Production Deployment

**Option 1: Single Server (Hackathon)**
```
- Deploy all services on one VPS (DigitalOcean, AWS EC2)
- Use systemd for process management
- Nginx as reverse proxy
- Let's Encrypt for HTTPS
```

**Option 2: Cloud Native (Post-Hackathon)**
```
- Kubernetes cluster
- Separate pods for each service
- Horizontal pod autoscaling
- Managed PostgreSQL (AWS RDS, GCP Cloud SQL)
- Managed Redis (AWS ElastiCache, GCP Memorystore)
```

---

## 7. Development Workflow

### 7.1 Local Development Setup

**Step 1: Clone Repository**
```bash
git clone https://github.com/MRiARC/ai-coding-harness.git
cd ai-coding-harness
```

**Step 2: Environment Setup**
```bash
# Copy environment template
cp .env.example .env

# Edit with your API keys
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GITHUB_TOKEN=ghp_...
```

**Step 3: Start Services**
```bash
# Start infrastructure
docker-compose up -d postgres redis

# Start Go API server
cd api-server
go run cmd/server/main.go

# Start Python agent service (separate terminal)
cd agent-service
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Start frontend (separate terminal)
cd frontend
npm install
npm run dev
```

**Step 4: Access Application**
```
Frontend: http://localhost:3000
API: http://localhost:8080
Agent Service: http://localhost:8000
```

### 7.2 Testing Strategy

**Go Tests**:
```bash
cd api-server
go test ./... -v -cover
```

**Python Tests**:
```bash
cd agent-service
pytest tests/ -v --cov=agents
```

**Integration Tests**:
```bash
# End-to-end test
./scripts/e2e-test.sh
```

### 7.3 CI/CD Pipeline

**GitHub Actions Workflow**:
```yaml
name: CI/CD

on: [push, pull_request]

jobs:
  test-go:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-go@v4
        with:
          go-version: '1.21'
      - run: cd api-server && go test ./...

  test-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: cd agent-service && pip install -r requirements.txt
      - run: cd agent-service && pytest

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: cd frontend && npm install
      - run: cd frontend && npm test

  deploy:
    needs: [test-go, test-python, test-frontend]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        run: ./scripts/deploy.sh
```

---

## 8. Feature-to-Tech Mapping

### 8.1 Agent System Features

| Feature | Technology | Implementation |
|---------|-----------|----------------|
| **Architect Agent** | Python + LangGraph | StateGraph workflow for task decomposition |
| **Manager Agents** | Python + LangGraph | Multi-factor scoring algorithm in Python |
| **Specialist Agents** | Python + LangGraph | 11-step workflow as LangGraph state machine |
| **Agent Communication** | Redis Pub/Sub | Publish events, subscribe to updates |
| **Context Management** | PostgreSQL JSONB | Store context windows with compression |
| **Token Tracking** | PostgreSQL + Go | Go aggregates, Python reports usage |

### 8.2 Tool System Features

| Feature | Technology | Implementation |
|---------|-----------|----------------|
| **Tier 1 Tools** | Python | Simple functions, no restrictions |
| **Tier 2 Tools** | Python | Permission check before execution |
| **Tier 3 Tools** | Python + Docker | Sandboxed execution in containers |
| **Tool Registry** | Python dict | Dynamic tool loading and validation |
| **Permission Gating** | Python decorator | `@require_tier(3)` decorator pattern |

### 8.3 Verification Features

| Feature | Technology | Implementation |
|---------|-----------|----------------|
| **Self-Check** | Python | Run linters, tests before PR |
| **CI/CD** | GitHub Actions | Automated workflow on PR |
| **Code Review Agent** | Python + LangGraph | LLM-based code analysis |
| **Pipeline Orchestration** | Python async | Sequential stage execution |

### 8.4 Security Features

| Feature | Technology | Implementation |
|---------|-----------|----------------|
| **Input Validation** | Go middleware | Validate before proxying to Python |
| **Prompt Injection Detection** | Python regex | Pattern matching on user input |
| **Sandboxing** | Docker | Isolated containers for code execution |
| **Secret Detection** | Python regex | Pre-commit hook scanning |
| **Audit Logging** | PostgreSQL | Immutable append-only logs |

### 8.5 UI Features

| Feature | Technology | Implementation |
|---------|-----------|----------------|
| **Task Board** | React + DnD | Drag-and-drop Kanban board |
| **Real-time Updates** | WebSocket | Go broadcasts, React receives |
| **Metrics Charts** | Recharts | Line/bar charts from API data |
| **Log Viewer** | React + Virtual Scroll | Efficient rendering of large logs |
| **Configuration Editor** | React forms | YAML generation from form inputs |

---

## 9. Performance Considerations

### 9.1 Optimization Strategies

**Go API Server**:
- Connection pooling for PostgreSQL (max 25 connections)
- Redis caching for frequently accessed data (TTL: 5 minutes)
- Gzip compression for HTTP responses
- HTTP/2 support for multiplexing

**Python Agent Service**:
- Async/await for I/O operations
- Connection pooling for database
- LRU cache for model responses (development only)
- Batch LLM requests when possible

**Database**:
- Indexes on frequently queried columns
- JSONB GIN indexes for context searches
- Partitioning for large tables (metrics, logs)
- Regular VACUUM and ANALYZE

**Frontend**:
- Code splitting with React.lazy()
- Virtual scrolling for large lists
- Debounced search inputs
- Service worker for offline support

### 9.2 Scalability Considerations

**Horizontal Scaling**:
- Go API server: Stateless, can run multiple instances behind load balancer
- Python agent service: Can run multiple workers (Gunicorn/Uvicorn)
- PostgreSQL: Read replicas for queries
- Redis: Redis Cluster for high availability

**Vertical Scaling**:
- Increase Go server memory for more concurrent connections
- Increase Python workers for more parallel agent execution
- Increase PostgreSQL resources for larger datasets

---

## 10. Monitoring & Observability

### 10.1 Logging Strategy

**Structured Logging Format**:
```json
{
  "timestamp": "2026-09-26T20:00:00Z",
  "level": "INFO",
  "service": "api-server",
  "message": "Task created",
  "task_id": "uuid",
  "user_id": "uuid",
  "duration_ms": 45
}
```

**Log Levels**:
- DEBUG: Development debugging
- INFO: Normal operations
- WARN: Recoverable errors
- ERROR: Errors requiring attention
- CRITICAL: System failures

### 10.2 Metrics Collection

**Key Metrics**:
```
# API Server
- http_requests_total (counter)
- http_request_duration_seconds (histogram)
- websocket_connections_active (gauge)

# Agent Service
- agent_tasks_completed_total (counter)
- agent_tokens_consumed_total (counter)
- agent_execution_duration_seconds (histogram)
- agent_errors_total (counter)

# Database
- db_connections_active (gauge)
- db_query_duration_seconds (histogram)
```

### 10.3 Health Checks

**Endpoints**:
```
GET /health/live    # Is service running?
GET /health/ready   # Can service accept traffic?
```

**Checks**:
- Database connectivity
- Redis connectivity
- Disk space availability
- Memory usage

---

## 11. Security Best Practices

### 11.1 API Security

- **Authentication**: JWT tokens or API keys
- **Rate Limiting**: 100 requests/minute per IP
- **CORS**: Whitelist frontend origin only
- **Input Validation**: Strict schema validation
- **SQL Injection**: Use parameterized queries only

### 11.2 Secret Management

- **Development**: `.env` file (gitignored)
- **Production**: Environment variables or secret manager (AWS Secrets Manager, HashiCorp Vault)
- **Rotation**: Automated key rotation every 90 days

### 11.3 Code Execution Security

- **Sandboxing**: Docker containers with no network
- **Resource Limits**: CPU 30s, Memory 512MB
- **Filesystem**: Temporary only, auto-cleanup
- **User**: Run as non-root user in container

---

## 12. Development Timeline

### Phase 1: Foundation (Days 1-3)
- Set up project structure
- Configure databases
- Implement basic Go API server
- Implement basic Python agent service
- Test communication between services

### Phase 2: Core Features (Days 4-7)
- Implement Architect agent
- Implement Manager agents
- Implement 3-5 Specialist agents
- Implement basic tool system
- Implement task decomposition workflow

### Phase 3: Verification & Security (Days 8-10)
- Implement verification pipeline
- Add security controls
- Implement monitoring
- Add error recovery

### Phase 4: UI & Polish (Days 11-13)
- Build React dashboard
- Add real-time updates
- Polish UX
- Write documentation
- Prepare demo

---

## 13. Quick Start Commands

```bash
# Initialize project
./scripts/init.sh

# Start development environment
docker-compose up -d
make dev

# Run tests
make test

# Build for production
make build

# Deploy
make deploy
```

---

## Appendix: Technology Decision Matrix

| Requirement | Option A | Option B | **Choice** | Reason |
|-------------|----------|----------|------------|--------|
| API Server | Go | Rust | **Go** | Faster development, excellent concurrency |
| Agent System | Python | TypeScript | **Python** | LLM ecosystem, LangGraph |
| Database | PostgreSQL | MongoDB | **PostgreSQL** | ACID, JSONB support |
| Cache | Redis | Memcached | **Redis** | Pub/Sub support |
| Frontend | React | Vue | **React** | Larger ecosystem, team familiarity |
| Communication | gRPC | HTTP REST | **HTTP REST** | Simpler debugging, good enough performance |

---

**Document Version**: 1.0  
**Last Updated**: September 2026  
**Status**: Ready for Implementation

