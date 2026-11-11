from __future__ import annotations

import re
import sys
from functools import wraps as wraps
from pathlib import Path as Path
from typing import TYPE_CHECKING as TYPE_CHECKING
from typing import Any as Any
from typing import Callable as Callable

import click

from ._build import site
from ._build.steps import PROJECT_ERRORS, USER_CODE_ERRORS, BuildError
from ._cli import options as _options
from ._cli.app import OrderedGroup as OrderedGroup
from ._cli.app import cli as cli
from ._cli.build import build as build
from ._cli.build import freeze as freeze
from ._cli.build import freeze_cache as freeze_cache
from ._cli.build import os as os
from ._cli.build import preview as preview
from ._cli.build import print_warning as print_warning
from ._cli.build import quarto as quarto
from ._cli.build import repository as repository
from ._cli.build import serve as serve
from ._cli.build import timings as timings
from ._cli.build import zipfile as zipfile
from ._cli.project import changelog as changelog
from ._cli.project import changelog_page as changelog_page
from ._cli.project import config as config
from ._cli.project import init as init
from ._cli.project import migrate_layout as migrate_layout
from ._cli.project import scan as scan
from ._cli.project import uninstall as uninstall
from ._content import user_guide as user_guide
from ._project import Project as Project
from ._project import manifest as _manifest
from ._project.layout import CONVENTIONAL_DOC_DIRS as CONVENTIONAL_DOC_DIRS
from ._project.layout import Layout as Layout
from ._project.manifest import ManifestError as ManifestError
from ._project.remote import HttpRemote as HttpRemote
from ._project.scaffold import update_gitignore as update_gitignore
from ._reference.exports import Exports as Exports
from ._website import quarto_yml as quarto_yml
from .config import ConfigError as ConfigError
from .core import GreatDocs as GreatDocs

# Command handlers report `PROJECT_ERRORS` as `Error: <message>` or JSON and exit with
# status 1. Handlers that load the project's package also report `USER_CODE_ERRORS`.
# Commands may handle additional errors separately. Unhandled exceptions show a traceback
# and exit with status 1.


def _detect_python_version(project_root: Path) -> str | None:
    """
    Choose the Python version a documentation workflow runs on

    Parameters
    ----------
    project_root
        The directory holding the packaging files.

    Returns
    -------
    :
        A `major.minor` version from the project's Python requirement. For a requirement
        containing `>=` or `~=`, the first version (the lower bound), such as `3.10` for
        `>=3.10,<3.13`; otherwise, the highest version named. `None` when the project declares
        no requirement, the requirement names no version, or the metadata cannot be read.
    """
    try:
        requires_python = _manifest.read(project_root)["requires_python"]
    except ManifestError:
        return None

    # CI uses major.minor versions, for example from `>=3.12`, `>=3.10,<3.13`,
    # `~=3.11` or `>=3.9`.
    matches = re.findall(r"(\d+\.\d+)", requires_python)
    if not matches:
        return None

    # Treat the first version as the lower bound for `>=` and `~=` requirements.
    if ">=" in requires_python or "~=" in requires_python:
        return matches[0]

    # Other specifiers use the highest named version as the likely CI target.
    versions = [tuple(map(int, v.split("."))) for v in matches]
    max_version = max(versions)
    return f"{max_version[0]}.{max_version[1]}"


def _detect_package_manager(project_root: Path) -> str:
    """Detect the package manager used by the project.

    Checks for lock files to determine which package manager is in use:
    - uv.lock -> uv
    - poetry.lock -> poetry
    - Otherwise -> pip (default)

    Returns:
        One of: 'uv', 'poetry', or 'pip'
    """
    if (project_root / "uv.lock").exists():
        return "uv"
    if (project_root / "poetry.lock").exists():
        return "poetry"
    return "pip"


def _detect_optional_dependencies(project_root: Path) -> list[str]:
    """
    Choose the extras a documentation workflow installs

    Parameters
    ----------
    project_root
        The directory holding the packaging files.

    Returns
    -------
    :
        The sorted names of extras related to documentation, development or testing, such
        as `dev`, `docs` or `test`, for a command like `pip install -e ".[dev,docs]"`. An empty
        list when there are none or the project's metadata cannot be read.
    """
    try:
        extras = _manifest.read(project_root)["optional_dependencies"]
    except ManifestError:
        return []

    # Documentation workflows may also need development, notebook or test dependencies.
    terms = ["dev", "doc", "notebook", "test", "all", "full"]
    return sorted(extra for extra in extras if any(term in extra.lower() for term in terms))


@click.group(cls=OrderedGroup)
def ci() -> None:
    """Helpers meant to run inside CI (GitHub Actions).

    These emit the "preview this build locally" hints that let reviewers open a
    pull request's docs without a preview host: a workflow log notice and a
    sticky PR comment, both pointing at 'great-docs preview'.

    \b
    Examples:
      great-docs ci notice --run "$GITHUB_RUN_ID" --pr 302
      great-docs ci pr-comment --run "$GITHUB_RUN_ID" --pr 302
    """


@click.command(name="pr-comment")
@click.option(
    "--run", "run_id", type=int, required=True, help="Workflow run id that built the site."
)
@click.option("--pr", type=int, required=True, help="Pull request number to comment on.")
@click.option(
    "--repo",
    default=None,
    help="GitHub repo as 'owner/repo' (default: $GITHUB_REPOSITORY, then git remote).",
)
def ci_pr_comment(run_id: int, pr: int, repo: str | None) -> None:
    """Post or refresh a sticky PR comment with the local-preview command.

    Reads the token from GITHUB_TOKEN / GH_TOKEN and needs 'pull-requests: write'.
    """
    from ._build.ci import post_preview_comment
    from ._build.pr_preview import PreviewError

    try:
        action, repo_slug = post_preview_comment(run_id=run_id, pr=pr, repo_override=repo)
        click.echo(f"✓ {action.capitalize()} preview comment on {repo_slug}#{pr}")
    except PreviewError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command(name="notice")
@click.option(
    "--run", "run_id", type=int, required=True, help="Workflow run id that built the site."
)
@click.option("--pr", type=int, default=None, help="Pull request number (adds the --pr hint).")
def ci_notice(run_id: int, pr: int | None) -> None:
    """Print a workflow log notice with the local-preview command."""
    from ._build.ci import render_notice_lines

    for line in render_notice_lines(run_id, pr):
        click.echo(line)


ci.add_command(ci_pr_comment)
ci.add_command(ci_notice)


# Register commands in the desired order
cli.add_command(init)
cli.add_command(build)
cli.add_command(preview)
cli.add_command(uninstall)
cli.add_command(config)
cli.add_command(ci)


cli.add_command(migrate_layout)


cli.add_command(scan)


cli.add_command(freeze)


# ---------------------------------------------------------------------------
# great-docs timing
# ---------------------------------------------------------------------------


cli.add_command(timings)


@click.command(name="setup-github-pages")
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--main-branch",
    type=str,
    default="main",
    help="Main branch name for deployment (default: main)",
)
@click.option(
    "--python-version",
    type=str,
    default=None,
    help="Python version for CI (default: auto-detect from pyproject.toml, or 3.11)",
)
@click.option(
    "--package-manager",
    type=click.Choice(["auto", "pip", "uv", "poetry"]),
    default="auto",
    help="Package manager for installing dependencies (default: auto-detect)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing workflow file without prompting",
)
@click.option(
    "--install-from-main",
    is_flag=True,
    help="Install Great Docs from GitHub main branch instead of PyPI release",
)
@_options.config_option
def setup_github_pages(
    project_path: str | None,
    main_branch: str,
    python_version: str | None,
    package_manager: str,
    force: bool,
    install_from_main: bool,
    config_path: str | None = None,
) -> None:
    """Set up automatic deployment to GitHub Pages.

    This command creates a GitHub Actions workflow that automatically builds
    and deploys your documentation when you push to the main branch.

    \b
    The workflow will:
    • Build docs on every push and pull request
    • Deploy to GitHub Pages on main branch pushes
    • Use Quarto's official GitHub Action for reliable builds
    • Install dev dependencies (auto-detected from your package manager)

    The Python version is automatically detected from your pyproject.toml's
    `requires-python` field. Use '--python-version' to override.

    The package manager is auto-detected by checking for lock files:
    • uv.lock -> uses uv (installs dev dependencies automatically)
    • poetry.lock -> uses poetry (installs with dev dependencies)
    • Otherwise -> uses pip with optional extras like [dev,docs]

    After running this command, commit the workflow file and enable GitHub
    Pages in your repository settings (Settings -> Pages ->
    Source: GitHub Actions).

    \b
    Examples:
      great-docs setup-github-pages                     # Auto-detect everything
      great-docs setup-github-pages --main-branch dev   # Deploy from 'dev' branch
      great-docs setup-github-pages --python-version 3.12
      great-docs setup-github-pages --package-manager uv
      great-docs setup-github-pages --force             # Overwrite existing workflow
      great-docs setup-github-pages --install-from-main # Use GitHub main branch
    """

    try:
        layout = Layout.make(
            Path(project_path or Path.cwd()), Path(config_path) if config_path else None
        )
        project_root = layout.package_root

        # Auto-detect Python version if not specified
        # Great Docs requires Python 3.11+, so we enforce that as the floor
        min_great_docs_version = (3, 11)
        if python_version is None:
            detected_version = _detect_python_version(project_root)
            if detected_version:
                detected_tuple = tuple(int(x) for x in detected_version.split("."))
                if detected_tuple < min_great_docs_version:
                    python_version = f"{min_great_docs_version[0]}.{min_great_docs_version[1]}"
                    click.echo(
                        f"📦 Project requires Python {detected_version}, "
                        f"but Great Docs needs >={python_version}; using {python_version}"
                    )
                else:
                    python_version = detected_version
                    click.echo(f"📦 Detected Python {python_version} from pyproject.toml")
            else:
                python_version = "3.12"
                click.echo("📦 Using default Python 3.12 (no requires-python found)")

        # Auto-detect package manager if not specified
        if package_manager == "auto":
            package_manager = _detect_package_manager(project_root)
            if package_manager == "uv":
                click.echo("🔧 Detected uv (found uv.lock)")
            elif package_manager == "poetry":
                click.echo("🔧 Detected poetry (found poetry.lock)")
            else:
                click.echo("🔧 Using pip (no uv.lock or poetry.lock found)")

        # Determine great-docs install source
        if install_from_main:
            great_docs_install = "git+https://github.com/posit-dev/great-docs.git"
            click.echo("📥 Will install Great Docs from GitHub main branch")
        else:
            great_docs_install = "great-docs"
            click.echo("📥 Will install Great Docs from PyPI (latest release)")

        # Generate install commands based on package manager
        if package_manager == "uv":
            install_commands = f"""\
          python -m pip install uv
          uv sync
          uv pip install {great_docs_install}"""
            build_command = "uv run great-docs build"
        elif package_manager == "poetry":
            install_commands = f"""\
          python -m pip install poetry
          poetry install
          poetry run pip install {great_docs_install}"""
            build_command = "poetry run great-docs build"
        else:
            # pip: try to detect optional dependencies
            optional_deps = _detect_optional_dependencies(project_root)
            if optional_deps:
                extras = ",".join(optional_deps)
                click.echo(f"📋 Found optional dependencies: {extras}")
                install_commands = f"""\
          python -m pip install --upgrade pip
          python -m pip install -e ".[{extras}]"
          python -m pip install {great_docs_install}"""
            else:
                install_commands = f"""\
          python -m pip install --upgrade pip
          python -m pip install -e .
          python -m pip install {great_docs_install}"""
            build_command = "great-docs build"

        if config_path:
            import shlex

            build_command += " --config " + shlex.quote(
                str(layout.config_path.relative_to(project_root))
            )

        # Create .github/workflows directory
        workflow_dir = project_root / ".github" / "workflows"
        workflow_file = workflow_dir / "docs.yml"

        # Check if workflow file already exists
        if workflow_file.exists() and not force:
            if not click.confirm(
                f"⚠️  Workflow file already exists at {workflow_file.relative_to(project_root)}\n"
                "   Overwrite it?",
                default=False,
            ):
                click.echo("❌ Aborted. Use --force to overwrite without prompting.")
                sys.exit(1)

        # Create directory structure
        workflow_dir.mkdir(parents=True, exist_ok=True)

        # Load template
        try:
            # For Python 3.9+
            from importlib.resources import files

            template_file = files("great_docs").joinpath("assets/github-workflow-template.yml")
            template_content = template_file.read_text()
        except (ImportError, AttributeError):
            # For Python 3.8 or earlier
            from importlib_resources import files

            template_file = files("great_docs").joinpath("assets/github-workflow-template.yml")
            template_content = template_file.read_text()

        # Replace placeholders (using replace() to handle linter-formatted templates)
        workflow_content = template_content.replace("{ main_branch }", main_branch)
        workflow_content = workflow_content.replace("{main_branch}", main_branch)
        workflow_content = workflow_content.replace("{ python_version }", python_version)
        workflow_content = workflow_content.replace("{python_version}", python_version)
        workflow_content = workflow_content.replace("{install_commands}", install_commands)
        workflow_content = workflow_content.replace("{build_command}", build_command)
        workflow_content = re.sub(
            r"(?<![\w/-])(?:great-docs|docs)/_site",
            lambda match: layout.site_dir.relative_to(project_root).as_posix(),
            workflow_content,
        )

        # Write workflow file
        workflow_file.write_text(workflow_content)

        click.echo(
            f"✅ Created GitHub Actions workflow at {workflow_file.relative_to(project_root)}"
        )
        click.echo()
        click.echo("📋 Next steps:")
        click.echo("   1. Commit and push the workflow file to your repository")
        click.echo("   2. Go to your repository Settings → Pages")
        click.echo("   3. Set Source to 'GitHub Actions' (or 'gh-pages branch' if using that)")
        click.echo(f"   4. Push changes to '{main_branch}' branch to trigger deployment")
        click.echo()
        click.echo("💡 The workflow will:")
        click.echo(f"   • Build docs on every push to '{main_branch}' and pull requests")
        click.echo("   • Automatically deploy to GitHub Pages on main branch")
        click.echo("   • Comment on pull requests with a 'great-docs preview' command")

    except PROJECT_ERRORS as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Register commands in the desired order
