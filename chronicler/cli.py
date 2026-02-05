"""CLI entry point for Chronicler."""

from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.syntax import Syntax

from .config import ChroniclerConfig, load_config
from .config.loader import DEFAULT_CONFIG_TEMPLATE

app = typer.Typer(
    name="chronicler",
    help="Living Technical Ledger — auto-generate .tech.md for your repos.",
)

config_app = typer.Typer(help="Manage Chronicler configuration.")
app.add_typer(config_app, name="config")

# Global state
_config: ChroniclerConfig | None = None


def _get_config() -> ChroniclerConfig:
    if _config is None:
        return load_config()
    return _config


@app.callback()
def main(
    config: Annotated[
        str | None, typer.Option("--config", "-c", help="Path to chronicler.yaml")
    ] = None,
) -> None:
    """Global options."""
    global _config
    _config = load_config(config)


@app.command()
def crawl(
    repo: str = typer.Argument(..., help="Repository path, URL, or org/repo"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
) -> None:
    """Crawl a repository and collect metadata."""
    cfg = _get_config()
    rprint(f"[bold]Crawling[/bold] {repo} (provider: {cfg.vcs.provider})...")


@app.command()
def draft(
    repo: str = typer.Argument(..., help="Repository to generate .tech.md for"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
) -> None:
    """Generate .tech.md from crawled data."""
    cfg = _get_config()
    rprint(f"[bold]Drafting[/bold] .tech.md for {repo} (llm: {cfg.llm.provider})...")


@app.command()
def validate(
    path: str = typer.Argument(".chronicler", help="Path to .chronicler directory"),
) -> None:
    """Validate .tech.md files against schema."""
    rprint(f"[bold]Validating[/bold] {path}...")


@config_app.command("show")
def config_show() -> None:
    """Show current resolved configuration."""
    import yaml

    cfg = _get_config()
    rprint(Syntax(yaml.dump(cfg.model_dump(), default_flow_style=False), "yaml"))


@config_app.command("init")
def config_init(
    force: bool = typer.Option(False, "--force", help="Overwrite existing config"),
) -> None:
    """Create default chronicler.yaml in current directory."""
    target = Path("chronicler.yaml")
    if target.exists() and not force:
        rprint("[yellow]chronicler.yaml already exists.[/yellow] Use --force to overwrite.")
        raise typer.Exit(1)
    target.write_text(DEFAULT_CONFIG_TEMPLATE)
    rprint(f"[green]Created[/green] {target}")


if __name__ == "__main__":
    app()
