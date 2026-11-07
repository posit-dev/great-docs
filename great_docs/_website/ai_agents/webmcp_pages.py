"""
Prepare authored pages for the site's WebMCP tools

A page opts out with `webmcp: false` in its front matter. The page gains the
`gd-no-webmcp` body class, which tells `webmcp.js` to register no tools on it.
`webmcp: {listed: false}` keeps a page out of the WebMCP manifest instead.

The facts of each page and section, including these choices, are written to
`_gd_webmcp_pages.json` in the build directory for the manifest writer. The file
lists every page source in the build directory, so the manifest writer lists only
the pages a version rendered and uses the facts to describe them.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from typing import TYPE_CHECKING, Any

from ..._content.pages import section_destination
from ..._yaml import YamlMapping, add_body_class
from .. import page_scan
from ..page_metadata import Page

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from ..._layout import Layout
    from ...config import Config

__all__ = [
    "FACTS_FILE",
    "NO_WEBMCP_CLASS",
    "Facts",
    "PageFacts",
    "SectionFacts",
    "prepare",
    "read",
]

NO_WEBMCP_CLASS = "gd-no-webmcp"
"""The body class of a page that registers no WebMCP tools"""

FACTS_FILE = "_gd_webmcp_pages.json"
"""The file in the build directory that holds the authored pages' facts"""

_SCHEMA = 1


@dataclass(frozen=True)
class SectionFacts:
    """An authored section of the site"""

    id: str
    """The section's directory relative to the build directory, such as `user-guide`"""

    title: str
    """The section name shown in the navigation, or its `id` when it has none"""

    kind: str
    """`blog` for a blog section, else `guide`"""


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
    """The `id` of the section holding the page, or an empty string outside a section"""

    tags: tuple[str, ...]
    """The page's tags"""

    status: str | None
    """The page's status, such as `new`, or `None` when it has none"""

    date: str | None
    """The page's date as written, or `None` when it has none"""

    draft: bool
    """Whether the page is a draft"""

    webmcp: bool
    """Whether the page registers WebMCP tools"""

    listed: bool
    """Whether the WebMCP manifest lists the page"""


@dataclass(frozen=True)
class Facts:
    """The authored sections and pages of a build directory"""

    sections: tuple[SectionFacts, ...]
    """The sections, in navigation order"""

    pages: tuple[PageFacts, ...]
    """The pages, in path order"""


def _sections(config: Config, layout: Layout) -> list[tuple[Path, SectionFacts]]:
    """
    List the authored sections in the build directory

    Parameters
    ----------
    config
        The Great Docs configuration, including custom `sections`.
    layout
        The project's directories.

    Returns
    -------
    :
        Each section's resolved directory and facts, in navigation order.
    """
    blogs = {
        destination.resolve()
        for section in config.sections
        if section.get("type") == "blog"
        and (destination := section_destination(layout, section)) is not None
    }
    sections: list[tuple[Path, SectionFacts]] = []
    for directory in page_scan.content_dirs(config, layout, reference=False):
        resolved = directory.path.resolve()
        section_id = directory.path.relative_to(layout.build_dir).as_posix()
        kind = "blog" if resolved in blogs else "guide"
        sections.append((resolved, SectionFacts(section_id, directory.label or section_id, kind)))
    return sections


def _authored_pages(build_dir: Path) -> Iterator[Page]:
    """
    Read the authored pages in the build directory

    Parameters
    ----------
    build_dir
        The Quarto project directory.

    Returns
    -------
    :
        Each `.qmd` and `.md` page, in path order. Paths with a part starting with `_` or
        `.`, which Quarto does not render, and unreadable pages are skipped.
    """
    for path in sorted([*build_dir.rglob("*.qmd"), *build_dir.rglob("*.md")]):
        relative = path.relative_to(build_dir)
        if any(part.startswith(("_", ".")) for part in relative.parts):
            continue
        try:
            yield Page.make(path, build_dir)
        except (OSError, UnicodeDecodeError):
            continue


def _choices(front_matter: YamlMapping) -> tuple[bool, bool]:
    """
    Read a page's `webmcp` option

    Parameters
    ----------
    front_matter
        The page's front matter.

    Returns
    -------
    :
        Whether the page registers tools, which only `false` turns off, and whether the
        manifest lists it, which only a mapping with `listed: false` turns off.
    """
    value = front_matter.get("webmcp")
    listed = front_matter.mapping("webmcp").get("listed") is not False
    return value is not False, listed


def prepare(config: Config, layout: Layout) -> Facts:
    """
    Mark the pages that opt out of WebMCP and write the authored pages' facts

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
        The facts of each section and page.
    """
    build_dir = layout.build_dir
    sections = _sections(config, layout)
    pages: list[PageFacts] = []
    for page in _authored_pages(build_dir):
        front_matter = page.front_matter
        tools, listed = _choices(front_matter)
        if not tools:
            content = add_body_class(page.content, NO_WEBMCP_CLASS)
            if content != page.content:
                _ = page.path.write_text(content, encoding="utf-8")
        resolved = page.path.resolve()
        section = next((s.id for root, s in sections if resolved.is_relative_to(root)), "")
        pages.append(
            PageFacts(
                path=page.output_path,
                source=page.path.relative_to(build_dir).as_posix(),
                title=front_matter.string("title"),
                description=front_matter.string("description"),
                section=section,
                tags=tuple(front_matter.strings("tags")),
                status=front_matter.string("status"),
                date=front_matter.string("date"),
                draft=front_matter.get("draft") is True,
                webmcp=tools,
                listed=listed,
            )
        )
    facts = Facts(tuple(section for _, section in sections), tuple(pages))
    data = {
        "schema": _SCHEMA,
        "sections": [asdict(section) for section in facts.sections],
        "pages": [asdict(page) for page in facts.pages],
    }
    _ = (build_dir / FACTS_FILE).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return facts


def read(project_dir: Path) -> Facts | None:
    """
    Read the facts file of a Quarto project directory

    Parameters
    ----------
    project_dir
        The directory that rendered a version of the site.

    Returns
    -------
    :
        The facts, or `None` when the file is missing, unreadable or from another
        version of Great Docs.
    """
    try:
        data: Any = json.loads((project_dir / FACTS_FILE).read_text(encoding="utf-8"))
        if data.get("schema") != _SCHEMA:
            return None
        sections = tuple(SectionFacts(**section) for section in data["sections"])
        pages = tuple(
            replace(PageFacts(**page), tags=tuple(page["tags"])) for page in data["pages"]
        )
    except (OSError, ValueError, AttributeError, KeyError, TypeError):
        return None
    return Facts(sections, pages)
