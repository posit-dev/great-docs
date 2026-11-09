"""
The tags index page and tag pill data for authored pages

Pages declare tags in their front matter. A tag with `/` separators nests under its
parents when tags are hierarchical; `\\/` is a literal slash. Shadow tags appear in
neither the index page nor the pills.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from yaml12 import format_yaml

from .._content.naming import title_from_name
from .._contribution import Contribution, InlineData, NavbarLink
from .._icons import get_icon_svg
from .._translations import translate
from . import page_scan
from .navigation import navbar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

    from .._project.layout import Layout
    from ..config import Config

__all__ = [
    "DATA_FILENAME",
    "INDEX_PAGE",
    "TagNode",
    "TaggedPage",
    "collect",
    "group",
    "hierarchy",
    "page_data",
    "render_index",
    "split_tag",
    "write",
]

INDEX_PAGE = "tags/index.qmd"
DATA_FILENAME = "_tags.json"

# Pandoc parses Markdown inside raw HTML, so plain labels need Markdown escaping too.
_MARKDOWN_PUNCTUATION = re.compile(r"([\\`*_\[\]$~^@])")

# Inline code spans delimited by matching runs of backticks.
_CODE_SPAN = re.compile(r"(?<!`)(?P<ticks>`+)(?!`).+?(?<!`)(?P=ticks)(?!`)")


@dataclass(frozen=True)
class TaggedPage:
    """An authored page whose front matter lists tags"""

    href: str
    """The page's source path relative to the build directory, such as `user-guide/intro.qmd`"""

    title: str
    """The page title, or a title made from the file name when the page has none"""

    section: str
    """The section name shown beside the page, empty for a section without a title"""

    tags: tuple[str, ...]
    """The tags the page shows, in front matter order, without shadow tags"""

    shadowed: bool
    """Whether the page lists a shadow tag"""

    location: str | None
    """Where the page shows its tag pills, `top` or `bottom`, when it overrides the default"""


@dataclass
class TagNode:
    """A tag in the hierarchy of the index page"""

    pages: list[TaggedPage] = field(default_factory=lambda: list[TaggedPage]())
    """The pages with exactly this tag"""

    children: dict[str, TagNode] = field(default_factory=lambda: dict[str, TagNode]())
    """The nested tags, by their last part"""


def collect(config: Config, layout: Layout) -> list[TaggedPage]:
    """
    Collect tagged user guide, recipe and custom section pages

    Index pages are excluded.

    Parameters
    ----------
    config
        The Great Docs configuration.
    layout
        The project's directories.

    Returns
    -------
    :
        The pages whose front matter has a non-empty `tags` list, in scan order.
    """
    shadow = set(config.tags_shadow)
    dirs = page_scan.content_dirs(config, layout, reference=False)
    pages: list[TaggedPage] = []
    for scanned in page_scan.scan(dirs, layout.build_dir, skip_index=True):
        front_matter = scanned.page.front_matter
        raw_tags = front_matter.sequence("tags")
        if not raw_tags:
            continue
        names = [name for tag in raw_tags if (name := str(tag).strip())]
        title = front_matter.string("title")
        location = front_matter.string("tag-location")
        pages.append(
            TaggedPage(
                href=scanned.href,
                title=title_from_name(scanned.page.path.stem) if title is None else title,
                section=scanned.section,
                tags=tuple(name for name in names if name not in shadow),
                shadowed=any(name in shadow for name in names),
                location=location if location in ("top", "bottom") else None,
            )
        )
    return pages


def group(pages: Iterable[TaggedPage]) -> dict[str, list[TaggedPage]]:
    """
    Group pages by the tags they show

    Parameters
    ----------
    pages
        The tagged pages.

    Returns
    -------
    :
        The pages for each tag. Tags follow their first occurrence in `pages`; each
        group preserves page order.
    """
    groups: dict[str, list[TaggedPage]] = {}
    for page in pages:
        for tag in page.tags:
            groups.setdefault(tag, []).append(page)
    return groups


def split_tag(tag: str) -> list[str]:
    r"""
    Split a tag into its hierarchy levels

    The tag splits at each `/` not preceded by a backslash, and `\/` becomes a literal `/`.
    Empty parts are dropped.

    Parameters
    ----------
    tag
        The tag as written in front matter.

    Returns
    -------
    :
        The levels, outermost first, without surrounding whitespace.
    """
    parts = (part.replace("\\/", "/").strip() for part in re.split(r"(?<!\\)/", tag))
    return [part for part in parts if part]


