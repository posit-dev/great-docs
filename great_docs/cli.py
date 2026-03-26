from __future__ import annotations

import re
import sys
from pathlib import Path

import click

from . import __version__
from .core import GreatDocs


def _detect_python_version_from_pyproject(project_root: Path) -> str | None:
    """Detect the minimum Python version from pyproject.toml.

    Parses the `requires-python` field (e.g., '>=3.12', '>=3.10,<3.13')
    and returns a suitable Python version string for CI (e.g., '3.12').

    Returns None if pyproject.toml doesn't exist or has no version requirement.
    """
    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        return None

    try:
        # Use tomllib (Python 3.11+) or tomli as fallback
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        requires_python = data.get("project", {}).get("requires-python")
        if not requires_python:
            return None

        # Parse version specifier to find minimum version
        # Common patterns: ">=3.12", ">=3.10,<3.13", "~=3.11", ">=3.9"
        # Extract versions from specifiers
        version_pattern = r"(\d+\.\d+)"
        matches = re.findall(version_pattern, requires_python)

        if not matches:
            return None

        # For >= specifiers, use the specified version
        if ">=" in requires_python or "~=" in requires_python:
            # Return the first (minimum) version found
            return matches[0]

        # For other specifiers, try to pick a reasonable version
        # Find the highest version mentioned (likely the target)
        versions = [tuple(map(int, v.split("."))) for v in matches]
        max_version = max(versions)
        return f"{max_version[0]}.{max_version[1]}"

    except Exception:
        # If parsing fails, return None to use default
        return None


