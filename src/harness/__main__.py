"""Enable `python -m harness` (the Makefile's `run` target)."""

from harness.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
