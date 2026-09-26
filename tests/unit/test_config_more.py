"""Extended config tests: empty files, path resolution edges (issue 1.3)."""

from __future__ import annotations

from harness.config import ConfigLoader, load_config


def test_empty_yaml_file_yields_defaults(isolated_env) -> None:
    (isolated_env / "harness.yaml").write_text("")  # parses as None
    config = load_config()
    assert config.version == 1
    assert config.budget.total_tokens == 2_000_000


def test_explicit_path_missing_falls_back_to_defaults(isolated_env) -> None:
    loader = ConfigLoader(isolated_env / "nope.yaml")
    assert loader.resolve_path() is None
    config = loader.load()  # missing explicit file -> defaults, not an error
    assert config.storage.backend == "sqlite"


def test_resolve_path_defaults_order(isolated_env) -> None:
    (isolated_env / "harness.example.yaml").write_text("run:\n  max_steps: 3\n")
    resolved = ConfigLoader().resolve_path()
    assert resolved is not None and resolved.name == "harness.example.yaml"


def test_repo_example_config_is_always_valid() -> None:
    """The committed config.example.yaml must never rot."""
    from pathlib import Path

    example = Path(__file__).resolve().parents[2] / "config.example.yaml"
    config = load_config(example)
    assert {a.role for a in config.agents} == {
        "architect",
        "manager",
        "locator",
        "implementer",
        "verifier",
    }
    assert config.models["default"].api_key_env == "AI_API_KEY"
