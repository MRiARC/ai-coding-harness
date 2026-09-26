"""Persona knowledge layer tests (issue #78): registry, cards, search, tool."""

from __future__ import annotations

import json
from pathlib import Path

from harness.agents.prompts import ROLE_PRESETS, system_prompt
from harness.knowledge.registry import (
    DEFAULT_SKILL_CARD_CHARS,
    PLAYBOOKS,
    export_cards,
    knowledge_section,
    knowledge_summary,
    load_playbook,
    search_knowledge,
    skill_card,
)
from harness.tools.knowledge import KnowledgeSearchTool
from harness.tools.registry import TOOL_NAMES, build_default_tools


def test_every_persona_has_a_playbook() -> None:
    missing = [role for role in ROLE_PRESETS if role not in PLAYBOOKS]
    assert not missing, f"playbooks missing for: {missing}"
    assert len(PLAYBOOKS) == len(ROLE_PRESETS) == 13


def test_every_playbook_has_canonical_sections() -> None:
    for role, playbook in PLAYBOOKS.items():
        assert "## CORE PRINCIPLES" in playbook, role
        assert "## CHECKLIST" in playbook, role
        assert "## ANTI-PATTERNS" in playbook, role
        assert "## REFERENCES" in playbook, role


def test_load_playbook_unknown_role_returns_empty() -> None:
    assert load_playbook("mystery-role") == ""


def test_skill_card_contains_core_and_checklist() -> None:
    card = skill_card("security")
    assert "CORE PRINCIPLES" in card and "CHECKLIST" in card
    assert "PATTERNS" not in card  # sections after CHECKLIST are excluded


def test_skill_card_is_capped() -> None:
    card = skill_card("architect", max_chars=300)
    assert len(card) <= 300 + len("\n[skill card truncated]")
    assert "[skill card truncated]" in card


def test_knowledge_section_wraps_card() -> None:
    section = knowledge_section("verifier")
    assert section.startswith("PERSONA KNOWLEDGE (skill card):")
    assert "fail" in section.lower()
    assert knowledge_section("mystery-role") == ""


def test_search_finds_owasp_in_security_playbook() -> None:
    findings = search_knowledge("owasp injection authorization", role="security")
    assert findings
    assert all(f["role"] == "security" for f in findings)
    assert any("OWASP" in f["line"] or "injection" in f["line"].lower() for f in findings)


def test_search_scoped_to_role_falls_back_to_all() -> None:
    findings = search_knowledge("owasp", role=None, limit=3)
    roles = {f["role"] for f in findings}
    assert len(roles) > 1  # unscoped: matches across personas
    scoped = search_knowledge("test pyramid", role="testing")
    assert scoped and all(f["role"] == "testing" for f in scoped)


def test_search_empty_query_returns_empty() -> None:
    assert search_knowledge("  ") == []
    assert search_knowledge("ab") == []  # terms shorter than 3 chars ignored


def test_search_result_shape() -> None:
    finding = search_knowledge("idempotency pagination", role="backend-api")[0]
    assert set(finding) == {"role", "section", "line"}
    assert len(finding["line"]) <= 221  # capped line length


def test_knowledge_summary_lists_all_roles() -> None:
    summary = knowledge_summary()
    assert set(summary) == set(ROLE_PRESETS)
    assert all(size > 1000 for size in summary.values())  # real playbooks, not stubs


def test_export_cards_writes_json(tmp_path: Path) -> None:
    target = export_cards(tmp_path / "cards.json")
    payload = json.loads(target.read_text())
    assert set(payload) == set(ROLE_PRESETS)
    assert all("CORE PRINCIPLES" in card for card in payload.values())


# -- tool integration ------------------------------------------------------------
def test_knowledge_tool_in_registry() -> None:
    assert TOOL_NAMES["search_knowledge"] == 1
    tools = {tool.name: tool for tool in build_default_tools(Path("."))}
    assert "search_knowledge" in tools


def test_knowledge_tool_executes_queries() -> None:
    tool = KnowledgeSearchTool()
    assert tool.validate_input({}) != []
    assert tool.validate_input({"query": "owasp"}) == []
    assert tool.check_permissions({}) is True
    result = tool.execute(query="owasp injection", role="security")
    assert result.success and result.data["matches"] > 0
    assert "[security /" in result.output


def test_knowledge_tool_no_matches_is_success_with_zero() -> None:
    result = KnowledgeSearchTool().execute(query="zzzqqqxyzzy")
    assert result.success and result.data["matches"] == 0


# -- prompt injection ---------------------------------------------------------------
def test_system_prompt_injects_knowledge_section() -> None:
    prompt = system_prompt("security", knowledge=knowledge_section("security"))
    assert "PERSONA KNOWLEDGE (skill card):" in prompt
    assert "OWASP" in prompt


def test_system_prompt_without_knowledge_omits_section() -> None:
    prompt = system_prompt("security", knowledge="")
    assert "PERSONA KNOWLEDGE" not in prompt


def test_skill_card_defaults_match_constant() -> None:
    card = skill_card("architect")
    assert len(card) <= DEFAULT_SKILL_CARD_CHARS + len("\n[skill card truncated]")


def test_skill_card_fallback_without_canonical_sections(monkeypatch) -> None:
    """A playbook lacking CORE/PATTERNS still yields a capped card."""
    monkeypatch.setitem(
        PLAYBOOKS, "synthetic-role", "# Synthetic\nBody line one.\nBody line two.\n"
    )
    card = skill_card("synthetic-role")
    assert card.startswith("Body line one.")
    assert "CORE PRINCIPLES" not in card


def test_persona_knowledge_disabled_returns_empty(tmp_path: Path) -> None:
    """knowledge_enabled=False strips the skill card from the agent."""
    from pathlib import Path as _Path

    from harness.agents.llm_agent import LLMAgent, StoreWindow
    from harness.config import BudgetConfig
    from harness.engine.budget import BudgetGovernor
    from harness.infrastructure.context_store import MemoryContextStore
    from harness.infrastructure.model_providers import FakeProvider
    from harness.tools.registry import build_default_tools

    store = MemoryContextStore()
    governor = BudgetGovernor(store, BudgetConfig(total_tokens=10_000), "corr-k")
    agent = LLMAgent(
        agent_id="k-1",
        model_config={"provider": "fake"},
        tools=list(build_default_tools(_Path("."))),
        context_window=StoreWindow(store, "k-1", "t-1"),
        provider=FakeProvider(
            __import__("harness.config", fromlist=["ModelConfig"]).ModelConfig(
                provider="fake", name="f"
            ),
            [],
        ),
        store=store,
        governor=governor,
        role="security",
        knowledge_enabled=False,
    )
    assert agent._persona_knowledge() == ""
    agent.knowledge_enabled = True
    assert "OWASP" in agent._persona_knowledge()
