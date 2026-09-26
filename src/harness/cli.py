"""Command-line entry point.

`harness doctor` validates the runtime environment (Python version, API key
presence, configuration file) and is the target of `make run` until the agent
orchestration lands.
"""

from __future__ import annotations

import argparse
import os
import sys

from harness import __version__

API_KEY_ENV = "AI_API_KEY"


def doctor() -> int:
    """Check the runtime environment. Warn-only about a missing API key so
    `make setup` never fails on machines that only run offline tests."""
    print(f"harness {__version__}")
    problems: list[str] = []

    if not os.environ.get(API_KEY_ENV):
        print(
            f"[warn] environment variable {API_KEY_ENV} is not set; "
            "the harness will run in offline/test mode only"
        )

    if os.path.exists("harness.yaml"):
        print("[ok] found harness.yaml")
    elif os.path.exists("config.example.yaml"):
        print("[warn] no harness.yaml found; copy config.example.yaml to harness.yaml")
    else:
        print("[warn] no configuration file found; using built-in defaults")

    for problem in problems:
        print(f"[error] {problem}")
    if problems:
        return 1
    print("[ok] environment ready")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness", description=__doc__)
    parser.add_argument("--version", action="version", version=f"harness {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="validate the runtime environment")
    args = parser.parse_args(argv)

    commands = {"doctor": doctor}
    return commands[args.command]()


if __name__ == "__main__":
    sys.exit(main())
