"""Read and update chronicler.yaml configuration."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def _set_nested(data: dict, dotted_key: str, value: str) -> None:
    """Set a value in a nested dict using dot notation (e.g., 'llm.provider')."""
    keys = dotted_key.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]

    # Try to preserve types: booleans, ints, floats
    final_key = keys[-1]
    if value.lower() in ("true", "false"):
        current[final_key] = value.lower() == "true"
    elif value.isdigit():
        current[final_key] = int(value)
    else:
        try:
            current[final_key] = float(value)
        except ValueError:
            current[final_key] = value


def main(args: list[str] | None = None) -> None:
    if args is None:
        args = sys.argv[1:]

    config_path = Path("chronicler.yaml")
    if not config_path.exists():
        print("No chronicler.yaml found. Run `/chronicler init` first.")
        sys.exit(1)

    data = yaml.safe_load(config_path.read_text()) or {}

    if not args:
        # No args: just print the current config
        print(yaml.dump(data, default_flow_style=False, sort_keys=False))
        return

    # Parse key=value pairs
    for arg in args:
        if "=" not in arg:
            print(f"Invalid argument (expected key=value): {arg}")
            sys.exit(1)
        key, value = arg.split("=", 1)
        _set_nested(data, key.strip(), value.strip())
        print(f"  Set {key.strip()} = {value.strip()}")

    config_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    print(f"\nUpdated chronicler.yaml:")
    print(yaml.dump(data, default_flow_style=False, sort_keys=False))


if __name__ == "__main__":
    main()
