"""
Page render times published with the site

`build-timings.json` records how long Quarto took to render each page and whether the page had
cached results in a freeze cache. The next parallel build reads Quarto's start-up time from it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from .._layout import Layout

__all__ = ["write"]


def write(
    layout: Layout,
    page_timings: Sequence[Mapping[str, Any]] | None = None,
    timings_by_version: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    render: Mapping[str, object] | None = None,
) -> Path | None:
    """
    Write `build-timings.json` to the site

    Each page entry retains `page` and `seconds` and gains `frozen`, which is true when the
    page has results in the persisted freeze cache or the Quarto project's cache. Pages are
    listed slowest first.

    Parameters
    ----------
    layout
        The project's layout, which locates the site and both freeze caches.
    page_timings
        The render time of each page of a single-version site.
    timings_by_version
        The render time of each page, by version tag. When given, `page_timings` and `render`
        are ignored.
    render
        The process count, group count and Quarto start-up time for a parallel render of a
        single-version site.

    Returns
    -------
    :
        The path written, or `None` when the site does not exist or there are no timings.
    """
    if not layout.site_dir.exists():
        return None

    frozen = _frozen_pages(layout)
    payload: dict[str, object] = {
        "build_time": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if timings_by_version:
        seconds = {tag: _total(timings) for tag, timings in timings_by_version.items()}
        payload["total_seconds"] = round(sum(seconds.values()), 3)
        payload["versions"] = {
            tag: {"seconds": seconds[tag], "pages": _slowest_first(timings, frozen)}
            for tag, timings in timings_by_version.items()
        }
    elif page_timings:
        payload["total_seconds"] = _total(page_timings)
        payload["pages"] = _slowest_first(page_timings, frozen)
        if render:
            payload["render"] = render
    else:
        return None

    path = layout.site_dir / "build-timings.json"
    _ = path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def _frozen_pages(layout: Layout) -> set[str]:
    """
    Find the pages with cached results in either freeze cache

    Parameters
    ----------
    layout
        The project's layout, which locates the persisted cache and the Quarto project's cache.

    Returns
    -------
    :
        The cached pages as source paths without their extension, such as `user-guide/intro`.
    """
    pages: set[str] = set()
    for cache in (layout.freeze_dir, layout.build_dir / "_freeze"):
        if cache.is_dir():
            # A page's results sit at `<page>/execute-results/html.json` in the cache
            pages.update(
                str(results.relative_to(cache).parent.parent)
                for results in cache.rglob("execute-results/html.json")
            )
    return pages


def _slowest_first(timings: Sequence[Mapping[str, Any]], frozen: set[str]) -> list[dict[str, Any]]:
    """
    List page timings from slowest to fastest and mark each page's freeze status

    Parameters
    ----------
    timings
        The render time of each page.
    frozen
        The cached pages, as source paths without their extension.

    Returns
    -------
    :
        A copy of each timing with `frozen` added.
    """
    marked = [
        {**timing, "frozen": str(timing["page"]).rsplit(".", 1)[0] in frozen} for timing in timings
    ]
    return sorted(marked, key=lambda timing: timing["seconds"], reverse=True)


def _total(timings: Sequence[Mapping[str, Any]]) -> float:
    """
    Add up page render times

    Parameters
    ----------
    timings
        The render time of each page.

    Returns
    -------
    :
        The total in seconds, rounded to milliseconds.
    """
    return round(sum(timing["seconds"] for timing in timings), 3)