cli.add_command(setup_github_pages)


@click.command(name="check-links")
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--source-only",
    is_flag=True,
    help="Only check links in Python source files",
)
@click.option(
    "--docs-only",
    is_flag=True,
    help="Only check links in documentation files",
)
@click.option(
    "--timeout",
    type=float,
    default=10.0,
    help="Timeout in seconds for each HTTP request (default: 10)",
)
@click.option(
    "--ignore",
    "-i",
    multiple=True,
    help="URL pattern to ignore (can be used multiple times)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed progress for each URL checked",
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Output results as JSON",
)
@_options.config_option
def check_links(
    project_path: str | None,
    source_only: bool,
    docs_only: bool,
    timeout: int,
    ignore: tuple[str, ...],
    verbose: bool,
    json_output: bool,
    config_path: str | None = None,
) -> None:
    """Check for broken links in source code and documentation.

    This command scans Python source files and documentation ('.qmd', '.md')
    for URLs and checks their HTTP status. It reports broken links (404s)
    and warns about redirects.

    \b
    Default ignore patterns include:
    • localhost and 127.0.0.1 URLs
    • example.com, example.org, yoursite.com URLs
    • Placeholder URLs with brackets like [username]

    \b
    Examples:
      great-docs check-links                        # Check all links
      great-docs check-links --verbose              # Show progress for each URL
      great-docs check-links --docs-only            # Only check documentation
      great-docs check-links --source-only          # Only check source code
      great-docs check-links -i "github.com/.*#"    # Ignore GitHub anchor links
      great-docs check-links --timeout 5            # Use 5 second timeout
      great-docs check-links --json-output          # Output as JSON
    """
    import json as json_module

    try:
        docs = GreatDocs(project_path=project_path, config_path=config_path)

        # Determine what to scan
        include_source = not docs_only
        include_docs = not source_only

        # Build ignore patterns list
        ignore_patterns = list(ignore) if ignore else []
        # Add default ignore patterns
        default_ignores = [
            r"localhost",
            r"127\.0\.0\.1",
            r"0\.0\.0\.0",
            r"example\.com",
            r"example\.org",
            r"example\.net",
            r"\[",  # URLs with brackets (placeholders like [username])
            r"yoursite\.com",
            r"your-package",
            r"YOUR-USERNAME",
            r"\.git(@|$)",  # Git URLs (pip install git+...) with optional branch/tag
        ]
        ignore_patterns.extend(default_ignores)

        if not json_output:
            click.echo("🔗 Checking links...")
            if not include_source:
                click.echo("   (documentation files only)")
            elif not include_docs:
                click.echo("   (source files only)")

        results = docs.check_links(
            include_source=include_source,
            include_docs=include_docs,
            timeout=timeout,
            ignore_patterns=ignore_patterns,
            verbose=verbose,
        )

        if json_output:
            # Output as JSON
            click.echo(json_module.dumps(results, indent=2))
            sys.exit(1 if results["broken"] else 0)

        # Print summary
        click.echo("\n" + "=" * 60)
        click.echo("📊 Link Check Summary")
        click.echo("=" * 60)

        total_checked = results["total"] - len(results["skipped"])
        click.echo(f"\n   Total URLs found: {results['total']}")
        click.echo(f"   URLs checked: {total_checked}")
        click.echo(f"   URLs skipped: {len(results['skipped'])}")

        click.echo(f"\n   ✅ OK: {len(results['ok'])}")
        click.echo(f"   ↪️  Redirects: {len(results['redirects'])}")
        click.echo(f"   ❌ Broken: {len(results['broken'])}")

        # Show broken links
        if results["broken"]:
            click.echo("\n" + "-" * 60)
            click.echo("❌ Broken Links:")
            click.echo("-" * 60)
            for item in results["broken"]:
                status = item["status"] or "N/A"
                click.echo(f"\n   [{status}] {item['url']}")
                click.echo(f"   Error: {item['error']}")
                click.echo("   Found in:")
                for f in item["files"]:
                    click.echo(f"     • {f}")

        # Show redirects
        if results["redirects"]:
            click.echo("\n" + "-" * 60)
            click.echo("↪️  Redirects (consider updating):")
            click.echo("-" * 60)
            for item in results["redirects"]:
                click.echo(f"\n   [{item['status']}] {item['url']}")
                click.echo(f"   → {item['location']}")
                click.echo("   Found in:")
                for f in item["files"]:
                    click.echo(f"     • {f}")

        # Exit with error code if broken links found
        if results["broken"]:
            click.echo("\n⚠️  Found broken links. Please fix them before deployment.")
            sys.exit(1)
        else:
            click.echo("\n✅ All links are valid!")
            sys.exit(0)

    except ImportError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("\nInstall the requests package with: pip install requests", err=True)
        sys.exit(1)
    except PROJECT_ERRORS as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


cli.add_command(check_links)


# ---------------------------------------------------------------------------
# great-docs check-examples
# ---------------------------------------------------------------------------


@click.command(name="check-examples")
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--timeout",
    type=int,
    default=30,
    help=(
        "Seconds budgeted per cell. Each page's render stops after the cell count "
        "times this value plus 60 seconds (default: 30)"
    ),
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Output results as JSON",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show full tracebacks in console output",
)
@click.option(
    "--include",
    type=str,
    default=None,
    help="Glob pattern to filter which files to check (relative to the docs source directory)",
)
@click.option(
    "--exclude",
    type=str,
    default=None,
    help="Glob pattern to exclude files from checking (relative to the docs source directory)",
)
@click.option(
    "--no-docstrings",
    is_flag=True,
    help="Skip docstring example checking",
)
@click.option(
    "--docstrings-only",
    is_flag=True,
    help="Only check docstring examples, skip .qmd files",
)
@click.option(
    "--parallel",
    is_flag=True,
    help="Run pages concurrently (each in its own subprocess/kernel)",
)
@click.option(
    "--jobs",
    "-j",
    type=int,
    default=1,
    help="Number of concurrent pages (implies --parallel if > 1)",
)
@click.option(
    "--log-file",
    type=click.Path(),
    default=None,
    help="Where to write full tracebacks (default: .great-docs/check-examples.log)",
)
@_options.config_option
def check_examples(
    paths: tuple[str, ...],
    project_path: str | None,
    timeout: int,
    json_output: bool,
    verbose: bool,
    include: str | None,
    exclude: str | None,
    no_docstrings: bool,
    docstrings_only: bool,
    parallel: bool,
    jobs: int,
    log_file: str | None,
    config_path: str | None = None,
) -> None:
    """Check that Python code examples execute without errors.

    Renders .qmd files and docstring examples via Quarto, reporting which
    cells succeed and which error. Every cell is executed even if earlier
    cells fail (Quarto's error: true mode).

    Requires Quarto to be installed (https://quarto.org).

    PATHS are optional files or directories to check. When omitted, the
    entire project is scanned.

    \b
    Examples:
      great-docs check-examples
      great-docs check-examples reference/
      great-docs check-examples guide/getting-started.qmd --verbose
      great-docs check-examples --json-output
      great-docs check-examples --parallel --jobs 4
      great-docs check-examples --no-docstrings --timeout 60
    """
    from ._build.log import Colors, MultiProgressBar, ProgressBar
    from ._checks.examples import (
        check_examples as run_check,
    )
    from ._checks.examples import (
        format_console,
        format_json,
        write_log_file,
    )

    layout = Layout.make(
        Path(project_path) if project_path else Path.cwd(),
        Path(config_path) if config_path else None,
    )
    project_root = layout.package_root
    # Click validates PATHS against the working directory, which may differ
    # from the package root (e.g. when run from inside `docs/`)
    paths = tuple(str(Path(p).resolve()) for p in paths)

    if not json_output:
        click.echo("Checking examples...")

    # Progress bar state — populated by progress_setup callback
    colors = Colors()
    progress_bar: ProgressBar | MultiProgressBar | None = None
    section_indices: dict[str, int] = {}

    def _progress_setup(section_totals: dict[str, int]) -> None:
        nonlocal progress_bar, section_indices
        if json_output or not section_totals:
            return
        labels = list(section_totals.keys())
        if len(labels) == 1:
            progress_bar = ProgressBar(
                label=labels[0],
                total=section_totals[labels[0]],
                colors=colors,
            )
            section_indices[labels[0]] = 0
        else:
            progress_bar = MultiProgressBar(labels=labels, colors=colors)
            for i, label in enumerate(labels):
                section_indices[label] = i
                progress_bar.set_total(i, section_totals[label])

    def _progress_callback(section: str, page_path: str, current: int, total: int) -> None:
        if progress_bar is None:
            return
        idx = section_indices.get(section, 0)
        if isinstance(progress_bar, MultiProgressBar):
            progress_bar.update(idx, current)
        else:
            progress_bar.update(current)

    result = run_check(
        project_root=project_root,
        paths=paths if paths else None,
        timeout=timeout,
        include=include,
        exclude=exclude,
        no_docstrings=no_docstrings,
        docstrings_only=docstrings_only,
        parallel=parallel,
        jobs=jobs,
        progress_callback=_progress_callback if not json_output else None,
        progress_setup=_progress_setup if not json_output else None,
        layout=layout,
    )

    if progress_bar is not None:
        progress_bar.finish()

    # Check for setup errors (exit code 2)
    setup_errors = [p for p in result.pages if p.status == "error" and p.path == "(setup)"]
    if setup_errors:
        for err in setup_errors:
            click.echo(f"Error: {err.message}", err=True)
        sys.exit(2)

    if json_output:
        click.echo(format_json(result))
    else:
        click.echo(format_console(result, verbose=verbose))

        # Write log file
        resolved_log = (
            Path(log_file) if log_file else project_root / ".great-docs" / "check-examples.log"
        )
        if write_log_file(result, resolved_log):
            click.echo(f"Full tracebacks: {resolved_log}")

    if result.cells_failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)


cli.add_command(check_examples)