class OrderedGroup(click.Group):
    """Click group that lists commands in the order they were added."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands.keys())


@click.group(cls=OrderedGroup)
@click.version_option(version=__version__, prog_name="great-docs")
def cli():
    """Great Docs - Beautiful documentation for Python packages.

    Great Docs generates professional documentation sites with auto-generated
    API references, CLI documentation, smart navigation, and modern styling.

    Get started with 'great-docs init' to set up your docs, then use
    'great-docs build' to generate your site.
    """
    pass


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Delete existing great-docs.yml and generate a fresh default config",
)
def init(project_path: str | None, force: bool) -> None:
    """Initialize great-docs in your project (one-time bootstrap).

    Creates a fresh great-docs.yml configuration file with discovered
    package exports and sensible defaults. Refuses to run if
    great-docs.yml already exists (use --force to reset).

    \b
    • Creates great-docs.yml with discovered API exports
    • Auto-detects your package name and public API
    • Updates .gitignore to exclude the build directory
    • Detects docstring style (numpy, google, sphinx)

    After init, customize great-docs.yml then use 'great-docs build'
    for all subsequent builds. You should never need to run init again
    unless you want to completely reset your configuration.

    \b
    Examples:
      great-docs init                       # Initialize in current directory
      great-docs init --force               # Reset config to defaults
      great-docs init --project-path ../pkg # Initialize in another project
    """
    try:
        docs = GreatDocs(project_path=project_path)
        docs.install(force=force)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


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
def build(project_path: str | None, watch: bool, no_refresh: bool) -> None:
    """Build your documentation site.

    Requires great-docs.yml to exist (run 'great-docs init' first).
    This is the only command you need day-to-day and in CI.

    Creates the 'great-docs/' build directory, copies all assets,
    and builds the documentation site. The build directory is ephemeral and
    should not be committed to version control.

    \b
    1. Creates great-docs/ directory with all assets
    2. Copies user guide files from project root
    3. Generates index.qmd from README.md
    4. Refreshes API reference configuration (discovers API changes)
    5. Generates llms.txt and llms-full.txt for AI/LLM indexing
    6. Creates source links to GitHub
    7. Generates CLI reference pages (if enabled)
    8. Generates API reference pages
    9. Runs Quarto to render the final HTML site in great-docs/_site/

    Use --no-refresh to skip API discovery for faster rebuilds when your
    package's public API hasn't changed.

    \b
    Examples:
      great-docs build                      # Full build with API refresh
      great-docs build --no-refresh         # Fast rebuild (skip API discovery)
      great-docs build --watch              # Rebuild on file changes
      great-docs build --project-path ../pkg
    """
    try:
        docs = GreatDocs(project_path=project_path)
        docs.build(watch=watch, refresh=not no_refresh)
    except KeyboardInterrupt:
        click.echo("\n👋 Stopped watching")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
def uninstall(project_path: str | None) -> None:
    """Remove great-docs from your project.

    This command removes the great-docs configuration and build directory:

    \b
    • Deletes great-docs.yml configuration file
    • Removes great-docs/ build directory

    Your source files (user_guide/, README.md, etc.) are preserved.

    \b
    Examples:
      great-docs uninstall                  # Remove from current project
    """
    try:
        docs = GreatDocs(project_path=project_path)
        docs.uninstall()
    except Exception as e:
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
def preview(project_path: str | None, port: int) -> None:
    """Preview your documentation locally.

    Starts a local HTTP server and opens the built documentation site in your
    default browser. If the site hasn't been built yet, it will build it first.

    The site is served from great-docs/_site/. Use 'great-docs build' to
    rebuild if you've made changes.

    \b
    Examples:
      great-docs preview                    # Preview on port 3000
      great-docs preview --port 8080        # Preview on port 8080
    """
    try:
        docs = GreatDocs(project_path=project_path)
        docs.preview(port=port)
    except KeyboardInterrupt:
        click.echo("\n👋 Server stopped")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing great-docs.yml without prompting",
)
def config(project_path: str | None, force: bool) -> None:
    """Generate a great-docs.yml configuration file.

    Creates a great-docs.yml file with all available options documented.
    The generated file contains commented examples for each setting.

    \b
    Examples:
      great-docs config                     # Generate in current directory
      great-docs config --force             # Overwrite existing file
      great-docs config --project-path ../pkg
    """
    from pathlib import Path

    from .config import create_default_config

    try:
        project_root = Path(project_path) if project_path else Path.cwd()
        config_path = project_root / "great-docs.yml"

        if config_path.exists() and not force:
            if not click.confirm(
                f"⚠️  Configuration file already exists at {config_path}\n   Overwrite it?"
            ):
                click.echo("Cancelled.")
                return

        config_content = create_default_config()
        config_path.write_text(config_content, encoding="utf-8")
        click.echo(f"✓ Created {config_path}")
        click.echo("\nEdit this file to customize your documentation settings.")
        click.echo("See https://posit-dev.github.io/great-docs/user-guide/03-configuration.html")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Register commands in the desired order
cli.add_command(init)
cli.add_command(build)
cli.add_command(preview)
cli.add_command(uninstall)
cli.add_command(config)


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
    "--verbose",
    "-v",
    is_flag=True,
    help="Show method names for each class",
)
def scan(project_path: str | None, docs_dir: str | None, verbose: bool) -> None:
    """Discover package exports and preview what can be documented.

    This command analyzes your package to find public classes, functions,
    and other exports. Use this to see what's available before writing
    your reference config.

    \b
    Examples:
      great-docs scan                       # Show discovered exports
      great-docs scan --verbose             # Include method names for classes
      great-docs scan -v                    # Short form of --verbose
    """

    try:
        docs = GreatDocs(project_path=project_path)

        # Detect package name
        package_name = docs._detect_package_name()
        if not package_name:
            click.echo("Error: Could not detect package name.", err=True)
            sys.exit(1)

        importable_name = docs._normalize_package_name(package_name)

        # Section 1: Discovery
        click.echo("─" * 50)
        click.echo("📡 Discovery")
        click.echo("─" * 50)
        click.echo(f"Package: {importable_name}\n")

        # Get discovered exports
        exports = docs._get_package_exports(importable_name)
        if not exports:
            click.echo("No exports discovered.")
            sys.exit(0)

        # Categorize exports
        categories = docs._categorize_api_objects(importable_name, exports)

        # Build sets of what's in the reference config
        reference_config = docs._config.reference
        ref_items = set()  # Items explicitly listed
        ref_classes_with_members = set()  # Classes with members: true (or default)
        ref_classes_without_members = set()  # Classes with members: false

        for section in reference_config:
            for item in section.get("contents", []):
                if isinstance(item, str):
                    ref_items.add(item)
                elif isinstance(item, dict):
                    name = item.get("name", "")
                    ref_items.add(name)
                    # Check members setting
                    members = item.get("members", True)
                    if members is False:
                        ref_classes_without_members.add(name)
                    else:
                        ref_classes_with_members.add(name)

        # Section 2: Exports
        click.echo("\n" + "─" * 50)
        click.echo(f"📦 Exports ({len(exports)} item(s))")
        click.echo("─" * 50)

        # Markers with colors
        marker_included = click.style("[x]", fg="green")
        marker_not_included = click.style("[ ]", fg="red")
        marker_class_only = click.style("[-]", fg="yellow")

        # Show class-like categories (with method details)
        _class_like_cats = [
            ("classes", "Classes"),
            ("dataclasses", "Dataclasses"),
            ("abstract_classes", "Abstract Classes"),
            ("protocols", "Protocols"),
        ]
        for cat_key, label in _class_like_cats:
            cat_items = categories.get(cat_key)
            if cat_items:
                click.echo(f"\n{label}:")
                for class_name in cat_items:
                    method_names = categories.get("class_method_names", {}).get(class_name, [])

                    # Determine class marker
                    if class_name in ref_classes_without_members:
                        class_marker = marker_class_only
                    elif class_name in ref_classes_with_members or class_name in ref_items:
                        class_marker = marker_included
                    else:
                        class_marker = marker_not_included

                    click.echo(f"• {class_marker} {class_name}")
                    for method in method_names:
                        full_method = f"{class_name}.{method}"
                        method_marker = (
                            marker_included if full_method in ref_items else marker_not_included
                        )
                        click.echo(f"    • {method_marker} {full_method}")

        # Show flat categories (simple lists)
        _flat_cats = [
            ("enums", "Enumerations"),
            ("exceptions", "Exceptions"),
            ("namedtuples", "Named Tuples"),
            ("typeddicts", "Typed Dicts"),
            ("functions", "Functions"),
            ("async_functions", "Async Functions"),
            ("constants", "Constants"),
            ("type_aliases", "Type Aliases"),
            ("other", "Other"),
        ]
        for cat_key, label in _flat_cats:
            cat_items = categories.get(cat_key)
            if cat_items:
                click.echo(f"\n{label}:")
                for name in cat_items:
                    m = marker_included if name in ref_items else marker_not_included
                    click.echo(f"• {m} {name}")

        # Section 3: Config status
        click.echo("\n" + "─" * 50)
        click.echo("📋 Reference Config")
        click.echo("─" * 50)

        if reference_config:
            click.echo(f"\n✅ Found in great-docs.yml ({len(reference_config)} section(s))")
            if verbose:
                for section in reference_config:
                    title = section.get("title", "Untitled")
                    contents = section.get("contents", [])
                    click.echo(f"    • {title}: {len(contents)} item(s)")
        else:
            click.echo("\n💡 No reference config found. Add one to great-docs.yml:")
            click.echo("   reference:")
            click.echo("     - title: Core Classes")
            click.echo("       desc: Main classes for the package")
            click.echo("       contents:")
            click.echo("         - name: MyClass")
            click.echo("           members: false     # Don't document methods")
            click.echo("         - SimpleClass        # Methods inline")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


cli.add_command(scan)


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
    "--force",
    is_flag=True,
    help="Overwrite existing workflow file without prompting",
)
def setup_github_pages(
    project_path: str | None, main_branch: str, python_version: str | None, force: bool
) -> None:
    """Set up automatic deployment to GitHub Pages.

    This command creates a GitHub Actions workflow that automatically builds
    and deploys your documentation when you push to the main branch.

    \b
    The workflow will:
    • Build docs on every push and pull request
    • Deploy to GitHub Pages on main branch pushes
    • Use Quarto's official GitHub Action for reliable builds

    The Python version is automatically detected from your pyproject.toml's
    `requires-python` field. Use --python-version to override.

    After running this command, commit the workflow file and enable GitHub
    Pages in your repository settings (Settings → Pages → Source: GitHub Actions).

    \b
    Examples:
      great-docs setup-github-pages                     # Auto-detect Python version
      great-docs setup-github-pages --main-branch dev   # Deploy from 'dev' branch
      great-docs setup-github-pages --python-version 3.12
      great-docs setup-github-pages --force             # Overwrite existing workflow
    """

    try:
        # Determine project root
        project_root = Path(project_path) if project_path else Path.cwd()

        # Auto-detect Python version if not specified
        if python_version is None:
            detected_version = _detect_python_version_from_pyproject(project_root)
            if detected_version:
                python_version = detected_version
                click.echo(f"📦 Detected Python {python_version} from pyproject.toml")
            else:
                python_version = "3.12"
                click.echo("📦 Using default Python 3.12 (no requires-python found)")

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
        click.echo("   • Create preview deployments for pull requests")

    except Exception as e:
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
def check_links(
    project_path: str | None,
    source_only: bool,
    docs_only: bool,
    timeout: int,
    ignore: tuple[str, ...],
    verbose: bool,
    json_output: bool,
) -> None:
    """Check for broken links in source code and documentation.

    This command scans Python source files and documentation (`.qmd`, `.md`)
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
        docs = GreatDocs(project_path=project_path)

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
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