def hierarchy(groups: Mapping[str, Sequence[TaggedPage]], config: Config) -> TagNode:
    """
    Arrange the tags in a tree

    Parameters
    ----------
    groups
        The pages for each tag.
    config
        The Great Docs configuration. `tags.hierarchical` controls nesting.

    Returns
    -------
    :
        The root, whose children are the top-level tags. A node's pages follow the sorted
        order of the tags that lead to it.
    """
    root = TagNode()
    for tag, pages in sorted(groups.items(), key=lambda item: item[0]):
        parts = split_tag(tag) if config.tags_hierarchical else [tag.replace("\\/", "/")]
        node = root
        for part in parts:
            if part := part.strip():
                node = node.children.setdefault(part, TagNode())
        node.pages.extend(pages)
    return root


def render_index(groups: Mapping[str, Sequence[TaggedPage]], config: Config) -> str:
    """
    Render the tags index page

    Each tag has a pill heading followed by links to its pages. Hierarchical tags nest
    under their parents; flat tags are listed alphabetically. Each heading carries the
    id that the tag pills on pages link to.

    Parameters
    ----------
    groups
        The pages for each tag.
    config
        The Great Docs configuration.

    Returns
    -------
    :
        The page source, front matter included.
    """
    lang = config.lang
    front_matter = format_yaml(
        {
            "title": translate("site_tags", lang),
            "bread-crumbs": False,
            "toc": False,
            "body-classes": "gd-tags-index",
        }
    )
    lines = [
        "---",
        front_matter.rstrip(),
        "---",
        "",
        translate("tags_intro", lang),
        "",
    ]
    ids = _heading_ids(groups, config)
    if config.tags_hierarchical:
        _render_tree(lines, hierarchy(groups, config), config, ids, parents=())
    else:
        for tag in sorted(groups, key=str.lower):
            pages = groups[tag]
            icon = _icon_html(tag, config.tags_icons)
            pill = _heading_pill(tag.replace("\\/", "/"), icon, tooltip=_tooltip(pages, lang))
            lines.extend((f'<div id="{ids[(tag,)]}" class="gd-tag-heading">{pill}</div>', ""))
            _render_page_links(lines, pages, indent_class="")
    return "\n".join(lines)


def page_data(
    pages: Sequence[TaggedPage],
    groups: Mapping[str, Sequence[TaggedPage]],
    config: Config,
    *,
    report: Callable[[str], None],
) -> dict[str, Any]:
    """
    Build the data for tag pills on each page

    Parameters
    ----------
    pages
        The tagged pages.
    groups
        The pages for each tag.
    config
        The Great Docs configuration.
    report
        The callback that reports a warning for each unknown icon name.

    Returns
    -------
    :
        The tags of each page, a page count and sections for each tag's tooltip, the
        id of each tag's heading on the index page, the translated tooltip templates,
        the icons as inline SVG, the shadow tags, and the pill placement.
    """
    page_tags: dict[str, list[str]] = {}
    for tag, tagged in groups.items():
        for page in tagged:
            page_tags.setdefault(page.href, []).append(tag)
    # A page with only shadow tags still gets an entry, without pills.
    for page in pages:
        if page.shadowed and page.href not in page_tags:
            page_tags[page.href] = []

    tag_meta = {
        tag: {"count": len(tagged), "sections": sorted({p.section for p in tagged if p.section})}
        for tag, tagged in groups.items()
    }
    ids = _heading_ids(groups, config)
    # A hierarchical tag of only slashes has no levels, and so no heading.
    anchors = {tag: ids[levels] for tag in groups if (levels := _levels(tag, config)) in ids}

    lang = config.lang
    tooltip_templates = {
        "one": translate("tags_page_count_one", lang),
        "other": translate("tags_page_count_other", lang),
        "one_no_section": translate("tags_page_count_one_no_section", lang),
        "other_no_section": translate("tags_page_count_other_no_section", lang),
    }

    icons: dict[str, str] = {}
    for tag, icon_name in config.tags_icons.items():
        if svg := get_icon_svg(icon_name, size=14, css_class="gd-tag-icon-svg"):
            icons[tag] = svg
        else:
            report(f"Warning: Unknown tag icon '{icon_name}' for tag '{tag}'")

    return {
        "page_tags": page_tags,
        "tag_meta": tag_meta,
        "anchors": anchors,
        "tooltip_templates": tooltip_templates,
        "icons": icons,
        "shadow": list(dict.fromkeys(config.tags_shadow)),
        "hierarchical": config.tags_hierarchical,
        "default_location": config.tags_location,
        "page_tag_locations": {page.href: page.location for page in pages if page.location},
    }


