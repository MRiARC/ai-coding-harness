"""Command-line entry point.

- `harness doctor [--probe-model]` - validate the runtime environment
  (`make setup` target; the model probe is opt-in because it costs tokens)
- `harness run` - TUI cockpit on a TTY, headless health summary otherwise
- `harness replay [RUN_ID]` - replay a recorded evidence trace offline
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from harness import __version__
from harness.config import ConfigError, ConfigLoader

API_KEY_ENV = "AI_API_KEY"


def doctor(probe_model: bool = False) -> int:
    """Check the runtime environment. Warn-only about a missing API key so
    `make setup` never fails on machines that only run offline tests."""
    from harness.monitoring.health import run_health_checks

    print(f"harness {__version__}")
    loader = ConfigLoader()
    path = loader.resolve_path()
    if path is None:
        print("[warn] no configuration file found; using built-in defaults")
        print(
            f"[warn] environment variable {API_KEY_ENV} is not set; "
            "the harness will run in offline/test mode only"
        )
        print("[ok] environment ready")
        return 0

    try:
        config = loader.load()
    except ConfigError as exc:
        print(f"[error] configuration invalid:\n{exc}")
        return 1

    print(f"[ok] configuration valid: {path}")
    default_model = config.models.get("default")
    key_env = default_model.api_key_env if default_model else API_KEY_ENV
    if not os.environ.get(key_env):
        print(
            f"[warn] environment variable {key_env} is not set; "
            "the harness will run in offline/test mode only"
        )
    report = run_health_checks(Path.cwd(), config_path=path, model_probe=probe_model)
    for check in report.checks:
        if check["name"] == "model-api":
            mark = "ok" if check["ok"] else "warn"
            print(f"[{mark}] model probe: {check['detail']}")
    print("[ok] environment ready")
    return 0


def run_command() -> int:
    """`make run`: TUI cockpit on a TTY, headless health summary otherwise."""
    from harness.monitoring.health import run_health_checks

    report = run_health_checks(Path.cwd())
    if sys.stdin.isatty():
        from harness.engine.evidence import find_evidence
        from harness.ui.tui import CockpitApp

        pack = find_evidence(Path.cwd() / "results") or _adhoc_pack()
        CockpitApp(pack).run()
        return 0
    print(report.summary())
    print("[info] no TTY detected; headless mode. Pipe an issue or use a terminal for the cockpit.")
    return 0 if report.ready else 1


def _adhoc_pack() -> Any:  # EvidencePack; late import keeps CLI startup light
    from harness.engine.evidence import EvidencePack

    return EvidencePack(Path.cwd() / "results", "adhoc")


def replay_command(run_id: str | None) -> int:
    """Replay a recorded evidence trace (offline demo / post-run audit)."""
    from harness.engine.evidence import find_evidence
    from harness.ui.tui import format_event

    pack = find_evidence(Path.cwd() / "results", run_id)
    if pack is None:
        print("[error] no evidence pack found under results/; run the pipeline first")
        return 1
    events = pack.read_trace()
    if sys.stdin.isatty():
        from harness.ui.tui import CockpitApp

        CockpitApp(pack).run()
        return 0
    for event in events:
        print(format_event(event))
    print(f"[ok] replayed {pack.run_id} ({len(events)} events) - headless mode")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness", description=__doc__)
    parser.add_argument("--version", action="version", version=f"harness {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor_parser = subparsers.add_parser("doctor", help="validate the runtime environment")
    doctor_parser.add_argument(
        "--probe-model",
        action="store_true",
        help="make one tiny live model call (costs tokens; offline CI omits this)",
    )
    subparsers.add_parser(
        "run", help="launch the harness (TUI on a TTY, headless summary otherwise)"
    )
    replay_parser = subparsers.add_parser(
        "replay", help="replay a recorded evidence trace (default: most recent)"
    )
    replay_parser.add_argument("run_id", nargs="?", default=None)

    args = parser.parse_args(argv)
    if args.command == "doctor":
        return doctor(probe_model=args.probe_model)
    if args.command == "replay":
        return replay_command(args.run_id)
    return run_command()


if __name__ == "__main__":
    sys.exit(main())
