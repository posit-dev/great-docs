"""
Documentation build order and shared state

Builds produce a single-version or versioned site. Watch mode serves a prepared project
with `quarto preview` and repeats preparation after source edits. Rendering and freezing
use the same preparation steps, except that freezing skips remote content publication.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from importlib import metadata
from importlib import util as import_util
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._content import user_guide as user_guide_pages
from .._contribution import Contribution
from .._project import Project
from .._reference.exports import Exports
from .._subprocess import TEXT_MODE_KWARGS
from .._website import page_dates
from .._website.navigation import shared_sidebar
from ..config import Config
from . import (
    content,
    finish,
    freeze,
    generated,
    outputs,
    parallel_render,
    passes,
    prepare,
    quarto,
    reference,
    render,
    site,
    watch,
)
from .log import BuildLog, estimate_build_time
from .steps import USER_CODE_ERRORS, BuildError, Outcome, Step, Warn, count_listed, run_steps

if TYPE_CHECKING:
    from .._apiref.api_reference import APIReference
    from .._content.user_guide import UserGuide
    from .._layout import Layout
    from .._remote import Remote
    from .._website.identity import Identity

__all__ = ["Run", "prepare_for_freeze", "preparation_steps", "run"]


@dataclass
class Run:
    """
    Values read by several steps of one documentation build

    Each build starts from a new `Run` with no results from earlier builds.

    Attributes
    ----------
    project
        The documented project, read from its files when the build starts.
    identity
        The site's name and addresses, resolved from configuration and project metadata
        when the build starts.
    exports
        The package models and exports shared by this build, loaded on demand.
    watch
        Whether the site is served in watch mode.
    page_authors
        The configured page authors, with local portrait paths replaced by site URLs.
    has_api_reference
        Whether the site has an API reference. Preparing the build directory sets it to
        `False` when the reference is disabled, the project is not a Python project, no
        package name is detected, or the package has nothing to document.
    quarto_config
        The site's Quarto configuration, initially empty and updated in memory during
        preparation. Preparation writes the finished configuration to `_quarto.yml`
        unless rendering versions separately. Each version then writes its own
        configuration.
    api_block
        The `api-reference` block of `quarto_config`, or `None` for a site without an API
        reference.
    user_guide
        The user guide discovered during build preparation, or `None` when no guide
        pages were found.
    contributions
        The navigation, resources, render exclusions and script data recorded for the
        Quarto configuration, in preparation step order.
    """

    project: Project
    identity: Identity
    exports: Exports
    watch: bool
    page_authors: list[dict[str, Any]]
    has_api_reference: bool = True
    quarto_config: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())
    api_block: dict[str, Any] | None = None
    user_guide: UserGuide | None = None
    contributions: list[Contribution] = field(default_factory=lambda: list[Contribution]())

    @classmethod
    def make(cls, config: Config, layout: Layout, *, watch: bool) -> Run:
        """
        Create build state from the project's current files

        Parameters
        ----------
        config
            The project's configuration.
        layout
            The project's directories.
        watch
            Whether the site is served in watch mode.

        Returns
        -------
        :
            The initial build state with the project's name, metadata, GitHub repository,
            site identity and page authors.
        """
        project = Project.make(config, layout)
        identity = site.identity(config, layout, project)
        return cls(
            project=project,
            identity=identity,
            exports=Exports(config, project),
            watch=watch,
            page_authors=page_dates.site_authors(config, layout.source_dir, identity.base_url),
        )


def run(
    config: Config,
    layout: Layout,
    *,
    remote: Remote,
    watch: bool = False,
    refresh: bool = True,
    version_tags: list[str] | None = None,
    latest_only: bool = False,
    jobs: int | str | None = None,
) -> None:
    """
    Build the documentation site or serve it with `quarto preview`

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    remote
        The source of GitHub and PyPI data.
    watch
        Whether to serve the prepared project with `quarto preview` and repeat preparation
        after source edits. Watch mode skips the full render and the steps that follow it.
    refresh
        Whether to rediscover the package's exports for the API reference.
    version_tags
        The versions of a versioned site to render, or `None` for all of them.
    latest_only
        Whether to render only the latest version of a versioned site.
    jobs
        The number of Quarto processes that render a single-version site, `"auto"`, or
        `None` to read the `GREAT_DOCS_RENDER_JOBS` environment variable.

    Raises
    ------
    FileNotFoundError
        If the project has no `great-docs.yml`.
    BuildError
        If Quarto is missing or too old, or a build step reports a failure. The failure
        has already been reported.
    """
    outputs.validate(config, layout)
    if not layout.config_path.exists():
        raise FileNotFoundError(
            "great-docs.yml not found. Run 'great-docs init' first to "
            "generate a configuration file."
        )
    try:
        quarto.ensure_installed()
    except BuildError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise

    # Reject invalid process counts before preparation. Preserve the previous build's
    # timings before preparation clears them; they guide how pages are split.
    render_jobs = parallel_render.resolve_jobs(jobs)
    last_timings: dict[str, float] = {}
    last_startup: float | None = None
    if render_jobs > 1:
        timing_files = (
            layout.site_dir / "build-timings.json",
            layout.build_dir / "_site" / "build-timings.json",
        )
        last_timings = parallel_render.read_timings(*timing_files)
        last_startup = parallel_render.read_startup(*timing_files)

    # Share project facts within this build; reread packaging files for each new build.
    current = Run.make(config, layout, watch=watch)
    log = _make_log(current, config, layout)

    # The finishing steps need timings collected during rendering.
    render_timings: dict[str, Any] = {}

    def render_site() -> Outcome:
        result, render_timings["render"] = render.site(
            config, layout, current.quarto_config, log, render_jobs, last_timings, last_startup
        )
        render_timings["page_timings"] = result.page_timings
        return "Site rendered"

    def render_versions() -> Outcome:
        outcome, result = render.versions(
            current,
            config,
            layout,
            log,
            version_tags,
            latest_only,
            default_description=site.default_description(config, current.project),
            structured_data=site.structured_data(current, config),
        )
        render_timings["timings_by_version"] = result.get("timings_by_version")
        return outcome

    # Each version writes its own configuration; preparation only needs the mapping in memory.
    versioned_render = config.has_versions and not watch
    preparation = preparation_steps(
        current,
        config,
        layout,
        log,
        remote=remote,
        refresh=refresh,
        write_quarto_config=not versioned_render,
    )
    if watch:
        render_step = Step("Build site with Quarto", lambda: "Starting watch mode...")
    elif versioned_render:
        render_step = Step("Build site with Quarto", render_versions, user_code=True, quiet=False)
    else:
        render_step = Step("Build site with Quarto", render_site, quiet=False)
    # Watch mode uses a live preview, so the steps after a full render do not apply.
    finishing = [] if watch else _finishing_steps(current, config, layout, log, render_timings)
    steps = [*preparation, render_step, *finishing]
    log.total_steps = count_listed(steps)
    log.header()

    if watch:
        _watch(current, config, layout, log, steps, remote=remote, refresh=refresh)
        return

    run_steps(steps, log, layout.build_dir)
    site_path = layout.site_dir / "index.html"
    log.footer(site_path=str(site_path if site_path.exists() else layout.site_dir))
    finish.print_layout_notice(layout)


def prepare_for_freeze(config: Config, layout: Layout, log: BuildLog, *, remote: Remote) -> None:
    """
    Prepare the Quarto project for freezing, excluding remote content

    Quarto requires matching page sources to reuse frozen results. Use the build's
    preparation steps so freezing and rendering use matching sources.

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.
    log
        The build log that the steps write to.
    remote
        The source of GitHub and PyPI data.

    Raises
    ------
    BuildError
        If a step reports a failure. The log already contains the report.
    """
    current = Run.make(config, layout, watch=False)
    steps = preparation_steps(current, config, layout, log, remote=remote)
    freeze.prepare(steps, log, layout.build_dir)


def preparation_steps(
    run: Run,
    config: Config,
    layout: Layout,
    log: BuildLog,
    *,
    remote: Remote,
    refresh: bool = True,
    write_quarto_config: bool = True,
) -> list[Step]:
    """
    List the build's preparation steps in execution order

    These steps write the Quarto project before rendering. Step functions are resolved
    when each step runs, so replacements made after this list is created take effect.

    Parameters
    ----------
    run
        The current build.
    config
        The project's configuration.
    layout
        The project's directories.
    log
        The build log that the steps write to.
    remote
        The source of GitHub and PyPI data.
    refresh
        Whether to rediscover the package's exports for the API reference.
    write_quarto_config
        Whether the last step writes the finished Quarto configuration to `_quarto.yml`.
        If false, the build directory retains the initial configuration whose header
        marks it as generated.

    Returns
    -------
    :
        The steps in the order they run.
    """
    # Results shared between preparation steps
    ref: APIReference | None = None
    frozen_pages: list[str] = []

    def generate_api_reference() -> Outcome:
        nonlocal ref
        outcome, ref = reference.api(run, config, layout, log)
        return outcome

    def prepare_freeze_cache() -> Outcome:
        outcome, frozen_pages[:] = passes.freeze_cache(
            run,
            config,
            layout,
            default_description=site.default_description(config, run.project),
            structured_data=site.structured_data(run, config),
        )
        return outcome

    def list_frozen_pages() -> Outcome:
        for page in frozen_pages:
            log.detail(f"  - {page}")
        return None

    steps = [
        Step(
            "Prepare build directory",
            lambda: prepare.build_directory(
                run, config, layout, remote=remote, page_authors=run.page_authors
            ),
        ),
        Step(
            "Show render settings",
            lambda: render.show_settings(config, log),
            quiet=False,
            listed=False,
        ),
        Step(
            "Configure API reference",
            lambda: reference.api_config(run, refresh=refresh),
            user_code=True,
        ),
        Step(
            "Generate llms.txt / llms-full.txt",
            lambda: generated.llms_txt(run, config, layout),
            warn=Warn(
                USER_CODE_ERRORS, "Error generating llms.txt", "llms.txt generation had issues"
            ),
            user_code=True,
        ),
        Step(
            "Generate SKILL.md",
            lambda: generated.skills(run, config, layout),
            warn=Warn(
                USER_CODE_ERRORS, "Error generating SKILL.md", "SKILL.md generation had issues"
            ),
            user_code=True,
        ),
        Step(
            "Check the site URL",
            lambda: generated.check_site_url(run, config, log),
            user_code=True,
            quiet=False,
            listed=False,
        ),
        Step(
            "Generate changelog",
            lambda: generated.changelog(run, config, layout, remote=remote),
            remote_content=True,
        ),
        Step(
            "Generate CLI reference",
            lambda: reference.cli(run, config, layout),
            warn=Warn(USER_CODE_ERRORS, "Error generating CLI docs", "CLI generation had issues"),
            user_code=True,
        ),
        Step(
            "Generate Go CLI reference",
            lambda: reference.go_cli(run, config, layout),
            warn=Warn((OSError,), "Error generating Go CLI docs", "Go CLI generation had issues"),
            user_code=True,
        ),
        Step(
            "Generate Rust CLI reference",
            lambda: reference.rust_cli(run, config, layout),
            warn=Warn(
                (OSError,), "Error generating Rust CLI docs", "Rust CLI generation had issues"
            ),
            user_code=True,
        ),
        Step(
            "Generate MCP server reference",
            lambda: reference.mcp(run, config, layout),
            warn=Warn(USER_CODE_ERRORS, "Error generating MCP docs", "MCP generation had issues"),
            user_code=True,
        ),
        Step(
            "Process User Guide",
            lambda: content.user_guide(
                run, config, layout, page_authors=run.page_authors, remote=remote
            ),
            fails_on=(ValueError,),
            user_code=True,
        ),
        Step(
            "Process custom sections",
            lambda: content.sections(run, config, layout, page_authors=run.page_authors),
            fails_on=(ValueError,),
        ),
        Step(
            "Process custom pages",
            lambda: content.custom_pages(
                run,
                config,
                layout,
                page_authors=run.page_authors,
                identity=run.identity,
                structured_data=site.structured_data(run, config),
                default_description=site.default_description(config, run.project),
            ),
            fails_on=(ValueError,),
        ),
        Step("Process page tags", lambda: generated.tags(run, config, layout)),
        Step(
            "Process page status badges",
            lambda: generated.page_statuses(run, config, layout),
        ),
        Step(
            "Copy assets",
            lambda: content.assets(run, config, layout, remote=remote),
            fails_on=(ValueError, FileNotFoundError),
        ),
        Step("Generate API reference", generate_api_reference, user_code=True),
        Step(
            "Build interlinks index",
            lambda: reference.interlinks(run, config, layout, log, api_reference=ref),
            quiet=False,
        ),
        Step("Prepare freeze cache", prepare_freeze_cache, quiet=False),
        Step("List frozen pages", list_frozen_pages, quiet=False, listed=False),
        Step(
            "Expand mock-code cells",
            lambda: passes.mock_cells(layout, log),
            quiet=False,
            listed=False,
        ),
        Step(
            "Render d2 diagrams",
            lambda: passes.d2_diagrams(layout, log),
            user_code=True,
            quiet=False,
            listed=False,
        ),
        Step(
            "Pre-render terminal recordings",
            lambda: passes.terminal_recordings(run, config, layout, log),
            quiet=False,
            listed=False,
        ),
        Step(
            "Share sidebars",
            lambda: passes.shared_sidebars(run, config, layout, log),
            quiet=False,
            listed=False,
        ),
    ]
    if write_quarto_config:
        steps.append(
            Step(
                "Write the site configuration",
                lambda: site.write_quarto_config(run, layout),
                listed=False,
            )
        )
    return steps


def _finishing_steps(
    run: Run,
    config: Config,
    layout: Layout,
    log: BuildLog,
    render_timings: dict[str, Any],
) -> list[Step]:
    """
    List the steps that follow rendering, in execution order

    Parameters
    ----------
    run
        The current build.
    config
        The project's configuration.
    layout
        The project's directories.
    log
        The build log that the steps write to.
    render_timings
        The timing results collected during rendering.

    Returns
    -------
    :
        The steps in the order they run.
    """
    steps: list[Step] = []
    if not config.has_versions:
        steps.append(
            Step(
                "Assemble the site",
                lambda: render.assemble_site(layout),
                quiet=False,
                listed=False,
            )
        )
    steps += [
        Step(
            "Generate SEO files",
            lambda: finish.seo_files(config, layout, run.identity.base_url),
            warn=Warn((OSError,), "Error generating SEO files", "SEO files had issues"),
        ),
        Step(
            "Write build timings",
            lambda: finish.write_timings(layout, log, **render_timings),
            quiet=False,
            listed=False,
        ),
        Step(
            "Save the freeze cache",
            lambda: finish.save_freeze_cache(layout, log),
            quiet=False,
            listed=False,
        ),
    ]
    if config.has_versions:
        steps.append(
            Step(
                "Save an API snapshot",
                lambda: finish.save_api_snapshot(run, config, layout, log),
                user_code=True,
                quiet=False,
                listed=False,
            )
        )
    steps.append(
        Step(
            "Record site ownership",
            lambda: finish.record_site_ownership(layout),
            quiet=False,
            listed=False,
        )
    )
    return steps


def _watch(
    run: Run,
    config: Config,
    layout: Layout,
    log: BuildLog,
    steps: list[Step],
    *,
    remote: Remote,
    refresh: bool,
) -> None:
    """
    Prepare the Quarto project and preview it with rebuilds after source edits

    Each rebuild reloads `great-docs.yml` and repeats preparation while the preview runs.

    Parameters
    ----------
    run
        The initial build state populated by `steps`.
    config
        The project's configuration.
    layout
        The project's directories.
    log
        The build log, with its header already written.
    steps
        The steps that prepare the project, ending with the render step.
    remote
        The source of GitHub and PyPI data.
    refresh
        Whether each rebuild rediscovers the package's exports for the API reference.

    Raises
    ------
    BuildError
        If an initial preparation step fails. The log already contains the report.
    """
    run_steps(steps, log, layout.build_dir)
    log.footer(watch_mode=True)
    finish.print_layout_notice(layout)
    preview_env = quarto.environment(config)
    preview_env[shared_sidebar.PREVIEW_ENV] = "1"

    def rebuild(staging: watch.Staging) -> dict[str, Any]:
        edited = Config(
            config.project_root, config_path=config.config_path, cache_dir=config.cache_dir
        )
        current = Run.make(edited, staging, watch=True)
        rebuild_log = BuildLog()
        preparation = preparation_steps(
            current, edited, staging, rebuild_log, remote=remote, refresh=refresh
        )
        rebuild_log.total_steps = count_listed(preparation)
        run_steps(preparation, rebuild_log, staging.build_dir)
        return current.quarto_config

    watch.serve(layout, preview_env, rebuild, run.quarto_config)


def _make_log(run: Run, config: Config, layout: Layout) -> BuildLog:
    """
    Create a build log with package details and an estimated build time

    Parameters
    ----------
    run
        The current build.
    config
        The project's configuration.
    layout
        The project's directories.

    Returns
    -------
    :
        The build log, with package details omitted when no package is detected.
    """
    package_name = run.project.name or ""
    package_version = ""
    package_location = ""
    if package_name:
        package_version = _installed_version(package_name)
        package_location = _package_location(run.project, package_name, layout.package_root)
    return BuildLog(
        package_name=package_name,
        package_version=package_version,
        package_location=package_location,
        estimated_seconds=_estimated_seconds(config, layout),
    )


def _installed_version(package_name: str) -> str:
    """
    Read the installed version of a distribution

    Parameters
    ----------
    package_name
        The distribution's name.

    Returns
    -------
    :
        The version, or `""` when the distribution is not installed.
    """
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return ""


def _package_location(project: Project, package_name: str, package_root: Path) -> str:
    """
    Find the package directory or the remote URL of a temporary clone

    Parameters
    ----------
    project
        The documented project.
    package_name
        The package's distribution name.
    package_root
        The project directory in which to look up the Git remote URL.

    Returns
    -------
    :
        The package's directory, the repository's remote URL for a package in a temporary
        clone, or `""` when the package is not found.
    """
    location = ""
    # Prefer project source directories to match the package search order for introspection.
    module_name = package_name.replace("-", "_")
    for search_path in project.search_paths():
        candidate = Path(search_path) / module_name
        if candidate.is_dir() and (candidate / "__init__.py").exists():
            location = str(candidate)
            break
    if not location:
        try:
            spec = import_util.find_spec(module_name)
            if spec and spec.origin:
                location = str(Path(spec.origin).parent)
        except (ImportError, ValueError):
            # A missing parent or a module without `__spec__` prevents location lookup.
            pass
    # A repository URL identifies a temporary clone more clearly than its local path.
    if location:
        try:
            import tempfile

            git_remote = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=str(package_root),
                capture_output=True,
                **TEXT_MODE_KWARGS,
            )
            if git_remote.returncode == 0 and git_remote.stdout.strip():
                remote_url = git_remote.stdout.strip()
                tmp_prefixes = ("/tmp/", "/var/folders/", tempfile.gettempdir())
                if any(location.startswith(p) for p in tmp_prefixes):
                    location = remote_url
        except OSError:
            # Keep the local path if the Git process cannot start.
            pass
    return location


def _estimated_seconds(config: Config, layout: Layout) -> float:
    """
    Estimate the build time from page, API item and code cell counts

    Parameters
    ----------
    config
        The project's configuration.
    layout
        The project's directories.

    Returns
    -------
    :
        The estimated build time in seconds.
    """
    n_api_items = 0
    n_total_pages = 0
    n_code_cells = 0
    # The previous build's inventory is the best count available before
    # this build resolves the package.
    import zlib

    from .._interlinks.sphinx_inventory import INVENTORY_FILENAME, decode

    inventory_path = layout.build_dir / INVENTORY_FILENAME
    if inventory_path.exists():
        try:
            n_api_items = len(decode(inventory_path.read_bytes()).entries)
        except (OSError, ValueError, zlib.error):
            pass

    try:
        page_dirs: list[Path] = []

        # Leave directory warnings to build preparation.
        guide_dir = user_guide_pages.find_dir(config, layout, report=lambda _: None)
        if guide_dir and guide_dir.is_dir():
            page_dirs.append(guide_dir)

        for section in config.sections:
            section_dir_name = section.get("dir", "")
            if section_dir_name:
                section_dir = layout.package_root / section_dir_name
                if section_dir.is_dir():
                    page_dirs.append(section_dir)

        for page_dir in page_dirs:
            for pattern in ("*.qmd", "*.md"):
                for page in page_dir.rglob(pattern):
                    n_total_pages += 1
                    try:
                        text = page.read_text(encoding="utf-8", errors="ignore")
                        n_code_cells += text.count("```{python}")
                    except OSError:
                        pass

        # Approximate one reference page per API item.
        n_total_pages += n_api_items

        # Allow for the homepage, changelog and citation page.
        n_total_pages += 3

        # Allow ten pages for an enabled CLI reference.
        if config.cli_enabled:
            n_total_pages += 10
    except OSError:
        pass  # Keep the counts collected before the filesystem error.

    return estimate_build_time(
        n_api_items=n_api_items,
        n_total_pages=n_total_pages,
        n_code_cells=n_code_cells,
    )