def write(config: Config, layout: Layout, *, report: Callable[[str], None]) -> Contribution | None:
    """
    Write the tags index page and the tag pill data

    When `tags.index_page` is set, the index page is written with a navbar link labelled
    in the site's language. The data file is written when `tags.show_on_pages` is set.

    Parameters
    ----------
    config
        The Great Docs configuration.
    layout
        The project's directories.
    report
        The callback for index creation messages and unknown icon warnings.

    Returns
    -------
    :
        The index page's navbar link before Reference and the data for `page-tags.js`,
        each when enabled, or `None` when no page has a visible tag.
    """
    build_dir = layout.build_dir
    pages = collect(config, layout)
    groups = group(pages)
    if not groups:
        return None

    links: tuple[NavbarLink, ...] = ()
    if config.tags_index_page:
        index = build_dir / INDEX_PAGE
        index.parent.mkdir(parents=True, exist_ok=True)
        _ = index.write_text(render_index(groups, config), encoding="utf-8")
        report(f"Created {index.relative_to(build_dir)}")
        link = NavbarLink(
            text=navbar.TAGS.label(config), href=INDEX_PAGE, before="reference/index.qmd"
        )
        links = (link,)

    data: tuple[InlineData, ...] = ()
    if config.tags_show_on_pages:
        pills = page_data(pages, groups, config, report=report)
        _ = (build_dir / DATA_FILENAME).write_text(json.dumps(pills), encoding="utf-8")
        data = (InlineData("__GD_TAGS_DATA__", pills, before="page-tags.js"),)
    return Contribution(navbar=links, inline_data=data)


def _levels(tag: str, config: Config) -> tuple[str, ...]:
    """
    Find the levels of the index heading that shows a tag

    Parameters
    ----------
    tag
        The tag as written in front matter.
    config
        The Great Docs configuration. `tags.hierarchical` controls nesting.

    Returns
    -------
    :
        The tag's hierarchy levels when tags are hierarchical, otherwise the tag alone.
    """
    return tuple(split_tag(tag)) if config.tags_hierarchical else (tag,)


def _heading_ids(
    groups: Mapping[str, Sequence[TaggedPage]], config: Config
) -> dict[tuple[str, ...], str]:
    """
    Give each heading on the index page a unique id

    An id is the heading's levels joined in lower case, with each run of characters
    other than letters and digits replaced by `-`. Headings whose ids would coincide
    take a numeric suffix, such as `c-2`, in the sorted order of their levels.

    Parameters
    ----------
    groups
        The pages for each tag.
    config
        The Great Docs configuration.

    Returns
    -------
    :
        The id of each heading, parents without pages included, by its levels.
    """
    headings: set[tuple[str, ...]] = set()
    for tag in groups:
        levels = _levels(tag, config)
        headings.update(levels[:depth] for depth in range(1, len(levels) + 1))
    ids: dict[tuple[str, ...], str] = {}
    taken: set[str] = set()
    for levels in sorted(headings):
        base = re.sub(r"[\W_]+", "-", "-".join(levels).lower()).strip("-") or "tag"
        heading_id, suffix = base, 1
        while heading_id in taken:
            suffix += 1
            heading_id = f"{base}-{suffix}"
        taken.add(heading_id)
        ids[levels] = heading_id
    return ids


def _render_tree(
    lines: list[str],
    node: TagNode,
    config: Config,
    ids: Mapping[tuple[str, ...], str],
    *,
    parents: tuple[str, ...],
) -> None:
    """
    Append the headings and page links for a node's children and their descendants

    A nested tag's pill shows its parent's path as a muted left segment, which carries the
    parent's icon.

    Parameters
    ----------
    lines
        The page lines, extended in place.
    node
        The node whose children and descendants supply the headings and links.
    config
        The Great Docs configuration.
    ids
        The heading ids, by tag levels.
    parents
        The levels of the node's tag, empty for the root.

    Returns
    -------
    :
    """
    icons = config.tags_icons
    depth = len(parents)
    indent_class = f" gd-tag-indent-{min(depth, 2)}" if depth > 0 else ""
    prefix = "/".join(parents)
    for name, child in sorted(node.children.items(), key=lambda item: item[0].lower()):
        levels = (*parents, name)
        tooltip = _tooltip(child.pages, config.lang)
        if prefix:
            parent_icon = _icon_html(prefix, icons)
            pill = _heading_pill(name, "", parent=prefix, parent_icon=parent_icon, tooltip=tooltip)
        else:
            pill = _heading_pill(name, _icon_html(name, icons), tooltip=tooltip)
        heading = f'<div id="{ids[levels]}" class="gd-tag-heading{indent_class}">{pill}</div>'
        lines.extend((heading, ""))
        if child.pages:
            _render_page_links(lines, child.pages, indent_class=indent_class)
        if child.children:
            _render_tree(lines, child, config, ids, parents=levels)


