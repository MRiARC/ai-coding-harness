"""Persona knowledge registry (issue #78).

Loads the curated per-persona playbooks from `knowledge/corpus/`, extracts
bounded **skill cards** for system-prompt injection, and provides lexical
**corpus search** so any persona can consult any other persona's book.

Design constraints (M5 token diet, #61):
- The skill card is capped (`DEFAULT_SKILL_CARD_CHARS`) — always-on
  expertise without blowing the prompt budget.
- The full playbook stays in the package and is reachable on demand via
  the `search_knowledge` tool — depth when the model asks for it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness.agents.prompts import ROLE_PRESETS

CORPUS_DIR = Path(__file__).parent / "corpus"
DEFAULT_SKILL_CARD_CHARS = 1500
DEFAULT_SEARCH_LIMIT = 6
_MAX_LINE_LEN = 220


def _load_all() -> dict[str, str]:
    """Load every corpus playbook keyed by its ROLE_PRESETS role name.

    Files are named exactly after the role (`architect.md`, ...); roles
    without a file are absent from the mapping (the loader returns "").
    """
    playbooks: dict[str, str] = {}
    for role in ROLE_PRESETS:
        path = CORPUS_DIR / f"{role}.md"
        if path.is_file():
            playbooks[role] = path.read_text(encoding="utf-8")
    return playbooks


PLAYBOOKS = _load_all()


def load_playbook(role: str) -> str:
    """Full playbook text for `role`; empty string when none exists."""
    return PLAYBOOKS.get(role, "")


def skill_card(role: str, max_chars: int = DEFAULT_SKILL_CARD_CHARS) -> str:
    """Bounded always-on expertise: CORE PRINCIPLES + CHECKLIST sections.

    Falls back to the first `max_chars` characters of the playbook when the
    canonical sections are missing. Returns "" for unknown roles.
    """
    playbook = load_playbook(role)
    if not playbook:
        return ""
    core_start = playbook.find("## CORE PRINCIPLES")
    patterns_start = playbook.find("## PATTERNS")
    if core_start >= 0 and patterns_start > core_start:
        card = playbook[core_start:patterns_start].rstrip()
    else:
        body = playbook.splitlines()[1:] if "\n" in playbook else [playbook]
        card = "\n".join(body)
    if len(card) > max_chars:
        card = card[:max_chars].rsplit("\n", 1)[0] + "\n[skill card truncated]"
    return card


def knowledge_section(role: str, max_chars: int = DEFAULT_SKILL_CARD_CHARS) -> str:
    """The system-prompt fragment for `role` (empty when disabled/unknown)."""
    card = skill_card(role, max_chars)
    if not card:
        return ""
    return "PERSONA KNOWLEDGE (skill card):\n" + card


def search_knowledge(
    query: str, role: str | None = None, limit: int = DEFAULT_SEARCH_LIMIT
) -> list[dict[str, str]]:
    """Lexical search over the corpus; most persona books first when scoped.

    Returns up to `limit` findings: `{"role", "section", "line"}`. Scoring is
    simple term overlap — deterministic, dependency-free, good enough to
    surface the right checklist row without an embedding stack.
    """
    terms = [term.lower() for term in query.split() if len(term) > 2]
    if not terms:
        return []
    books: list[tuple[str, str]] = (
        [(role, load_playbook(role))] if role and load_playbook(role) else sorted(PLAYBOOKS.items())
    )
    scored: list[tuple[int, str, str, str]] = []
    for book_role, playbook in books:
        current_section = ""
        for line in playbook.splitlines():
            if line.startswith("## "):
                current_section = line[3:].strip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            lowered = stripped.lower()
            score = sum(1 for term in terms if term in lowered)
            if score:
                display = (
                    stripped if len(stripped) <= _MAX_LINE_LEN else stripped[:_MAX_LINE_LEN] + "…"
                )
                scored.append((score, book_role, current_section, display))
    scored.sort(key=lambda item: (-item[0], item[1], item[3]))
    return [
        {"role": book_role, "section": section, "line": line}
        for _, book_role, section, line in scored[: max(1, limit)]
    ]


def knowledge_summary() -> dict[str, Any]:
    """Registry introspection: roles covered and playbook sizes (bytes)."""
    return {role: len(playbook) for role, playbook in sorted(PLAYBOOKS.items())}


def export_cards(path: Path, max_chars: int = DEFAULT_SKILL_CARD_CHARS) -> Path:
    """Export all skill cards as one JSON document (platform/evidence use)."""
    payload = {role: skill_card(role, max_chars) for role in sorted(PLAYBOOKS)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path
