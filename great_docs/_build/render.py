"""
The build steps that render the site with Quarto

`site` renders a single-version site in one Quarto process or several, `versions` renders
each selected version of a versioned site and assembles them, and `assemble_site` copies a
single-version site to a site directory outside the build directory. Starting Quarto and its
environment belong to `quarto`, splitting pages among processes to `parallel_render`.
"""

from __future__ import annotations

import threading
from functools import cache
from typing import TYPE_CHECKING, Any

from .._reference import documented
from . import quarto
from .steps import Outcome, StepError

if TYPE_CHECKING:
    from .._layout import Layout
    from .._website.seo.structured_data import StructuredData
    from ..config import Config
    from . import parallel_render
    from .log import BuildLog
    from .pipeline import Run

__all__ = ["assemble_site", "site", "versions"]


def site(
    config: Config,
    layout: Layout,
    log: BuildLog,
    jobs: int,
    last_timings: dict[str, float],
    last_startup: float | None,
) -> tuple[quarto.RenderResult | parallel_render.RenderResult, dict[str, object] | None]:
    """
    Render a single-version site with Quarto and show its progress

    Retry a transient failure once in one process, including failures from parallel renders.

    Parameters
    ----------
    config
        The project's configuration, which sets Quarto's environment.
    layout
        The project's directories.
    log
        The build log.
    jobs
        The number of Quarto processes to split the pages among.
    last_timings
        The last build's render time of each page, which guides the split.
    last_startup
        How long Quarto took to start in the last parallel build, which also guides the
        split; `None` when unknown.

    Returns
    -------
    :
        The successful render result, and how the parallel render went: its number of
        processes and groups and how long Quarto took to start. The second is `None`
        unless a parallel render produced the result.

    Raises
    ------
    StepError
        If Quarto fails to render the site.
    """
    from . import parallel_render

    env = quarto.environment(config)
    result: quarto.RenderResult | parallel_render.RenderResult | None = None
    render_stats: dict[str, object] | None = None
    if jobs > 1:
        # Experimental: split the pages among several Quarto processes
        bar = log.progress("Rendering pages", 1)
        bar_lock = threading.Lock()
        pages_started = 0

        def on_start(pages: int, groups: int, workers: int) -> None:
            bar.total = max(pages, 1)
            log.detail(
                f"Rendering {pages} pages in {groups} groups with {workers} Quarto processes"
            )

        def on_page(_page: str) -> None:
            nonlocal pages_started
            with bar_lock:
                pages_started = min(pages_started + 1, bar.total)
                bar.update(pages_started)

        parallel = parallel_render.render(
            layout.build_dir,
            env,
            jobs,
            last_timings,
            on_start=on_start,
            on_page=on_page,
            overhead=last_startup,
        )
        bar.finish()
        if parallel.fallback:
            log.detail(f"Rendering in one process: {parallel.fallback}")
        else:
            for warning in parallel.warnings:
                log.warn(warning)
            render_stats = {"processes": parallel.workers, "groups": parallel.targets}
            if parallel.startup is not None:
                render_stats["startup_seconds"] = parallel.startup
            result = parallel

    if result is None:
        result = _render_in_one_process(layout, log, "Rendering pages", env)

    if result.returncode != 0 and quarto.is_transient_error(result.stderr):
        log.warn("Quarto hit a transient filesystem error — retrying render...")
        render_stats = None
        result = _render_in_one_process(layout, log, "Rendering pages (retry)", env)

    if result.returncode != 0:
        raise StepError("Quarto render failed", detail=result.stderr)
    return result, render_stats


