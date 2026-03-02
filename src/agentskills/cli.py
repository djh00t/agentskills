"""Command-line interface for agentskills tool distribution."""

from __future__ import annotations

import sys

from agentskills.installer import build_parser


def main() -> int:
    """Runs the agentskills CLI."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except (ValueError, FileNotFoundError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
