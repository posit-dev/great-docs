"""
Write `gd-webmcp.json`, the manifest that the site's WebMCP tools read

The manifest describes what was published: its pages come from the rendered
`search.json`, its API from the rendered `objects.inv`, and the authored pages'
facts and the sidebars describe them. It holds no page text, so it stays small
enough to fetch on a tool's first call.

A versioned site has one manifest in each version's root: the site root for the
latest version and `v/<version>/` for each other version that was rendered. All
paths in a manifest are relative to its directory.
"""

from __future__ import annotations

import json
import re
import zlib
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, cast

from ... import __version__
from ..._interlinks.index import AliasClaims, resolve_aliases, root_modules
from ..._interlinks.sphinx_inventory import INVENTORY_FILENAME, InventoryEntry, decode
from ..._versions.model import get_latest_version, parse_versions_config, version_url_segment
from ..._yaml import YamlMapping
from .. import quarto_yml
from . import webmcp_pages

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from pathlib import Path

    from ..._project.layout import Layout
    from ...config import Config
    from .webmcp_pages import SectionFacts

__all__ = ["MANIFEST_FILE", "Root", "SiteInfo", "build", "roots", "write"]

MANIFEST_FILE = "gd-webmcp.json"
"""The manifest's name in each version root"""

_SCHEMA = 1

_DESCRIPTION_CHARS = 300
_SUMMARY_CHARS = 200
_CHANGELOG_VERSIONS = 100

# The files an agent may want besides the pages, by manifest key
_RESOURCES = {
    "llms_txt": "llms.txt",
    "llms_full_txt": "llms-full.txt",
    "skills": ".well-known/agent-skills/index.json",
    "mcp": ".well-known/mcp.json",
    "search": "search.json",
    "changelog": "changelog.md",
}

# Body classes that mark generated reference pages, most specific first
_KIND_CLASSES = (
    ("doc-cli-api-page", "cli"),
    ("doc-mcp-api-page", "mcp"),
    ("doc-api-page", "api"),
    ("doc-reference", "reference"),
)

_REFERENCE = "reference"

_INPUT_SUFFIXES = (".qmd", ".md", ".ipynb", ".rmd")