cli.add_command(changelog)


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--docs-dir",
    type=str,
    help="Path to documentation directory relative to project root",
)
@click.option(
    "--include-docstrings",
    is_flag=True,
    help="Also check Python docstrings",
)
@click.option(
    "--spelling-only",
    is_flag=True,
    help="Only check spelling (SpellCheck rule)",
)
@click.option(
    "--grammar-only",
    is_flag=True,
    help="Exclude spelling, check grammar/style only",
)
@click.option(
    "--only",
    "only_rules",
    type=str,
    help="Only run these rules (comma-separated)",
)
@click.option(
    "--ignore",
    "ignore_rules",
    type=str,
    help="Skip these rules (comma-separated)",
)
@click.option(
    "-d",
    "--dictionary",
    "custom_words",
    multiple=True,
    help="Additional word(s) to consider correct (can be used multiple times)",
)
@click.option(
    "--dictionary-file",
    type=click.Path(exists=True),
    help="Path to file with custom words (one per line)",
)
@click.option(
    "--dialect",
    type=click.Choice(["us", "uk", "au", "in", "ca"], case_sensitive=False),
    default="us",
    help="English dialect (default: us)",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Show detailed progress for each file checked",
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Output results as JSON for CI",
)
@click.option(
    "--compact",
    is_flag=True,
    help="One line per issue (GCC-style output)",
)
@click.option(
    "--max-issues",
    type=int,
    default=None,
    help="Exit with error if more than N issues found",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Disable smart defaults (check everything, no builtin dictionary)",
)
@click.option(
    "--no-builtin-dictionary",
    is_flag=True,
    help="Don't add built-in technical terms to dictionary",
)
@click.argument("files", nargs=-1, type=click.Path(exists=True))
@_options.config_option
def proofread(
    project_path,
    docs_dir,
    include_docstrings,
    spelling_only,
    grammar_only,
    only_rules,
    ignore_rules,
    custom_words,
    dictionary_file,
    dialect,
    verbose,
    json_output,
    compact,
    max_issues,
    strict,
    no_builtin_dictionary,
    files,
    config_path: str | None = None,
):
    """Check spelling and grammar in documentation files using Harper.

    Harper is a fast, privacy-first grammar checker that runs locally.
    It checks spelling, grammar, punctuation, and style in a single pass.

    \b
    By default, checks all documentation files (.qmd, .md) in the project.
    Uses smart defaults to reduce noise in technical documentation:
      - Ignores formatting rules that conflict with code/YAML (unless '--strict')
      - Includes a built-in dictionary of technical terms (unless '--no-builtin-dictionary')

    \b
    Examples:
      great-docs proofread                         # Check all docs (smart defaults)
      great-docs proofread --strict                # Check everything (no smart defaults)
      great-docs proofread --spelling-only         # Just spelling
      great-docs proofread --dialect=uk            # UK English
      great-docs proofread -d griffe -d quartodoc  # Add custom words
      great-docs proofread --json-output           # JSON output for CI
      great-docs proofread --ignore=SpellCheck     # Skip specific rules
      great-docs proofread README.md user_guide/*.qmd  # Specific files
      great-docs proofread recipes/                # Pages in a directory

    \b
    Requires harper-cli to be installed:
      brew install harper      # macOS
      cargo install harper-cli # any platform
    """
    import json as json_module
    from collections import defaultdict

    from ._checks import inputs
    from ._checks import proofread as proofreading
    from ._checks.harper import HarperError, HarperNotFoundError, check_harper_available

    try:
        # Check if Harper is available
        available, harper_info = check_harper_available()
        if not available:
            click.echo(f"Error: {harper_info}", err=True)
            sys.exit(3)

        show_progress = verbose and not json_output and not compact
        if show_progress:
            click.echo(f"\n🔍 Proofreading with {harper_info}...\n")
            if not strict:
                click.echo("Using smart defaults for technical docs. Use --strict to disable.\n")

        # Determine files to check
        layout = Layout.make(
            Path(project_path) if project_path else Path.cwd(),
            Path(config_path) if config_path else None,
        )
        config = layout.load_config()

        if files:
            files_to_check = inputs.expand_directories(Path(f) for f in files)
        else:
            if docs_dir:
                files_to_check = inputs.find_pages_in(Path(docs_dir), layout)
            else:
                files_to_check = inputs.find_pages(
                    config,
                    layout,
                    report=lambda message: click.echo(f"⚠️  {message}", err=True),
                )
            if include_docstrings:
                project = Project.make(config, layout)
                if project.importable_name:
                    files_to_check += inputs.find_modules(layout, project.importable_name)

        if not files_to_check:
            click.echo("No documentation files found to check.", err=True)
            sys.exit(0)

        words = list(custom_words)
        if dictionary_file:
            try:
                with open(dictionary_file, "r", encoding="utf-8") as f:
                    for line in f:
                        word = line.strip()
                        if word and not word.startswith("#"):
                            words.append(word)
            except (OSError, UnicodeDecodeError) as e:
                click.echo(f"Warning: Could not read dictionary file: {e}", err=True)

        only = ["SpellCheck"] if spelling_only else []
        ignore = ["SpellCheck"] if grammar_only and not spelling_only else []
        if only_rules:
            only.extend(only_rules.split(","))
        if ignore_rules:
            ignore.extend(ignore_rules.split(","))

        options = proofreading.Options(
            dialect=dialect,
            words=words,
            only_rules=only,
            ignore_rules=ignore,
            builtin_dictionary=not strict and not no_builtin_dictionary,
            default_ignores=not strict,
        )
        # Harper checks Python files only when docstring checking is requested.
        checked_suffixes = {".md", ".qmd", ".py"} if include_docstrings else {".md", ".qmd"}
        checked_files = [f for f in files_to_check if f.suffix in checked_suffixes]
        all_results = proofreading.check(
            checked_files,
            layout.package_root,
            options,
            report=click.echo if show_progress else lambda _line: None,
        )

        # Aggregate results
        total_issues = sum(len(r.issues) for r in all_results)

        # Group by kind and rule
        by_kind = defaultdict(int)
        by_rule = defaultdict(int)
        all_lints = []

        for result in all_results:
            for lint in result.issues:
                by_kind[lint.kind] += 1
                by_rule[lint.rule] += 1
                all_lints.append(lint)

        # Output results
        if json_output:
            output = {
                "version": "1.0.0",
                "harper_version": harper_info.split()[-1] if harper_info else "unknown",
                "dialect": dialect,
                "files_checked": len(checked_files),
                "total_issues": total_issues,
                "summary": {
                    "by_kind": dict(by_kind),
                    "by_rule": dict(by_rule),
                },
                "issues": [
                    {
                        "file": lint.file,
                        "line": lint.line,
                        "column": lint.column,
                        "kind": lint.kind,
                        "rule": lint.rule,
                        "message": lint.message,
                        "matched_text": lint.matched_text,
                        "suggestions": lint.suggestions,
                        "priority": lint.priority,
                    }
                    for lint in all_lints
                ],
            }
            click.echo(json_module.dumps(output, indent=2))

        elif compact:
            # GCC-style output: file:line:col: kind::rule: message
            for lint in all_lints:
                click.echo(
                    f"{lint.file}:{lint.line}:{lint.column}: "
                    f"{lint.kind}::{lint.rule}: {lint.message}"
                )

        else:
            # Human-readable output
            if all_results:
                for result in all_results:
                    if result.issues:
                        click.echo(f"\n📄 {result.file} ({len(result.issues)} issue(s))")
                        for lint in result.issues:
                            # Clean up suggestion format
                            suggestion = ""
                            if lint.suggestions:
                                first_sugg = lint.suggestions[0]
                                # Harper suggestions often have "Replace with: " prefix
                                if "Replace with:" in first_sugg:
                                    first_sugg = first_sugg.replace("Replace with:", "→").strip()
                                    first_sugg = first_sugg.strip('"').strip('"').strip('"')
                                suggestion = f" {first_sugg}"

                            click.echo(
                                f"   Line {lint.line}, Col {lint.column} "
                                f'[{lint.kind}] "{lint.matched_text}"{suggestion}'
                            )
                            if verbose:
                                click.echo(f"      {lint.message}")
                    elif verbose and result.error is None:
                        click.echo(f"✅ {result.file}")

            # Print summary
            click.echo("\n" + "═" * 66)
            click.echo("📊 Proofread Results")
            click.echo("═" * 66)

            click.echo(f"\n   Files checked: {len(files_to_check)}")
            click.echo(f"   Issues found: {total_issues}")

            if by_kind:
                click.echo("\n   By category:")
                for kind, count in sorted(by_kind.items(), key=lambda x: -x[1]):
                    click.echo(f"     {kind}: {count}")

            if verbose and by_rule:
                click.echo("\n   By rule:")
                for rule, count in sorted(by_rule.items(), key=lambda x: -x[1]):
                    click.echo(f"     {rule}: {count}")

            click.echo("\n" + "─" * 66)

            if total_issues > 0:
                click.echo("💡 Tips:")
                click.echo("   • Add custom words: -d word1 -d word2")
                click.echo("   • Create dictionary: .great-docs-dictionary (one word per line)")
                click.echo("   • Disable a rule: --ignore SentenceCapitalization")
                click.echo("   • List all rules: harper-cli config")
                click.echo("─" * 66)

        # Determine exit code
        if max_issues is not None and total_issues > max_issues:
            if not json_output and not compact:
                click.echo(
                    f"\n⚠️  Found {total_issues} issue(s), exceeds threshold of {max_issues}."
                )
            sys.exit(1)
        elif total_issues > 0:
            if not json_output and not compact:
                click.echo(f"\n⚠️  Found {total_issues} issue(s).")
            sys.exit(1)
        else:
            if not json_output and not compact:
                click.echo("\n✅ No issues found!")
            sys.exit(0)

    except HarperNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(3)
    except HarperError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)
    except PROJECT_ERRORS as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


cli.add_command(proofread)


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--fix",
    is_flag=True,
    help="Attempt to fix some issues automatically (e.g., generate missing files)",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output results as JSON for CI integration",
)
@_options.config_option
def seo(
    project_path: str | None, fix: bool, json_output: bool, config_path: str | None = None
) -> None:
    """Audit SEO health of your documentation site.

    Checks for common SEO issues and provides recommendations for improvement.
    Run this after building your site with 'great-docs build'.

    \b
    Checks performed:
      • sitemap.xml presence and validity
      • robots.txt presence and configuration
      • Canonical URLs on all pages
      • Meta descriptions on pages
      • JSON-LD structured data
      • Page titles with site name
      • Missing alt text on images
      • Broken internal links (basic check)

    \b
    Examples:
      great-docs seo                        # Audit SEO health
      great-docs seo --fix                  # Fix issues where possible
      great-docs seo --json                 # JSON output for CI
    """
    import html
    import json
    import xml.etree.ElementTree as ET

    from ._website.seo import robots, sitemap

    try:
        layout = Layout.make(
            Path(project_path) if project_path else Path.cwd(),
            Path(config_path) if config_path else None,
        )
        config = layout.load_config()
        site_dir = layout.site_dir

        if not site_dir.exists():
            click.echo("Error: Site not built. Run 'great-docs build' first.", err=True)
            sys.exit(1)

        separate_site = layout.source_dir != layout.package_root
        if fix and separate_site:
            from ._build.ownership import validate_site_dir

            validate_site_dir(site_dir)
            ownership_path = site_dir / ".great-docs-site.json"
            ownership = json.loads(ownership_path.read_text(encoding="utf-8"))

        def record_generated_file(name: str) -> None:
            if separate_site and (site_dir / name).is_file():
                ownership["paths"] = sorted(set(ownership["paths"]) | {name})
                ownership_path.write_text(json.dumps(ownership, indent=2) + "\n", encoding="utf-8")

        issues = []
        warnings = []
        info = []

        identity = site.identity(config, layout, Project.make(config, layout))
        canonical_base = identity.base_url

        # ── Check sitemap.xml ────────────────────────────────────────────
        sitemap_path = site_dir / "sitemap.xml"
        if sitemap_path.exists():
            try:
                tree = ET.parse(sitemap_path)
                root = tree.getroot()
                # Count URLs in sitemap
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                urls = root.findall(".//sm:url", ns)
                if urls:
                    info.append(f"✅ sitemap.xml: {len(urls)} URLs indexed")
                else:
                    warnings.append("⚠️  sitemap.xml is empty (no URLs)")
            except ET.ParseError as e:
                issues.append(f"❌ sitemap.xml is malformed: {e}")
        else:
            issues.append("❌ sitemap.xml not found")
            if fix:
                sitemap.write(site_dir, config, canonical_base, report=click.echo)
                record_generated_file("sitemap.xml")
                info.append("   → Generated sitemap.xml")

        # ── Check robots.txt ─────────────────────────────────────────────
        robots_path = site_dir / "robots.txt"
        if robots_path.exists():
            robots_content = robots_path.read_text()
            if "Sitemap:" in robots_content:
                info.append("✅ robots.txt: includes sitemap reference")
            else:
                warnings.append("⚠️  robots.txt: missing sitemap reference")
            if "User-agent:" in robots_content:
                info.append("✅ robots.txt: has user-agent rules")
        else:
            issues.append("❌ robots.txt not found")
            if fix:
                robots.write(site_dir, config, canonical_base, report=click.echo)
                record_generated_file("robots.txt")
                info.append("   → Generated robots.txt")

        # ── Check HTML pages ─────────────────────────────────────────────
        html_files = list(site_dir.rglob("*.html"))
        pages_checked = 0
        pages_missing_canonical = 0
        pages_missing_description = 0
        pages_missing_site_name = 0
        pages_with_json_ld = 0
        images_missing_alt = 0

        # The audit requires the site name only when a string template contains
        # `{site_name}`. A missing placeholder or non-string value skips this
        # check.
        title_template = config.seo_title_template
        site_name = identity.name
        if not isinstance(title_template, str) or "{site_name}" not in title_template:
            site_name = ""

        for html_file in html_files:
            rel_path = html_file.relative_to(site_dir).as_posix()

            # Skip internal files
            if rel_path.startswith("_") or rel_path.startswith("."):
                continue

            pages_checked += 1
            content = html_file.read_text(encoding="utf-8", errors="ignore")

            # Check canonical URL
            if 'rel="canonical"' not in content:
                pages_missing_canonical += 1

            # Check meta description
            if not re.search(r'<meta\s+name="description"', content):
                pages_missing_description += 1

            # Require the site name in ordinary page titles. Exempt the home page,
            # which uses only that name, and redirect stubs, which immediately
            # send readers elsewhere.
            title_match = re.search(r"<title>([^<]+)</title>", content)
            is_redirect = 'http-equiv="refresh"' in content
            if site_name and title_match and rel_path != "index.html" and not is_redirect:
                if site_name not in html.unescape(title_match.group(1)):
                    pages_missing_site_name += 1

            # Check JSON-LD
            if "application/ld+json" in content:
                pages_with_json_ld += 1

            # Check images for alt text
            for img_match in re.finditer(r"<img\s+[^>]*>", content):
                img_tag = img_match.group(0)
                if 'alt="' not in img_tag and "alt='" not in img_tag:
                    images_missing_alt += 1

        # Report HTML page analysis
        info.append(f"✅ Analyzed {pages_checked} HTML pages")

        if pages_missing_canonical > 0:
            if canonical_base:
                issues.append(f"❌ {pages_missing_canonical} pages missing canonical URLs")
            else:
                warnings.append(
                    f"⚠️  {pages_missing_canonical} pages missing canonical URLs "
                    "(set seo.canonical.base_url)"
                )
        else:
            info.append("✅ All pages have canonical URLs")

        if pages_missing_description > 0:
            warnings.append(f"⚠️  {pages_missing_description} pages missing meta descriptions")
        else:
            info.append("✅ All pages have meta descriptions")

        if pages_missing_site_name > 0:
            warnings.append(f"⚠️  {pages_missing_site_name} pages have titles without the site name")

        if pages_with_json_ld > 0:
            info.append(f"✅ {pages_with_json_ld} pages have JSON-LD structured data")
        else:
            warnings.append("⚠️  No pages have JSON-LD structured data")

        if images_missing_alt > 0:
            warnings.append(f"⚠️  {images_missing_alt} images missing alt text")
        elif pages_checked > 0:
            info.append("✅ All images have alt text")

        # ── Output results ───────────────────────────────────────────────
        if json_output:
            result = {
                "status": "fail" if issues else ("warn" if warnings else "pass"),
                "pages_checked": pages_checked,
                "issues": issues,
                "warnings": warnings,
                "info": info,
            }
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo("\n" + "═" * 60)
            click.echo("📊 SEO Audit Results")
            click.echo("═" * 60)

            if info:
                click.echo("\n" + "\n".join(info))

            if warnings:
                click.echo("\n" + "\n".join(warnings))

            if issues:
                click.echo("\n" + "\n".join(issues))

            click.echo("\n" + "─" * 60)
            if issues:
                click.echo(f"❌ {len(issues)} issue(s) found")
                sys.exit(1)
            elif warnings:
                click.echo(f"⚠️  {len(warnings)} warning(s)")
            else:
                click.echo("✅ All SEO checks passed!")

    except (*PROJECT_ERRORS, ValueError) as e:
        if json_output:
            click.echo(json.dumps({"status": "error", "error": str(e)}))
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


