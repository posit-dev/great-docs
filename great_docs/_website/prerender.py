"""
Page source transformations before Quarto rendering

Each pass rewrites page sources in place, so it runs after all steps that create or copy pages.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from . import page_metadata, quarto_yml

if TYPE_CHECKING:
    from pathlib import Path

    from ..config import Config
    from .seo.structured_data import StructuredData

# Only column 0 matches, so nested `freeze:` keys remain unchanged.
_FREEZE_KEY_RE = re.compile(r"^freeze:\s+(.+)$", re.MULTILINE)


def expand_freeze_shorthand(project_dir: Path) -> list[str]:
    """
    Rewrite each page's top-level `freeze:` key as `execute: freeze:`

    Great Docs accepts `freeze: auto` and `freeze: true` in page front matter. Quarto reads
    the setting only under `execute:`. Add the setting after an existing standalone
    `execute:` line, or create a new block if there is no such line.

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
        if not content.startswith("---"):
            continue

        parts = content.split("---", 2)
        if len(parts) < 3:
            continue

        frontmatter = parts[1]
        m = _FREEZE_KEY_RE.search(frontmatter)
        if not m:
            continue

        freeze_value = m.group(1).strip()
        new_frontmatter = frontmatter[: m.start()] + frontmatter[m.end() :]

        exec_match = re.search(r"^execute:\s*$", new_frontmatter, re.MULTILINE)
        if exec_match:
            insert_pos = exec_match.end()
            new_frontmatter = (
                new_frontmatter[:insert_pos]
                + f"\n  freeze: {freeze_value}"
                + new_frontmatter[insert_pos:]
            )
        else:
            new_frontmatter = new_frontmatter.rstrip() + f"\nexecute:\n  freeze: {freeze_value}\n"

        _ = qmd.write_text(f"---{new_frontmatter}---{parts[2]}", encoding="utf-8")
        modified.append(str(qmd.relative_to(project_dir)))

    return modified


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