def _render_page_links(lines: list[str], pages: Sequence[TaggedPage], *, indent_class: str) -> None:
    """
    Append links to a tag's pages, each with its section badge

    Parameters
    ----------
    lines
        The page lines, extended in place.
    pages
        The tag's pages.
    indent_class
        The class that indents a nested tag's links, with a leading space, or empty.

    Returns
    -------
    :
    """
    lines.append(f'<div class="gd-tag-pages{indent_class}">')
    for page in pages:
        section = _text(page.section)
        badge = f' <span class="gd-tag-section">{section}</span>' if section else ""
        title = _title(page.title)
        lines.append(f'<div class="gd-tag-page-link">[{title}](../{page.href}){badge}</div>')
    lines.extend(("</div>", ""))


def _icon_html(tag: str, icons: Mapping[str, str]) -> str:
    """
    Render a tag's icon for a pill heading

    Parameters
    ----------
    tag
        The tag name. The name with `\\/` replaced by `/` is tried when the original
        name has no icon.
    icons
        Lucide icon names by tag.

    Returns
    -------
    :
        The inline SVG in a spacing `<span>`, or an empty string when the tag has no known icon.
    """
    icon_name = icons.get(tag) or icons.get(tag.replace("\\/", "/"))
    if not icon_name:
        return ""
    svg = get_icon_svg(icon_name, size=14, css_class="gd-tag-icon-svg")
    if not svg:
        return ""
    return (
        f'<span style="margin-right:0.4em;display:inline-flex;vertical-align:middle">{svg}</span>'
    )


def _tooltip(pages: Sequence[TaggedPage], lang: str) -> str:
    """
    Format a translated tooltip with a tag's page count and sections

    Parameters
    ----------
    pages
        The pages with the tag.
    lang
        The site's language code.

    Returns
    -------
    :
        Text such as `2 pages in Recipes, User Guide`, or an empty string when
        there are no pages.
    """
    count = len(pages)
    if count == 0:
        return ""
    sections = sorted({page.section for page in pages if page.section})
    if sections:
        key = "tags_page_count_one" if count == 1 else "tags_page_count_other"
        template = translate(key, lang)
        return template.replace("{count}", str(count)).replace("{sections}", ", ".join(sections))
    key = "tags_page_count_one_no_section" if count == 1 else "tags_page_count_other_no_section"
    return translate(key, lang).replace("{count}", str(count))


def _heading_pill(
    name: str, icon: str, *, parent: str = "", parent_icon: str = "", tooltip: str = ""
) -> str:
    """
    Render a tag's pill for the index page

    Parameters
    ----------
    name
        The tag, or its last part when nested.
    icon
        The tag's icon HTML for a top-level pill.
    parent
        The parent tag's path for a nested pill, which shows it as a muted left segment.
    parent_icon
        The parent's icon HTML, shown in the left segment.
    tooltip
        The tooltip text, or empty for none.

    Returns
    -------
    :
        The pill as a `<span>`.
    """
    tip_attr = f' data-tippy-content="{html.escape(tooltip)}"' if tooltip else ""
    if parent:
        return (
            f'<span class="gd-tag-pill gd-tag-pill-segmented"{tip_attr}>'
            f'<span class="gd-tag-pill-segment gd-tag-pill-parent">{parent_icon}{_text(parent)}</span>'
            '<span class="gd-tag-pill-sep"></span>'
            f'<span class="gd-tag-pill-segment">{_text(name)}</span>'
            "</span>"
        )
    return f'<span class="gd-tag-pill"{tip_attr}>{icon}{_text(name)}</span>'


def _text(value: str) -> str:
    """
    Escape plain text for the index page's HTML and Markdown

    Parameters
    ----------
    value
        A tag or section name.

    Returns
    -------
    :
        The text, which Quarto shows unchanged, without markup.
    """
    return _MARKDOWN_PUNCTUATION.sub(r"\\\1", html.escape(value, quote=False))


def _title(value: str) -> str:
    """
    Escape a page title for the text of a Markdown link

    Parameters
    ----------
    value
        The page title, which Quarto reads as Markdown.

    Returns
    -------
    :
        The title with `&`, `<`, `>`, `[` and `]` escaped outside code spans. Code
        spans remain literal, and Markdown such as emphasis renders as in the page's
        own heading.
    """
    # Pandoc displays code span contents literally, so added escapes would be visible.
    parts: list[str] = []
    start = 0
    for span in _CODE_SPAN.finditer(value):
        parts.extend((_title_text(value[start : span.start()]), span.group()))
        start = span.end()
    parts.append(_title_text(value[start:]))
    return "".join(parts)


def _title_text(value: str) -> str:
    """
    Escape a title fragment outside code spans for a Markdown link

    Parameters
    ----------
    value
        A title fragment outside code spans.

    Returns
    -------
    :
        The fragment with `&`, `<` and `>` escaped for HTML and `[` and `]` escaped
        for Markdown.
    """
    return re.sub(r"([\[\]])", r"\\\1", html.escape(value, quote=False))