cli.add_command(seo)


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--check",
    "checks",
    multiple=True,
    type=click.Choice(
        [
            "config",
            "docstrings",
            "cross-refs",
            "style",
            "directives",
            "stale-versions",
            "descriptions",
            "front-matter",
        ]
    ),
    help="Run only specific checks (can be repeated). Default: all checks.",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output results as JSON for CI integration",
)
@_options.config_option
def lint(
    project_path: str | None,
    checks: tuple[str, ...],
    json_output: bool,
    config_path: str | None = None,
) -> None:
    """Lint documentation quality for your package.

    Analyzes your package's public API for documentation issues including
    missing docstrings, broken cross-references, inconsistent formatting,
    malformed directives, and stale version annotations. Also reports
    outdated keys in great-docs.yml, pages that fall back to the default
    search description, and front matter values of the wrong type.

    \b
    Checks performed:
      • config-key           great-docs.yml keys spelled the old way, or ignored
      • missing-docstring    Public exports or methods without docstrings
      • broken-xref          '%seealso' references to unknown symbols
      • ambiguous-xref       References to a short name two objects claim
      • unread-source        A linked source's inventory could not be read
      • style-mismatch       Docstrings not matching configured style (numpy/google/sphinx)
      • unknown-directive    Unrecognized '%directive' names
      • stale-badge          Version badges far behind latest release
      • stale-callout        Version callouts that are very old
      • stale-upcoming       'upcoming:' frontmatter for already-released versions
      • default-description  Pages with no opening paragraph to describe them in search
      • front-matter         great-docs front matter keys set to a value of the wrong type

    \b
    Examples:
      great-docs lint                                # Run all checks
      great-docs lint --check stale-versions         # Only check for stale annotations
      great-docs lint --check docstrings             # Only check for missing docstrings
      great-docs lint --check config                 # Only check great-docs.yml keys
      great-docs lint --check descriptions           # Only check search descriptions
      great-docs lint --check front-matter           # Only check front matter value types
      great-docs lint --check cross-refs --check style
      great-docs lint --json                         # JSON output for CI
      great-docs lint --json | jq '.issues[] | select(.severity == "error")'
    """
    import json
    import textwrap

    from ._checks.lint import run_lint

    try:
        project_root = Path(project_path) if project_path else Path.cwd()
        check_set = set(checks) if checks else None

        result = run_lint(
            project_root, checks=check_set, quiet=json_output, config_path=config_path
        )

        if json_output:
            click.echo(json.dumps(result.to_dict(), indent=2))
        else:
            click.echo("\n" + "═" * 60)
            click.echo("📋 Documentation Lint Results")
            click.echo("═" * 60)

            if result.package_name:
                click.echo(f"\nPackage: {result.package_name}")
                click.echo(f"Exports checked: {result.exports_count}")

            if not result.issues:
                click.echo("\n✅ All documentation checks passed!")
            else:
                # Group issues by check type
                by_check: dict[str, list] = {}
                for issue in result.issues:
                    by_check.setdefault(issue.check, []).append(issue)

                for check_name, issues in sorted(by_check.items()):
                    click.echo(f"\n{'─' * 60}")

                    # Count severities
                    errs = sum(1 for i in issues if i.severity == "error")
                    warns = sum(1 for i in issues if i.severity == "warning")
                    infos = sum(1 for i in issues if i.severity == "info")
                    label_parts = []
                    if errs:
                        label_parts.append(f"{errs} error(s)")
                    if warns:
                        label_parts.append(f"{warns} warning(s)")
                    if infos:
                        label_parts.append(f"{infos} info")
                    label = ", ".join(label_parts)

                    click.echo(f"  {check_name}  [{label}]")
                    click.echo(f"{'─' * 60}")

                    for issue in issues:
                        if issue.severity == "error":
                            icon = "❌"
                        elif issue.severity == "info":
                            icon = "ℹ️ "
                        else:
                            icon = "⚠️ "
                        symbol_str = f"  {issue.symbol}" if issue.symbol else ""
                        click.echo(f"  {icon}{symbol_str}")
                        # Wrap long messages indented below the path
                        msg_indent = "        "
                        lines = textwrap.wrap(issue.message, width=56)
                        for line in lines:
                            click.echo(f"{msg_indent}{line}")

                click.echo(f"\n{'─' * 60}")
                n_errors = len(result.errors)
                n_warnings = len(result.warnings)
                if n_errors:
                    click.echo(f"❌ {n_errors} error(s), {n_warnings} warning(s)")
                else:
                    click.echo(f"⚠️  {n_warnings} warning(s)")

            try:
                from ._layout_migration.notice import layout_notice
                from ._project.layout import Layout

                layout = Layout.make(
                    project_root,
                    Path(config_path) if config_path is not None else None,
                )
            except (OSError, ValueError):
                pass
            else:
                notice = layout_notice(layout)
                if notice is not None:
                    click.echo(notice)

        # Exit with non-zero status on errors (for CI)
        if result.errors:
            sys.exit(1)

    except (*PROJECT_ERRORS, *USER_CODE_ERRORS, ValueError) as e:
        if json_output:
            click.echo(json.dumps({"status": "error", "error": str(e)}))
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


cli.add_command(lint)


@click.command("api-diff")
@click.argument("old_version")
@click.argument("new_version")
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--package",
    help="Python package name (auto-detected from pyproject.toml if omitted)",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    help="Output results as JSON",
)
@click.option(
    "--graph",
    is_flag=True,
    help="Show dependency graph as Mermaid diagram for the NEW version",
)
@click.option(
    "--timeline",
    is_flag=True,
    help="Show API surface growth timeline across all version tags",
)
@click.option(
    "--symbol",
    help="Track a single symbol across versions (shows signature history)",
)
@click.option(
    "--changes-only",
    is_flag=True,
    help="With --symbol, show only versions where the symbol changed",
)
@click.option(
    "--table",
    is_flag=True,
    help="With --symbol, show parameter evolution as a table",
)
@click.option(
    "--html",
    is_flag=True,
    help="With --symbol --table, output HTML (with disclosure wrapper)",
)
@_options.config_option
def api_diff_cmd(
    old_version: str,
    new_version: str,
    project_path: str | None,
    package: str | None,
    json_output: bool,
    graph: bool,
    timeline: bool,
    symbol: str | None,
    changes_only: bool,
    table: bool,
    html: bool,
    config_path: str | None = None,
) -> None:
    """Compare the public API between two versions.

    Analyzes how the API surface changed between 'OLD_VERSION' and
    'NEW_VERSION' (git tags). Detects added, removed, and changed symbols,
    tracks parameter changes, and flags breaking changes with migration
    hints.

    \b
    Use 'HEAD' as 'NEW_VERSION' to compare against the working tree.

    \b
    Examples:
      great-docs api-diff v0.1.0 v0.2.0
      great-docs api-diff v1.0.0 HEAD
      great-docs api-diff v0.9.0 v1.0.0 --json
      great-docs api-diff v0.1.0 v0.2.0 --graph
      great-docs api-diff v0.1.0 HEAD --timeline
      great-docs api-diff v0.1.0 v0.5.0 --symbol GreatDocs
      great-docs api-diff v0.1.0 v0.5.0 --symbol GreatDocs --changes-only
      great-docs api-diff v0.1.0 v0.5.0 --symbol GreatDocs --table
      great-docs api-diff v0.1.0 v0.5.0 --symbol GreatDocs --table --html
    """
    import json
    import shutil

    from ._api_evolution.compare import api_diff
    from ._api_evolution.history import build_dependency_graph, build_timeline, symbol_history
    from ._api_evolution.render import (
        evolution_table_html,
        evolution_table_text,
        timeline_to_mermaid,
    )
    from ._api_evolution.snapshot import _detect_package_name, snapshot_at_tag, snapshot_from_griffe

    project_root = Path(project_path) if project_path else Path.cwd()
    importable_name = package or _detect_package_name(
        project_root, Path(config_path) if config_path else None
    )

    try:
        # --- Symbol history mode ---
        if symbol:
            from ._api_evolution.snapshot import list_version_tags

            all_tags = list_version_tags(project_root)
            # Filter to tags between old_version and new_version (inclusive)
            try:
                start_idx = all_tags.index(old_version)
            except ValueError:
                start_idx = 0
            try:
                end_idx = all_tags.index(new_version) + 1
            except ValueError:
                end_idx = len(all_tags)
            selected_tags = all_tags[start_idx:end_idx]

            if not selected_tags:
                click.echo(
                    f"No version tags found between {old_version} and {new_version}.",
                    err=True,
                )
                sys.exit(1)

            hist = symbol_history(
                project_root, symbol, package_name=importable_name, tags=selected_tags
            )
            if hist is None:
                click.echo("Could not determine package name.", err=True)
                sys.exit(1)

            if json_output:
                click.echo(json.dumps(hist.to_dict(changes_only=changes_only), indent=2))
            elif table:
                if html:
                    click.echo(
                        evolution_table_html(hist, changes_only=changes_only, disclosure=True)
                    )
                else:
                    click.echo(evolution_table_text(hist, changes_only=changes_only))
            else:
                entries = hist.changed_entries if changes_only else hist.entries
                term_width = shutil.get_terminal_size((80, 24)).columns
                sep = "═" * min(term_width, 60)
                thin = "─" * min(term_width, 60)

                click.echo(f"\n{sep}")
                click.echo(f"Symbol History: {hist.symbol_name}")
                click.echo(f"Package: {hist.package_name}")
                if changes_only:
                    click.echo("Showing only versions with changes")
                click.echo(sep)

                if not entries:
                    click.echo("\n  (no entries)")
                else:
                    for entry in entries:
                        click.echo(f"\n{thin}")
                        if entry.present:
                            tag = ""
                            if entry.change:
                                if entry.change.is_breaking:
                                    tag = "  ⚠ BREAKING"
                                elif entry.change.change_type == "added":
                                    tag = "  ✚ NEW"
                                else:
                                    tag = "  ∆ CHANGED"
                            click.echo(f"  {entry.version}{tag}")
                            click.echo(f"    {entry.signature}")
                            if entry.change and entry.change.details:
                                for detail in entry.change.details:
                                    click.echo(f"      {detail}")
                        else:
                            click.echo(f"  {entry.version}  ✖ NOT PRESENT")
                            if entry.change and entry.change.details:
                                for detail in entry.change.details:
                                    click.echo(f"      {detail}")

                click.echo(f"\n{sep}\n")
            return

        # --- Timeline mode ---
        if timeline:
            tl = build_timeline(project_root, importable_name)
            if not tl:
                click.echo("No version tags found or could not build snapshots.", err=True)
                sys.exit(1)
            if json_output:
                click.echo(json.dumps(tl, indent=2))
            else:
                click.echo(timeline_to_mermaid(tl))
            return

        # --- Diff ---
        result = api_diff(project_root, old_version, new_version, package_name=importable_name)

        if result is None:
            click.echo(
                "Could not build API snapshots. Check that the tags exist and the "
                "package source is present at those versions.",
                err=True,
            )
            sys.exit(1)

        # --- Graph mode ---
        if graph:
            from great_docs._reference import documented as documented_reference

            package_exports = Exports.make(
                Layout.make(project_root, Path(config_path) if config_path else None)
            )
            project = package_exports.project
            documented = (
                documented_reference.symbol_names(
                    package_exports.config,
                    importable_name=project.module or result.package_name.replace("-", "_"),
                    search_paths=project.search_paths(),
                    create_sections=package_exports.sections,
                )
                or None
            )
            # Build graph for the new version
            if new_version.upper() == "HEAD":
                snap = snapshot_from_griffe(
                    result.package_name, version="HEAD", documented_names=documented
                )
            else:
                snap = snapshot_at_tag(
                    project_root, new_version, result.package_name, documented_names=documented
                )
            if snap is None:
                click.echo("Could not build snapshot for graph.", err=True)
                sys.exit(1)
            dep_graph = build_dependency_graph(snap)
            if json_output:
                click.echo(
                    json.dumps(
                        {
                            "nodes": dep_graph.nodes,
                            "inheritance": [
                                {"child": e.child, "parent": e.parent}
                                for e in dep_graph.inheritance
                            ],
                        },
                        indent=2,
                    )
                )
            else:
                click.echo(dep_graph.to_mermaid())
            return

        # --- JSON output ---
        if json_output:
            click.echo(json.dumps(result.to_dict(), indent=2))
            return

        # --- Text output ---
        term_width = shutil.get_terminal_size((80, 24)).columns
        sep = "═" * min(term_width, 60)
        thin = "─" * min(term_width, 60)

        click.echo(f"\n{sep}")
        click.echo(f"API Diff: {result.old_version} → {result.new_version}")
        click.echo(f"Package: {result.package_name}")
        click.echo(sep)

        # Summary
        click.echo(
            f"\n  Added: {len(result.added)}  │  "
            f"Removed: {len(result.removed)}  │  "
            f"Changed: {len(result.changed)}  │  "
            f"Breaking: {len(result.breaking_changes)}"
        )

        if not result.added and not result.removed and not result.changed:
            click.echo("\n✅ No API changes detected.")
            return

        # Added
        if result.added:
            click.echo(f"\n{thin}")
            click.echo(f"  ✚ Added ({len(result.added)})")
            click.echo(thin)
            for c in result.added:
                click.echo(f"    + {c.symbol}")

        # Removed
        if result.removed:
            click.echo(f"\n{thin}")
            click.echo(f"  ✖ Removed ({len(result.removed)})  [BREAKING]")
            click.echo(thin)
            for c in result.removed:
                click.echo(f"    - {c.symbol}")
                if c.migration_hint:
                    click.echo(f"      hint: {c.migration_hint}")

        # Changed
        if result.changed:
            click.echo(f"\n{thin}")
            click.echo(f"  ∆ Changed ({len(result.changed)})")
            click.echo(thin)
            for c in result.changed:
                label = "  ⚠ BREAKING" if c.is_breaking else ""
                click.echo(f"    ~ {c.symbol}{label}")
                for detail in c.details:
                    click.echo(f"        {detail}")
                if c.migration_hint:
                    click.echo(f"        hint: {c.migration_hint}")

        # Breaking summary
        if result.has_breaking_changes:
            click.echo(f"\n{sep}")
            click.echo(f"⚠  {len(result.breaking_changes)} breaking change(s) detected")
            click.echo(sep)

        click.echo()

    except (*PROJECT_ERRORS, *USER_CODE_ERRORS) as e:
        if json_output:
            click.echo(json.dumps({"status": "error", "error": str(e)}))
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


