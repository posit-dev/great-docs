"""Build, preview, freeze and timing commands"""

from __future__ import annotations

import os
import re
import sys
import zipfile
from pathlib import Path

import click

from .._build import freeze as freeze_cache
from .._build import from_repo as repository
from .._build import quarto, serve
from .._build.steps import PROJECT_ERRORS, USER_CODE_ERRORS, BuildError, print_warning
from .._content import user_guide
from .._project.layout import Layout
from .._project.remote import HttpRemote
from ..core import GreatDocs
from . import options as _options


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--watch",
    is_flag=True,
    help="Watch for changes and rebuild automatically",
)
@click.option(
    "--no-refresh",
    is_flag=True,
    help="Skip re-discovering package exports (faster rebuild when API unchanged)",
)
@click.option(
    "--versions",
    "version_filter",
    type=str,
    default=None,
    help="Build only specific versions (comma-separated tags, e.g. '0.3,dev')",
)
@click.option(
    "--latest-only",
    is_flag=True,
    help="Build only the latest version (skip historical versions)",
)
@click.option(
    "--from-repo",
    "from_repo",
    type=str,
    default=None,
    help="Clone a remote Git repository and build its docs (HTTPS or SSH URL)",
)
@click.option(
    "--branch",
    type=str,
    default=None,
    help="Branch or tag to check out when using --from-repo (default: repo default)",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="Where to copy --from-repo output (default: the checkout deployment path, e.g. docs/_site)",
)
@click.option(
    "--shallow",
    is_flag=True,
    help="Force shallow clone with --from-repo (fastest, but no versioned docs or page dates)",
)
@click.option(
    "--preview",
    "preview_after",
    is_flag=True,
    help="Start a preview server after building with --from-repo",
)
@click.option(
    "--jobs",
    "-j",
    type=str,
    default=None,
    help="Render pages with this many Quarto processes (a number or 'auto'; experimental)",
)
@_options.config_option
def build(
    project_path: str | None,
    watch: bool,
    no_refresh: bool,
    version_filter: str | None,
    latest_only: bool,
    from_repo: str | None,
    branch: str | None,
    output_dir: str | None,
    shallow: bool,
    preview_after: bool,
    jobs: str | None = None,
    config_path: str | None = None,
) -> None:
    """
    Build your documentation site

    Requires a configuration such as 'docs/great-docs.yml' (run 'great-docs init' first).
    This is the only command you need day-to-day and in CI.

    Creates the 'docs/_quarto/default/' Quarto project, copies assets,
    and publishes the site to 'docs/_site/'. Historical projects use
    'docs/_quarto/<tag>/'. These generated directories should not be committed.
    Use '--config website/great-docs.yml' for a custom source directory.

    Use '--project-path' to point to a project in a different directory.
    Use '--watch' to serve the site with 'quarto preview' and rebuild after
    changes to the documentation sources, 'great-docs.yml' or the package.

    Use '--no-refresh' to skip API discovery for faster rebuilds when your
    package's public API hasn't changed.

    When multi-version documentation is configured, use '--versions' to
    build only specific versions, or '--latest-only' to skip historical
    versions.

    Use '--from-repo' to build documentation from a remote Git repository.
    This clones the repo into a temporary directory, creates an isolated
    virtual environment, installs the package and great-docs, builds the
    site, and copies the output to '--output-dir'. By default it preserves the
    checkout's deployment path under the current directory, such as 'docs/_site/'.

    Add '--preview' to automatically start a local server after a
    '--from-repo' build completes, opening the site in your browser.

    Use '--jobs' (experimental) to render a single-version site with several
    Quarto processes at once. Pass a number, or 'auto' to pick one from the
    CPU count. The GREAT_DOCS_RENDER_JOBS environment variable sets a default.

    \b
    Examples:
      great-docs build                      # Full build with API refresh
      great-docs build --no-refresh         # Fast rebuild (skip API discovery)
      great-docs build --watch              # Rebuild on file changes
      great-docs build --versions 0.3,dev   # Build specific versions only
      great-docs build --latest-only        # Build only the latest version
      great-docs build --jobs auto          # Render pages in parallel
      great-docs build --project-path ../pkg
      great-docs build --from-repo https://github.com/owner/pkg.git
      great-docs build --from-repo git@github.com:owner/pkg.git --branch v1.0
      great-docs build --from-repo https://github.com/owner/pkg.git --output-dir ./site
      great-docs build --from-repo https://github.com/owner/pkg.git --shallow
      great-docs build --from-repo https://github.com/owner/pkg.git --preview
    """
    try:
        if from_repo:
            # Remote build: clone, install, build, copy output
            if project_path:
                click.echo(
                    "Warning: --project-path is ignored when --from-repo is used",
                    err=True,
                )
            if watch:
                click.echo("Error: --watch is not supported with --from-repo", err=True)
                sys.exit(1)
            version_tags = None
            if version_filter:
                version_tags = [v.strip() for v in version_filter.split(",") if v.strip()]
            built_site = repository.build(
                from_repo,
                branch=branch,
                output_dir=output_dir,
                refresh=not no_refresh,
                version_tags=version_tags,
                latest_only=latest_only,
                shallow=shallow,
                config_path=config_path,
                report=click.echo,
            )
            if preview_after:
                serve.site(built_site, report=click.echo)
        else:
            if branch:
                click.echo("Warning: --branch is ignored without --from-repo", err=True)
            if shallow:
                click.echo("Warning: --shallow is ignored without --from-repo", err=True)
            if output_dir:
                click.echo("Warning: --output-dir is ignored without --from-repo", err=True)
            if preview_after:
                click.echo("Warning: --preview is ignored without --from-repo", err=True)
            docs = GreatDocs(project_path=project_path, config_path=config_path)
            # Parse version filter if provided
            version_tags = None
            if version_filter:
                version_tags = [v.strip() for v in version_filter.split(",") if v.strip()]
            docs.build(
                watch=watch,
                refresh=not no_refresh,
                version_tags=version_tags,
                latest_only=latest_only,
                jobs=jobs,
            )
    except KeyboardInterrupt:
        click.echo("\n👋 Stopped watching")
    except BuildError:
        # Exit without repeating the build's failure report
        sys.exit(1)
    except serve.ServeError as e:
        click.echo(f"❌ {e}")
        sys.exit(1)
    except (*PROJECT_ERRORS, *USER_CODE_ERRORS, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--port",
    type=int,
    default=3000,
    show_default=True,
    help="Port for the local preview server",
)
@click.option(
    "--site-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=None,
    help="Path to a pre-built site directory to serve (bypasses project detection)",
)
@click.option("--pr", type=int, default=None, help="Preview the CI docs build for this PR number.")
@click.option("--run", type=int, default=None, help="Preview a specific workflow run id.")
@click.option("--branch", default=None, help="Preview the newest CI docs build for a branch.")
@click.option(
    "--repo",
    default=None,
    help="GitHub repo as 'owner/repo' (default: detect from git remote / config).",
)
@click.option(
    "--artifact",
    default="docs-html",
    show_default=True,
    help="Name of the CI artifact to fetch.",
)
@click.option(
    "--path",
    "open_path",
    default="",
    help="Open the browser at this page within the site (e.g. reference/index.html).",
)
@click.option("--no-open", is_flag=True, help="Serve without launching a browser.")
@click.option("--refresh", is_flag=True, help="Ignore the local cache and re-download.")
@click.option(
    "--clear-cache",
    is_flag=True,
    help="Delete the downloaded PR-preview cache and exit.",
)
@click.option(
    "--use-gh",
    is_flag=True,
    help="Fetch via the 'gh' CLI (uses your existing gh auth) instead of a token.",
)
@click.option(
    "--env-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Load a .env for GITHUB_TOKEN/GH_TOKEN (default: auto-detect .env).",
)
@_options.config_option
def preview(
    project_path: str | None,
    port: int,
    site_dir: str | None,
    pr: int | None,
    run: int | None,
    branch: str | None,
    repo: str | None,
    artifact: str,
    open_path: str,
    no_open: bool,
    refresh: bool,
    clear_cache: bool,
    use_gh: bool,
    env_file: str | None,
    config_path: str | None = None,
) -> None:
    """
    Preview your documentation locally

    Starts a local HTTP server and opens the built documentation site in your
    default browser. If the site hasn't been built yet, it will build it first.

    The default site is served from 'docs/_site/'. Use '--config' to select a
    custom documentation directory. Run 'great-docs build' after source changes.

    Use '--site-dir' to preview a site from any directory (e.g. output from
    a '--from-repo' build).

    Use '--pr', '--run', or '--branch' to fetch and preview a site that CI
    already built (no hosting setup required). Downloading CI artifacts needs a
    GitHub token with 'Actions: read' (via GITHUB_TOKEN, a .env, or 'gh auth
    login' + '--use-gh'). For fork PRs you'll be viewing contributor-authored
    HTML locally.

    \b
    Examples:
      great-docs preview                    # Preview on port 3000
      great-docs preview --port 8080        # Preview on port 8080
      great-docs preview --site-dir /tmp/weathervault-site
      great-docs preview --pr 302           # Newest CI build for PR #302
      great-docs preview --run 18273645521  # A specific workflow run
      great-docs preview --pr 302 --path reference/mcp/gd_config.html
    """
    if clear_cache:
        from .._build.pr_preview import clear_cache as _clear_cache

        existed, path = _clear_cache()
        if existed:
            click.echo(f"✓ Cleared PR-preview cache at {path}")
        else:
            click.echo(f"No PR-preview cache to clear ({path} does not exist).")
        return

    exclusive = [
        ("--pr", pr is not None),
        ("--run", run is not None),
        ("--branch", branch is not None),
    ]
    given = [name for name, present in exclusive if present]
    if len(given) > 1:
        click.echo(f"Error: {', '.join(given)} are mutually exclusive; pass only one.", err=True)
        sys.exit(1)

    try:
        if given:
            if site_dir:
                click.echo("Warning: --site-dir is ignored with --pr/--run/--branch", err=True)
            from .._build.pr_preview import PreviewError, preview_pr

            try:
                preview_pr(
                    project_path,
                    pr=pr,
                    run=run,
                    branch=branch,
                    repo=repo,
                    artifact=artifact,
                    path=open_path,
                    port=port,
                    open_browser=not no_open,
                    refresh=refresh,
                    use_gh=use_gh,
                    env_file=env_file,
                )
            except PreviewError as e:
                click.echo(f"Error: {e}", err=True)
                sys.exit(1)
        elif site_dir:
            if project_path:
                click.echo(
                    "Warning: --project-path is ignored when --site-dir is used",
                    err=True,
                )
            serve.site(
                site_dir,
                port=port,
                open_path=open_path,
                open_browser=not no_open,
                report=click.echo,
            )
        else:
            docs = GreatDocs(project_path=project_path, config_path=config_path)
            docs.preview(port=port, open_path=open_path, open_browser=not no_open)
    except KeyboardInterrupt:
        click.echo("\n👋 Server stopped")
    except serve.ServeError as e:
        click.echo(f"❌ {e}")
        sys.exit(1)
    except SystemExit:
        raise
    except BuildError:
        # Exit without repeating the build's failure report
        sys.exit(1)
    except (*PROJECT_ERRORS, *USER_CODE_ERRORS, ValueError, zipfile.BadZipFile) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _freeze_info(project_root: Path, persist_dir: Path, layout: Layout | None = None) -> None:
    """
    Display freeze settings and cached pages for the current version
    """
    import json
    import re as _re
    from datetime import datetime

    layout = layout or Layout.make(project_root)
    cfg = layout.load_config()
    project_mode = cfg.freeze

    click.echo()
    if project_mode is not None:
        label = "auto" if project_mode == "auto" else str(project_mode)
        click.echo(f"  Project freeze: {label} (all executable pages)")
    else:
        click.echo("  Project freeze: disabled")
    click.echo(f"  Freeze cache:   {os.path.relpath(persist_dir, project_root)}/")
    click.echo()

    # Scan source .qmd files for per-page freeze declarations
    freeze_re = _re.compile(r"^freeze:\s+(.+)$", re.MULTILINE)
    exec_freeze_re = _re.compile(r"^execute:\s*\n\s+freeze:\s+(.+)$", re.MULTILINE)

    def _extract_frontmatter(text: str) -> str:
        if not text.startswith("---"):
            return ""
        end = text.find("\n---", 3)
        if end == -1:
            return ""
        return text[3:end]

    per_page_modes: dict[str, str] = {}
    source_dirs = [layout.source_dir / "recipes"]
    guide_dir = user_guide.find_dir(
        cfg, layout, report=lambda message: click.echo(f"  ⚠️  {message}", err=True)
    )
    if guide_dir is not None:
        source_dirs.append(guide_dir)
    for src_path in source_dirs:
        if not src_path.is_dir():
            continue
        for qmd_file in sorted(src_path.rglob("*.qmd")):
            content = qmd_file.read_text(encoding="utf-8", errors="replace")
            frontmatter = _extract_frontmatter(content)
            match = freeze_re.search(frontmatter) or exec_freeze_re.search(frontmatter)
            if match:
                rel_path = str(qmd_file.relative_to(project_root))
                per_page_modes[rel_path] = match.group(1).strip()

    if per_page_modes:
        click.echo("  Per-page overrides:")
        for source, mode in per_page_modes.items():
            click.echo(f"    {source}  (freeze: {mode})")
        click.echo()

    if not persist_dir.is_dir():
        click.echo("  No freeze cache found yet (run a build to populate it).")
        return

    cache_entries = sorted(
        cache_json
        for cache_json in persist_dir.rglob("execute-results/html.json")
        if not cache_json.is_relative_to(persist_dir / "_versions")
    )
    if not cache_entries:
        click.echo("  Freeze cache directory exists but contains no current page entries.")
        return

    click.echo(f"  {len(cache_entries)} cached page(s):")
    click.echo()

    for cache_json in cache_entries:
        rel = cache_json.relative_to(persist_dir)
        # execute-results/html.json → parent.parent is the page stem
        page_stem = str(rel.parent.parent)

        try:
            data = json.loads(cache_json.read_text(encoding="utf-8"))
            ts_match = _re.search(
                r"Executed at: ([\d-]+ [\d:]+)",
                data.get("result", {}).get("markdown", ""),
            )
            if ts_match:
                timestamp = ts_match.group(1)
            else:
                mtime = cache_json.stat().st_mtime
                timestamp = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
            click.echo(f"  ✓  {page_stem}")
            click.echo(f"       frozen at {timestamp}")
        # An unreadable, undecodable or invalid cache file raises `OSError` or `ValueError`;
        # JSON without a `result` mapping holding `markdown` text raises the other two
        except (OSError, ValueError, AttributeError, TypeError):
            click.echo(f"  ?  {page_stem}")
            click.echo("       cache file exists but could not be parsed")

    click.echo()
    click.echo(f"  {len(cache_entries)} page(s) cached")
    click.echo()
    click.echo("  ℹ To re-freeze a stale page: great-docs freeze <page>")