cli.add_command(check_links)


@click.command("spell-check")
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
    help="Also check spelling in Python docstrings",
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
    "-v",
    "--verbose",
    is_flag=True,
    help="Show detailed progress for each file checked",
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Output results as JSON",
)
def spell_check(
    project_path,
    docs_dir,
    include_docstrings,
    custom_words,
    dictionary_file,
    verbose,
    json_output,
):
    """[DEPRECATED] Check spelling in documentation files.

    ⚠️  This command is deprecated. Use 'great-docs proofread' instead.

    The proofread command uses Harper, a fast grammar checker that provides:
    - Spelling AND grammar checking in one pass
    - Better suggestions with context
    - More rule categories (style, punctuation, etc.)
    - Custom dictionary support

    \b
    Migration:
      great-docs spell-check           →  great-docs proofread --spelling-only
      great-docs spell-check -d word   →  great-docs proofread -d word

    Original description:
    This command scans documentation files (.qmd, .md) for spelling errors.
    It intelligently skips code blocks, inline code, URLs, and technical terms.

    A built-in dictionary of common programming terms is included (e.g., "api",
    "cli", "json", "yaml", "pytest", etc.). You can add custom words using
    -d/--dictionary or --dictionary-file.

    \b
    Examples:
      great-docs spell-check                        # Check all docs
      great-docs spell-check --verbose              # Show progress
      great-docs spell-check -d myterm -d anotherterm  # Add custom words
      great-docs spell-check --dictionary-file words.txt  # Load custom dictionary
      great-docs spell-check --include-docstrings   # Also check Python docstrings
      great-docs spell-check --json-output          # Output as JSON
    """
    import json as json_module

    # Show deprecation warning
    if not json_output:
        click.echo(
            "\n⚠️  DEPRECATION WARNING: 'spell-check' is deprecated.\n"
            "   Use 'great-docs proofread' instead for better results.\n"
            "   Migration: great-docs proofread --spelling-only\n",
            err=True,
        )

    try:
        docs = GreatDocs(project_path=project_path)

        # Build custom dictionary
        custom_dictionary = list(custom_words) if custom_words else []

        # Load dictionary file if provided
        if dictionary_file:
            try:
                with open(dictionary_file, "r", encoding="utf-8") as f:
                    for line in f:
                        word = line.strip()
                        if word and not word.startswith("#"):
                            custom_dictionary.append(word)
            except Exception as e:
                click.echo(f"Warning: Could not read dictionary file: {e}", err=True)

        if verbose and not json_output:
            click.echo("\n🔍 Checking spelling in documentation...\n")

        results = docs.spell_check(
            include_docs=True,
            include_docstrings=include_docstrings,
            custom_dictionary=custom_dictionary if custom_dictionary else None,
            verbose=verbose and not json_output,
        )

        if json_output:
            click.echo(json_module.dumps(results, indent=2))
            sys.exit(1 if results["misspelled"] else 0)

        # Print summary
        click.echo("\n" + "=" * 60)
        click.echo("📝 Spell Check Results")
        click.echo("=" * 60)

        click.echo(f"\n   Words checked: {results['total_words']}")
        click.echo(f"   Unique misspellings: {len(results['misspelled'])}")
        click.echo(f"   Files with issues: {len(results['by_file'])}")

        if results["skipped_files"]:
            click.echo(f"   Skipped files: {len(results['skipped_files'])}")

        # Show misspelled words
        if results["misspelled"]:
            click.echo("\n" + "-" * 60)
            click.echo("❌ Misspelled Words:")
            click.echo("-" * 60)

            for item in results["misspelled"]:
                word = item["word"]
                suggestions = item["suggestions"][:3]
                files = item["files"]

                click.echo(f"\n   '{word}'")
                if suggestions:
                    click.echo(f"   Suggestions: {', '.join(suggestions)}")
                click.echo("   Found in:")
                for f in files[:3]:  # Limit files shown
                    click.echo(f"     • {f}")
                if len(files) > 3:
                    click.echo(f"     ... and {len(files) - 3} more file(s)")

                # Show context
                contexts = item.get("contexts", [])
                if contexts:
                    click.echo("   Context:")
                    for ctx in contexts[:2]:
                        click.echo(f'     "{ctx[:70]}..."' if len(ctx) > 70 else f'     "{ctx}"')

            click.echo("\n" + "-" * 60)
            click.echo("\n💡 Tips:")
            click.echo("   • Add custom words with: -d word1 -d word2")
            click.echo("   • Create a dictionary file with words (one per line)")
            click.echo("   • Use --dictionary-file words.txt to load it")

            click.echo(f"\n⚠️  Found {len(results['misspelled'])} spelling issue(s).")
            sys.exit(1)
        else:
            click.echo("\n✅ No spelling errors found!")
            sys.exit(0)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


