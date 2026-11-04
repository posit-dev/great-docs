"""
Page source transformations before Quarto rendering

Each pass rewrites page sources in place, so it runs after all steps that create or copy pages.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from yaml12 import format_yaml

from .._yaml import YamlMapping, locate_front_matter
from . import page_metadata, quarto_yml

if TYPE_CHECKING:
    from pathlib import Path

    from ..config import Config
    from .seo.structured_data import StructuredData

# Only column 0 matches, so nested `freeze:` keys remain unchanged.
_FREEZE_LINE_RE = re.compile(r"^freeze:.*\n", re.MULTILINE)
_EXECUTE_LINE_RE = re.compile(r"^execute:[ \t]*(.*)$", re.MULTILINE)
# The indentation of the first entry after a line, skipping blank and comment lines
_ENTRY_INDENT_RE = re.compile(r"\n(?:[ \t]*(?:#.*)?\n)*([ \t]+)\S")


def expand_freeze_shorthand(project_dir: Path) -> list[str]:
    """
    Rewrite each page's top-level `freeze:` key as `execute: freeze:`

    Great Docs accepts `freeze: auto` and `freeze: true` in page front matter. Quarto reads
    the setting only under `execute:`. The setting joins an existing `execute:` mapping in
    either block or flow style, or a new block when the page has none. A page whose
    `execute:` already sets `freeze` keeps that value and loses the shorthand. The rest of
    the page keeps its text.

    Parameters
    ----------
    project_dir
        The Quarto project directory, whose `.qmd` files are rewritten in place.

    Returns
    -------
    :
        Paths of rewritten pages, relative to `project_dir`.
    """
    modified: list[str] = []
    for qmd in project_dir.rglob("*.qmd"):
        content = qmd.read_text(encoding="utf-8")
        block = locate_front_matter(content)
        if block is None or "freeze" not in block.mapping:
            continue

        front_matter = _nest_freeze(content[: block.end], block.mapping)
        if front_matter is None:
            continue

        _ = qmd.write_text(front_matter + content[block.end :], encoding="utf-8")
        modified.append(str(qmd.relative_to(project_dir)))

    return modified


def _nest_freeze(front_matter: str, mapping: YamlMapping) -> str | None:
    """
    Move a top-level `freeze` setting under `execute`

    Parameters
    ----------
    front_matter
        The page's front matter, from the opening `---` line to the end of the closing one.
    mapping
        The parsed front matter, which has a top-level `freeze` key.

    Returns
    -------
    :
        The rewritten front matter, or `None` when the `freeze` line cannot be found or
        `execute` holds something other than a mapping.
    """
    freeze = format_yaml(mapping.get("freeze"))
    text, count = _FREEZE_LINE_RE.subn("", front_matter, count=1)
    if count == 0:
        return None

    if "execute" not in mapping:
        closing = text.rindex("\n---") + 1
        return f"{text[:closing]}execute:\n  freeze: {freeze}\n{text[closing:]}"

    execute = mapping.get("execute")
    if isinstance(execute, dict) and "freeze" in execute:
        return text
    line = _EXECUTE_LINE_RE.search(text)
    if line is None or not (execute is None or isinstance(execute, dict)):
        return None

    value = line.group(1)
    if value.startswith("{"):
        brace = line.start(1) + 1
        separator = ", " if execute else ""
        return f"{text[:brace]}freeze: {freeze}{separator}{text[brace:]}"
    if value and not value.startswith("#"):
        return None

    indent = _ENTRY_INDENT_RE.match(text, line.end()) if execute else None
    entry = f"\n{indent.group(1) if indent else '  '}freeze: {freeze}"
    return text[: line.end()] + entry + text[line.end() :]


def write_page_metadata(
    project_dir: Path,
    config: Config,
    default_description: str | None,
    structured_data: StructuredData | None,
) -> None:
    """
    Write search descriptions, social card options and `<head>` tags into pages

    Descriptions and social cards depend on page content. Run after that content is final.
    A missing `_quarto.yml` is treated as an empty configuration.

    Parameters
    ----------
    project_dir
        The Quarto project directory.
    config
        Project configuration.
    default_description
        The site's default description as plain text.
    structured_data
        The JSON-LD for the homepage and reference pages, or `None` when structured data is
        disabled.

    Returns
    -------
    :
        `None`; page sources are updated in place.
    """
    _ = page_metadata.write_to_pages(
        project_dir,
        quarto_yml.read(project_dir, seed_website=True),
        config,
        default_description,
        structured_data,
    )
