"""Architect agent (milestone 2, issues 2.1-2.3): analyze, decompose, review.

Per DESIGN_SPEC §2.1 adapted to the evaluation contract: repository analysis
consumes a deterministic repo summary (the filesystem indexer lands in
milestone 3 with the tool runtime), decomposition emits an in-process Plan
instead of GitHub issues, and final review judges the aggregate diff against
the plan's acceptance criteria locally.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from harness.agents.llm_agent import LLMAgent, StoreWindow
from harness.agents.task import Task
from harness.engine.budget import BudgetGovernor
from harness.infrastructure.context_store import ContextStore
from harness.infrastructure.model_providers import ModelProvider
from harness.tools.base import Tool

PROFILE_SCHEMA = (
    '{"languages": [str], "frameworks": [str], "test_framework": str, '
    '"build_system": str, "conventions": [str], "notes": str}'
)
PLAN_SCHEMA = (
    '{"issue_summary": str, "complexity": int(1-10), '
    '"subtasks": [{"id": str, "title": str, "description": str, '
    '"specialty": str, "complexity": int, "files": [str], '
    '"acceptance_criteria": [str], "depends_on": [str]}], '
    '"risks": [str], "needs_collaboration": bool}'
)
VERDICT_SCHEMA = '{"approved": bool, "issues": [str], "summary": str}'


class RepositoryProfile(BaseModel):
    """Structured understanding of the target repository."""

    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    test_framework: str = ""
    build_system: str = ""
    conventions: list[str] = Field(default_factory=list)
    notes: str = ""


class SubTask(BaseModel):
    """One atomic unit of the plan; `files` drives the Manager's overlap gate."""

    id: str
    title: str
    description: str
    specialty: str = "implementer"
    complexity: int = Field(default=5, ge=1, le=10)
    files: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)

    def to_task(self) -> Task:
        return Task(
            id=self.id,
            title=self.title,
            description=self.description,
            acceptance_criteria=self.acceptance_criteria,
            specialty=self.specialty,
            complexity=self.complexity,
            files=self.files,
            metadata={"depends_on": self.depends_on},
        )


class Plan(BaseModel):
    """The Architect's decomposition of one issue."""

    issue_summary: str = ""
    complexity: int = Field(default=5, ge=1, le=10)
    subtasks: list[SubTask] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    needs_collaboration: bool = False


class ReviewVerdict(BaseModel):
    """Final review outcome with evidence-backed findings."""

    approved: bool
    issues: list[str] = Field(default_factory=list)
    summary: str = ""


class ArchitectAgent(LLMAgent):
    """Top-tier agent: analysis, decomposition, final review, global rules."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("role", "architect")
        super().__init__(**kwargs)

    async def analyze_repository(self, repo_summary: dict[str, Any]) -> RepositoryProfile:
        """Turn a deterministic repo summary into a structured profile.

        The profile is also saved to the global context so every downstream
        agent shares one understanding of the codebase.
        """
        prompt = (
            f"Analyze this repository summary and reply with JSON only.\nSummary: {repo_summary}"
        )
        data = await self.structured_call(
            "Reply with JSON matching: " + PROFILE_SCHEMA, prompt, PROFILE_SCHEMA
        )
        profile = RepositoryProfile.model_validate(data)
        self.store.save_global("repo_profile", profile.model_dump())
        return profile

    async def decompose(self, issue_text: str, profile: RepositoryProfile | None = None) -> Plan:
        """Decompose one issue into subtasks with acceptance criteria."""
        profile_section = f"Repository profile: {profile.model_dump()}\n" if profile else ""
        prompt = (
            f"{profile_section}Decompose this issue into atomic subtasks. "
            f"Each subtask lists the files it will touch.\nISSUE:\n{issue_text}"
        )
        data = await self.structured_call(
            "Reply with JSON matching: " + PLAN_SCHEMA, prompt, PLAN_SCHEMA
        )
        plan = Plan.model_validate(data)
        self.store.save_global("plan", plan.model_dump())
        return plan

    async def review(self, diff: str, plan: Plan) -> ReviewVerdict:
        """Judge the aggregate diff against the plan's acceptance criteria."""
        criteria = "\n".join(
            f"- {st.id}: {'; '.join(st.acceptance_criteria) or st.title}" for st in plan.subtasks
        )
        prompt = (
            "Review this diff against the acceptance criteria. "
            f"Reply with JSON only.\nCRITERIA:\n{criteria}\nDIFF:\n{diff[:12000]}"
        )
        data = await self.structured_call(
            "Reply with JSON matching: " + VERDICT_SCHEMA, prompt, VERDICT_SCHEMA
        )
        return ReviewVerdict.model_validate(data)

    async def reframe(self, task: Task, escalation_message: str) -> Task:
        """Level-3 recovery: restate a task the team could not complete."""
        prompt = (
            f"This task repeatedly failed. Reframe it smaller and clearer.\n"
            f"TASK: {task.title}\n{task.description}\nFAILURE: {escalation_message}"
        )
        data = await self.structured_call(
            'Reply with JSON: {"title": str, "description": str, "acceptance_criteria": [str]}',
            prompt,
            '{"title": str, "description": str, "acceptance_criteria": [str]}',
        )
        return task.model_copy(
            update={
                "title": data.get("title", task.title),
                "description": data.get("description", task.description),
                "acceptance_criteria": data.get("acceptance_criteria", task.acceptance_criteria),
                "metadata": {**task.metadata, "reframed": True},
            }
        )


def build_architect(
    agent_id: str,
    model_config: dict[str, Any],
    provider: ModelProvider,
    store: ContextStore,
    governor: BudgetGovernor,
    tools: list[Tool] | None = None,
) -> ArchitectAgent:
    """Convenience factory wiring the architect role defaults."""
    return ArchitectAgent(
        agent_id=agent_id,
        model_config=model_config,
        tools=tools or [],
        context_window=StoreWindow(store, agent_id, "planning"),
        provider=provider,
        store=store,
        governor=governor,
    )
