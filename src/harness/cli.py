"""Command-line entry point.

`harness doctor` validates the runtime environment (Python version, API key
presence, configuration file) and is the target of `make run` until the agent
orchestration lands.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from harness import __version__
from harness.config import ConfigError, ConfigLoader

API_KEY_ENV = "AI_API_KEY"


def doctor() -> int:
    """Check the runtime environment. Warn-only about a missing API key so
    `make setup` never fails on machines that only run offline tests."""
    print(f"harness {__version__}")
    problems: list[str] = []

    loader = ConfigLoader()
    path = loader.resolve_path()
    if path is None:
        print("[warn] no configuration file found; using built-in defaults")
        print(
            f"[warn] environment variable {API_KEY_ENV} is not set; "
            "the harness will run in offline/test mode only"
        )
    else:
        try:
            config = loader.load()
        except ConfigError as exc:
            problems.append(f"configuration invalid:\n{exc}")
        else:
            print(f"[ok] configuration valid: {path}")
            default_model = config.models.get("default")
            key_env = default_model.api_key_env if default_model else API_KEY_ENV
            if not os.environ.get(key_env):
                print(
                    f"[warn] environment variable {key_env} is not set; "
                    "the harness will run in offline/test mode only"
                )

    for problem in problems:
        print(f"[error] {problem}")
    if problems:
        return 1
    print("[ok] environment ready")
    return 0


def run_command() -> int:
    """`make run`: TUI cockpit on a TTY, headless health summary otherwise."""
    from harness.monitoring.health import run_health_checks

    report = run_health_checks(Path.cwd())
    if sys.stdin.isatty():
        from harness.engine.evidence import EvidencePack
        from harness.ui.tui import CockpitApp, latest_evidence

        pack = latest_evidence(Path.cwd() / "results") or EvidencePack(
            Path.cwd() / "results", "adhoc"
        )
        app = CockpitApp(pack)
        app.run()
        return 0
    print(report.summary())
    print("[info] no TTY detected; headless mode. Pipe an issue or use a terminal for the cockpit.")
    return 0 if report.ready else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness", description=__doc__)
    parser.add_argument("--version", action="version", version=f"harness {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="validate the runtime environment")
    subparsers.add_parser(
        "run", help="launch the harness (TUI on a TTY, headless summary otherwise)"
    )
    args = parser.parse_args(argv)

    commands = {"doctor": doctor, "run": run_command}
    return commands[args.command]()


if __name__ == "__main__":
    sys.exit(main())