cli.add_command(api_diff_cmd)


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--check",
    is_flag=True,
    help="Validate version configuration and exit with non-zero on errors",
)
@_options.config_option
def versions(project_path: str | None, check: bool, config_path: str | None = None) -> None:
    """List configured documentation versions.

    Shows the multi-version documentation configuration from 'great-docs.yml',
    including version tags, labels, and status indicators.

    \b
    Examples:
      great-docs versions              # List all configured versions
      great-docs versions --check      # Validate configuration
    """
    from great_docs._versions.model import get_latest_version, parse_versions_config

    try:
        project_root = Path(project_path or ".").resolve()
        layout = Layout.make(project_root, Path(config_path) if config_path else None)
        project_root = layout.package_root
        cfg = layout.load_config()

        if not cfg.has_versions:
            click.echo("No versions configured in great-docs.yml.")
            click.echo("Add a 'versions:' list to enable multi-version docs.")
            return

        try:
            entries = parse_versions_config(cfg.versions)
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

        if check:
            click.echo(f"✓ {len(entries)} version(s) configured")
            latest = get_latest_version(entries)
            if latest:
                click.echo(f"  Latest: {latest.tag} ({latest.label})")
            else:
                click.echo("  Warning: no version marked as latest", err=True)
                sys.exit(1)
            return

        # Table header
        click.echo(f"  {'TAG':<12} {'LABEL':<20} {'STATUS':<16} {'API SOURCE'}")
        click.echo(f"  {'─' * 12} {'─' * 20} {'─' * 16} {'─' * 24}")

        for v in entries:
            status = "—"
            if v.latest:
                status = "latest ✓"
            elif v.prerelease:
                status = "prerelease"
            elif v.eol:
                status = "eol"

            api_source = "live introspection"
            if v.api_snapshot:
                api_source = v.api_snapshot
            elif v.git_ref:
                api_source = f"git tag: {v.git_ref}"

            click.echo(f"  {v.tag:<12} {v.label:<20} {status:<16} {api_source}")

        click.echo()

    except PROJECT_ERRORS as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


cli.add_command(versions)


@click.command("api-snapshot")
@click.argument("version_tag", required=False)
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--package",
    help="Python package name (auto-detected from 'pyproject.toml' if omitted)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    help="Output file path (default: '.great-docs/snapshots/<version>.json')",
)
@click.option(
    "--all-tags",
    is_flag=True,
    help="Snapshot all version tags in the repository",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing snapshot files",
)
@_options.config_option
def api_snapshot_cmd(
    version_tag: str | None,
    project_path: str | None,
    package: str | None,
    output: str | None,
    all_tags: bool,
    force: bool,
    config_path: str | None = None,
) -> None:
    """Capture a JSON snapshot of a package's public API.

    Snapshots record every public symbol, its parameters, type annotations,
    and other metadata. They are used to build versioned API reference pages
    and compute diff annotations without needing access to old source code.

    \b
    With no arguments, snapshot the *current* working-tree API:
      'great-docs api-snapshot'

    \b
    Snapshot a specific git tag:
      'great-docs api-snapshot v1.0.0'

    \b
    Snapshot all version tags at once:
      'great-docs api-snapshot --all-tags'

    \b
    Snapshots are saved to '.great-docs/snapshots/<version>.json' by default.
    """
    from ._api_evolution.snapshot import (
        _detect_package_name,
        list_version_tags,
        snapshot_at_tag,
        snapshot_from_griffe,
    )

    project_root = Path(project_path) if project_path else Path.cwd()

    # Resolve package name
    pkg_name = package or _detect_package_name(
        project_root, Path(config_path) if config_path else None
    )
    if not pkg_name:
        click.echo(
            "Could not detect package name. Pass --package or add [project] "
            "name to pyproject.toml.",
            err=True,
        )
        sys.exit(1)

    from great_docs._reference import documented as documented_reference

    try:
        package_exports = Exports.make(
            Layout.make(project_root, Path(config_path) if config_path else None)
        )
        project = package_exports.project
        documented = (
            documented_reference.symbol_names(
                package_exports.config,
                importable_name=project.module or pkg_name.replace("-", "_"),
                search_paths=project.search_paths(),
                create_sections=package_exports.sections,
            )
            or None
        )
    except BuildError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Default snapshot directory
    snap_dir = project_root / ".great-docs" / "snapshots"

    # Determine which versions to snapshot
    if all_tags:
        tags = list_version_tags(project_root)
        if not tags:
            click.echo("No version tags found in repository.", err=True)
            sys.exit(1)
    elif version_tag:
        tags = [version_tag]
    else:
        # Current working tree
        tags = ["HEAD"]

    saved = 0
    failed = 0

    for tag in tags:
        # Determine output path
        if output and len(tags) == 1:
            out_path = Path(output)
        else:
            label = tag if tag != "HEAD" else "dev"
            out_path = snap_dir / f"{label}.json"

        if out_path.exists() and not force:
            click.echo(f"  ⏭  {tag}: {out_path} already exists (use --force to overwrite)")
            continue

        try:
            if tag == "HEAD":
                snap = snapshot_from_griffe(pkg_name, version="dev", documented_names=documented)
            else:
                snap = snapshot_at_tag(project_root, tag, pkg_name, documented_names=documented)

            if snap is None:
                click.echo(f"  ✗  {tag}: could not build snapshot", err=True)
                failed += 1
                continue

            snap.save(out_path)
            click.echo(f"  ✓  {tag}: {snap.symbol_count} symbols → {out_path}")
            saved += 1

        except USER_CODE_ERRORS as e:
            click.echo(f"  ✗  {tag}: {e}", err=True)
            failed += 1

    click.echo()
    if saved:
        click.echo(f"Saved {saved} snapshot(s).")
    if failed:
        click.echo(f"Failed: {failed}")
        sys.exit(1)


cli.add_command(api_snapshot_cmd)


# ══════════════════════════════════════════════════════════════════════════════
# SKILL MANAGEMENT COMMANDS
# ══════════════════════════════════════════════════════════════════════════════


@click.group(cls=OrderedGroup)
def skill():
    """Manage AI coding agent skills.

    Install, check, and list SKILL.md files so AI coding agents can
    learn to use your Python package.

    \b
    Quick start:
      great-docs skill install great-docs      # install Great Docs' own skill
      great-docs skill install great-tables    # install from PyPI package
      great-docs skill install pointblank      # works with any GD-powered package
      great-docs skill check                   # verify freshness
      great-docs skill check --update          # auto-update outdated skills
      great-docs skill list great-tables       # see what's bundled
    """


@click.command(name="install")
@click.argument("source", required=False)
@click.option(
    "-g",
    "--global",
    "global_",
    is_flag=True,
    help="Install the skill globally (~/) instead of in the current repository.",
)
@click.option(
    "-p",
    "--path",
    type=str,
    help="Custom path where to install the skill.",
)
@click.option(
    "-d",
    "--detect",
    is_flag=True,
    help="Automatically detect and update existing installations.",
)
@click.option(
    "--agent",
    type=click.Choice(["claude", "copilot", "cursor", "windsurf", "opencode", "codex"]),
    help="Target agent format (auto-detected if not specified).",
)
@click.option(
    "--name",
    "skill_name",
    type=str,
    help="Override the skill name.",
)
def skill_install(
    source: str | None,
    global_: bool,
    path: str | None,
    detect: bool,
    agent: str | None,
    skill_name: str | None,
) -> None:
    """Install skills for AI coding agents.

    SOURCE can be a Python package name or a documentation site URL.
    If omitted, looks for skills in the current package.

    \b
    Examples:
      great-docs skill install                    # current package (pyproject.toml)
      great-docs skill install great-tables       # any installed package
      great-docs skill install polars pointblank  # multiple packages at once
      great-docs skill install https://posit-dev.github.io/great-tables/
      great-docs skill install great-tables --agent claude           # Claude Code
      great-docs skill install great-tables --agent copilot          # GitHub Copilot
      great-docs skill install great-tables --global                 # install to ~/
      great-docs skill install great-tables --path .claude/skills/gt # custom path
      great-docs skill install --detect           # find and refresh all skills
    """
    from ._skills.install import install_skill as _install_skill

    kwargs: dict = {
        "global_": global_,
        "path": path,
        "detect": detect,
        "skill_name": skill_name,
    }

    if agent:
        kwargs["agent"] = agent

    if source:
        if source.startswith(("http://", "https://")):
            kwargs["url"] = source
        else:
            kwargs["package"] = source
    else:
        # Use the current project's declared package name when no source is supplied.
        project_root = Path.cwd()
        pkg_name = _detect_current_package(project_root)
        if pkg_name:
            kwargs["package"] = pkg_name
        else:
            click.echo(
                "Error: No source specified and no package found in current directory.", err=True
            )
            click.echo("Usage: great-docs skill install <package-or-url>", err=True)
            sys.exit(1)

    results = _install_skill(**kwargs)
    if not results:
        sys.exit(1)


@click.command(name="check")
@click.argument("package", required=False)
@click.option(
    "-g",
    "--global",
    "global_",
    is_flag=True,
    help="Only check global installations (in home directory).",
)
@click.option(
    "-l",
    "--local",
    is_flag=True,
    default=True,
    help="Only check local installations (in current repository).",
)
@click.option(
    "-u",
    "--update",
    is_flag=True,
    help="Automatically update any outdated skills found.",
)
def skill_check(
    package: str | None,
    global_: bool,
    local: bool,
    update: bool,
) -> None:
    """Check if installed skills are up to date.

    Scans for installed SKILL.md files and compares their content hash
    with the currently installed package to detect changes.

    \b
    Examples:
      great-docs skill check                # check all installed skills
      great-docs skill check great-tables   # check a specific package
      great-docs skill check --global       # check global installations only
      great-docs skill check --update       # reinstall any that have changed
    """
    from ._skills.install import check_skill as _check_skill

    click.echo("Checking installed skills...")
    results = _check_skill(
        package=package,
        global_=global_,
        local=local,
        update=update,
    )

    if not results:
        click.echo("No installed skills found.")
    else:
        current = sum(1 for r in results if r["status"] == "current")
        outdated = sum(1 for r in results if r["status"] == "outdated")
        updated = sum(1 for r in results if r["status"] == "updated")
        local = sum(1 for r in results if r["status"] == "local")

        click.echo()
        parts = []
        if current:
            parts.append(f"{current} current")
        if outdated:
            parts.append(f"{outdated} outdated")
        if updated:
            parts.append(f"{updated} updated")
        if local:
            parts.append(f"{local} local")
        click.echo(f"Summary: {', '.join(parts)}")


