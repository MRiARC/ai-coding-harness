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


def test_postgres_backend_rejected_at_validation() -> None:
    """Audit §15: the unimplemented postgres backend fails fast, clearly."""
    import pytest

    from harness.config import ConfigError, ConfigLoader, HarnessConfig

    config = HarnessConfig.model_validate(
        {
            "models": {"default": {"provider": "fake", "name": "m"}},
            "storage": {"backend": "postgres"},
        }
    )
    errors = config.validate_references()
    assert any("not supported in eval mode" in error for error in errors)

    # And the loader surfaces it as a ConfigError with the same message.
    from pathlib import Path as _Path

    bad = _Path("bad-harness.yaml")
    bad.write_text("storage:\n  backend: postgres\n")
    with pytest.raises(ConfigError) as excinfo:
        ConfigLoader(bad).load()
    assert "not supported in eval mode" in str(excinfo.value)
    bad.unlink()


def test_pinned_runtime_dependencies() -> None:
    """Audit §16: runtime deps are exact pins, not open ranges."""
    from pathlib import Path

    text = (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text()
    for package in ("pydantic==", "PyYAML==", "httpx==", "structlog==", "textual=="):
        assert package in text
    assert "pydantic>=" not in text