_CHANGELOG_HEADING = re.compile(r"^##[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)


@dataclass(frozen=True)
class SiteInfo:
    """What the manifest says about the package and its site"""

    name: str | None
    """The package's distribution name"""

    title: str
    """The site name shown in page titles"""

    description: str | None
    """The site's default description"""

    version: str | None
    """The documented version of an unversioned site"""

    repo: str | None
    """The source repository's address"""

    license: str | None
    """The package's license"""

    install: tuple[str, ...]
    """The commands that install the package"""


@dataclass(frozen=True)
class Root:
    """A directory that receives a manifest"""

    site_dir: Path
    """The rendered site of one version"""

    project_dir: Path
    """The Quarto project directory that rendered it"""

    version: str | None
    """The version it documents, or `None` for an unversioned site"""

    url: str | None
    """Its address with a trailing slash, or `None` when unknown"""


def roots(config: Config, layout: Layout, base_url: str | None) -> list[Root]:
    """
    List the directories that receive a manifest

    Parameters
    ----------
    config
        The project's configuration, including its `versions`.
    layout
        The project's directories.
    base_url
        The site's address with a trailing slash, or `None` when unknown.

    Returns
    -------
    :
        The site root, then on a versioned site each other version root holding an
        `index.html`, in the configured order.
    """
    if not config.has_versions:
        return [Root(layout.site_dir, layout.build_dir, None, base_url)]
    entries = parse_versions_config(config.versions)
    latest = get_latest_version(entries) or entries[0]
    found: list[Root] = []
    for entry in sorted(entries, key=lambda entry: entry.tag != latest.tag):
        version = entry.version or version_url_segment(entry.tag)
        if entry.tag == latest.tag:
            site_dir, url = layout.site_dir, base_url
        else:
            segment = version_url_segment(entry.tag)
            site_dir = layout.site_dir / "v" / segment
            url = f"{base_url}v/{segment}/" if base_url else None
        if (site_dir / "index.html").is_file():
            project_dir = layout.build_dir_for(entry.tag, latest.tag)
            found.append(Root(site_dir, project_dir, version, url))
    return found


def write(targets: Iterable[Root], site: SiteInfo, *, warn: Callable[[str], None]) -> list[Path]:
    """
    Write a manifest to each root

    Parameters
    ----------
    targets
        The directories that receive a manifest.
    site
        What the manifests say about the package and its site.
    warn
        A callback that receives a warning about missing or unreadable files.

    Returns
    -------
    :
        The manifests written.
    """
    written: list[Path] = []
    for root in targets:
        manifest = build(root, site, warn=warn)
        text = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        path = root.site_dir / MANIFEST_FILE
        _ = path.write_text(text + "\n", encoding="utf-8")
        written.append(path)
    return written


def build(root: Root, site: SiteInfo, *, warn: Callable[[str], None]) -> dict[str, Any]:
    """
    Describe one version root

    Parameters
    ----------
    root
        The directory to describe.
    site
        What the manifest says about the package and its site.
    warn
        A callback that receives a warning about missing or unreadable files.

    Returns
    -------
    :
        The manifest. Optional fields of each entry are left out when empty.
    """
    site_dir = root.site_dir
    facts = webmcp_pages.read(root.project_dir)
    page_facts = {page.path: page for page in facts.pages} if facts else {}
    section_facts = list(facts.sections) if facts else []
    sidebar = _sidebar_positions(root.project_dir)
    heads = _Heads(site_dir, site.description)

    found = _search_pages(site_dir)
    if found is None:
        warn(f"No readable search.json in {site_dir}; the WebMCP manifest lists no pages")
        found = []

    kinds = {section.id: section.kind for section in section_facts}
    pages: list[dict[str, Any]] = []
    for path, title in found:
        fact = page_facts.get(path)
        if fact is not None and (fact.draft or not fact.listed):
            continue
        section = fact.section if fact is not None and fact.section else ""
        if not section and path.startswith(f"{_REFERENCE}/"):
            section = _REFERENCE
        description = fact.description if fact is not None else None
        position = sidebar.get(path)
        pages.append(
            _entry(
                path=path,
                md=_markdown(site_dir, path),
                title=title or (fact.title if fact is not None else None) or path,
                section=section,
                group=position[1] if position else None,
                description=_cap(description, _DESCRIPTION_CHARS) or heads.description(path),
                kind=_kind(path, heads.classes(path), section, kinds.get(section)),
                tags=list(fact.tags) if fact is not None else [],
                status=fact.status if fact is not None else None,
                date=fact.date if fact is not None else None,
            )
        )

    sections = _sections(section_facts, pages)
    order = {section["id"]: rank for rank, section in enumerate(sections, start=1)}
    pages.sort(key=lambda page: _page_order(page, order, sidebar))

    manifest: dict[str, Any] = {
        "schema": _SCHEMA,
        "generator": f"great-docs {__version__}",
        "site": _entry(
            name=site.name,
            title=site.title,
            description=site.description,
            version=root.version or site.version,
            url=root.url,
            repo=site.repo,
            license=site.license,
            install=list(site.install),
        ),
        "resources": {key: path for key, path in _RESOURCES.items() if (site_dir / path).is_file()},
        "sections": sections,
        "pages": pages,
        "api": _api(site_dir, sidebar, heads, warn),
        "cli": [
            _entry(command=page["title"], path=page["path"], md=page.get("md"))
            for page in pages
            if page["kind"] == "cli"
        ],
    }
    if (changelog := _changelog(site_dir)) is not None:
        manifest["changelog"] = changelog
    return manifest


def _entry(**fields: Any) -> dict[str, Any]:
    """Keep the fields that have a value"""
    return {key: value for key, value in fields.items() if value not in (None, "", [], {})}


def _cap(text: str | None, limit: int) -> str | None:
    """Collapse whitespace and shorten text to at most `limit` characters"""
    if text is None:
        return None
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text or None


def _markdown(site_dir: Path, path: str) -> str | None:
    """Find the Markdown copy published beside a page"""
    md = PurePosixPath(path).with_suffix(".md").as_posix()
    return md if (site_dir / md).is_file() else None


def _search_pages(site_dir: Path) -> list[tuple[str, str | None]] | None:
    """
    Read the pages of the rendered `search.json`

    Parameters
    ----------
    site_dir
        The rendered site of one version.

    Returns
    -------
    :
        Each page's path and title, in the file's order and without duplicates, or `None`
        when the file is missing or not a list.
    """
    try:
        entries: object = json.loads((site_dir / "search.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(entries, list):
        return None
    titles: dict[str, str | None] = {}
    for entry in cast("list[object]", entries):
        href = _mapping(entry).string("href")
        path = _clean(href.partition("#")[0]) if href else ""
        if path and path not in titles:
            titles[path] = _mapping(entry).string("title") or None
    return list(titles.items())


def _items(value: object) -> list[object]:
    """Read a parsed list, or nothing when the value is not a list"""
    return cast("list[object]", value) if isinstance(value, list) else []


def _mapping(value: object) -> YamlMapping:
    """Read a parsed mapping, or an empty one when the value is not a mapping"""
    return YamlMapping(cast("dict[str, Any]", value)) if isinstance(value, dict) else YamlMapping()


def _clean(href: str) -> str:
    """Make a project path or link relative to the site root"""
    href = href.strip()
    while href.startswith("./"):
        href = href[2:]
    return href.lstrip("/")


def _sidebar_positions(project_dir: Path) -> dict[str, tuple[int, str | None]]:
    """
    Find each page's place in the sidebars

    Parameters
    ----------
    project_dir
        The Quarto project directory that rendered the site.

    Returns
    -------
    :
        Each linked page's position across the sidebars and the innermost sidebar section
        holding it, from its first link. Empty when `_quarto.yml` can't be read.
    """
    try:
        quarto_config = quarto_yml.read(project_dir)
    except (OSError, ValueError):
        return {}
    sidebars = _mapping(quarto_config).mapping("website").entries("sidebar")
    positions: dict[str, tuple[int, str | None]] = {}
    for sidebar in sidebars:
        for href, group in _links(_mapping(sidebar).get("contents"), None):
            _ = positions.setdefault(href, (len(positions), group))
    return positions


def _links(contents: object, group: str | None) -> Iterator[tuple[str, str | None]]:
    """Yield each sidebar link's output page and the section around it, in order"""
    for item in _items(contents):
        fields = _mapping(item)
        href = item if isinstance(item, str) else fields.string("href")
        if href and "://" not in href:
            path = PurePosixPath(_clean(href))
            if path.suffix.lower() in _INPUT_SUFFIXES:
                path = path.with_suffix(".html")
            yield path.as_posix(), group
        if "contents" in fields:
            yield from _links(fields.get("contents"), fields.string("section") or group)


def _kind(path: str, classes: frozenset[str], section: str, section_kind: str | None) -> str:
    """
    Classify a page

    Parameters
    ----------
    path
        The page relative to the site root.
    classes
        Its `<body>` classes.
    section
        The `id` of its section, or an empty string.
    section_kind
        The kind of an authored section, or `None`.

    Returns
    -------
    :
        `api`, `cli` or `mcp` for an object page, `reference` for a reference index,
        `post` for a blog post, `guide` for another page in an authored section, else
        `page`.
    """
    for cls, kind in _KIND_CLASSES:
        if cls in classes:
            return kind
    if section_kind == "blog":
        return "page" if path == f"{section}/index.html" else "post"
    return "guide" if section_kind is not None else "page"


def _sections(
    section_facts: list[SectionFacts], pages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """List the sections that hold a listed page, in navigation order"""
    used = {page.get("section") for page in pages}
    sections = [
        {"id": section.id, "title": section.title, "kind": section.kind}
        for section in section_facts
        if section.id in used
    ]
    if _REFERENCE in used and all(section["id"] != _REFERENCE for section in sections):
        sections.append({"id": _REFERENCE, "title": "Reference", "kind": _REFERENCE})
    return sections


def _page_order(
    page: dict[str, Any], order: dict[str, int], sidebar: dict[str, tuple[int, str | None]]
) -> tuple[int, int, int, str]:
    """Sort pages outside a section first, the home page leading, then by sidebar order"""
    path = page["path"]
    position = sidebar.get(path)
    if path == "index.html":
        return (0, 0, -1, path)
    if position is None:
        return (order.get(page.get("section", ""), 0), 1, 0, path)
    return (order.get(page.get("section", ""), 0), 0, position[0], path)


class _HeadParser(HTMLParser):
    """Read a page's `<body>` classes and `<meta name="description">`"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.classes: frozenset[str] = frozenset()
        self.description: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "meta" and values.get("name") == "description" and self.description is None:
            self.description = values.get("content")
        elif tag == "body":
            self.classes = frozenset((values.get("class") or "").split())


class _Heads:
    """The rendered pages' body classes and descriptions, each page read once"""

    def __init__(self, site_dir: Path, site_description: str | None) -> None:
        self._site_dir = site_dir
        self._site_description = _cap(site_description, _DESCRIPTION_CHARS)
        self._read: dict[str, _HeadParser] = {}

    def _parse(self, path: str) -> _HeadParser:
        if (parser := self._read.get(path)) is None:
            parser = _HeadParser()
            try:
                text = (self._site_dir / path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            # Everything needed comes before the page's content.
            end = text.find("<main")
            parser.feed(text if end < 0 else text[:end])
            self._read[path] = parser
        return parser

    def classes(self, path: str) -> frozenset[str]:
        """The page's `<body>` classes"""
        return self._parse(path).classes

    def description(self, path: str, limit: int = _DESCRIPTION_CHARS) -> str | None:
        """The page's own description, leaving out the site's default"""
        text = _cap(self._parse(path).description, limit)
        if text is None or text == _cap(self._site_description, limit):
            return None
        return text


def _api(
    site_dir: Path,
    sidebar: dict[str, tuple[int, str | None]],
    heads: _Heads,
    warn: Callable[[str], None],
) -> list[dict[str, Any]]:
    """
    List the objects the rendered `objects.inv` documents

    Parameters
    ----------
    site_dir
        The rendered site of one version.
    sidebar
        Each page's sidebar position and section, which names an object's reference
        section.
    heads
        The rendered pages, whose descriptions are the objects' docstring summaries.
    warn
        A callback that receives a warning about an unreadable inventory.

    Returns
    -------
    :
        One entry per published name, in inventory order. Empty when the site has no
        inventory.
    """
    path = site_dir / INVENTORY_FILENAME
    if not path.is_file():
        return []
    try:
        inventory = decode(path.read_bytes())
    except (OSError, ValueError, zlib.error) as error:
        warn(f"Could not read {path} for the WebMCP manifest: {error}")
        return []
    entries = [entry for entry in inventory.entries if entry.domain == "py"]
    # A re-exported object is listed again under its canonical name; keep the public one.
    public = [entry for entry in entries if entry.dispname == entry.name]
    aliases = _aliases(public, entries, root_modules(inventory))
    # A page's description summarizes the object it documents, such as a class, and not the
    # methods documented with it.
    owners: dict[str, str] = {}
    for entry in public:
        page = _clean(entry.uri.partition("#")[0])
        if page not in owners or entry.name.count(".") < owners[page].count("."):
            owners[page] = entry.name
    found: list[dict[str, Any]] = []
    for entry in public:
        page = _clean(entry.uri.partition("#")[0])
        position = sidebar.get(page)
        owner = bool(page) and owners[page] == entry.name
        found.append(
            _entry(
                name=entry.name,
                kind=entry.role,
                section=position[1] if position else None,
                summary=heads.description(page, _SUMMARY_CHARS) if owner else None,
                path=page,
                md=_markdown(site_dir, page) if page else None,
                aliases=aliases.get(entry.name, []),
            )
        )
    return found


def _aliases(
    public: list[InventoryEntry], entries: list[InventoryEntry], modules: tuple[str, ...]
) -> dict[str, list[str]]:
    """
    Find the short names that refer to exactly one object

    Each object claims its name without the root module and its bare name; a method or
    attribute also claims its class-qualified name. A name claimed twice is dropped.

    Parameters
    ----------
    public
        The objects under their public names.
    entries
        Every entry, whose names are never taken as short names.
    modules
        The inventory's root modules.

    Returns
    -------
    :
        The sorted short names of each object, keyed by its full name.
    """
    claimed: list[tuple[str, str]] = []
    for entry in public:
        head, _, stem = entry.name.partition(".")
        if not stem or head not in modules:
            continue
        claimed.append((stem, entry.name))
        owner, _, bare = stem.rpartition(".")
        if not owner:
            continue
        claimed.append((bare, entry.name))
        owner_bare = owner.rpartition(".")[2]
        if owner_bare != owner and entry.role in ("method", "attribute", "property"):
            claimed.append((f"{owner_bare}.{bare}", entry.name))
    claims = AliasClaims(
        claimed=tuple(claimed), published=frozenset(entry.name for entry in entries)
    )
    found: dict[str, list[str]] = {}
    for alias, target in resolve_aliases(claims).kept.items():
        found.setdefault(target, []).append(alias)
    return {name: sorted(names) for name, names in found.items()}


def _changelog(site_dir: Path) -> dict[str, Any] | None:
    """
    Describe the rendered changelog page

    Parameters
    ----------
    site_dir
        The rendered site of one version.

    Returns
    -------
    :
        The page, its Markdown copy and the release headings found in it, or `None` when
        the site has no changelog page.
    """
    if not (site_dir / "changelog.html").is_file():
        return None
    md = _markdown(site_dir, "changelog.html")
    versions: list[str] = []
    if md is not None:
        try:
            text = (site_dir / md).read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        versions = [match.group(1) for match in _CHANGELOG_HEADING.finditer(text)]
    return _entry(path="changelog.html", md=md, versions=versions[:_CHANGELOG_VERSIONS])