@click.command(name="list")
@click.argument("source", required=False)
@click.option(
    "--url",
    type=str,
    help="Documentation site URL to query for available skills.",
)
def skill_list(source: str | None, url: str | None) -> None:
    """List available skills from a package or URL.

    Shows all SKILL.md files bundled in a package or discoverable at a URL,
    including their names and file paths.

    \b
    Examples:
      great-docs skill list                   # current package (pyproject.toml)
      great-docs skill list great-tables      # any installed package
      great-docs skill list https://posit-dev.github.io/great-tables/
    """
    from ._skills.install import list_skills as _list_skills

    if source:
        if source.startswith(("http://", "https://")):
            url = source
            source = None

    if url:
        click.echo(f"Skills available at {url}:")
        results = _list_skills(url=url)
    elif source:
        click.echo(f"Skills bundled in '{source}':")
        results = _list_skills(package=source)
    else:
        project_root = Path.cwd()
        pkg_name = _detect_current_package(project_root)
        if pkg_name:
            click.echo(f"Skills bundled in '{pkg_name}':")
            results = _list_skills(package=pkg_name)
        else:
            click.echo("Error: No source specified and no package found.", err=True)
            sys.exit(1)

    if not results:
        click.echo("No skills found.")
        sys.exit(1)


def _detect_current_package(project_root: Path) -> str | None:
    """
    Read the package name declared by a project

    Parameters
    ----------
    project_root
        The directory holding the packaging files.

    Returns
    -------
    :
        The distribution name as written, or `None` when the project declares no name or its
        metadata cannot be read.
    """
    try:
        return _manifest.read(project_root)["name"]
    except ManifestError:
        return None


skill.add_command(skill_install)
skill.add_command(skill_check)
skill.add_command(skill_list)
cli.add_command(skill)


# ---------------------------------------------------------------------------
# termshow commands
# ---------------------------------------------------------------------------


@click.group()
def termshow():
    """Terminal recording and playback for CLI/TUI documentation.

    Record terminal sessions, edit them with YAML scripts, and render
    them as SVG frame sequences for the termshow player.
    """
    pass


@click.command("record")
@click.argument("output", type=click.Path(), required=False)
@click.option(
    "--steps",
    "steps_file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Run the steps in this .termshow.yml script instead of recording live",
)
@click.option("--cols", type=int, default=None, help="Terminal width in columns")
@click.option("--rows", type=int, default=None, help="Terminal height in rows")
@click.option("--shell", type=str, default=None, help="Shell to spawn (default: $SHELL)")
@click.option("--capture-input", is_flag=True, help="Also capture keyboard input events")
def term_record(
    output: str | None,
    steps_file: str | None,
    cols: int | None,
    rows: int | None,
    shell: str | None,
    capture_input: bool,
) -> None:
    """Record a terminal session to a .termshow file.

    Spawns an interactive shell and captures all output with timing.
    Press Ctrl+D or type 'exit' to stop recording.

    With --steps, nothing is typed by hand: the script's `steps:` are run in
    a hidden terminal and the session is saved. OUTPUT defaults to the
    recording the script belongs to (demo.termshow for demo.termshow.yml),
    and --cols, --rows, and --shell override the script's `record:` settings.

    Examples:
      great-docs termshow record docs/assets/install.termshow
      great-docs termshow record --steps docs/assets/install.termshow.yml
    """
    if steps_file:
        _record_steps(steps_file, output, cols=cols, rows=rows, shell=shell)
        return
    if output is None:
        raise click.UsageError("Missing argument 'OUTPUT'.")

    from ._term_player.recorder import record_session

    if not output.endswith(".termshow"):
        output += ".termshow"

    record_session(output, shell=shell, cols=cols, rows=rows, capture_input=capture_input)


def _record_steps(
    steps_file: str, output: str | None, *, cols: int | None, rows: int | None, shell: str | None
) -> None:
    """`termshow record --steps`: run a script's steps and save the recording."""
    from dataclasses import replace

    from ._term_player.importer import _write_termshow
    from ._term_player.steps import StepsError, load_steps, record_steps

    script_path = Path(steps_file)
    if output is None:
        if not script_path.name.endswith(".termshow.yml"):
            raise click.UsageError(
                f"Give an OUTPUT path: {script_path.name} isn't named NAME.termshow.yml"
            )
        output_path = script_path.with_name(script_path.name[: -len(".yml")])
    else:
        output_path = Path(output if output.endswith(".termshow") else output + ".termshow")

    try:
        settings, steps = load_steps(script_path)
    except StepsError as e:
        raise click.ClickException(str(e)) from None
    overrides = {"cols": cols, "rows": rows, "shell": shell}
    settings = replace(settings, **{k: v for k, v in overrides.items() if v is not None})

    def progress(i: int, step) -> None:
        click.secho(f"  {i + 1}/{len(steps)} {step.describe()}", dim=True, err=True)

    count = f"{len(steps)} step{'' if len(steps) == 1 else 's'}"
    click.echo(f"Running {count} from {script_path} in {settings.shell!r}", err=True)
    try:
        recording = record_steps(settings, steps, title=output_path.stem, on_step=progress)
    except StepsError as e:
        click.echo(f"✗ {e}", err=True)
        if e.screen:
            click.echo("\nThe screen at the time:", err=True)
            for line in e.screen.splitlines():
                click.echo(f"  │ {line}", err=True)
        raise SystemExit(1) from None

    _write_termshow(recording, output_path)
    click.echo(
        f"✓ Recorded {output_path} ({recording.duration:.1f}s, {len(recording.events)} events)"
    )


@click.command("render")
@click.argument("source", type=click.Path(exists=True))
@click.option(
    "--output-dir", "-o", type=click.Path(), default=None, help="Output directory for frames"
)
@click.option("--interval", type=float, default=2.0, help="Keyframe interval in seconds")
@click.option(
    "--script", type=click.Path(exists=True), default=None, help="Path to .termshow.yml script"
)
def term_render(source: str, output_dir: str | None, interval: float, script: str | None) -> None:
    """Render a .termshow recording into SVG frames.

    Processes the recording through the virtual terminal emulator and
    produces SVG keyframes + a manifest.json for the player, along with
    the recording's transcript (_transcript.md).
    """
    from ._term_player.prerender import load_recording, render_recording
    from ._term_player.prerender import output_dir as recording_output_dir

    source_path = Path(source)
    recording, script_obj = load_recording(source_path, Path(script) if script else None)
    if output_dir is None:
        # The shortcode's fallback expects output beside the recording in
        # `termshow/<name>/`.
        output_dir = str(recording_output_dir(source_path, source_path.parent, source_path.parent))
    manifest = render_recording(recording, script_obj, Path(output_dir), keyframe_interval=interval)

    stats = manifest.stats
    click.echo(
        f"✓ Rendered {stats.keyframes} keyframes ({stats.frames} unique screens) to {output_dir}/"
    )
    click.echo(f"  Duration: {manifest.duration:.1f}s | Chapters: {len(manifest.chapters)}")
    click.echo(f"  Page payload: {stats.manifest_bytes / 1024:.1f} KB")


@click.command("import-cast")
@click.argument("source", type=click.Path(exists=True))
@click.argument("output", type=click.Path())
def term_import_cast(source: str, output: str) -> None:
    """Import an asciicast (.cast) file to .termshow format."""
    from ._term_player.importer import import_asciicast

    if not output.endswith(".termshow"):
        output += ".termshow"

    recording = import_asciicast(source, output)
    click.echo(f"✓ Imported {source} → {output}")
    click.echo(f"  Duration: {recording.duration:.1f}s | Events: {len(recording.events)}")


@click.command("import-tape")
@click.argument("tape", type=click.Path(exists=True, dir_okay=False))
@click.argument("output", type=click.Path(), required=False)
@click.option("--record", "record_now", is_flag=True, help="Record the script once it's written")
@click.option("--force", is_flag=True, help="Overwrite OUTPUT if it exists")
def term_import_tape(tape: str, output: str | None, record_now: bool, force: bool) -> None:
    """Convert a VHS .tape file to a .termshow.yml script with steps.

    Each tape command becomes a step or a setting. Commands with no
    Termshow equivalent, such as Output or Set FontSize, are listed, and
    left as comments at the top of the script. OUTPUT defaults to
    demo.termshow.yml for demo.tape.

    Examples:
      great-docs termshow import-tape demo.tape
      great-docs termshow import-tape demo.tape docs/assets/demo.termshow.yml --record
    """
    from ._term_player.tape import TapeError, convert_tape

    tape_path = Path(tape)
    if output is None:
        output_path = tape_path.with_name(tape_path.stem + ".termshow.yml")
    elif output.endswith(".termshow.yml"):
        output_path = Path(output)
    else:
        output_path = Path(output.removesuffix(".termshow") + ".termshow.yml")
    if output_path.exists() and not force:
        raise click.ClickException(f"{output_path} already exists (use --force to replace it)")

    try:
        script = convert_tape(tape_path)
    except TapeError as e:
        raise click.ClickException(f"{tape_path.name}, {e}") from None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        script.to_yaml(source_name=tape_path.name, script_name=str(output_path)),
        encoding="utf-8",
    )

    count = len(script.steps)
    click.echo(f"✓ Converted {tape} → {output_path} ({count} step{'' if count == 1 else 's'})")
    if script.skipped:
        click.echo("  Not converted:")
        for skipped in script.skipped:
            click.echo(f"    line {skipped.line}: {skipped.text} ({skipped.reason})")

    if record_now:
        _record_steps(str(output_path), None, cols=None, rows=None, shell=None)
    else:
        click.echo(f"  Record it with: great-docs termshow record --steps {output_path}")


@click.command("play")
@click.argument("source", type=click.Path(exists=True))
@click.option("--speed", type=float, default=1.0, help="Playback speed multiplier")
@click.option(
    "--script", type=click.Path(exists=True), default=None, help="Path to .termshow.yml script"
)
@click.option("--no-script", is_flag=True, help="Ignore any companion .termshow.yml script")
def term_play(source: str, speed: float, script: str | None, no_script: bool) -> None:
    """Play a recording directly in the terminal.

    Applies the companion .termshow.yml script (cuts and speed changes) unless
    --no-script is given. Accepts .termshow and asciicast (.cast) files. Press
    Ctrl+C to stop.

    Examples:
      great-docs termshow play demos/install.termshow
      great-docs termshow play demos/install.termshow --speed 2
    """
    from ._term_player import apply_script
    from ._term_player.playback import play_recording
    from ._term_player.prerender import load_recording

    if speed <= 0:
        raise click.BadParameter("must be greater than 0", param_hint="--speed")

    recording, script_obj = load_recording(
        Path(source), Path(script) if script else None, use_script=not no_script
    )
    if script_obj is not None:
        recording = apply_script(recording, script_obj)

    try:
        play_recording(recording, speed=speed)
    except KeyboardInterrupt:
        click.echo("\n✓ Playback stopped.")


