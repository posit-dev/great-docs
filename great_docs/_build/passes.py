"""
Build steps for page content, metadata and shared sidebars

Expand freeze shorthand and mock-code cells, write page metadata, render d2 diagrams and
terminal recordings, and share rendered reference sidebars before Quarto renders pages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .._term_player import prerender as term_prerender
from .._website import page_metadata, prerender, quarto_yml
from .._website.navigation import shared_sidebar
from .steps import Outcome, Skipped

if TYPE_CHECKING:
    from .._project.layout import Layout
    from .._website.seo.structured_data import StructuredData
    from ..config import Config
    from .log import BuildLog
    from .pipeline import Run

__all__ = ["d2_diagrams", "freeze_cache", "mock_cells", "shared_sidebars", "terminal_recordings"]


def freeze_cache(
    run: Run,
    config: Config,
    layout: Layout,
    *,
    default_description: str | None,
    structured_data: StructuredData | None,
) -> tuple[Outcome, list[str]]:
    """
    Expand freeze shorthand and write page metadata

    Parameters
    ----------
    run
        The build's watch status and Quarto configuration for page selection and metadata.
    config
        The project's configuration.
    layout
        The project's directories.
    default_description
        The search description for pages that have none of their own, or `None`.
    structured_data
        The package's JSON-LD description for the pages, or `None` when it is disabled.

    Returns
    -------
    :
        The result line or skip reason, and the pages whose freeze shorthand was expanded.
    """
    build_dir = layout.build_dir
    frozen_pages = prerender.expand_freeze_shorthand(build_dir)
    # Versioned builds write metadata after resolving each version's content. Watch mode
    # bypasses that pipeline, so it needs metadata here.
    if not config.has_versions or run.watch:
        _ = page_metadata.write_to_pages(
            build_dir, run.quarto_config, config, default_description, structured_data
        )
    if frozen_pages:
        return f"Using {len(frozen_pages)} page(s) from the freeze cache", frozen_pages
    if layout.freeze_dir.is_dir():
        return "Freeze cache will be restored during render", frozen_pages
    return Skipped("no frozen pages"), frozen_pages


def mock_cells(layout: Layout, log: BuildLog) -> Outcome:
    """
    Expand `source-code: mock` cells

    Parameters
    ----------
    layout
        The project's directories.
    log
        The build log.

    Returns
    -------
    :
        `None`; the result is a detail line of the previous step.
    """
    from .._website.mock_code import process_directory

    modified = process_directory(layout.build_dir)
    if modified:
        log.detail(f"Expanded {len(modified)} mock-code cell(s): " + ", ".join(modified))
    return None


def d2_diagrams(layout: Layout, log: BuildLog) -> Outcome:
    """
    Render d2 diagrams as light and dark SVG files, which Quarto cannot generate

    Parameters
    ----------
    layout
        The project's directories, including the cache of rendered diagrams.
    log
        The build log.

    Returns
    -------
    :
        `None`; the result is a detail line of the previous step.
    """
    from .._website.d2 import process_directory

    modified = process_directory(layout.build_dir, cache_dir=layout.cache_dir / "d2")
    if modified:
        log.detail(f"Rendered d2 diagrams in {len(modified)} page(s): " + ", ".join(modified))
    return None


def terminal_recordings(run: Run, config: Config, layout: Layout, log: BuildLog) -> None:
    """
    Render the source directory's `.termshow` recordings for the `termshow` shortcode

    Add the player's resources to the build's Quarto configuration.

    Parameters
    ----------
    run
        The build state holding the Quarto configuration.
    config
        The project's configuration.
    layout
        The project's directories.
    log
        The build log for recording failures and a summary of successful renders.

    Returns
    -------
    :
    """
    source_dir = layout.source_dir
    build_dir = layout.build_dir
    recordings = term_prerender.find_recordings(
        source_dir,
        layout.generated_dirs(),
        prune_non_doc=source_dir == layout.package_root,
    )
    done = term_prerender.render_recordings(recordings, source_dir, build_dir, report=log.warn)
    if done.count:
        log.detail(
            f"Pre-rendered {done.count} terminal recording(s) "
            f"({done.manifest_bytes / 1024:.0f} KB of player data)"
        )
        quarto_yml.apply(run.quarto_config, done.contribution, config)


def shared_sidebars(run: Run, config: Config, layout: Layout, log: BuildLog) -> Outcome:
    """
    Render each long reference sidebar once for reuse across pages

    Each version's directory has its own shared sidebars.

    Parameters
    ----------
    run
        The build's watch status and Quarto configuration, updated with shared sidebars.
    config
        The project's configuration.
    layout
        The project's directories.
    log
        The build log.

    Returns
    -------
    :
        `None`; the result is a detail line of the previous step.
    """
    if run.watch or not config.has_versions:
        shared = shared_sidebar.prepare(layout.build_dir, run.quarto_config)
        if shared:
            log.detail("Sharing rendered sidebar(s): " + ", ".join(shared))
    return None