cli.add_command(spell_check)


@click.command()
@click.option(
    "--project-path",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to your project root directory (default: current directory)",
)
@click.option(
    "--max-releases",
    type=int,
    default=None,
    help="Maximum number of releases to include (default: from config or 50)",
)
def changelog(project_path: str | None, max_releases: int | None) -> None:
    """Generate a Changelog page from GitHub Releases.

    Fetches published releases from the GitHub API and renders them as a
    changelog.qmd page in the build directory. The page is also linked in
    the navbar automatically.

    \b
    Requires the project to have a GitHub repository URL in pyproject.toml.
    Set GITHUB_TOKEN or GH_TOKEN to avoid API rate limits.
    """
    try:
        docs = GreatDocs(project_path=project_path)

        # Override max_releases in config if provided
        if max_releases is not None:
            docs._config._config.setdefault("changelog", {})["max_releases"] = max_releases

        owner, repo, _base_url = docs._get_github_repo_info()
        if not owner or not repo:
            click.echo(
                "Error: No GitHub repository URL found in pyproject.toml. "
                "Add a [project.urls] entry like:\n\n"
                '  Repository = "https://github.com/owner/repo"',
                err=True,
            )
            sys.exit(1)

        result = docs._generate_changelog_page()
        if result:
            docs._add_changelog_to_navbar()
            click.echo(f"✅ Changelog generated: {docs.project_path / result}")
        else:
            click.echo("No published releases found on GitHub.")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


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
):
    """Check spelling and grammar in documentation files using Harper.

    Harper is a fast, privacy-first grammar checker that runs locally.
    It checks spelling, grammar, punctuation, and style in a single pass.

    \b
    By default, checks all documentation files (.qmd, .md) in the project.
    Uses smart defaults to reduce noise in technical documentation:
      - Ignores formatting rules that conflict with code/YAML (unless --strict)
      - Includes a built-in dictionary of technical terms (unless --no-builtin-dictionary)

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

    \b
    Requires harper-cli to be installed:
      brew install harper      # macOS
      cargo install harper-cli # any platform
    """
    import json as json_module
    import tempfile
    from collections import defaultdict

    from ._harper import (
        HarperError,
        HarperNotFoundError,
        check_harper_available,
        get_builtin_dictionary,
        get_default_ignore_rules,
        run_harper,
        run_harper_on_text,
    )

    try:
        # Check if Harper is available
        available, harper_info = check_harper_available()
        if not available:
            click.echo(f"Error: {harper_info}", err=True)
            sys.exit(3)

        if verbose and not json_output and not compact:
            click.echo(f"\n🔍 Proofreading with {harper_info}...\n")
            if not strict:
                click.echo("Using smart defaults for technical docs. Use --strict to disable.\n")

        # Determine files to check
        docs = GreatDocs(project_path=project_path)
        files_to_check: list[Path] = []

        if files:
            # User specified files
            files_to_check = [Path(f) for f in files]
        else:
            # Auto-discover documentation files
            user_guide_dir = docs.project_root / "user_guide"
            if user_guide_dir.exists():
                files_to_check.extend(user_guide_dir.rglob("*.qmd"))
                files_to_check.extend(user_guide_dir.rglob("*.md"))

            # Check README
            readme = docs.project_root / "README.md"
            if readme.exists():
                files_to_check.append(readme)

            # Check recipes if they exist
            recipes_dir = docs.project_root / "recipes"
            if recipes_dir.exists():
                files_to_check.extend(recipes_dir.rglob("*.qmd"))
                files_to_check.extend(recipes_dir.rglob("*.md"))

        if not files_to_check:
            click.echo("No documentation files found to check.", err=True)
            sys.exit(0)

        # Build custom dictionary file
        # Start with builtin dictionary unless disabled
        dict_path = None
        words = []

        if not strict and not no_builtin_dictionary:
            words.extend(get_builtin_dictionary())

        # Add user-provided words
        if custom_words:
            words.extend(custom_words)

        # Load from dictionary file if provided
        if dictionary_file:
            try:
                with open(dictionary_file, "r", encoding="utf-8") as f:
                    for line in f:
                        word = line.strip()
                        if word and not word.startswith("#"):
                            words.append(word)
            except Exception as e:
                click.echo(f"Warning: Could not read dictionary file: {e}", err=True)

        if words:
            # Create temporary dictionary file
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
            tmp.write("\n".join(words))
            tmp.close()
            dict_path = tmp.name

        # Build rule filters
        only = None
        ignore = None

        # Start with default ignores for technical docs (unless --strict)
        if not strict:
            ignore = get_default_ignore_rules()

        if spelling_only:
            only = ["SpellCheck"]
        elif grammar_only:
            ignore = (ignore or []) + ["SpellCheck"]

        if only_rules:
            only = only_rules.split(",") if only is None else only + only_rules.split(",")

        if ignore_rules:
            ignore = ignore_rules.split(",") if ignore is None else ignore + ignore_rules.split(",")

        # Separate files by type (Harper doesn't recognize .qmd)
        md_files = [f for f in files_to_check if f.suffix == ".md"]
        qmd_files = [f for f in files_to_check if f.suffix == ".qmd"]
        py_files = [f for f in files_to_check if f.suffix == ".py"]

        all_results = []

        # Check .md files directly
        if md_files:
            if verbose and not json_output and not compact:
                click.echo(f"Checking {len(md_files)} Markdown file(s)...\n")

            results = run_harper(
                md_files,
                dialect=dialect,
                user_dict_path=dict_path,
                ignore_rules=ignore,
                only_rules=only,
            )
            all_results.extend(results)

        # Check .qmd files via stdin (Harper doesn't recognize extension)
        # We extract prose only (skip code blocks) to avoid false positives
        for qmd_file in qmd_files:
            if verbose and not json_output and not compact:
                click.echo(f"Checking {qmd_file.name}...")

            try:
                from ._harper import extract_prose_from_markdown

                content = qmd_file.read_text(encoding="utf-8")

                # Extract prose sections, skipping fenced code blocks and frontmatter
                prose_content, line_mapping = extract_prose_from_markdown(content)

                lints = run_harper_on_text(
                    prose_content,
                    dialect=dialect,
                    user_dict_path=dict_path,
                    ignore_rules=ignore,
                    only_rules=only,
                )

                # Convert to file result with proper path and remap line numbers
                from ._harper import HarperFileResult

                rel_path = str(qmd_file.relative_to(docs.project_root))
                for lint in lints:
                    lint.file = rel_path
                    # Remap line number from prose content back to original file
                    if lint.line in line_mapping:
                        lint.line = line_mapping[lint.line]

                all_results.append(
                    HarperFileResult(
                        file=rel_path,
                        lint_count=len(lints),
                        lints=lints,
                        error=None,
                    )
                )
            except Exception as e:
                from ._harper import HarperFileResult

                rel_path = str(qmd_file.relative_to(docs.project_root))
                all_results.append(
                    HarperFileResult(
                        file=rel_path,
                        lint_count=0,
                        lints=[],
                        error=str(e),
                    )
                )

        # Check Python files if requested
        if include_docstrings and py_files:
            if verbose and not json_output and not compact:
                click.echo(f"\nChecking {len(py_files)} Python file(s) for docstrings...\n")

            results = run_harper(
                py_files,
                dialect=dialect,
                user_dict_path=dict_path,
                ignore_rules=ignore,
                only_rules=only,
            )
            all_results.extend(results)

        # Clean up temp dictionary file
        if dict_path:
            try:
                Path(dict_path).unlink()
            except Exception:
                pass

        # Aggregate results
        total_issues = sum(r.lint_count for r in all_results)
        files_with_issues = sum(1 for r in all_results if r.lint_count > 0)

        # Group by kind and rule
        by_kind = defaultdict(int)
        by_rule = defaultdict(int)
        all_lints = []

        for result in all_results:
            for lint in result.lints:
                by_kind[lint.kind] += 1
                by_rule[lint.rule] += 1
                all_lints.append(lint)

        # Output results
        if json_output:
            output = {
                "version": "1.0.0",
                "harper_version": harper_info.split()[-1] if harper_info else "unknown",
                "dialect": dialect,
                "files_checked": len(files_to_check),
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
                    if result.lint_count > 0:
                        click.echo(f"\n📄 {result.file} ({result.lint_count} issue(s))")
                        for lint in result.lints:
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
    except Exception as e:
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
def seo(project_path: str | None, fix: bool, json_output: bool) -> None:
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
    import json
    import xml.etree.ElementTree as ET

    try:
        docs = GreatDocs(project_path=project_path)
        site_dir = docs.project_path / "_site"

        if not site_dir.exists():
            click.echo("Error: Site not built. Run 'great-docs build' first.", err=True)
            sys.exit(1)

        issues = []
        warnings = []
        info = []

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
                docs._generate_sitemap_xml()
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
                docs._generate_robots_txt()
                info.append("   → Generated robots.txt")

        # ── Check HTML pages ─────────────────────────────────────────────
        html_files = list(site_dir.rglob("*.html"))
        pages_checked = 0
        pages_missing_canonical = 0
        pages_missing_description = 0
        pages_missing_title_template = 0
        pages_with_json_ld = 0
        images_missing_alt = 0

        canonical_base = docs._get_canonical_base_url()

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

            # Check title template (should have | or -)
            title_match = re.search(r"<title>([^<]+)</title>", content)
            if title_match:
                title = title_match.group(1)
                if " | " not in title and " - " not in title:
                    pages_missing_title_template += 1

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

        if pages_missing_title_template > 0:
            warnings.append(
                f"⚠️  {pages_missing_title_template} pages have plain titles "
                "(consider adding site name)"
            )

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

    except Exception as e:
        if json_output:
            click.echo(json.dumps({"status": "error", "error": str(e)}))
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)


cli.add_command(seo)


def main() -> None:
    """Main CLI entry point for great-docs."""
    cli()


if __name__ == "__main__":
    main()
