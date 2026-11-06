"""
A page of project authors and citation formats from `CITATION.cff`
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from yaml12 import read_yaml

from .. import page_dates

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from ..._layout import Layout
    from ...config import Config

__all__ = ["FILENAME", "write_page"]

FILENAME = "citation.qmd"


def write_page(
    config: Config,
    layout: Layout,
    package_name: str | None,
    authors: list[dict[str, Any]],
    *,
    report: Callable[[str], None],
) -> Path | None:
    """
    Write the authors and citation page from the project's `CITATION.cff` file

    The page lists the citation's authors with their roles, links the source file in the
    repository, and gives the citation in BibTeX, APA and RIS formats. The year comes from
    `date-released`, or is the current year when that is missing or not a date.

    Parameters
    ----------
    config
        The Great Docs configuration. An author's role comes from the configured author with
        the same name, or is `"Author"` if there is none or it has no role.
    layout
        The package root to read `CITATION.cff` from and the build directory to write
        `citation.qmd` into.
    package_name
        The distribution name used in the introduction. If `None` or empty, the
        introduction uses "this package".
    authors
        The configured authors, with local portrait paths replaced by site URLs.
    report
        A callback that receives the line announcing the written page.

    Returns
    -------
    :
        The path of the written page, or `None` if the project has no `CITATION.cff` file.
    """
    source = layout.package_root / "CITATION.cff"
    if not source.exists():
        return None

    with open(source, encoding="utf-8") as f:
        citation = cast("dict[str, Any]", read_yaml(f))
    cff_authors: list[dict[str, Any]] = citation.get("authors") or []

    intro_paragraph = f"""
To cite {package_name or "this package"} in publications, please use the following citation.
"""

    configured_authors: list[dict[str, Any]] = config.authors or []
    authors_section = "## Authors\n\n"
    for author in cff_authors:
        full_name = _full_name(author)
        role = "Author"
        for configured in configured_authors:
            if configured.get("name") == full_name:
                role = configured.get("role", "Author")
                break
        authors_section += f"{full_name}. {role}.  \n"

    citation_section = "## Citation\n\n"
    repo_url = citation.get("repository-code") or citation.get("url")
    if repo_url:
        citation_file_link = f"{repo_url.rstrip('/')}/blob/main/CITATION.cff"
        citation_section += f"**Source:** [`CITATION.cff`]({citation_file_link})\n\n"
    else:
        citation_section += "**Source:** `CITATION.cff`\n\n"

    year = _year(citation.get("date-released"))
    citation_section += _bibtex(citation, cff_authors, year)
    citation_section += _apa(citation, cff_authors, year)
    citation_section += _ris(citation, cff_authors, year)

    content = f"""---
title: "Authors and Citation"
---
{intro_paragraph}

{authors_section}

{citation_section}
"""
    path = layout.build_dir / FILENAME
    _ = path.write_text(page_dates.add_to_page(content, source, config, authors), encoding="utf-8")
    report(f"Created {path}")
    return path


def _full_name(author: Mapping[str, Any]) -> str:
    """
    Join a `CITATION.cff` author's given and family names

    Parameters
    ----------
    author
        The author entry.

    Returns
    -------
    :
        The full name with surrounding whitespace removed, including when a name part
        is missing.
    """
    return f"{author.get('given-names', '')} {author.get('family-names', '')}".strip()


def _year(date_released: Any) -> int:
    """
    Extract the year from a `date-released` value

    Parameters
    ----------
    date_released
        The value: an ISO date string, a date, or `None`.

    Returns
    -------
    :
        The release year, or the current year when the value is missing or not a date.
    """
    year = datetime.now().year
    if date_released:
        try:
            if isinstance(date_released, str):
                year = datetime.fromisoformat(date_released).year
            elif hasattr(date_released, "year"):
                year = date_released.year
        except (ValueError, AttributeError):
            pass
    return year


def _bibtex(citation: Mapping[str, Any], authors: list[dict[str, Any]], year: int) -> str:
    """
    Format the citation as a BibTeX `@Manual` entry

    Parameters
    ----------
    citation
        The parsed `CITATION.cff` file.
    authors
        The file's authors.
    year
        The release year.

    Returns
    -------
    :
        A Markdown section with the entry in a `bibtex` code block.
    """
    text = "### BibTeX\n\n```bibtex\n@Manual{,\n"
    if citation.get("title"):
        text += f"  title = {{{citation['title']}}},\n"
    if authors:
        text += f"  author = {{{' and '.join(_full_name(a) for a in authors)}}},\n"
    text += f"  year = {{{year}}},\n"
    if citation.get("version"):
        text += f"  note = {{Python package version {citation['version']}}},\n"
    if citation.get("url"):
        text += f"  url = {{{citation['url']}}},\n"
    return text + "}\n```\n\n"


def _apa(citation: Mapping[str, Any], authors: list[dict[str, Any]], year: int) -> str:
    """
    Format the citation as an APA software reference

    Authors appear as family names with initials, joined with commas and an ampersand.

    Parameters
    ----------
    citation
        The parsed `CITATION.cff` file.
    authors
        The file's authors.
    year
        The release year.

    Returns
    -------
    :
        A Markdown section with the reference, or the heading alone when there are no
        authors.
    """
    text = "### APA\n\n"
    if not authors:
        return text

    apa_authors: list[str] = []
    for author in authors:
        family = author.get("family-names", "")
        given: str = author.get("given-names", "")
        initials = ". ".join([name[0] for name in given.split() if name]) + "." if given else ""
        apa_authors.append(f"{family}, {initials}" if initials else family)

    if len(apa_authors) == 1:
        names = apa_authors[0]
    elif len(apa_authors) == 2:
        names = f"{apa_authors[0]} & {apa_authors[1]}"
    else:
        names = ", ".join(apa_authors[:-1]) + ", & " + apa_authors[-1]

    title = citation.get("title", "")
    version = citation.get("version", "")
    url = citation.get("url", "")
    return text + f"{names} ({year}). *{title}* (Version {version}) [Computer software]. {url}\n\n"


def _ris(citation: Mapping[str, Any], authors: list[dict[str, Any]], year: int) -> str:
    """
    Format the citation as a RIS record for reference managers

    Parameters
    ----------
    citation
        The parsed `CITATION.cff` file.
    authors
        The file's authors.
    year
        The release year.

    Returns
    -------
    :
        A Markdown section with the record, of type `COMP`, in a `ris` code block.
    """
    text = "### RIS\n\n```ris\nTY  - COMP\n"
    if citation.get("title"):
        text += f"TI  - {citation['title']}\n"
    for author in authors:
        text += f"AU  - {author.get('family-names', '')}, {author.get('given-names', '')}\n"
    text += f"PY  - {year}\n"
    if citation.get("version"):
        text += f"VL  - {citation['version']}\n"
    if citation.get("url"):
        text += f"UR  - {citation['url']}\n"
    if citation.get("abstract"):
        text += f"AB  - {citation['abstract']}\n"
    return text + "ER  - \n```\n"
