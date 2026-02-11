"""Thin CLI wrapper for chronicler-lite skill modules.

Usage:
    python -m chronicler_lite.cli init --path <workspace>
    python -m chronicler_lite.cli regenerate --path <workspace>
    python -m chronicler_lite.cli status --path <workspace> [--format json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def cmd_init(args: argparse.Namespace) -> None:
    from chronicler_lite.skill.init import main as init_main

    init_main(args.path)


def cmd_regenerate(args: argparse.Namespace) -> None:
    from chronicler_lite.skill.regenerate import main as regen_main

    # regenerate.main() uses cwd as root; chdir so --path is respected
    os.chdir(args.path)
    regen_main(None)


def cmd_status(args: argparse.Namespace) -> None:
    if args.format == "json":
        from chronicler_core.freshness import check_staleness

        root = Path(args.path).resolve()
        report = check_staleness(root)
        data = {
            "stale_count": len(report.stale),
            "total_count": report.total_files,
        }
        print(json.dumps(data))
    else:
        from chronicler_lite.skill.status import main as status_main

        status_main(args.path)


def main() -> None:
    parser = argparse.ArgumentParser(prog="chronicler-lite")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialize project")
    p_init.add_argument("--path", required=True, help="Workspace root path")
    p_init.set_defaults(func=cmd_init)

    # regenerate
    p_regen = sub.add_parser("regenerate", help="Regenerate stale docs")
    p_regen.add_argument("--path", required=True, help="Workspace root path")
    p_regen.set_defaults(func=cmd_regenerate)

    # status
    p_status = sub.add_parser("status", help="Show staleness report")
    p_status.add_argument("--path", required=True, help="Workspace root path")
    p_status.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    try:
        args.func(args)
    except FileNotFoundError:
        print(f"Error: directory not found: {args.path}", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: permission denied: {args.path}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
