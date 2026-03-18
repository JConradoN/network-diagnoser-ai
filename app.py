"""Network Diagnoser AI main entrypoint."""

from __future__ import annotations

import sys

from cli import main as cli_main


def main() -> int:
    """Run robust CLI. Defaults to 'scan' when no subcommand is provided."""
    argv = sys.argv[1:]
    if not argv:
        argv = ["scan"]
    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