@click.command("export")
@click.argument("source", type=click.Path(exists=True))
@click.option(
    "--svg",
    "fmt",
    flag_value="svg",
    default=True,
    help="Write an animated SVG (the default)",
)
@click.option(
    "--cast",
    "fmt",
    flag_value="cast",
    help="Write an asciicast file for asciinema (version 3 unless --v2 is given)",
)
@click.option("--gif", "fmt", flag_value="gif", help="Write an animated GIF (needs ffmpeg)")
@click.option("--mp4", "fmt", flag_value="mp4", help="Write an MP4 video (needs ffmpeg)")
@click.option("--webm", "fmt", flag_value="webm", help="Write a WebM video (needs ffmpeg)")
@click.option(
    "--bundle",
    "fmt",
    flag_value="bundle",
    help="Write a bundle for the Termshow player: the recording in one .termshow.json file",
)
@click.option("--v2", is_flag=True, help="With --cast, write asciicast version 2")
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    default=None,
    help="Output file (default: the recording's name with the format's extension, or "
    ".termshow.json for a bundle). Its extension picks the format when no format option is "
    "given",
)
@click.option(
    "--script", type=click.Path(exists=True), default=None, help="Path to .termshow.yml script"
)
@click.option("--no-script", is_flag=True, help="Ignore any companion .termshow.yml script")
@click.option("--no-loop", is_flag=True, help="Play once and stop on the last screen")
@click.option(
    "--end-pause",
    type=float,
    default=2.0,
    show_default=True,
    help="Seconds to hold the last screen before looping",
)
@click.option("--chapter-cards", is_flag=True, help="Show a title card at each chapter")
@click.option("--no-annotations", is_flag=True, help="Leave out the script's annotations")
@click.option(
    "--font-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Embed this .woff2/.woff/.ttf/.otf font for the terminal text",
)
@click.option(
    "--fps",
    type=click.IntRange(min=1, max=60),
    default=None,
    help="Frames per second of a GIF or video  [default: 20 for GIF, 30 for video]",
)
@click.option(
    "--scale",
    type=float,
    default=None,
    help="Pixels per SVG unit in a GIF or video  [default: 1 for GIF, 2 for video]",
)
@click.option(
    "--max-idle",
    type=float,
    default=None,
    help="Shorten pauses longer than this many seconds in a GIF or video",
)
@click.pass_context
def term_export(
    ctx: click.Context,
    source: str,
    fmt: str,
    v2: bool,
    output: str | None,
    script: str | None,
    no_script: bool,
    no_loop: bool,
    end_pause: float,
    chapter_cards: bool,
    no_annotations: bool,
    font_file: str | None,
    fps: int | None,
    scale: float | None,
    max_idle: float | None,
) -> None:
    """Export a recording as an animated SVG, a GIF or video, an asciicast file, or a bundle.

    The SVG plays with CSS alone, so it works as an image in a GitHub or
    GitLab README. The companion .termshow.yml script's cuts, speed changes,
    chapters, and annotations are applied unless --no-script is given.

    With --gif, --mp4, or --webm, each screen is drawn like a screenshot
    and ffmpeg joins them, for places that can't show an animated SVG, such
    as pull request comments, chat, and slides. This needs ffmpeg and
    rsvg-convert (or resvg).

    With a light/dark theme pair, two files are written (NAME-light and
    NAME-dark), along with a <picture> snippet that picks one by the
    reader's color scheme (for SVG and GIF).

    With --cast, the recording is written for asciinema's player, CLI, and
    asciinema.org. The script's cuts and speed changes are applied, its
    chapters become markers, and its theme (the light side of a pair) is
    kept. Annotations, highlights, and snippets are left out.

    With --bundle, the recording is written as one .termshow.json file
    with everything the Termshow player needs, including the transcript.
    Point a <termshow-player> element's src at it, or the termshow
    shortcode's file.

    Examples:
      great-docs termshow export demos/install.termshow
      great-docs termshow export demos/install.termshow --svg -o install.svg
      great-docs termshow export demos/install.termshow --gif --max-idle 2
      great-docs termshow export demos/install.termshow -o install.mp4
      great-docs termshow export demos/install.termshow --cast
      great-docs termshow export demos/install.termshow --bundle
    """
    from ._term_player import apply_script, generate_manifest
    from ._term_player.bundle import BUNDLE_SUFFIX
    from ._term_player.export import SIZE_WARNING_BYTES, export_svg, picture_snippet
    from ._term_player.prerender import load_recording
    from ._term_player.video import VIDEO_FORMATS

    # The file extension of each format, and the format of each extension
    extensions = {"bundle": BUNDLE_SUFFIX.lstrip(".")}
    formats = {"json": "bundle"}
    suffix = Path(output).suffix.lower().lstrip(".") if output else ""
    named = formats.get(suffix, suffix)
    if ctx.get_parameter_source("fmt") == click.core.ParameterSource.DEFAULT:
        if named in (*VIDEO_FORMATS, "cast", "bundle"):
            fmt = named
    elif named in (*VIDEO_FORMATS, "svg", "cast", "bundle") and named != fmt:
        raise click.UsageError(
            f"--{fmt} writes a .{extensions.get(fmt, fmt)} file, but -o ends in .{suffix}"
        )

    # The formats each option applies to
    applies = {
        "--no-loop": (no_loop, ("svg", "gif")),
        "--end-pause": (end_pause != 2.0, ("svg", *VIDEO_FORMATS)),
        "--chapter-cards": (chapter_cards, ("svg",)),
        "--no-annotations": (no_annotations, ("svg", *VIDEO_FORMATS)),
        "--font-file": (font_file, ("svg",)),
        "--fps": (fps is not None, VIDEO_FORMATS),
        "--scale": (scale is not None, VIDEO_FORMATS),
        "--max-idle": (max_idle is not None, VIDEO_FORMATS),
        "--v2": (v2, ("cast",)),
    }
    for name, (given, formats) in applies.items():
        if given and fmt not in formats:
            names = [f"--{f}" for f in formats]
            listed = ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]
            raise click.UsageError(f"{name} only applies to {listed}")
    if end_pause < 0:
        raise click.BadParameter("can't be negative", param_hint="--end-pause")
    if scale is not None and scale <= 0:
        raise click.BadParameter("must be more than 0", param_hint="--scale")
    if max_idle is not None and max_idle <= 0:
        raise click.BadParameter("must be more than 0", param_hint="--max-idle")

    source_path = Path(source)
    recording, script_obj = load_recording(
        source_path, Path(script) if script else None, use_script=not no_script
    )

    out_path = Path(output) if output else source_path.with_suffix(f".{extensions.get(fmt, fmt)}")
    if fmt == "cast":
        _export_cast(recording, script_obj, source_path, out_path, version=2 if v2 else 3)
        return
    if fmt == "bundle":
        _export_bundle(recording, script_obj, out_path)
        return

    if script_obj is not None:
        recording = apply_script(recording, script_obj)
    manifest = generate_manifest(recording, script_obj)

    if fmt in VIDEO_FORMATS:
        options = dict(
            fps=fps,
            scale=scale,
            loop=not no_loop,
            end_pause=end_pause,
            annotations=not no_annotations,
            max_idle=max_idle,
        )
        _export_video(manifest, out_path, fmt, options)
        return

    if manifest.dark is not None:
        sides = [
            (out_path.with_name(f"{out_path.stem}-light{out_path.suffix}"), False),
            (out_path.with_name(f"{out_path.stem}-dark{out_path.suffix}"), True),
        ]
    else:
        sides = [(out_path, False)]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    for path, dark in sides:
        try:
            svg = export_svg(
                manifest,
                dark=dark,
                loop=not no_loop,
                end_pause=end_pause,
                chapter_cards=chapter_cards,
                annotations=not no_annotations,
                font_file=font_file,
            )
        except ValueError as e:
            raise click.ClickException(str(e)) from e
        path.write_text(svg, encoding="utf-8")
        size = len(svg.encode("utf-8"))
        click.echo(f"✓ Exported {path} ({size / 1024:.1f} KB)")
        if size > SIZE_WARNING_BYTES:
            click.echo(
                f"  Warning: over {SIZE_WARNING_BYTES // (1024 * 1024)} MB, which README "
                "viewers can be slow to play. Cutting idle stretches or long scrolling "
                "output (cuts, speed_map) in the script makes it smaller.",
                err=True,
            )

    click.echo(
        f"  Duration: {manifest.duration:.1f}s | Unique screens: {len(manifest.frames)}"
        f" | Unique rows: {len(manifest.lines)}"
    )
    if len(sides) == 2:
        alt = manifest.title or "Terminal recording"
        click.echo("\nPaste this where the recording should appear:\n")
        click.echo(picture_snippet(sides[0][0].name, sides[1][0].name, alt))


def _export_video(manifest, out_path: Path, fmt: str, options: dict) -> None:
    """Write `termshow export --gif/--mp4/--webm`'s files and report what went into them."""
    from ._term_player.export import picture_snippet
    from ._term_player.video import SIZE_WARNING_BYTES, VideoError, export_video

    if manifest.dark is not None:
        sides = [
            (out_path.with_name(f"{out_path.stem}-light{out_path.suffix}"), False),
            (out_path.with_name(f"{out_path.stem}-dark{out_path.suffix}"), True),
        ]
    else:
        sides = [(out_path, False)]

    for path, dark in sides:
        try:
            result = export_video(manifest, path, fmt, dark=dark, **options)
        except (VideoError, ValueError) as e:
            raise click.ClickException(str(e)) from e
        size = path.stat().st_size
        click.echo(f"✓ Exported {path} ({size / 1024:.1f} KB, {result.width}×{result.height})")
        if size > SIZE_WARNING_BYTES:
            click.echo(
                f"  Warning: over {SIZE_WARNING_BYTES // (1024 * 1024)} MB, which GitHub won't "
                "take in an issue or pull request. A lower --fps or --scale, --max-idle, or "
                "cuts in the script make it smaller.",
                err=True,
            )

    click.echo(
        f"  Duration: {result.duration:.1f}s | Frames: {result.stills}"
        f" | Unique images: {result.images}"
    )
    if len(sides) == 2 and fmt == "gif":
        alt = manifest.title or "Terminal recording"
        click.echo("\nPaste this where the recording should appear:\n")
        click.echo(picture_snippet(sides[0][0].name, sides[1][0].name, alt))


def _export_bundle(recording, script, out_path: Path) -> None:
    """Write `termshow export --bundle`'s file and report what went into it."""
    from ._term_player.bundle import make_bundle

    manifest, text = make_bundle(recording, script)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    click.echo(f"✓ Exported {out_path} ({len(text.encode()) / 1024:.1f} KB)")
    click.echo(
        f"  Duration: {manifest.duration:.1f}s | Unique screens: {len(manifest.frames)}"
        f" | Unique rows: {len(manifest.lines)}"
    )
    click.echo(f'\nPlay it with <termshow-player src="{out_path.name}"></termshow-player>')


def _export_cast(recording, script, source_path: Path, out_path: Path, *, version: int) -> None:
    """Write `termshow export --cast`'s file and report what went into it."""
    from ._term_player.cast import export_asciicast, left_out

    if out_path.resolve() == source_path.resolve():
        raise click.UsageError(
            f"{out_path} is the recording being exported; choose another name with -o"
        )
    text = export_asciicast(recording, script, version=version)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")

    import json

    codes = [json.loads(line)[1] for line in text.splitlines()[1:]]
    events, markers = len(codes), codes.count("m")
    click.echo(f"✓ Exported {out_path} (asciicast v{version}, {len(text.encode()) / 1024:.1f} KB)")
    summary = f"  Events: {events}"
    if markers:
        summary += f" | Markers: {markers}"
    click.echo(summary)
    if script is not None and script.dark_theme is not None:
        click.echo("  The script's theme is a light/dark pair; the light side was used.")
    missing = left_out(script)
    if missing:
        click.echo(f"  Left out (they need the Termshow player): {', '.join(missing)}.", err=True)


@click.command("snap")
@click.argument("source", type=click.Path(exists=True))
@click.option("--at", "at", type=float, default=None, help="Playback time in seconds")
@click.option("--chapter", default=None, help="Take the last screen of the chapter with this label")
@click.option("--end", is_flag=True, help="Take the last screen (the default)")
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    default=None,
    help="Output .svg or .png file (default: the recording's name with -snap.svg)",
)
@click.option("--png", is_flag=True, help="Write a PNG (needs rsvg-convert or resvg)")
@click.option(
    "--scale",
    type=float,
    default=None,
    help="Pixels per SVG unit in a PNG  [default: 2]",
)
@click.option("--annotations", is_flag=True, help="Draw the annotations showing at that moment")
@click.option(
    "--font-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Embed this .woff2/.woff/.ttf/.otf font for the terminal text (SVG only)",
)
@click.option(
    "--script", type=click.Path(exists=True), default=None, help="Path to .termshow.yml script"
)
@click.option("--no-script", is_flag=True, help="Ignore any companion .termshow.yml script")
def term_snap(
    source: str,
    at: float | None,
    chapter: str | None,
    end: bool,
    output: str | None,
    png: bool,
    scale: float | None,
    annotations: bool,
    font_file: str | None,
    script: str | None,
    no_script: bool,
) -> None:
    """Take a screenshot of one moment in a recording.

    The screenshot is a still SVG, or a PNG with --png or an -o name ending
    in .png, for poster images, social cards, and slides. It uses the
    companion .termshow.yml script's cuts, speed changes, theme, window
    chrome, and prompt replacement unless --no-script is given, and --at
    is a time on the resulting playback timeline.

    With a light/dark theme pair, two files are written (NAME-light and
    NAME-dark), along with a <picture> snippet that picks one by the
    reader's color scheme.

    Examples:
      great-docs termshow snap demos/install.termshow
      great-docs termshow snap demos/install.termshow --at 12.5 -o shot.svg
      great-docs termshow snap demos/install.termshow --chapter Install --png
    """
    from ._term_player import apply_script, generate_manifest
    from ._term_player.export import picture_snippet
    from ._term_player.prerender import load_recording
    from ._term_player.snap import SnapError, rasterize, snap_svg, snap_time

    if sum([at is not None, chapter is not None, end]) > 1:
        raise click.UsageError("use only one of --at, --chapter, and --end")
    if output is not None:
        suffix = Path(output).suffix.lower()
        if suffix not in (".svg", ".png"):
            raise click.UsageError(f"-o must end in .svg or .png, got {output!r}")
        if png and suffix == ".svg":
            raise click.UsageError("--png writes a PNG, but -o ends in .svg")
        png = png or suffix == ".png"
    if not png:
        if scale is not None:
            raise click.UsageError("--scale only applies to PNG output")
    elif font_file is not None:
        raise click.UsageError("--font-file only applies to SVG output")
    if scale is not None and scale <= 0:
        raise click.BadParameter("must be more than 0", param_hint="--scale")

    source_path = Path(source)
    recording, script_obj = load_recording(
        source_path, Path(script) if script else None, use_script=not no_script
    )
    if script_obj is not None:
        recording = apply_script(recording, script_obj)
    manifest = generate_manifest(recording, script_obj)

    try:
        time = snap_time(manifest, at=at, chapter=chapter)
    except SnapError as e:
        raise click.UsageError(str(e)) from e

    ext = ".png" if png else ".svg"
    out_path = Path(output) if output else source_path.with_name(f"{source_path.stem}-snap{ext}")
    if manifest.dark is not None:
        sides = [
            (out_path.with_name(f"{out_path.stem}-light{ext}"), False),
            (out_path.with_name(f"{out_path.stem}-dark{ext}"), True),
        ]
    else:
        sides = [(out_path, False)]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    for path, dark in sides:
        try:
            svg = snap_svg(manifest, time, dark=dark, annotations=annotations, font_file=font_file)
            if png:
                rasterize(svg, path, scale=2.0 if scale is None else scale)
            else:
                path.write_text(svg, encoding="utf-8")
        except (SnapError, ValueError) as e:
            raise click.ClickException(str(e)) from e
        click.echo(f"✓ Saved {path} ({path.stat().st_size / 1024:.1f} KB)")

    click.echo(f"  At {time:.2f}s of {manifest.duration:.2f}s")
    if len(sides) == 2:
        alt = manifest.title or "Terminal recording"
        click.echo("\nPaste this where the screenshot should appear:\n")
        click.echo(picture_snippet(sides[0][0].name, sides[1][0].name, alt))


