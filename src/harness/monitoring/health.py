"""Health checks (milestone 3, issue 3.12).

Liveness (is the process alive?) is trivially yes; the substance is
readiness: can this harness actually run in THIS environment? Each check is
cheap, offline-friendly, and returns a named status so the TUI and the
doctor command share one implementation.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class HealthReport:
    checks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return all(check["ok"] for check in self.checks if check["required"])

    def summary(self) -> str:
        lines = [f"{'PASS' if c['ok'] else 'FAIL'} {c['name']}: {c['detail']}" for c in self.checks]
        lines.append(f"READY: {self.ready}")
        return "\n".join(lines)


def run_health_checks(
    repo_root: Path, config_path: Path | None = None, require_api_key: bool = False
) -> HealthReport:
    """Probe the environment: store, config, credentials, git, results dir."""
    report = HealthReport()

    def check(name: str, ok: bool, detail: str, required: bool = True) -> None:
        report.checks.append({"name": name, "ok": ok, "detail": detail, "required": required})

    # git available (the harness's primary write surface)
    git = shutil.which("git")
    check("git", git is not None, git or "git executable not found")

    # configuration loads
    try:
        from harness.config import load_config

        config = load_config(config_path)
        check(
            "config",
            True,
            f"model '{config.models['default'].name}' "
            f"provider '{config.models['default'].provider}'",
        )
        # credential presence (warn-only unless the caller demands it)
        key_env = config.models["default"].api_key_env
        has_key = bool(os.environ.get(key_env))
        check(
            "api-key",
            has_key or not require_api_key,
            f"env '{key_env}' {'set' if has_key else 'not set (offline/test mode)'}",
            required=require_api_key,
        )
    except Exception as exc:
        check("config", False, str(exc)[:200])

    # store backend writable
    try:
        from harness.infrastructure.context_store import SQLiteContextStore

        probe = SQLiteContextStore(Path(repo_root) / ".harness" / "health-probe.db")
        probe.save_global("probe", {"ok": True})
        ok = probe.load_global("probe") == {"ok": True}
        probe.close()
        (Path(repo_root) / ".harness" / "health-probe.db").unlink(missing_ok=True)
        check("context-store", ok, "sqlite read/write ok")
    except Exception as exc:
        check("context-store", False, str(exc)[:200])

    # results directory writable
    try:
        results = Path(repo_root) / "results"
        results.mkdir(parents=True, exist_ok=True)
        probe_file = results / ".health-probe"
        probe_file.write_text("ok")
        ok = probe_file.read_text() == "ok"
        probe_file.unlink(missing_ok=True)
        check("results-dir", ok, str(results))
    except Exception as exc:
        check("results-dir", False, str(exc)[:200])

    # model API reachability is deliberately NOT probed here: it costs tokens
    # and the FakeProvider path must stay fully offline.
    return report
