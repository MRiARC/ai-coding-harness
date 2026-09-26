"""Specialist factory (milestone 2, issues 2.8-2.10).

The classic specialist team (backend-api, database, frontend, testing,
devops, security, documentation, code-review) and the eval-mode trio
(locator, implementer, verifier) share one registry: `ROLE_PRESETS` in
`prompts.py` defines prompts/specialties/tool tiers, and this module maps
task specialties to roles and builds ready-to-run agents.
"""

from __future__ import annotations

from typing import Any

from harness.agents.llm_agent import LLMAgent, StoreWindow
from harness.agents.prompts import ROLE_PRESETS
from harness.engine.budget import BudgetGovernor
from harness.infrastructure.context_store import ContextStore
from harness.infrastructure.model_providers import ModelProvider
from harness.tools.base import Tool

SPECIALTY_ROLES: dict[str, tuple[str, ...]] = {
    # Free-form specialties the Architect's plans actually emit (live-run data):
    # they must route to an editing-capable role, not tie at neutral 0.5.
    "bugfix": ("implementer",),
    "bug-fix": ("implementer",),
    "implementation": ("implementer",),
    "fix": ("implementer",),
    "code-change": ("implementer",),
    "backend-api": ("backend-api", "implementer"),
    "database": ("database", "backend-api"),
    "frontend": ("frontend",),
    "testing": ("testing", "verifier"),
    "verification": ("verifier", "testing"),
    "localization": ("locator",),
    "devops": ("devops",),
    "security": ("security",),
    "documentation": ("documentation",),
    "code-review": ("code-review", "architect"),
    "architecture": ("architect",),
    "coordination": ("manager",),
}


def roles_for_specialty(specialty: str) -> tuple[str, ...]:
    """Roles able to take a task of this specialty, best first."""
    return SPECIALTY_ROLES.get(specialty, ("implementer",))


def build_agent(
    agent_id: str,
    role: str,
    model_config: dict[str, Any],
    provider: ModelProvider,
    store: ContextStore,
    governor: BudgetGovernor,
    tools: list[Tool] | None = None,
    model_tier: int | None = None,
    task_id: str = "ad-hoc",
    max_steps: int = 16,
    stale_tool_results: int = 6,
) -> LLMAgent:
    """Instantiate any registered role with its preset defaults applied."""
    if role not in ROLE_PRESETS:
        msg = f"unknown role '{role}'; known: {sorted(ROLE_PRESETS)}"
        raise ValueError(msg)
    preset = ROLE_PRESETS[role]
    return LLMAgent(
        agent_id=agent_id,
        model_config=model_config,
        tools=tools or [],
        context_window=StoreWindow(store, agent_id, task_id),
        provider=provider,
        store=store,
        governor=governor,
        role=role,
        model_tier=model_tier if model_tier is not None else min(4, preset.max_tool_tier.value + 1),
        max_steps=max_steps,
        stale_tool_results=stale_tool_results,
    )
