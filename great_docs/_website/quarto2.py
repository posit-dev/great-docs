"""
Adapt a build directory for Quarto 2 (experimental)

Quarto 2 reads `_quarto.yml` and page front matter much as Quarto 1 does, but some of the
settings great-docs relies on behave differently or are missing. `adapt_config` rewrites a
copy of the configuration as `_quarto.yml` is written, and `prepare_pages` changes the
build directory's pages and adds scripts before each render. Quarto 1 builds use neither.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any, cast

from yaml12 import parse_yaml

from .._yaml import locate_front_matter
from . import quarto_yml

__all__ = [
    "FILTER",
    "POST_RENDER_SCRIPT",
    "SETTINGS_KEY",
    "adapt_config",
    "definition_lists",
    "prepare_pages",
]

FILTER = "gd-quarto2"
"""The bundled extension whose filter stands in for HTML features Quarto 2 lacks"""

SETTINGS_KEY = "gd-quarto2"
"""The top-level `_quarto.yml` key that holds the filter's settings"""

POST_RENDER_SCRIPT = "scripts/quarto2-post-render.py"
"""The post-render script that finishes the pages Quarto 2 writes"""

_ASSETS = Path(__file__).parents[1] / "assets"
_SIDEBAR_KEY = re.compile(r"^sidebar:", re.MULTILINE)
_NAVBAR_TRUE = re.compile(r"^navbar:[ \t]*true[ \t]*\n", re.MULTILINE)
_PAGE_SUFFIXES = (".qmd", ".md")
_FENCE = re.compile(r"^(`{3,}|~{3,})")
_DEFINITION = re.compile(r"^:(?:[ \t]+(.*))?$")
_METADATA_FILES = ("_metadata.yml", "_metadata.yaml")


def adapt_config(quarto_config: dict[str, Any]) -> dict[str, Any]:
    """
    Return a copy of the configuration that Quarto 2 renders as Quarto 1 renders the original

    - Quarto 2 writes `search.json` only on request; the site's search and AI agent files
      read it.
    - Quarto 2 ignores `shift-heading-level-by` for HTML, and writes no Open Graph or
      Twitter card tags, so their settings move to the gd-quarto2 filter, which runs first.
    - Quarto 2 leaves root-relative addresses unchanged, sets no text direction, and drops
      its layout classes for a page's `body-classes`, so a post-render script, run last,
      finishes each page.

    Applying it again to its result changes nothing.

    Parameters
    ----------
    quarto_config
        The configuration, which is not changed.

    Returns
    -------
    :
        The adapted configuration.
    """
    adapted = cast("dict[str, Any]", _copy(quarto_config))
    settings = cast("dict[str, Any]", adapted.get(SETTINGS_KEY) or {})
    website: Any = adapted.get("website")
    if isinstance(website, dict):
        website = cast("dict[str, Any]", website)
        search = website.get("search")
        if search is None or search is True:
            website["search"] = {"search-json": True}
        elif isinstance(search, dict):
            _ = cast("dict[str, Any]", search).setdefault("search-json", True)
        if isinstance(website.get("title"), str):
            settings["site-title"] = website["title"]
        cards = _social_cards(website)
        if cards is not None:
            settings["social-cards"] = cards

    html: Any = adapted.get("format", {}).get("html")
    if isinstance(html, dict) and "shift-heading-level-by" in html:
        settings["shift-heading-level-by"] = cast("dict[str, Any]", html).pop(
            "shift-heading-level-by"
        )
    adapted[SETTINGS_KEY] = settings

    filters = quarto_yml.entries(adapted, "filters")
    filters[:] = [FILTER, *(entry for entry in filters if entry != FILTER)]

    project = cast("dict[str, Any]", adapted.setdefault("project", {}))
    scripts = quarto_yml.entries(project, "post-render")
    scripts[:] = [
        *(entry for entry in scripts if entry != POST_RENDER_SCRIPT),
        POST_RENDER_SCRIPT,
    ]
    return adapted


def prepare_pages(build_dir: Path) -> None:
    """
    Change a build directory's pages for a Quarto 2 render

    Copy the post-render script that `adapt_config` registers. Quarto 2 picks a page's
    sidebar by `site-sidebar`, and shows none on a page with a named `sidebar`, so rename
    each named `sidebar` in page front matter and directory metadata. Leave `sidebar: false`
    alone. Quarto 2 also shows no navbar on a page with `navbar: true`, which in Quarto 1
    only keeps the site's navbar, so remove that option.
    Rewrite each page's definition lists with `definition_lists`.

    Parameters
    ----------
    build_dir
        The Quarto project directory.

    Returns
    -------
    :
    """
    script = build_dir / POST_RENDER_SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    _ = shutil.copyfile(_ASSETS / "quarto2-post-render.py", script)

    for directory, subdirs, files in os.walk(build_dir):
        subdirs[:] = [
            name for name in subdirs if not name.startswith(("_", ".")) and name != "site_libs"
        ]
        for name in files:
            path = Path(directory) / name
            if name in _METADATA_FILES:
                _name_sidebar_in_metadata(path)
            elif name.endswith(_PAGE_SUFFIXES):
                _adapt_page(path)


