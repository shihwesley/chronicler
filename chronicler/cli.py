"""CLI entry point for Chronicler."""

import typer

app = typer.Typer(
    name="chronicler",
    help="Automated changelog and release notes generator from VCS history.",
)


@app.command()
def generate(
    repo: str = typer.Argument(..., help="Repository path or URL"),
    since: str = typer.Option(None, help="Start date or tag"),
    until: str = typer.Option(None, help="End date or tag"),
) -> None:
    """Generate changelog from repository history."""
    typer.echo(f"Generating changelog for {repo}...")


@app.command()
def init(
    path: str = typer.Argument(".", help="Project path to initialize"),
) -> None:
    """Initialize Chronicler configuration in a project."""
    typer.echo(f"Initializing Chronicler config in {path}...")


if __name__ == "__main__":
    app()