@click.command()
@click.argument("pages", nargs=-1, required=False)
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--freeze-dir",
    type=str,
    default=None,
    help="Where to persist execution results (default: '_freeze/' beside the selected configuration)",
)
@click.option(
    "--clean",
    is_flag=True,
    default=False,
    help="Delete existing _freeze/ before re-executing (forces full refresh).",
)
@click.option(
    "--info",
    is_flag=True,
    default=False,
    help="Show freeze settings and cached pages for the current version.",
)
@_options.config_option
def freeze(
    pages: tuple[str, ...],
    project_path: str | None,
    freeze_dir: str | None,
    clean: bool,
    info: bool,
    config_path: str | None = None,
) -> None:
    """
    Execute specific pages and persist their freeze cache

    Renders one or more QMD pages (always executing their code), then copies
    the resulting '_freeze/' entries back to a persistent location so they
    survive future builds.

    PAGES are paths to .qmd files relative to your project root (e.g.,
    'docs/user_guide/benchmarks.qmd'). Quarto always executes code when rendering
    individual files, even with freeze enabled (this is how you update
    frozen outputs).

    Use '--clean' to wipe the entire '_freeze/' cache before re-executing.
    This forces a full refresh of all specified pages from scratch.

    Use `--info` to see freeze settings and cached pages for the current
    version without rendering.

    After running, the updated '_freeze/' entries are ready to commit to
    version control.

    \b
    Examples:
      great-docs freeze docs/user_guide/benchmarks.qmd
      great-docs freeze docs/user_guide/benchmarks.qmd docs/user_guide/mcmc-demo.qmd
      great-docs freeze docs/user_guide/benchmarks.qmd --freeze-dir cached-results
      great-docs freeze docs/user_guide/benchmarks.qmd --clean
      great-docs freeze --info
    """
    import shutil

    project_root = Path(project_path) if project_path else Path.cwd()
    layout = Layout.make(project_root, Path(config_path) if config_path else None)
    project_root = layout.package_root
    build_dir = layout.build_dir
    persist_dir = Path(freeze_dir) if freeze_dir else layout.freeze_dir

    if info:
        _freeze_info(project_root, persist_dir, layout)
        return

    if not pages:
        click.echo("Error: Specify at least one PAGE, or use --info.", err=True)
        sys.exit(1)

    missing = [p for p in pages if not (project_root / p).is_file()]
    if missing:
        for page in missing:
            click.echo(f"Error: Page not found: {page}", err=True)
        sys.exit(1)

    # Check before `--clean` removes the cache that a failed render could not replace
    try:
        quarto.ensure_installed()
    except (quarto.QuartoNotFoundError, quarto.QuartoVersionError) as error:
        raise click.ClickException(str(error)) from error

    if clean:
        from .._build.ownership import validate_layout_outputs, validate_tree_symlinks

        try:
            validate_layout_outputs(layout)
            if ".." in persist_dir.parts:
                raise ValueError(f"Freeze cache path contains parent traversal: {persist_dir}")
            persist_dir = Path(os.path.abspath(persist_dir))
            for cache in (persist_dir, build_dir / "_freeze"):
                if any(parent.is_symlink() for parent in cache.parents):
                    raise ValueError(f"Freeze cache has a symlink parent: {cache}")
                validate_tree_symlinks(cache)
        except ValueError as error:
            raise click.ClickException(str(error)) from error
        if persist_dir.exists():
            shutil.rmtree(persist_dir)
            click.echo(f"Cleaned {os.path.relpath(persist_dir, project_root)}/")
        build_freeze = build_dir / "_freeze"
        if build_freeze.exists():
            shutil.rmtree(build_freeze)

    from .._build import pipeline
    from .._build.log import BuildLog

    config = layout.load_config()
    try:
        pipeline.prepare_for_freeze(
            config, layout, BuildLog(), remote=HttpRemote(report=print_warning)
        )
    except BuildError:
        # Exit without repeating the preparation failure report
        sys.exit(1)

    # Render each page individually (forces execution even with freeze)
    click.echo()
    rendered: list[str] = []
    failed: list[str] = []

    for page in pages:
        target = freeze_cache.find_page(build_dir, page)
        if target is None:
            click.echo(f"  ✗ {page} — not found in build directory", err=True)
            click.echo(
                "    Hint: The site does not publish this page. Freeze renders only pages of the\n"
                "    user guide, the configured sections and the custom pages.",
                err=True,
            )
            failed.append(page)
            continue

        click.echo(f"  Rendering {page} → {target.relative_to(build_dir)} ...")
        result = freeze_cache.render_page(config, build_dir, target)

        if result.returncode != 0:
            click.echo(f"  ✗ {page} — render failed", err=True)
            if result.stderr:
                # Show last few lines of error
                err_lines = result.stderr.strip().splitlines()[-5:]
                for line in err_lines:
                    click.echo(f"    {line}", err=True)
            failed.append(page)
        else:
            rendered.append(page)
            click.echo(f"  ✓ {page}")

    # Copy _freeze/ from build dir to persistent location
    build_freeze = build_dir / "_freeze"
    if build_freeze.is_dir() and rendered:
        click.echo()
        click.echo(f"Persisting _freeze/ → {persist_dir.relative_to(project_root)}/")
        updated_files = freeze_cache.merge(build_freeze, persist_dir)
        click.echo(f"  Updated {updated_files} cached file(s)")

        # Show git status hint
        click.echo()
        click.echo("To commit the updated freeze cache:")
        click.echo(f"  git add {persist_dir.relative_to(project_root)}/")
        click.echo(f'  git commit -m "Update freeze cache for {", ".join(rendered)}"')
    elif not rendered:
        click.echo()
        click.echo("No pages rendered successfully.")
    else:
        click.echo()
        click.echo("No _freeze/ directory produced (pages may not have executable code).")

    if failed:
        click.echo()
        click.echo(f"{len(failed)} page(s) failed to render.", err=True)
        sys.exit(1)