def _render_in_one_process(
    layout: Layout, log: BuildLog, label: str, env: dict[str, str]
) -> quarto.RenderResult:
    """
    Render the site with Quarto in one process and show page progress

    Quarto's warnings appear when the bar reaches its last page; warnings reported later
    are dropped.

    Parameters
    ----------
    layout
        The project's directories.
    log
        The build log.
    label
        The progress bar's label.
    env
        The environment for Quarto.

    Returns
    -------
    :
        The render result, whether rendering succeeded or failed.
    """
    bar = log.progress(label, 1)
    warnings: list[str] = []
    finished = False

    def on_page(progress: quarto.Progress) -> None:
        nonlocal finished
        if finished:
            return
        if progress.total != bar.total:
            bar.total = progress.total
        bar.update(progress.current)
        if progress.current >= progress.total:
            finished = True
            bar.finish()
            for warning in warnings:
                log.warn(warning)

    def on_warning(warning: str) -> None:
        if not finished:
            warnings.append(warning)

    result = quarto.render(layout.build_dir, env, on_page=on_page, on_warning=on_warning)
    bar.finish()  # The final page may already have finished the bar
    return result


def versions(
    run: Run,
    config: Config,
    layout: Layout,
    log: BuildLog,
    version_tags: list[str] | None,
    latest_only: bool,
    *,
    default_description: str | None,
    structured_data: StructuredData | None,
) -> tuple[Outcome, dict[str, Any]]:
    """
    Render the selected versions of a versioned site and assemble them

    Parameters
    ----------
    run
        The current build.
    config
        The project's configuration, including its `versions`.
    layout
        The project's directories.
    log
        The build log.
    version_tags
        The versions to render, or `None` for every version.
    latest_only
        Whether to render only the latest version.
    default_description
        The description of pages that declare none.
    structured_data
        The site's structured data, or `None` for none.

    Returns
    -------
    :
        The result line and the outcome of the versioned build.

    Raises
    ------
    StepError
        If every version fails to render.
    """
    from .._versions.build import run_versioned_build
    from .._versions.model import get_latest_version, parse_versions_config

    entries = parse_versions_config(config.versions)
    if latest_only:
        latest = get_latest_version(entries)
        latest_tag = latest.tag if latest else entries[0].tag
        targets = [v for v in entries if v.tag == latest_tag]
    elif version_tags:
        targets = [v for v in entries if v.tag in set(version_tags)]
    else:
        targets = list(entries)

    n_versions = len(targets)
    log.detail(
        f"Multi-version build: {'1 version' if n_versions == 1 else f'{n_versions} version(s)'}"
    )

    bars = log.multi_progress([f"v{v.label}" for v in targets])

    def on_progress(slot: int, current: int, total: int) -> None:
        bars.set_total(slot, total)
        bars.update(slot, current)

    # Uncached tag snapshots use the working tree's documented set. Cache the
    # result so it is resolved at most once per project name per build.
    @cache
    def documented_symbols(package_name: str) -> list[str]:
        return documented.symbol_names(
            config,
            importable_name=run.project.module or package_name.replace("-", "_"),
            search_paths=run.project.search_paths(),
            create_sections=run.exports.sections,
        )

    result = run_versioned_build(
        source_dir=layout.build_dir,
        project_root=layout.package_root,
        versions_config=config.versions,
        quarto_env=quarto.environment(config),
        version_tags=version_tags,
        latest_only=latest_only,
        progress_callback=on_progress,
        on_renders_done=bars.finish,
        badge_expiry_raw=config["new_is_old"],
        config=config,
        layout=layout,
        default_description=default_description,
        structured_data=structured_data,
        documented_symbols=documented_symbols,
    )

    for warning in result.get("warnings", []):
        log.warn(warning)

    n_built = len(result["versions_built"])
    if result["success"]:
        return f"{n_built} version(s) rendered", result
    for error in result["errors"]:
        log.error_detail(error)
    if not n_built:
        raise StepError("All version builds failed")
    return f"{n_built} version(s) rendered ({len(result['errors'])} failed)", result


def assemble_site(layout: Layout) -> Outcome:
    """
    Copy the rendered site to a site directory outside the build directory

    Parameters
    ----------
    layout
        The project's directories. Nothing is copied when the site directory is the build
        directory's `_site`.

    Returns
    -------
    :
        `None`; the step has no result line.
    """
    if layout.site_dir != layout.build_dir / "_site":
        from .._versions.build import assemble_site as assemble_versions

        assemble_versions(layout.build_dir, [], "", layout.site_dir, layout=layout)
    return None
