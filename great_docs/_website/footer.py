"""
Page footer credits for the package's developers and funder, and for Great Docs

The footer names the authors and maintainers, then the funder. A funder whose
name contains the word "Posit" also gets the "Supported by Posit" badge.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from .._manifest import Manifest
from .._subprocess import TEXT_MODE_KWARGS
from .._translations import translate
from . import quarto_yml

if TYPE_CHECKING:
    from ..config import Config

_POSIT_BADGE = (
    '<script src="https://cdn.jsdelivr.net/gh/posit-dev/'
    'supported-by-posit/js/badge.min.js"></script>'
)

# The directory that holds the `great_docs` package: the repository root of a
# development checkout, or `site-packages` for an installed copy.
_SOURCE_DIR = Path(__file__).resolve().parents[2]


def register(quarto_config: dict[str, Any], config: Config, metadata: Manifest) -> None:
    """
    Add the page footer and the Posit badge

    Centre the developer and funder credits in the footer. Include a Great Docs
    credit when `attribution` is enabled, even without other credits. Omit the
    footer when there are no credits. Add the badge script to the HTML header
    when the funder's name contains the word "Posit".

    Parameters
    ----------
    quarto_config
        Contents of `_quarto.yml`, updated in place.
    config
        Project configuration.
    metadata
        Package metadata with `authors` and `maintainers` from `pyproject.toml`.
        Each person is a name or a mapping with a `name`.

    Returns
    -------
    :
    """
    website = cast("dict[str, Any]", quarto_config.setdefault("website", {}))
    funding = config.funding
    funder = _funder(funding)

    lines: list[str] = []
    credits = _credits(config, metadata, funder)
    if credits:
        lines.append(credits)
    if config.attribution:
        lines.append(
            f"{translate('site_created_with', config.lang)} "
            f"<strong>Great&nbsp;Docs</strong>{_commit_label()}."
        )
    if lines:
        website["page-footer"] = {"center": "<br>".join(lines)}

    if funder and funding and re.search(r"\bPosit\b", funding["name"], re.IGNORECASE):
        quarto_yml.add_include(
            quarto_config,
            "include-in-header",
            {"text": _POSIT_BADGE},
            marker="supported-by-posit",
        )


def _credits(config: Config, metadata: Manifest, funder: str | None) -> str:
    """
    Build credit sentences for the developers and the funder

    Parameters
    ----------
    config
        Project configuration.
    metadata
        Package metadata with the `pyproject.toml` authors and maintainers.
    funder
        The funder's formatted name, or `None` if there is no funder.

    Returns
    -------
    :
        The credits, or an empty string if there are no developers or funder.
    """
    homepages: dict[str, str] = {}
    for author in cast("list[Any]", config.authors):
        if isinstance(author, dict):
            author = cast("dict[str, Any]", author)
            if author.get("name") and author.get("homepage"):
                homepages[author["name"]] = author["homepage"]

    names = _developer_names(config, metadata)
    names_html = [_strong(name.replace(" ", "&nbsp;"), homepages.get(name)) for name in names]

    sentences: list[str] = []
    if names_html:
        developed_by = translate("developed_by", config.lang)
        sentences.append(f"{developed_by} {_join(names_html, config.lang)}.")
    if funder:
        sentences.append(f"{translate('supported_by', config.lang)} {funder}.")
    return " ".join(sentences)


def _developer_names(config: Config, metadata: Manifest) -> list[str]:
    """
    List the developers' names: authors, then maintainers, then configured authors

    Parameters
    ----------
    config
        Project configuration, whose `authors` may name people missing from
        `pyproject.toml`.
    metadata
        Package metadata with the `pyproject.toml` authors and maintainers.

    Returns
    -------
    :
        The names in order. The `pyproject.toml` authors retain duplicates;
        maintainers and configured authors are added only if their names
        are absent.
    """
    names = [name for author in metadata.get("authors", []) if (name := _name(author)) is not None]
    for maintainer in metadata.get("maintainers", []):
        name = _name(maintainer)
        if name is not None and name not in names:
            names.append(name)
    # Only mappings count as configured authors; bare strings are ignored.
    for author in cast("list[Any]", config.authors):
        name = _name(author) if isinstance(author, dict) else None
        if name and name not in names:
            names.append(name)
    return names


def _name(person: Any) -> str | None:
    """
    Read a person's name from `pyproject.toml` metadata

    Parameters
    ----------
    person
        A name, or a mapping with a `name`.

    Returns
    -------
    :
        The name, or `None` for an unnamed mapping or an unsupported value.
    """
    if isinstance(person, dict):
        return cast("dict[str, Any]", person).get("name") or None
    return person if isinstance(person, str) else None


def _join(items: list[str], lang: str) -> str:
    """
    Join items with a translated "and" before the last item

    Parameters
    ----------
    items
        At least one item to join.
    lang
        The site language.

    Returns
    -------
    :
        `a`, `a and b`, or `a, b, and c`.
    """
    and_ = translate("and", lang)
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} {and_} {items[1]}"
    return ", ".join(items[:-1]) + f", {and_} " + items[-1]


def _funder(funding: dict[str, Any] | None) -> str | None:
    """
    Format the funder's name, linked to its homepage if it has one

    Parameters
    ----------
    funding
        The `funding` configuration.

    Returns
    -------
    :
        The name in bold, or `None` when `funding` has no name.
    """
    if not isinstance(funding, dict) or not funding.get("name"):
        return None
    return _strong(funding["name"].replace(" ", "&nbsp;"), funding.get("homepage"))


def _strong(text: str, url: str | None) -> str:
    """
    Render text in bold, as a link when a URL is given

    Parameters
    ----------
    text
        The HTML text.
    url
        The link target, or `None` or an empty string for no link.

    Returns
    -------
    :
        The bold HTML text, linked when a URL is given.
    """
    strong = f"<strong>{text}</strong>"
    return f'<a href="{url}">{strong}</a>' if url else strong


def _commit_label() -> str:
    """
    Link to the Great Docs commit when running from a development checkout

    Returns
    -------
    :
        A leading space followed by the linked short hash in parentheses,
        or an empty string for an installed copy or when `git` fails,
        is unavailable or times out.
    """
    try:
        remote = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=_SOURCE_DIR,
            capture_output=True,
            **TEXT_MODE_KWARGS,
            timeout=5,
        )
        # An installed copy may be inside the user's repository, so its commit
        # must not be attributed to Great Docs.
        if remote.returncode != 0 or "great-docs" not in remote.stdout.strip():
            return ""
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_SOURCE_DIR,
            capture_output=True,
            **TEXT_MODE_KWARGS,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if head.returncode != 0:
        return ""
    short_hash = head.stdout.strip()
    return (
        f' (<a href="https://github.com/posit-dev/great-docs/commit/{short_hash}">{short_hash}</a>)'
    )
