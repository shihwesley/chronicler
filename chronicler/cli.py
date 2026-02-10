"""CLI entry point for Chronicler."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich import print as rprint
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

from chronicler_core.config import ChroniclerConfig, load_config
from chronicler_core.config.loader import DEFAULT_CONFIG_TEMPLATE
from chronicler_core.converter import DocumentConverter, should_convert
from chronicler_core.drafter import Drafter
from chronicler_core.llm import create_llm_provider
from chronicler_core.merkle import MerkleTree, check_drift
from chronicler_core.merkle.tree import compute_file_hash
from chronicler_core.output import TechMdValidator, TechMdWriter
from chronicler_core.vcs import CrawlResult, VCSCrawler, create_provider
from chronicler_core.vcs.models import RepoMetadata

app = typer.Typer(
    name="chronicler",
    help="Living Technical Ledger — auto-generate .tech.md for your repos.",
)

config_app = typer.Typer(help="Manage Chronicler configuration.")
app.add_typer(config_app, name="config")

queue_app = typer.Typer(help="Manage job queue.")
app.add_typer(queue_app, name="queue")

obsidian_app = typer.Typer(help="Obsidian vault integration.")
app.add_typer(obsidian_app, name="obsidian")

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
    repo: str = typer.Argument(".", help="Repository to generate .tech.md for"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
    stale: Annotated[bool, typer.Option("--stale", help="Only regenerate stale docs")] = False,
    output: Annotated[
        str | None, typer.Option("--output", "-o", help="Override output directory")
    ] = None,
) -> None:
    """Generate .tech.md from crawled data."""
    cfg = _get_config()

    # --stale mode: only regenerate docs whose source files changed
    if stale:
        root = Path(repo).resolve()
        tree, was_fresh = _load_or_build_merkle(root)
        if was_fresh:
            rprint("[yellow]First scan — no drift baseline yet. Run full draft instead.[/yellow]")
            return
        stale_nodes = check_drift(tree)
        if not stale_nodes:
            rprint("[green]All docs up to date.[/green]")
            return
        rprint(f"[bold]{len(stale_nodes)} stale doc(s) found.[/bold] Regeneration would target:")
        for node in stale_nodes:
            rprint(f"  - {node.path} (doc: {node.doc_path or 'none'})")
        # Update merkle tree with current hashes after identifying stale docs
        for node in stale_nodes:
            fpath = root / node.path
            if fpath.is_file():
                new_hash = compute_file_hash(fpath)
                tree.update_node(node.path, source_hash=new_hash, doc_hash=node.doc_hash)
        merkle_path = root / MERKLE_JSON
        tree.save(merkle_path)
        rprint(f"[green]Merkle tree updated.[/green] Saved to {merkle_path}")
        return

    rprint(f"[bold]Drafting[/bold] .tech.md for {repo} (llm: {cfg.llm.provider})...")

    # 1. Create VCS provider and crawl
    try:
        vcs_provider = create_provider(cfg.vcs)
    except ValueError as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    crawler = VCSCrawler(vcs_provider, cfg.vcs)

    try:
        _validate_repo_id(repo)
    except ValueError as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    try:
        crawl_result = asyncio.run(crawler.crawl_repo(repo))
    except Exception as e:
        rprint(f"[red]Crawl failed:[/red] {e}")
        raise typer.Exit(1)

    # 2. Create LLM provider
    try:
        llm = create_llm_provider(cfg.llm)
    except ValueError as e:
        rprint(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # 3. Draft the .tech.md
    drafter = Drafter(llm, cfg)
    try:
        tech_doc = asyncio.run(drafter.draft_tech_doc(crawl_result))
    except Exception as e:
        rprint(f"[red]Draft failed:[/red] {e}")
        raise typer.Exit(1)

    # 4. Write or preview
    if dry_run:
        # Split frontmatter from body for syntax highlighting
        raw = tech_doc.raw_content
        if raw.startswith("---"):
            end = raw.find("---", 3)
            if end != -1:
                fm = raw[3:end].strip()
                body = raw[end + 3:].strip()
                rprint(Syntax(fm, "yaml", theme="monokai"))
                rprint()
                rprint(Syntax(body, "markdown", theme="monokai"))
            else:
                rprint(Syntax(raw, "markdown", theme="monokai"))
        else:
            rprint(Syntax(raw, "markdown", theme="monokai"))
    else:
        # Override output dir if --output given
        out_cfg = cfg.output
        if output:
            out_cfg = out_cfg.model_copy(update={"base_dir": output})
        writer = TechMdWriter(out_cfg)
        dest = writer.write(tech_doc)
        rprint(Panel(
            f"[dim]File:[/dim]         {dest}\n"
            f"[dim]Component:[/dim]    {tech_doc.component_id}\n"
            f"[dim]Size:[/dim]         {len(tech_doc.raw_content)} bytes",
            title="Draft Complete",
            border_style="green",
        ))


@app.command()
def validate(
    path: str = typer.Argument(".chronicler", help="Path to .chronicler directory"),
    format: Annotated[
        str, typer.Option("--format", "-f", help="Output format: table or json")
    ] = "table",
) -> None:
    """Validate .tech.md files against schema."""
    cfg = _get_config()
    rprint(f"[bold]Validating[/bold] {path}...")

    validator = TechMdValidator(mode=cfg.output.validation)
    results = validator.validate_directory(path)

    if not results:
        rprint("[yellow]No .tech.md files found.[/yellow]")
        raise typer.Exit(0)

    any_invalid = any(not r.valid for r in results)

    if format == "json":
        rprint(json.dumps([r.model_dump() for r in results], indent=2))
    else:
        table = Table(title=f"Validation Results ({len(results)} files)")
        table.add_column("Path", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Errors", justify="right", style="red")
        table.add_column("Warnings", justify="right", style="yellow")

        for r in results:
            status = "[green]PASS[/green]" if r.valid else "[red]FAIL[/red]"
            table.add_row(r.path, status, str(len(r.errors)), str(len(r.warnings)))
        rprint(table)

        # Show details for files with issues
        for r in results:
            if r.errors or r.warnings:
                rprint(f"\n[bold]{r.path}[/bold]")
                for err in r.errors:
                    rprint(f"  [red]error:[/red] {err}")
                for warn in r.warnings:
                    rprint(f"  [yellow]warn:[/yellow] {warn}")

    if any_invalid and cfg.output.validation == "strict":
        raise typer.Exit(1)


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


# ---------------------------------------------------------------------------
# Lite commands (search, deps, rebuild, queue)
# ---------------------------------------------------------------------------


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    k: int = typer.Option(10, "--k", help="Number of results to return"),
    mode: str = typer.Option(
        "auto", "--mode", help="Search mode: auto, lex, or vec"
    ),
    mv2_path: str = typer.Option(
        ".chronicler/chronicler.mv2", "--mv2-path", help="Path to .mv2 file"
    ),
) -> None:
    """Search the .mv2 knowledge base."""
    from chronicler_lite.storage.memvid_storage import MemVidStorage

    if mode not in ("auto", "lex", "vec"):
        rprint(f"[red]Error:[/red] Invalid mode '{mode}'. Choose auto, lex, or vec.")
        raise typer.Exit(1)

    storage = MemVidStorage(path=mv2_path)
    results = storage.search(query, k=k, mode=mode)

    if not results:
        rprint("[yellow]No results found.[/yellow]")
        raise typer.Exit(0)

    table = Table(title=f"Search Results ({len(results)})")
    table.add_column("doc_id", style="cyan")
    table.add_column("score", justify="right", style="green")
    table.add_column("snippet", style="dim")

    for r in results:
        snippet = r.content[:80] + ("..." if len(r.content) > 80 else "")
        table.add_row(r.doc_id, f"{r.score:.4f}", snippet)

    rprint(table)


@app.command()
def deps(
    component: str = typer.Argument(..., help="Component name for SPO lookup"),
    mv2_path: str = typer.Option(
        ".chronicler/chronicler.mv2", "--mv2-path", help="Path to .mv2 file"
    ),
) -> None:
    """Show dependency slots for a component."""
    from chronicler_lite.storage.memvid_storage import MemVidStorage

    storage = MemVidStorage(path=mv2_path)
    state = storage.state(component)

    if not state:
        rprint(f"[yellow]No state found for '{component}'.[/yellow]")
        raise typer.Exit(0)

    table = Table(title=f"State: {component}")
    table.add_column("slot", style="cyan")
    table.add_column("value", style="green")

    for slot, value in state.items():
        table.add_row(slot, str(value))

    rprint(table)


@app.command()
def rebuild(
    tech_md_dir: str = typer.Option(
        ".chronicler", "--tech-md-dir", help="Directory containing .tech.md files"
    ),
    mv2_path: str = typer.Option(
        ".chronicler/chronicler.mv2", "--mv2-path", help="Path to .mv2 output file"
    ),
) -> None:
    """Rebuild .mv2 index from .tech.md files."""
    from chronicler_lite.storage.memvid_storage import MemVidStorage

    md_dir = Path(tech_md_dir)
    files = list(md_dir.glob("*.tech.md"))

    if not files:
        rprint(f"[yellow]No .tech.md files found in {tech_md_dir}.[/yellow]")
        raise typer.Exit(0)

    storage = MemVidStorage(path=mv2_path)
    storage.rebuild(tech_md_dir)

    rprint(f"[green]Rebuilt[/green] {mv2_path} from {len(files)} .tech.md file(s).")


@queue_app.command("status")
def queue_status(
    db_path: str = typer.Option(
        ".chronicler/queue.db", "--db-path", help="Path to queue database"
    ),
) -> None:
    """Show job queue statistics."""
    from chronicler_lite.queue.sqlite_queue import SQLiteQueue

    queue = SQLiteQueue(db_path=db_path)
    stats = queue.stats()

    table = Table(title="Queue Stats")
    table.add_column("status", style="cyan")
    table.add_column("count", justify="right", style="green")

    for status, count in stats.items():
        table.add_row(status, str(count))

    rprint(table)


@queue_app.command("run")
def queue_run(
    db_path: str = typer.Option(
        ".chronicler/queue.db", "--db-path", help="Path to queue database"
    ),
) -> None:
    """Process pending jobs from the queue."""
    from rich.status import Status

    from chronicler_lite.queue.sqlite_queue import SQLiteQueue

    queue = SQLiteQueue(db_path=db_path)
    processed = 0

    with Status("[bold]Processing queue...", spinner="dots") as status:
        while True:
            job = queue.dequeue()
            if job is None:
                break

            status.update(f"[bold]Processing job {job.id}...")
            try:
                # Stub: log payload, real pipeline wired later
                rprint(f"[dim]Job {job.id}:[/dim] {json.dumps(job.payload)}")
                queue.ack(job.id)
                processed += 1
            except Exception as e:
                queue.nack(job.id, str(e))
                rprint(f"[red]Error processing {job.id}:[/red] {e}")

    rprint(f"[green]Done.[/green] Processed {processed} job(s).")


# ---------------------------------------------------------------------------
# Obsidian commands
# ---------------------------------------------------------------------------


@obsidian_app.command()
def export(
    vault: Annotated[str, typer.Option("--vault", "-v", help="Path to Obsidian vault")] = "",
    source: Annotated[str, typer.Option("--source", "-s", help="Path to .chronicler/ directory")] = ".chronicler",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be synced")] = False,
) -> None:
    """Export .tech.md files to Obsidian vault."""
    cfg = _get_config()
    vault_path = vault or cfg.obsidian.vault_path
    if not vault_path:
        typer.echo("Error: --vault is required or set obsidian.vault_path in config")
        raise typer.Exit(1)

    from chronicler_obsidian.sync import ObsidianSync
    from chronicler_obsidian.transform import (
        TransformPipeline,
        LinkRewriter,
        FrontmatterFlattener,
        DataviewInjector,
        IndexGenerator,
    )

    pipeline = TransformPipeline([
        LinkRewriter(),
        FrontmatterFlattener(),
        DataviewInjector(),
        IndexGenerator(),
    ])

    sync = ObsidianSync(
        source_dir=source,
        vault_path=vault_path,
        config=cfg.obsidian,
        pipeline=pipeline,
    )

    if dry_run:
        source_dir = Path(source)
        files = list(source_dir.rglob("*.tech.md")) if source_dir.is_dir() else []
        if not files:
            rprint("[yellow]No .tech.md files found.[/yellow]")
            raise typer.Exit(0)
        table = Table(title="Dry Run — files that would be synced")
        table.add_column("Source", style="cyan")
        table.add_column("Destination", style="green")
        for f in sorted(files):
            rel = str(f.relative_to(source_dir))
            dest = rel.replace(".tech.md", ".md")
            table.add_row(rel, dest)
        rprint(table)
        return

    report = sync.export()

    table = Table(title="Obsidian Export")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")
    table.add_row("Synced", str(report.synced))
    table.add_row("Skipped", str(report.skipped))
    table.add_row("Errors", str(len(report.errors)))
    table.add_row("Duration", f"{report.duration:.2f}s")
    rprint(table)

    for err in report.errors:
        rprint(f"  [red]error:[/red] {err.file}: {err.error}")


@obsidian_app.command(name="sync")
def sync_cmd(
    watch: Annotated[bool, typer.Option("--watch", "-w", help="Watch for changes")] = False,
    rest: Annotated[bool, typer.Option("--rest", help="Sync via REST API")] = False,
    vault: Annotated[str, typer.Option("--vault", "-v", help="Path to Obsidian vault")] = "",
    source: Annotated[str, typer.Option("--source", "-s", help="Source .chronicler/ directory")] = ".chronicler",
    url: Annotated[str, typer.Option("--url", help="REST API URL")] = "",
    token: Annotated[str, typer.Option("--token", help="REST API token")] = "",
) -> None:
    """Sync .tech.md files to Obsidian (watch mode or REST API)."""
    if not watch and not rest:
        typer.echo("Error: specify --watch or --rest")
        raise typer.Exit(1)

    cfg = _get_config()
    vault_path = vault or cfg.obsidian.vault_path

    from chronicler_obsidian.sync import ObsidianSync
    from chronicler_obsidian.transform import (
        TransformPipeline,
        LinkRewriter,
        FrontmatterFlattener,
        DataviewInjector,
        IndexGenerator,
    )

    pipeline = TransformPipeline([
        LinkRewriter(),
        FrontmatterFlattener(),
        DataviewInjector(),
        IndexGenerator(),
    ])

    sync = ObsidianSync(
        source_dir=source,
        vault_path=vault_path or "",
        config=cfg.obsidian,
        pipeline=pipeline,
    )

    if watch:
        if not vault_path:
            typer.echo("Error: --vault is required for watch mode")
            raise typer.Exit(1)
        rprint(f"[bold]Watching[/bold] {source} -> {vault_path}")
        sync.watch()
    elif rest:
        report = sync.sync_rest(
            api_url=url or None,
            token=token or None,
        )
        table = Table(title="REST Sync Report")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")
        table.add_row("Synced", str(report.synced))
        table.add_row("Skipped", str(report.skipped))
        table.add_row("Errors", str(len(report.errors)))
        table.add_row("Duration", f"{report.duration:.2f}s")
        rprint(table)

        for err in report.errors:
            rprint(f"  [red]error:[/red] {err.file}: {err.error}")


# ---------------------------------------------------------------------------
# Merkle commands (check, blast-radius) and draft --stale support
# ---------------------------------------------------------------------------

MERKLE_JSON = ".chronicler/.merkle.json"


def _load_or_build_merkle(root: Path) -> tuple[MerkleTree, bool]:
    """Load an existing .merkle.json or build a fresh tree.

    Returns (tree, was_fresh) where was_fresh is True if no file existed.
    """
    cfg = _get_config()
    merkle_path = root / MERKLE_JSON
    if merkle_path.is_file():
        return MerkleTree.load(merkle_path), False
    tree = MerkleTree.build(
        root,
        doc_dir=cfg.merkle.doc_dir,
        ignore_patterns=cfg.merkle.ignore_patterns,
    )
    merkle_path.parent.mkdir(parents=True, exist_ok=True)
    tree.save(merkle_path)
    return tree, True


@app.command()
def check(
    ci: Annotated[bool, typer.Option("--ci", help="Machine-readable output")] = False,
    fail_on_stale: Annotated[bool, typer.Option("--fail-on-stale", help="Exit 1 if stale docs found")] = False,
    path: Annotated[str, typer.Argument(help="Path to project root")] = ".",
) -> None:
    """Check docs for staleness against source file hashes."""
    root = Path(path).resolve()
    tree, was_fresh = _load_or_build_merkle(root)

    if was_fresh:
        msg = f"First scan complete — {len([n for n in tree.nodes.values() if n.source_hash])} files indexed, no drift baseline yet."
        if ci:
            typer.echo(msg)
        else:
            rprint(f"[yellow]{msg}[/yellow]")
        return

    stale_nodes = check_drift(tree)

    if ci:
        # Plain text, one stale path per line
        for node in stale_nodes:
            typer.echo(f"STALE {node.path}")
        if not stale_nodes:
            typer.echo("OK — all docs up to date")
        typer.echo(f"root_hash={tree.root_hash}")
    else:
        table = Table(title="Drift Check")
        table.add_column("File", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Doc", style="dim")

        # Show all leaf nodes (files with source_hash)
        for node in sorted(tree.nodes.values(), key=lambda n: n.path):
            if node.source_hash is None:
                continue
            if node in stale_nodes:
                status = "[red]stale[/red]"
            else:
                status = "[green]ok[/green]"
            doc = node.doc_path or "-"
            table.add_row(node.path, status, doc)

        rprint(table)
        rprint(f"\n[dim]Root hash:[/dim] {tree.root_hash}")

        if stale_nodes:
            rprint(f"\n[red]{len(stale_nodes)} stale doc(s) found.[/red]")
        else:
            rprint("\n[green]All docs up to date.[/green]")

    if fail_on_stale and stale_nodes:
        raise typer.Exit(code=1)


def _parse_tech_md_edges(tech_md_path: Path) -> list[dict]:
    """Parse YAML frontmatter from a .tech.md file and return its edges list.

    Each edge is expected to have at least a 'target' key, and optionally 'type'.
    """
    if not tech_md_path.is_file():
        return []
    content = tech_md_path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return []
    end = content.find("---", 3)
    if end == -1:
        return []
    try:
        fm = yaml.safe_load(content[3:end])
    except yaml.YAMLError:
        return []
    if not isinstance(fm, dict):
        return []
    edges = fm.get("edges", [])
    if not isinstance(edges, list):
        return []
    return edges


def _build_edge_graph(chronicler_dir: Path) -> dict[str, list[dict]]:
    """Scan all .tech.md files and build component_id -> edges adjacency map."""
    graph: dict[str, list[dict]] = {}
    if not chronicler_dir.is_dir():
        return graph
    for md in sorted(chronicler_dir.glob("*.tech.md")):
        edges = _parse_tech_md_edges(md)
        # Derive component_id from the frontmatter or filename
        content = md.read_text(encoding="utf-8")
        component_id = md.stem  # fallback
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                try:
                    fm = yaml.safe_load(content[3:end])
                    if isinstance(fm, dict) and "component_id" in fm:
                        component_id = fm["component_id"]
                except yaml.YAMLError:
                    pass
        graph[component_id] = edges
    return graph


@app.command(name="blast-radius")
def blast_radius(
    changed: Annotated[str, typer.Option("--changed", help="File path that changed")] = ...,
    depth: Annotated[int, typer.Option("--depth", help="Hop depth")] = 2,
    path: Annotated[str, typer.Argument(help="Path to project root")] = ".",
) -> None:
    """Show blast radius of a changed file through doc edges."""
    root = Path(path).resolve()
    cfg = _get_config()
    chronicler_dir = root / cfg.merkle.doc_dir

    # Load merkle tree to find the changed file's doc
    merkle_path = root / MERKLE_JSON
    if not merkle_path.is_file():
        rprint("[red]No .merkle.json found.[/red] Run 'chronicler check' first.")
        raise typer.Exit(1)

    tree = MerkleTree.load(merkle_path)
    node = tree.nodes.get(changed)
    if node is None:
        rprint(f"[red]File not found in merkle tree:[/red] {changed}")
        raise typer.Exit(1)

    # Build adjacency graph from .tech.md edges
    graph = _build_edge_graph(chronicler_dir)

    # Find which component_id the changed file belongs to
    # (the component whose doc covers this file)
    start_component = None
    if node.doc_path:
        # Read the doc to get its component_id
        doc_full = root / node.doc_path
        if doc_full.is_file():
            content = doc_full.read_text(encoding="utf-8")
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    try:
                        fm = yaml.safe_load(content[3:end])
                        if isinstance(fm, dict):
                            start_component = fm.get("component_id")
                    except yaml.YAMLError:
                        pass
    if not start_component:
        # Use the file path itself as a best-effort identifier
        start_component = changed

    # BFS over edge graph up to depth hops
    # Build a reverse adjacency map (who points to whom)
    all_targets: dict[str, set[str]] = {}
    for comp, edges in graph.items():
        for edge in edges:
            target = edge.get("target", "") if isinstance(edge, dict) else ""
            if target:
                all_targets.setdefault(comp, set()).add(target)
                # Bidirectional: if B depends on A, changing A affects B
                all_targets.setdefault(target, set()).add(comp)

    visited: set[str] = {start_component}
    levels: list[list[str]] = []
    frontier = {start_component}

    for _ in range(depth):
        next_level: list[str] = []
        next_frontier: set[str] = set()
        for comp in frontier:
            for neighbor in all_targets.get(comp, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    next_level.append(neighbor)
                    next_frontier.add(neighbor)
        levels.append(sorted(next_level))
        frontier = next_frontier

    # Display
    rprint(Panel(f"[bold]Blast radius for:[/bold] {changed}", border_style="red"))
    rprint(f"\n[bold]Direct impact:[/bold] {start_component}")

    any_impact = False
    for i, level in enumerate(levels, 1):
        label = f"{i}-hop dependencies"
        if level:
            any_impact = True
            rprint(f"\n[bold]{label}:[/bold]")
            for comp in level:
                edge_type = ""
                # Find the edge type from the graph
                for src, edges in graph.items():
                    for edge in edges:
                        if isinstance(edge, dict):
                            if edge.get("target") == comp or src == comp:
                                edge_type = edge.get("type", "")
                                break
                    if edge_type:
                        break
                suffix = f" [dim]({edge_type})[/dim]" if edge_type else ""
                rprint(f"  - {comp}{suffix}")
        else:
            rprint(f"\n[bold]{label}:[/bold] [dim]none[/dim]")

    if any_impact:
        rprint("\n[yellow]Recommended action:[/yellow] Review and update affected .tech.md files.")
    else:
        rprint("\n[green]Recommended action:[/green] No downstream impact detected.")


if __name__ == "__main__":
    app()
