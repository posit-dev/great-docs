from __future__ import annotations

import sys

import click

from . import __version__
from .core import GreatDocs


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
    default="3.11",
    help="Python version for CI (default: 3.11)",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing workflow file without prompting",
)
def setup_github_pages(
    project_path: str | None, main_branch: str, python_version: str, force: bool
) -> None:
    """Set up automatic deployment to GitHub Pages.

    This command creates a GitHub Actions workflow that automatically builds
    and deploys your documentation when you push to the main branch.

    \b
    The workflow will:
    • Build docs on every push and pull request
    • Deploy to GitHub Pages on main branch pushes
    • Use Quarto's official GitHub Action for reliable builds

    After running this command, commit the workflow file and enable GitHub
    Pages in your repository settings (Settings → Pages → Source: GitHub Actions).

    \b
    Examples:
      great-docs setup-github-pages                     # Use defaults
      great-docs setup-github-pages --main-branch dev   # Deploy from 'dev' branch
      great-docs setup-github-pages --python-version 3.12
      great-docs setup-github-pages --force             # Overwrite existing workflow
    """
    from pathlib import Path

    try:
        # Determine project root
        project_root = Path(project_path) if project_path else Path.cwd()

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
    """Check spelling in documentation files.

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


def main() -> None:
    """Main CLI entry point for great-docs."""
    cli()


if __name__ == "__main__":
    main()
