"""Workspace state placement (M6: product-grade posture).

Project-scoped work keeps state next to the project (`<scope>/.harness/`).
Broad workspaces — the home directory itself, its well-known user folders,
or temp dirs — get a hash-scoped state root under `~/.foreman/` instead, so
chatting against your Desktop never litters it with hidden harness folders.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

BROAD_DIR_NAMES = {"Desktop", "Documents", "Downloads", "Projects", "Pictures", "Music", "Movies", "Public"}


def is_broad_scope(scope: Path) -> bool:
    """Whether the scope is too broad/general to hold state inside itself."""
    scope = Path(scope).expanduser().resolve()
    home = Path.home().resolve()
    if scope == home:
        return True
    try:
        rel = scope.relative_to(home)
    except ValueError:
        return str(scope).startswith(("/tmp", "/private/tmp", "/var/folders"))
    # top-level home folders (Desktop/…) or anything directly under home
    return len(rel.parts) == 1 or rel.parts[0] in BROAD_DIR_NAMES


def state_root(scope: Path) -> Path:
    """Where harness state (chat.db, processes, results) lives for a scope."""
    scope = Path(scope).expanduser().resolve()
    if is_broad_scope(scope):
        digest = hashlib.sha1(str(scope).encode()).hexdigest()[:10]
        return Path.home() / ".foreman" / digest
    return scope / ".harness"
