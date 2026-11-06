"""
Prepare authored pages for the site's WebMCP tools

A page opts out with `webmcp: false` in its front matter. The page gains the
`gd-no-webmcp` body class, which tells `webmcp.js` to register no tools on it.
Each page's facts, including whether it opted out, are written to
`_gd_webmcp_pages.json` in the build directory for later build steps. The file
lists every page source in the build directory, so a step that needs only the
rendered pages must also apply the site's render exclusions.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from ..._yaml import add_body_class
from .. import page_scan
from ..page_metadata import Page

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from ..._layout import Layout
    from ...config import Config

__all__ = ["FACTS_FILE", "NO_WEBMCP_CLASS", "PageFacts", "prepare"]

NO_WEBMCP_CLASS = "gd-no-webmcp"
"""The body class of a page that registers no WebMCP tools"""

FACTS_FILE = "_gd_webmcp_pages.json"
"""The file in the build directory that holds the authored pages' facts"""


@dataclass(frozen=True)
class PageFacts:
    """What the WebMCP tools need to know about an authored page"""

    path: str
    """The rendered page relative to the site root, such as `user-guide/intro.html`"""

    source: str
    """The page's source relative to the build directory, such as `user-guide/intro.qmd`"""

    title: str | None
    """The page's title, or `None` when its front matter sets none"""

    description: str | None
    """The page's description, or `None` when its front matter sets none"""

    section: str
    """The section name shown beside the page, or an empty string outside a section"""

    draft: bool
    """Whether the page is a draft"""

    webmcp: bool
    """Whether the page registers WebMCP tools"""


def _authored_pages(config: Config, layout: Layout) -> Iterator[tuple[Page, str]]:
    """
    Read the authored pages in the build directory

    Parameters
    ----------
    config
        The Great Docs configuration, including custom `sections`.
    layout
        The project's directories.

    Returns
    -------
    :
        Each `.qmd` and `.md` page with its section name, in path order. Paths with a part
        starting with `_` or `.`, which Quarto does not render, and unreadable pages are
        skipped.
    """
    build_dir = layout.build_dir
    sections = [
        (directory.path.resolve(), directory.label)
        for directory in page_scan.content_dirs(config, layout, reference=False)
    ]
    for path in sorted([*build_dir.rglob("*.qmd"), *build_dir.rglob("*.md")]):
        relative = path.relative_to(build_dir)
        if any(part.startswith(("_", ".")) for part in relative.parts):
            continue
        try:
            page = Page.make(path, build_dir)
        except (OSError, UnicodeDecodeError):
            continue
        resolved = path.resolve()
        section = next((label for root, label in sections if resolved.is_relative_to(root)), "")
        yield page, section


def prepare(config: Config, layout: Layout) -> list[PageFacts]:
    """
    Mark the pages that opt out of WebMCP and write every authored page's facts

    Parameters
    ----------
    config
        The Great Docs configuration.
    layout
        The project's directories, whose build directory holds the pages and receives the
        facts file.

    Returns
    -------
    :
        The facts of each page, in path order.
    """
    facts: list[PageFacts] = []
    for page, section in _authored_pages(config, layout):
        front_matter = page.front_matter
        enabled = front_matter.get("webmcp") is not False
        if not enabled:
            content = add_body_class(page.content, NO_WEBMCP_CLASS)
            if content != page.content:
                _ = page.path.write_text(content, encoding="utf-8")
        facts.append(
            PageFacts(
                path=page.output_path,
                source=page.path.relative_to(layout.build_dir).as_posix(),
                title=front_matter.string("title"),
                description=front_matter.string("description"),
                section=section,
                draft=front_matter.get("draft") is True,
                webmcp=enabled,
            )
        )
    _write(layout.build_dir, facts)
    return facts


def _write(build_dir: Path, facts: list[PageFacts]) -> None:
    """
    Write the facts file

    Parameters
    ----------
    build_dir
        The Quarto project directory.
    facts
        The facts of each page.

    Returns
    -------
    :
    """
    data = {"schema": 1, "pages": [asdict(page) for page in facts]}
    _ = (build_dir / FACTS_FILE).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
