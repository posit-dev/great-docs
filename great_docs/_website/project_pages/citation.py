"""
A page of project authors and citation formats from `CITATION.cff`
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from yaml12 import read_yaml

from ..._project.repository import Repository
from .. import page_dates

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from ..._project.layout import Layout
    from ...config import Config

__all__ = ["FILENAME", "write_page"]

FILENAME = "citation.qmd"


def write_page(
    config: Config,
    layout: Layout,
    package_name: str | None,
    authors: list[dict[str, Any]],
    *,
    repository: Repository | None,
    ref: str,
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
    repository
        The documented repository, or `None` when unknown.
    ref
        The source ref for the documented repository. Other repositories use `main`.
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
    citation_file_link = _source_url(citation, repository, ref)
    if citation_file_link:
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


def _source_url(citation: Mapping[str, Any], repository: Repository | None, ref: str) -> str | None:
    """
    Resolve the citation's source without treating a general URL as a repository

    Parameters
    ----------
    citation
        The parsed citation, whose `repository-code` takes precedence over `url`.
    repository
        The documented repository, including any self-managed installation prefix.
    ref
        The source ref for the documented repository.

    Returns
    -------
    :
        A citation-file address for a recognised repository, the original citation URL
        otherwise, or `None` when neither citation nor project supplies an address.
    """
    url: str | None = citation.get("repository-code") or citation.get("url")
    selected = Repository.parse(url) if url else repository
    if url and selected is None and repository is not None and repository.provider == "gitlab":
        try:
            selected = Repository.parse(url, provider="gitlab", base_url=repository.base_url)
        except ValueError:
            pass
    if selected is None:
        return url
    return selected.file_url("CITATION.cff", ref if selected == repository else "main")


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
