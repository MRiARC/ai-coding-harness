"""Milestone 4.6: dependency-safe execution batching (audit §11).

The scheduler must combine the dependency DAG with file-set disjointness:
dependencies gate batch entry, unknown/empty file-sets force solo batches,
and a dependency cycle degrades to sequential instead of misparallelizing.
"""

from __future__ import annotations

from harness.agents.architect import SubTask
from harness.agents.manager import execution_batches


def test_dependency_gates_batch_entry() -> None:
    """B depends on A with disjoint files: B never shares A's batch."""
    a = SubTask(id="a", title="A", description="", files=["api.py"])
    b = SubTask(id="b", title="B", description="", files=["client.py"], depends_on=["a"])
    batches = execution_batches([a, b])
    assert [[s.id for s in batch] for batch in batches] == [["a"], ["b"]]


def test_disjoint_independent_subtasks_still_parallelize() -> None:
    a = SubTask(id="a", title="A", description="", files=["api.py"])
    b = SubTask(id="b", title="B", description="", files=["ui.py"])
    batches = execution_batches([a, b])
    assert [[s.id for s in batch] for batch in batches] == [["a", "b"]]


def test_empty_file_set_never_runs_parallel() -> None:
    """Unknown footprint = solo batch, even with no conflicts possible."""
    a = SubTask(id="a", title="A", description="", files=["api.py"])
    b = SubTask(id="b", title="B", description="", files=[])
    c = SubTask(id="c", title="C", description="", files=["ui.py"])
    batches = execution_batches([a, b, c])
    assert [[s.id for s in batch] for batch in batches] == [["a", "c"], ["b"]]


def test_overlapping_files_stay_sequential() -> None:
    a = SubTask(id="a", title="A", description="", files=["core.py"])
    b = SubTask(id="b", title="B", description="", files=["core.py"])
    batches = execution_batches([a, b])
    assert [[s.id for s in batch] for batch in batches] == [["a"], ["b"]]


def test_dependency_cycle_degrades_to_sequential() -> None:
    """A cycle must terminate as solo batches, not hang or parallelize."""
    a = SubTask(id="a", title="A", description="", files=["a.py"], depends_on=["b"])
    b = SubTask(id="b", title="B", description="", files=["b.py"], depends_on=["a"])
    batches = execution_batches([a, b])
    assert [[s.id for s in batch] for batch in batches] == [["a"], ["b"]]


def test_unknown_dependency_id_is_ignored() -> None:
    """A depends_on id outside the plan does not deadlock the scheduler."""
    a = SubTask(id="a", title="A", description="", files=["api.py"], depends_on=["ghost"])
    batches = execution_batches([a])
    assert [[s.id for s in batch] for batch in batches] == [["a"]]


def test_chained_dependencies_run_in_order() -> None:
    """A -> B -> C chain yields three sequential batches in plan order."""
    a = SubTask(id="a", title="A", description="", files=["one.py"])
    b = SubTask(id="b", title="B", description="", files=["two.py"], depends_on=["a"])
    c = SubTask(id="c", title="C", description="", files=["three.py"], depends_on=["b"])
    batches = execution_batches([c, b, a])
    assert [[s.id for s in batch] for batch in batches] == [["a"], ["b"], ["c"]]


def test_bugfix_specialty_routes_to_implementer_not_locator() -> None:
    """Live-run regression (M4 #58): 'bugfix' tasks must reach an
    editing-capable role, never tie onto the read-only Locator."""
    from harness.agents.manager import (
        SpecialistSlot,
        assign_specialists,
    )
    from harness.agents.task import Task

    locator = SpecialistSlot(
        agent_id="locator-1",
        specialties={"implementer", "localization", "code-navigation"},  # weak_specialties
        role="locator",
    )
    implementer = SpecialistSlot(
        agent_id="impl-1",
        specialties={"implementer", "backend-api", "database", "frontend", "refactoring"},
        role="implementer",
    )
    task = Task(id="t", title="Fix add()", description="", specialty="bugfix")
    chosen = assign_specialists(task, [locator, implementer])
    assert chosen == ["impl-1"]


def test_role_matches_specialty_synonyms() -> None:
    from harness.agents.manager import role_matches_specialty

    assert role_matches_specialty("implementer", "bugfix")
    assert role_matches_specialty("implementer", "fix")
    assert not role_matches_specialty("locator", "bugfix")
    assert not role_matches_specialty("implementer", None)