def definition_lists(markdown: str) -> str:
    """
    Rewrite Pandoc definition lists in the form Quarto 2 reads

    Quarto 2 has no Pandoc definition lists: it shows each definition as a paragraph that
    starts with `:`, and an empty definition is a parse error. A `.definition-list` div that
    holds a list of terms, each with a nested list of its definitions, renders as `<dl>`.
    Consecutive terms share one div, as they share one `<dl>` in Pandoc. Fenced code is left
    alone.

    Parameters
    ----------
    markdown
        A page's body.

    Returns
    -------
    :
        The body with each definition list rewritten.
    """
    lines = markdown.split("\n")
    output: list[str] = []
    fence: str | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if fence is not None:
            if line.strip().startswith(fence) and not line.strip()[len(fence) :].strip():
                fence = None
            output.append(line)
            i += 1
            continue
        opening = _FENCE.match(line)
        if opening is not None:
            fence = opening.group(1)
            output.append(line)
            i += 1
            continue
        starts_block = not output or not output[-1].strip() or output[-1].startswith(":::")
        items, end = _read_definition_items(lines, i) if starts_block else ([], i)
        if items:
            output.append("::: {.definition-list}")
            for term, definitions in items:
                output.append(f"* {term}")
                for first, rest in definitions:
                    output.append(f"  - {first}" if first else "  -")
                    output.extend(rest)
            output.append(":::")
            i = end
            continue
        output.append(line)
        i += 1
    return "\n".join(output)


def _read_definition_items(
    lines: list[str], start: int
) -> tuple[list[tuple[str, list[tuple[str, list[str]]]]], int]:
    """
    Read the definition list items that start at a line

    Returns
    -------
    :
        Each term with its definitions, as each definition's first line and its following
        lines, and the index of the line after the last definition. No items when the line
        does not start a definition list.
    """
    items: list[tuple[str, list[tuple[str, list[str]]]]] = []
    i = start
    end = start
    while True:
        term = lines[i] if i < len(lines) else ""
        if not term.strip() or term[0] in " \t:" or _FENCE.match(term):
            break
        k = _skip_one_blank(lines, i + 1)
        definitions: list[tuple[str, list[str]]] = []
        while k < len(lines) and (match := _DEFINITION.match(lines[k])):
            first = (match.group(1) or "").strip()
            rest: list[str] = []
            j = k + 1
            while j < len(lines):
                line = lines[j]
                if not line.strip():
                    after = j
                    while after < len(lines) and not lines[after].strip():
                        after += 1
                    if after < len(lines) and lines[after].startswith(("    ", "\t")):
                        rest.extend(lines[j:after])
                        j = after
                        continue
                    break
                if line.startswith(("    ", "\t")):
                    rest.append(line)
                elif not lines[j - 1].strip() or _DEFINITION.match(line) or line.startswith(":::"):
                    break
                else:
                    # A paragraph's lazy continuation line
                    rest.append("    " + line)
                j += 1
            definitions.append((first, rest))
            end = j
            k = _skip_one_blank(lines, j)
        if not definitions:
            break
        items.append((term.strip(), definitions))
        i = _skip_one_blank(lines, end)
    return items, end


def _skip_one_blank(lines: list[str], i: int) -> int:
    """Return the index past a blank line at `i`, or `i` when that line is not blank"""
    if i < len(lines) and not lines[i].strip():
        return i + 1
    return i


def _copy(value: Any) -> Any:
    """Copy the mappings and lists of a configuration value"""
    if isinstance(value, dict):
        return {key: _copy(item) for key, item in cast("dict[Any, Any]", value).items()}
    if isinstance(value, list):
        return [_copy(item) for item in cast("list[Any]", value)]
    return value


def _social_cards(website: dict[str, Any]) -> dict[str, Any] | None:
    """Remove the site's card options and return them as the filter's settings"""
    open_graph = website.pop("open-graph", None)
    twitter = website.pop("twitter-card", None)
    if not open_graph and not twitter:
        return None
    cards: dict[str, Any] = {}
    for option in (open_graph, twitter):
        if isinstance(option, dict) and "image" in option:
            cards["image"] = cast("dict[str, Any]", option)["image"]
    if isinstance(twitter, dict):
        twitter = cast("dict[str, Any]", twitter)
        if "card-style" in twitter:
            cards["card"] = twitter["card-style"]
        if "site" in twitter:
            cards["site"] = twitter["site"]
    return cards


def _adapt_page(path: Path) -> None:
    """Adapt a page's sidebar and navbar options for Quarto 2 and rewrite its definition lists"""
    content = path.read_text(encoding="utf-8")
    front_matter, body = "", content
    block = locate_front_matter(content)
    if block is not None:
        front_matter, body = content[: block.end], content[block.end :]
        sidebar: Any = block.mapping.get("sidebar")
        if isinstance(sidebar, str):
            front_matter = _SIDEBAR_KEY.sub("site-sidebar:", front_matter, count=1)
        if block.mapping.get("navbar") is True:
            front_matter = _NAVBAR_TRUE.sub("", front_matter, count=1)
    adapted = front_matter + definition_lists(body)
    if adapted != content:
        _ = path.write_text(adapted, encoding="utf-8")


def _name_sidebar_in_metadata(path: Path) -> None:
    """Rename `sidebar` to `site-sidebar` in directory metadata that names a sidebar"""
    content = path.read_text(encoding="utf-8")
    try:
        metadata = parse_yaml(content)
    except ValueError:
        return
    if not isinstance(metadata, dict):
        return
    metadata = cast("dict[str, Any]", metadata)
    sidebar: Any = metadata.get("sidebar")
    if isinstance(sidebar, str):
        _ = path.write_text(_SIDEBAR_KEY.sub("site-sidebar:", content, count=1), encoding="utf-8")
