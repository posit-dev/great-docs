"""
Search descriptions and social card options for pages Quarto renders

A single pass before rendering reads each page once and adds search
descriptions and social card options to its front matter.
The author's existing front matter, including comments, is preserved.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import TYPE_CHECKING, Any

from yaml12 import format_yaml

from .._yaml import FRONT_MATTER_OPENING, YamlMapping, split_front_matter
from . import head, scale_to_fit, social_cards
from .seo import description

if TYPE_CHECKING:
    from ..config import Config
    from .seo.structured_data import StructuredData


def rendered_pages(project_dir: Path, quarto_config: dict[str, Any]) -> Iterator[Path]:
    """
    Yield the Markdown pages eligible for Quarto rendering

    Parameters
    ----------
    project_dir
        The Quarto project directory.
    quarto_config
        Contents of its `_quarto.yml`.

    Returns
    -------
    :
        The `.qmd` and `.md` pages in path order.
    """
    render = quarto_config.get("project", {}).get("render", [])
    excluded = [p[1:] for p in render if isinstance(p, str) and p.startswith("!")]

    for path in sorted([*project_dir.rglob("*.qmd"), *project_dir.rglob("*.md")]):
        rel = path.relative_to(project_dir)
        # Quarto renders no file whose path has a part starting with `_` or `.`
        if any(part.startswith(("_", ".")) for part in rel.parts):
            continue
        if any(fnmatchcase(rel.as_posix(), pattern) for pattern in excluded):
            continue
        yield path


@dataclass(frozen=True)
class Page:
    """A page Quarto renders, read once by the pre-render pass"""

    path: Path
    """The page's source file"""

    output_path: str
    """The rendered page relative to the site root, such as `reference/index.html`"""

    content: str
    """The page source as read"""

    front_matter: YamlMapping
    """The parsed front matter, empty when the page has none or it is not a mapping"""

    body: str
    """The source after the front matter"""

    @classmethod
    def make(cls, path: Path, project_dir: Path) -> Page:
        """
        Read and parse a page

        Parameters
        ----------
        path
            The page's source file, a `.qmd` or `.md` file under `project_dir`.
        project_dir
            The Quarto project directory.

        Returns
        -------
        :
            The page.
        """
        content = path.read_text(encoding="utf-8")
        front_matter, body = split_front_matter(content)
        return cls(
            path=path,
            output_path=path.relative_to(project_dir).with_suffix(".html").as_posix(),
            content=content,
            front_matter=front_matter,
            body=body,
        )


def add_to_page(content: str, entries: dict[str, Any]) -> str:
    """
    Add entries to the start of a page's front matter

    Parameters
    ----------
    content
        The page source.
    entries
        Front matter keys and their values. Values that are strings must
        already be escaped for Quarto's Markdown.

    Returns
    -------
    :
        The page with the entries prepended, creating front matter if needed.
    """
    block = format_yaml(entries).rstrip()
    opening = FRONT_MATTER_OPENING.match(content)
    if opening is not None:
        return f"---\n{block}\n{content[opening.end() :]}"
    return f"---\n{block}\n---\n\n{content}"


def write_to_pages(
    project_dir: Path,
    quarto_config: dict[str, Any],
    config: Config,
    default: str | None,
    structured_data: StructuredData | None = None,
) -> list[Path]:
    """
    Write search descriptions and social card options into rendered pages

    Read each page once and write it at most once. When SEO is enabled, add
    `description-meta` to pages that lack a description. When social cards
    are enabled, add `open-graph` and `twitter-card` options to pages that set
    neither key. Skip each kind of metadata if the site's header includes
    already supply it. A page whose own header includes declare Open Graph
    tags gets options that switch the generated ones off. Add a scale-to-fit
    `<head>` tag for selectors resolved from page and directory metadata. Add
    the supplied JSON-LD to the homepage and reference pages unless the site's
    header includes or the page source already contain it.

    Parameters
    ----------
    project_dir
        The Quarto project directory.
    quarto_config
        Contents of its `_quarto.yml`, whose `website.title` names the site in
        card titles.
    config
        Project configuration.
    default
        The site's default description as plain text.
    structured_data
        The JSON-LD to add, or `None` when structured data is disabled.

    Returns
    -------
    :
        The pages that were changed.
    """
    write_descriptions = description.applies(quarto_config, config, project_dir)
    write_cards = social_cards.applies(quarto_config, config, project_dir)
    site_name = quarto_config.get("website", {}).get("title")
    header_description = description.header_description(quarto_config, project_dir)
    overrides = scale_to_fit.Overrides.make(project_dir)
    if structured_data and not structured_data.applies(quarto_config, project_dir):
        structured_data = None

    changed: list[Path] = []
    for path in rendered_pages(project_dir, quarto_config):
        page = Page.make(path, project_dir)
        entries: dict[str, Any] = {}
        if write_descriptions and (
            value := description.page_description(
                page.front_matter,
                page.body,
                default,
                citations=description.resolves_citations(page.front_matter, config),
            )
        ):
            entries["description-meta"] = value
        if write_cards:
            entries.update(
                social_cards.page_entries(
                    page.front_matter,
                    page.body,
                    path.parent,
                    site_name,
                    config,
                    default,
                    header_description,
                )
            )
        tags: list[str] = []
        if tag := overrides.tag(page):
            tags.append(tag)
        if structured_data and (tag := structured_data.tag(page)):
            tags.append(tag)
        content = add_to_page(page.content, entries) if entries else page.content
        if tags:
            content = head.add_tags(content, tags)
        if content == page.content:
            continue
        _ = path.write_text(content, encoding="utf-8")
        changed.append(path)
    return changed
