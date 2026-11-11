"""Documentation checking commands"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click

from .._build import site
from .._build.steps import PROJECT_ERRORS, USER_CODE_ERRORS
from .._project import Project
from .._project.layout import Layout
from ..core import GreatDocs
from . import options as _options


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
    from .._build.log import Colors, MultiProgressBar, ProgressBar
    from .._checks.examples import (
        check_examples as run_check,
    )
    from .._checks.examples import (
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

    from .._checks import inputs
    from .._checks import proofread as proofreading
    from .._checks.harper import HarperError, HarperNotFoundError, check_harper_available

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

    from .._website.seo import robots, sitemap

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
            from .._build.ownership import validate_site_dir

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

    from .._checks.lint import run_lint

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
                from .._layout_migration.notice import layout_notice
                from .._project.layout import Layout

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