def _format_seconds(s: float) -> str:
    """Format seconds as a human-readable duration string."""
    if s < 60:
        return f"{s:.1f}s"
    m = int(s) // 60
    sec = s - m * 60
    return f"{m}m {sec:.1f}s"


def _find_build_timing(
    project_path: Path, output_dir: Path | None = None, config_path: str | None = None
) -> Path | None:
    """Locate build-timings.json in the site output directory."""
    # Explicit output-dir takes priority
    if output_dir is not None:
        candidate = output_dir / "build-timings.json"
        if candidate.exists():
            return candidate
    # Prefer the selected layout's assembled deployment output.
    layout = Layout.make(project_path, Path(config_path) if config_path else None)
    candidate = layout.site_dir / "build-timings.json"
    if candidate.exists():
        return candidate
    # Single-version or build dir fallback
    candidate = project_path / "_site" / "build-timings.json"
    if candidate.exists():
        return candidate
    return None


def _print_timing_table(data: dict, top: int | None, version_filter: str | None) -> None:
    """Print an ASCII table from build-timings.json data."""

    build_time = data.get("build_time", "unknown")
    total = data.get("total_seconds", 0)

    click.echo()
    click.echo(f"  Build time: {build_time}")
    click.echo(f"  Total: {_format_seconds(total)}")
    click.echo()

    if "versions" in data:
        versions = data["versions"]
        if version_filter:
            if version_filter not in versions:
                click.echo(f"  Version '{version_filter}' not found.", err=True)
                click.echo(f"  Available: {', '.join(sorted(versions.keys()))}", err=True)
                sys.exit(1)
            versions = {version_filter: versions[version_filter]}

        for tag, vdata in versions.items():
            pages = vdata["pages"]
            if top:
                pages = pages[:top]
            click.echo(f"  Version: {tag} ({_format_seconds(vdata['seconds'])})")
            _print_page_table(pages)
            click.echo()
    elif "pages" in data:
        pages = data["pages"]
        if top:
            pages = pages[:top]
        _print_page_table(pages)
        click.echo()


