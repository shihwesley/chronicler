# CLI Interface Design for Chronicler

**Date:** 2026-01-23
**Status:** Proposed
**Author:** Claude + User

## Summary

Subcommand-based CLI using `chronicler` as the command name. Supports crawling, drafting, validation, and configuration management.

## Command Tree

```
chronicler
├── init                    # Initialize config in current dir
├── crawl
│   ├── org <org-name>      # Discover all repos in org
│   ├── repo <owner/repo>   # Single repo
│   └── list                # Show queued/in-progress jobs
├── draft
│   ├── <owner/repo>        # Generate .tech.md for repo
│   └── --local <path>      # Generate for local directory
├── validate
│   ├── <file.tech.md>      # Validate single file
│   └── --all               # Validate all in .chronicler/
├── status                  # Show queue status, rate limits
└── config
    ├── show                # Print current config
    └── set <key> <value>   # Update config
```

## Common Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--config` | `-c` | Custom config file path |
| `--dry-run` | `-n` | Preview without writing |
| `--verbose` | `-v` | Detailed output |
| `--json` | | Machine-readable output |
| `--help` | `-h` | Show help |

## Command Details

### `chronicler init`

Creates `chronicler.yaml` in current directory with defaults.

```bash
chronicler init
# Creates ./chronicler.yaml with commented defaults
```

### `chronicler crawl org <org-name>`

Discovers all repos in a GitHub organization, queues them for processing.

```bash
chronicler crawl org my-company
# Queues all repos in my-company org
# Use `chronicler status` to monitor progress
```

### `chronicler crawl repo <owner/repo>`

Queues a single repo for processing.

```bash
chronicler crawl repo my-company/auth-service
```

### `chronicler draft <owner/repo>`

Generates `.tech.md` for a repo (fetches from GitHub).

```bash
chronicler draft my-company/auth-service
# Outputs to ./.chronicler/auth-service.api.tech.md
```

### `chronicler draft --local <path>`

Generates `.tech.md` for a local directory.

```bash
chronicler draft --local ./my-project
# Analyzes local files, no GitHub API calls
```

### `chronicler validate <file>`

Validates a `.tech.md` file against the schema.

```bash
chronicler validate .chronicler/auth-service.api.tech.md
# Checks YAML schema + Mermaid syntax
```

### `chronicler status`

Shows queue status and API rate limits.

```bash
chronicler status
# Queue: 12 pending, 3 in-progress, 45 completed
# GitHub API: 4,521/5,000 remaining (resets in 42m)
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Validation failed |
| 2 | Configuration error |
| 3 | API error (rate limit, auth) |
| 4 | Queue error |

## Implementation

Using `click` or `typer` for Python CLI:

```python
import typer

app = typer.Typer()
crawl_app = typer.Typer()
app.add_typer(crawl_app, name="crawl")

@crawl_app.command("org")
def crawl_org(org_name: str, dry_run: bool = False):
    """Discover and queue all repos in an organization."""
    ...

@app.command()
def draft(
    repo: str = typer.Argument(None),
    local: str = typer.Option(None, "--local", "-l"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n"),
):
    """Generate .tech.md for a repository."""
    ...
```

## Dependencies

```
typer>=0.12.0
rich>=13.0.0  # For pretty output
```