@click.command("transcript")
@click.argument("source", type=click.Path(exists=True))
@click.option(
    "--markdown",
    "fmt",
    flag_value="markdown",
    default=True,
    help="Write the recording's text as Markdown (the default)",
)
@click.option("--vtt", "fmt", flag_value="vtt", help="Write the annotations as WebVTT captions")
@click.option(
    "--vtt-chapters", "fmt", flag_value="chapters", help="Write the chapters as a WebVTT track"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    default=None,
    help="Output file (default: print to the terminal)",
)
@click.option(
    "--script", type=click.Path(exists=True), default=None, help="Path to .termshow.yml script"
)
@click.option("--no-script", is_flag=True, help="Ignore any companion .termshow.yml script")
def term_transcript(
    source: str, fmt: str, output: str | None, script: str | None, no_script: bool
) -> None:
    """Write the text of a recording, or captions for it.

    The transcript holds everything the recording shows, including lines
    that scroll away, as plain text without colors. The companion
    .termshow.yml script's chapters split it into sections, its annotations
    become notes, and its prompt replacement is applied, unless --no-script
    is given. A full-screen program, like less or vim, keeps only its last
    screen.

    With --vtt, the annotations are written as WebVTT captions; with
    --vtt-chapters, the chapters are written as a WebVTT chapters track.
    Both are on the playback timeline (after cuts and speed changes).

    Great Docs builds write each recording's transcript next to its player,
    for screen readers, search, and the page's Markdown version.

    Examples:
      great-docs termshow transcript demos/install.termshow
      great-docs termshow transcript demos/install.termshow -o install.md
      great-docs termshow transcript demos/install.termshow --vtt -o install.vtt
    """
    from ._term_player.prerender import load_recording
    from ._term_player.transcript import transcript_markdown, transcript_vtt

    source_path = Path(source)
    recording, script_obj = load_recording(
        source_path, Path(script) if script else None, use_script=not no_script
    )
    if fmt == "markdown":
        text = transcript_markdown(recording, script_obj)
        empty = "The recording shows no text." if not text else ""
    else:
        text = transcript_vtt(recording, script_obj, chapters=fmt == "chapters")
        what = "chapters" if fmt == "chapters" else "annotations"
        empty = f"The recording has no {what}." if "-->" not in text else ""

    if output is None:
        click.echo(text, nl=False)
    else:
        out_path = Path(output)
        if out_path.resolve() == source_path.resolve():
            raise click.UsageError(f"{out_path} is the recording itself; choose another name")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        click.echo(f"✓ Wrote {out_path} ({len(text.encode()) / 1024:.1f} KB)")
    if empty:
        click.echo(empty, err=True)


@click.command("validate")
@click.argument("sources", nargs=-1, required=True, type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--script",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to .termshow.yml script (with a single recording)",
)
@click.option("--no-script", is_flag=True, help="Check the recording without its script")
@click.option("--strict", is_flag=True, help="Fail on warnings as well as errors")
def term_validate(
    sources: tuple[str, ...], script: str | None, no_script: bool, strict: bool
) -> None:
    """Check recordings and their scripts for mistakes.

    Errors are things the format doesn't allow: a malformed recording line,
    an unknown script key, a misspelled theme or position, a cut that ends
    before it starts, or a pattern that isn't a regular expression.

    Warnings are things that are allowed but probably not meant: an
    annotation that starts after the recording ends, overlapping cuts or
    snippets, chapters out of order, two annotations in the same spot, or a
    `match` pattern that never appears on screen while it's active.

    Each recording's companion .termshow.yml is checked with it. A script can
    also be given on its own, and its recording is found next to it. Exits
    with status 1 if there are errors (or, with --strict, warnings).

    Examples:
      great-docs termshow validate demos/install.termshow
      great-docs termshow validate demos/*.termshow --strict
    """
    from ._term_player.validate import ERROR, check_script_text, validate

    if script and len(sources) > 1:
        raise click.BadParameter("use it with a single recording", param_hint="--script")

    errors = warnings = 0
    for source in sources:
        source_path = Path(source)
        script_for = script
        if source_path.name.endswith(".termshow.yml"):
            script_for = script or source
            source_path = source_path.with_name(source_path.name[: -len(".yml")])
            if not source_path.exists() and not _has_steps(script_for):
                raise click.ClickException(f"No recording {source_path} for the script {source}")
        if source_path.exists():
            problems = validate(source_path, script_for, use_script=not no_script)
            checked = str(source_path)
        else:
            # A script with steps that hasn't been recorded yet is checked on its own
            script_path = Path(script_for)
            problems = []
            check_script_text(script_path.read_text(encoding="utf-8"), script_path.name, problems)
            checked = f"{script_path} (not recorded yet)"
        if not problems:
            click.echo(f"✓ {checked}: no problems")
        for problem in problems:
            click.echo(f"{problem.severity}: {problem}")
        errors += sum(1 for p in problems if p.severity == ERROR)
        warnings += sum(1 for p in problems if p.severity != ERROR)

    if errors or warnings:
        plural = lambda n, word: f"{n} {word}{'' if n == 1 else 's'}"  # noqa: E731
        click.echo(f"\n{plural(errors, 'error')}, {plural(warnings, 'warning')}")
    if errors or (strict and warnings):
        raise SystemExit(1)


def _has_steps(script: str) -> bool:
    """Whether a script has a `steps:` section, so it can be recorded from."""
    from yaml12 import parse_yaml

    try:
        data = parse_yaml(Path(script).read_text(encoding="utf-8"))
    except ValueError:
        return False
    return isinstance(data, dict) and "steps" in data


@click.command("check")
@click.argument("scripts", nargs=-1, required=True, type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--ignore",
    "ignore",
    multiple=True,
    metavar="REGEX",
    help="Leave text matching this pattern out of the comparison (repeatable)",
)
@click.option("--update", is_flag=True, help="Re-record the recordings that have drifted")
@click.option("--shell", type=str, default=None, help="Run the steps in this shell instead")
@click.option(
    "--json", "as_json", is_flag=True, help="Print the results as JSON, for CI and other tools"
)
def term_check(
    scripts: tuple[str, ...],
    ignore: tuple[str, ...],
    update: bool,
    shell: str | None,
    as_json: bool,
):
    """Check that recordings made from steps still match what the steps produce.

    Each script's steps are run again, as `record --steps` would, and the
    screen is compared with the committed recording at every marker and at
    the end. Timing isn't compared. Give the .termshow.yml scripts, or the
    .termshow recordings they belong to.

    Text that changes from run to run, such as a version number or a
    temporary path, can be left out with --ignore or the script's
    `check.ignore` list.

    Exits with status 1 if any recording has drifted or a step failed. With
    --update, recordings that have drifted are recorded again instead.

    With --json, the results are printed as one JSON object instead, with
    the same exit status. Progress still goes to stderr.

    Examples:
      great-docs termshow check docs/assets/*.termshow.yml
      great-docs termshow check docs/assets/install.termshow --ignore 'v\\d+\\.\\d+'
      great-docs termshow check docs/assets/*.termshow.yml --json > drift.json
    """
    import json
    import re

    from ._term_player.check import CheckError, check_script
    from ._term_player.importer import _write_termshow
    from ._term_player.steps import StepsError

    for pattern in ignore:
        try:
            re.compile(pattern)
        except re.error as e:
            raise click.BadParameter(
                f"{pattern!r} isn't a valid regular expression ({e})", param_hint="--ignore"
            ) from None

    results = []
    for script in scripts:
        script_path = Path(script)
        if script_path.name.endswith(".termshow"):
            script_path = script_path.with_name(script_path.name + ".yml")
        click.echo(f"Checking {script_path}", err=True)
        entry = {"script": script_path.as_posix(), "recording": None}
        try:
            result = check_script(script_path, ignore=ignore, shell=shell)
        except (CheckError, StepsError) as e:
            entry |= {"status": "failed", "error": str(e)}
            if isinstance(e, StepsError) and e.screen:
                entry["screen"] = e.screen
            results.append(entry)
            if not as_json:
                _echo_check_failure(entry)
            continue

        entry |= {
            "recording": result.recording_path.as_posix(),
            "status": "drifted" if result.drifted else "up_to_date",
            "compared": result.snapshots,
            "differences": [{"at": d.where, "diff": d.lines} for d in result.differences],
        }
        if result.drifted and update:
            _write_termshow(result.recording, result.recording_path)
            entry["status"] = "updated"
        results.append(entry)
        if not as_json:
            _echo_check_result(entry)

    counts = {
        status: sum(r["status"] == status for r in results)
        for status in ("up_to_date", "drifted", "updated", "failed")
    }
    if as_json:
        click.echo(json.dumps({"version": 1, "summary": counts, "results": results}, indent=2))
    elif len(scripts) > 1:
        changed = counts["drifted"] + counts["updated"]
        click.echo(
            f"\n{counts['up_to_date']} of {len(scripts)} up to date"
            + (f", {changed} {'updated' if update else 'drifted'}" if changed else "")
            + (f", {counts['failed']} couldn't be checked" if counts["failed"] else "")
        )
    if counts["failed"] or counts["drifted"]:
        raise SystemExit(1)


def _echo_check_failure(entry: dict) -> None:
    click.echo(f"✗ {entry['script']}: {entry['error']}")
    if entry.get("screen"):
        click.echo("\nThe screen at the time:")
        for line in entry["screen"].splitlines():
            click.echo(f"  │ {line}")


def _echo_check_result(entry: dict) -> None:
    recording = entry["recording"]
    if entry["status"] == "up_to_date":
        screens = f"{entry['compared']} screen{'' if entry['compared'] == 1 else 's'}"
        click.echo(f"✓ {recording} is up to date ({screens} compared)")
        return
    click.echo(f"✗ {recording} has drifted:\n")
    for difference in entry["differences"]:
        for line in difference["diff"]:
            color = {"+": "green", "-": "red", "@": "cyan"}.get(line[:1])
            if line.startswith(("+++", "---")):
                color = None
            click.secho(f"  {line}", fg=color)
        click.echo()
    if entry["status"] == "updated":
        click.echo(f"↻ Recorded {recording} again")


@click.command("assets")
@click.argument("dest", type=click.Path(file_okay=False))
def term_assets(dest: str) -> None:
    """Copy the web player into a directory, for pages built without Quarto.

    Writes termshow.js, termshow.css, and the fonts the stylesheet uses, then
    prints the HTML that loads them. Point a <termshow-player> element's src
    at a `termshow render` output directory to embed a recording.

    Examples:
      great-docs termshow assets site/player
    """
    from ._term_player.web import copy_player, player_snippet

    files = copy_player(dest)
    click.echo(f"✓ Copied {len(files)} player files to {dest}/")
    click.echo("\nAdd this to a page, with src pointing at a rendered recording:\n")
    click.echo(player_snippet(Path(dest).as_posix()))


termshow.add_command(term_record)
termshow.add_command(term_render)
termshow.add_command(term_play)
termshow.add_command(term_export)
termshow.add_command(term_snap)
termshow.add_command(term_transcript)
termshow.add_command(term_validate)
termshow.add_command(term_check)
termshow.add_command(term_assets)
termshow.add_command(term_import_cast)
termshow.add_command(term_import_tape)


@click.command("edit")
@click.argument("source", type=click.Path(exists=True))
@click.option("--port", type=int, default=8765, help="Local server port")
@click.option("--no-browser", is_flag=True, help="Don't auto-open browser")
def term_edit(source: str, port: int, no_browser: bool) -> None:
    """Open the Termshow Editor for a .termshow recording.

    Launches a browser-based timeline editor for adding chapters,
    annotations, and cuts. Changes are saved back to the .termshow.yml
    script file.

    Examples:
      great-docs termshow edit demos/my-demo.termshow
      great-docs termshow edit demos/install.termshow --port 9000
    """
    from ._term_player.editor import serve_editor

    serve_editor(source, port=port, no_browser=no_browser)


termshow.add_command(term_edit)
cli.add_command(termshow)


def main() -> None:
    """Main CLI entry point for great-docs."""
    cli()


if __name__ == "__main__":
    main()
