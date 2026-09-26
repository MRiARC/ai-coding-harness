# AI Coding Harness - Complete Context for AI Tools

## Project Overview
This is an autonomous coding agent harness for the LCC x DevClub Hackathon. It uses a hierarchical multi-agent system (Architect → Managers → Specialists) to autonomously complete software engineering tasks.

## Key Files to Read
1. **README.md** - Architecture diagrams and visual overview
2. **DESIGN_SPEC.md** - Complete 5,294-line design specification
3. **TECHNICAL_IMPLEMENTATION.md** - Technology stack and implementation guide
4. **IMPLEMENTATION_GUIDE.md** - Task breakdown for all GitHub issues

## Technology Stack
- **API Server**: Go 1.21+
- **Agent System**: Python 3.11+ with LangGraph
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **Frontend**: React 18 + Vite

## Architecture Summary
```
Frontend (React) 
    ↓ HTTP/WebSocket
API Gateway (Go:8080)
    ↓ HTTP REST
Agent Orchestrator (Python:8000)
    ↓
PostgreSQL + Redis + GitHub API
```

## Quick Start for AI Assistants

When helping implement this project:

1. **Read the specifications first**: Check README.md, DESIGN_SPEC.md, and TECHNICAL_IMPLEMENTATION.md
2. **Follow the tech stack**: Use Go for API, Python+LangGraph for agents
3. **Check GitHub issues**: 41 issues (#1-41) break down all tasks
4. **Follow patterns**: Code examples are in TECHNICAL_IMPLEMENTATION.md
5. **Maintain architecture**: Keep the 3-tier agent hierarchy (Architect → Managers → Specialists)

## Key Implementation Points

### Agent System (Python)
- Use LangGraph for agent workflows
- Architect decomposes tasks
- Managers assign using multi-factor algorithm
- Specialists execute 11-step workflow

### API Server (Go)
- HTTP server with WebSocket support
- Proxy requests to Python agent service
- Manage database and Redis connections

### Database Schema
- 8 main tables: repositories, tasks, agents, agent_contexts, global_rules, token_usage, metrics, audit_logs
- Use PostgreSQL with JSONB for flexibility

### Communication
- Go ↔ Python: HTTP REST
- Real-time updates: WebSocket
- Async events: Redis Pub/Sub

## GitHub Issues Structure
- Issue #1: Foundation (8 sub-issues: #4-11) - Both team members
- Issue #2: Agents (13 sub-issues: #12-24) - Team Member 1
- Issue #3: Verification/Security/UI (17 sub-issues: #25-41) - Team Member 2

## Important Design Decisions
1. **Go over Rust**: Faster development, good enough performance
2. **LangGraph**: Perfect for agent state management
3. **PostgreSQL**: JSONB support for flexible context storage
4. **Branch-per-agent**: Prevents merge conflicts during development
5. **Multi-factor assignment**: 40% specialty, 20% availability, 20% load, 20% capability

## Development Workflow
```bash
# Start infrastructure
docker-compose up -d postgres redis

# Start Go API server
cd api-server && go run cmd/server/main.go

# Start Python agent service
cd agent-service && uvicorn main:app --reload

# Start frontend
cd frontend && npm run dev
```

## Testing
- Go: `go test ./...`
- Python: `pytest tests/`
- Integration: `./scripts/e2e-test.sh`

## For More Details
Refer to the complete documentation files in the repository.
