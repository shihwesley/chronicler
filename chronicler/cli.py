"""CLI entry point for Chronicler."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

from .config import ChroniclerConfig, load_config
from .config.loader import DEFAULT_CONFIG_TEMPLATE
from .converter import DocumentConverter, should_convert
from .vcs import CrawlResult, VCSCrawler, create_provider
from .vcs.models import RepoMetadata

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


def _top_languages(languages: dict[str, int], n: int = 3) -> str:
    """Return top N languages sorted by bytes, formatted as comma-separated string."""
    sorted_langs = sorted(languages.items(), key=lambda x: x[1], reverse=True)[:n]
    return ", ".join(lang for lang, _ in sorted_langs) if sorted_langs else "-"


def _format_size(size_kb: int) -> str:
    """Format repo size (GitHub reports in KB) to human-readable."""
    if size_kb < 1024:
        return f"{size_kb} KB"
    return f"{size_kb / 1024:.1f} MB"


def _display_repo_list(repos: list[RepoMetadata]) -> None:
    """Display org/user repos as a Rich table."""
    table = Table(title=f"Repositories ({len(repos)})")
    table.add_column("Name", style="cyan")
    table.add_column("Languages", style="green")
    table.add_column("Size", justify="right")
    table.add_column("Topics", style="yellow")
    for r in repos:
        table.add_row(
            r.full_name,
            _top_languages(r.languages),
            _format_size(r.size),
            ", ".join(r.topics) if r.topics else "-",
        )
    rprint(table)


def _display_crawl_result(result: CrawlResult) -> None:
    """Display single-repo crawl result with metadata panel and file tree."""
    m = result.metadata
    lang_str = _top_languages(m.languages, n=5)
    topics_str = ", ".join(m.topics) if m.topics else "none"
    panel_text = (
        f"[bold]{m.full_name}[/bold]\n"
        f"{m.description or '(no description)'}\n\n"
        f"[dim]Branch:[/dim]    {m.default_branch}\n"
        f"[dim]Languages:[/dim] {lang_str}\n"
        f"[dim]Size:[/dim]      {_format_size(m.size)}\n"
        f"[dim]Topics:[/dim]    {topics_str}\n"
        f"[dim]URL:[/dim]       {m.url}"
    )
    rprint(Panel(panel_text, title="Repository Metadata", border_style="blue"))

    # Key files tree
    tree = Tree(f"[bold]Key Files[/bold] ({len(result.key_files)})")
    for path, content in sorted(result.key_files.items()):
        size_str = f" ({len(content)} bytes)" if content else ""
        tree.add(f"[green]{path}[/green]{size_str}")
    rprint(tree)

    # Converted documents
    if result.converted_docs:
        doc_tree = Tree(f"[bold]Converted Documents[/bold] ({len(result.converted_docs)})")
        for path, md in sorted(result.converted_docs.items()):
            doc_tree.add(f"[magenta]{path}[/magenta] ({len(md)} chars)")
        rprint(doc_tree)


def _validate_repo_id(repo_id: str) -> tuple[str, str]:
    """Validate and split a repo identifier into (owner, repo_name).

    Raises ValueError if format is invalid.
    """
    parts = repo_id.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError(f"Invalid repo identifier '{repo_id}': expected 'owner/repo'")
    return parts[0], parts[1]


def _cache_result(result: CrawlResult, base_dir: str) -> Path:
    """Cache CrawlResult to .chronicler/cache/{owner}/{repo}.json."""
    owner, repo_name = _validate_repo_id(result.metadata.full_name)
    # Sanitize path components to prevent traversal
    owner = owner.replace("..", "_").replace("/", "_").replace("\\", "_")
    repo_name = repo_name.replace("..", "_").replace("/", "_").replace("\\", "_")
    cache_dir = Path(base_dir) / "cache" / owner
    cache_path = cache_dir / f"{repo_name}.json"
    # Validate path before creating directories
    if not cache_path.resolve().is_relative_to(Path(base_dir).resolve()):
        raise ValueError(f"Cache path escapes base directory: {cache_path}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(result.model_dump_json(indent=2))
    return cache_path


@app.command()
def crawl(
    repo: str = typer.Argument(..., help="Repository path, URL, or org/repo"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
    include_docs: bool | None = typer.Option(
        None, "--include-docs/--no-docs", help="Convert documents found in repo"
    ),
) -> None:
    """Crawl a repository and collect metadata."""
    cfg = _get_config()
    do_docs = include_docs if include_docs is not None else cfg.document_conversion.enabled
    rprint(f"[bold]Crawling[/bold] {repo} (provider: {cfg.vcs.provider})...")

    try:
        provider = create_provider(cfg.vcs)
    except ValueError as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    crawler = VCSCrawler(provider, cfg.vcs)
    is_single_repo = "/" in repo

    if is_single_repo:
        try:
            _validate_repo_id(repo)
        except ValueError as e:
            rprint(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

    try:
        if is_single_repo:
            if dry_run:
                # Dry run: show metadata + tree but skip key file content
                metadata = asyncio.run(provider.get_repo_metadata(repo))
                tree_nodes = asyncio.run(provider.get_file_tree(repo))
                result = CrawlResult(metadata=metadata, tree=tree_nodes, key_files={})
                rprint("[yellow](dry run — key file content not fetched)[/yellow]\n")
                _display_crawl_result(result)
            else:
                result = asyncio.run(crawler.crawl_repo(repo))
                # Document conversion (local repos only)
                if do_docs and _is_local_repo(repo):
                    result = _convert_repo_docs(result, cfg)
                elif do_docs:
                    rprint("[dim]Document conversion available for local repos only[/dim]")
                _display_crawl_result(result)
                cache_path = _cache_result(result, cfg.output.base_dir)
                rprint(f"\n[green]Cached:[/green] {cache_path}")
        else:
            repos = asyncio.run(crawler.list_repos(repo))
            if not repos:
                rprint(f"[yellow]No repositories found for '{repo}'.[/yellow]")
                raise typer.Exit(0)
            if dry_run:
                rprint("[yellow](dry run — listing repos only)[/yellow]\n")
            _display_repo_list(repos)
    except ValueError as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(1)


def _is_local_repo(repo: str) -> bool:
    """Check if a repo identifier refers to a local path."""
    return Path(repo).exists()


def _convert_repo_docs(result: CrawlResult, cfg: ChroniclerConfig) -> CrawlResult:
    """Scan crawl tree for convertible documents and convert them."""
    converter = DocumentConverter(cfg.document_conversion)
    converted: dict[str, str] = {}
    # Only files in the tree that exist locally
    repo_root = Path(result.metadata.url) if Path(result.metadata.url).is_dir() else None
    if repo_root is None:
        return result
    for node in result.tree:
        if node.type != "file":
            continue
        if not should_convert(node.path, cfg.document_conversion):
            continue
        full_path = repo_root / node.path
        if not full_path.is_file():
            continue
        try:
            conv = converter.convert(full_path)
            if conv is not None:
                converted[node.path] = conv.markdown
        except Exception:
            pass
    if converted:
        result = result.model_copy(update={"converted_docs": converted})
    return result


@app.command()
def convert(
    file: str = typer.Argument(..., help="Path to document file to convert"),
    output: str | None = typer.Option(None, "--output", "-o", help="Write markdown to file"),
) -> None:
    """Convert a document file to markdown."""
    cfg = _get_config()
    converter = DocumentConverter(cfg.document_conversion)

    try:
        conv_result = converter.convert(file)
    except Exception as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if conv_result is None:
        rprint(f"[red]Error:[/red] Could not convert '{file}'")
        raise typer.Exit(1)

    if output:
        Path(output).write_text(conv_result.markdown)
        rprint(f"[green]Written to[/green] {output}")
    else:
        rprint(conv_result.markdown)

    rprint(
        Panel(
            f"[dim]Source:[/dim]  {conv_result.source_path}\n"
            f"[dim]Format:[/dim]  {conv_result.format}\n"
            f"[dim]Cached:[/dim]  {conv_result.cached}",
            title="Conversion Result",
            border_style="green",
        )
    )


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