def _print_page_table(pages: list[dict]) -> None:
    """Print a page timing table."""
    if not pages:
        click.echo("  No page timings recorded.")
        return

    # Check if any pages have freeze info
    has_frozen = any(p.get("frozen") for p in pages)

    # Compute column widths
    max_page = max(len(p["page"]) for p in pages)
    max_page = max(max_page, 4)  # minimum width for "Page" header
    time_col = 10  # width for time column
    bar_col = 20  # width for bar chart

    slowest = pages[0]["seconds"] if pages else 1

    # Header
    if has_frozen:
        header = f"  {'Page':<{max_page}}  {'Time':>{time_col}}    Bar"
        click.echo(header)
        click.echo(f"  {'─' * max_page}  {'─' * time_col}  {'─' * (bar_col + 2)}")
    else:
        header = f"  {'Page':<{max_page}}  {'Time':>{time_col}}  Bar"
        click.echo(header)
        click.echo(f"  {'─' * max_page}  {'─' * time_col}  {'─' * bar_col}")

    # Rows
    for p in pages:
        page = p["page"]
        secs = p["seconds"]
        time_str = _format_seconds(secs)
        bar_len = int((secs / slowest) * bar_col) if slowest > 0 else 0
        bar = "█" * bar_len
        if has_frozen:
            marker = "❄" if p.get("frozen") else " "
            click.echo(f"  {page:<{max_page}}  {time_str:>{time_col}} {marker} {bar}")
        else:
            click.echo(f"  {page:<{max_page}}  {time_str:>{time_col}}  {bar}")

    if has_frozen:
        click.echo()
        click.echo("  ❄ = served from freeze cache")


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--top",
    type=int,
    default=None,
    help="Show only the N slowest pages.",
)
@click.option(
    "--version",
    "version_filter",
    type=str,
    default=None,
    help="Show timings for a specific version only (multi-version builds).",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output raw JSON instead of a table.",
)
@click.option(
    "--output-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=None,
    help="Path to the build output directory (if different from default _site).",
)
@_options.config_option
def timings(
    project_path: str | None,
    top: int | None,
    version_filter: str | None,
    output_json: bool,
    output_dir: str | None,
    config_path: str | None = None,
) -> None:
    """Show page-level build timings from the last build.

    Reads the build-timings.json artifact generated during 'great-docs build' and
    displays per-page render durations as a sorted table. Pages are listed
    slowest-first to help identify bottlenecks.

    Run 'great-docs build' first to generate the timing data.

    \b
    Examples:
      great-docs timings
      great-docs timings --top 10
      great-docs timings --version 0.10
      great-docs timings --output-dir ./public
      great-docs timings --json
    """
    import json

    project_root = Path(project_path) if project_path else Path.cwd()
    out_dir = Path(output_dir) if output_dir else None
    timing_path = _find_build_timing(project_root, output_dir=out_dir, config_path=config_path)

    if not timing_path:
        click.echo("No build-timings.json found.", err=True)
        click.echo("Run 'great-docs build' first to generate timing data.", err=True)
        sys.exit(1)

    data = json.loads(timing_path.read_text())

    if output_json:
        click.echo(json.dumps(data, indent=2))
        return

    _print_timing_table(data, top=top, version_filter=version_filter)
