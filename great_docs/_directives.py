from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class DocDirectives:
    """
    Extracted directives from a docstring.

    Attributes
    ----------
    seealso
        List of `(name, description)` tuples for cross-referencing. The description is an empty
        string when not provided.
    nodoc
        If `True`, exclude this item from documentation.
    """

    seealso: list[tuple[str, str]] = field(default_factory=list)
    nodoc: bool = False

    def __bool__(self) -> bool:
        """Return True if any directive was found."""
        return bool(self.seealso or self.nodoc)


# Single-line directive patterns (with % prefix, no colon)
# Each pattern matches a complete line starting with the directive
DIRECTIVE_PATTERNS = {
    "seealso": re.compile(r"^\s*%seealso\s+(.+?)\s*$", re.MULTILINE),
    "nodoc": re.compile(r"^\s*%nodoc(?:\s+(true|yes|1))?\s*$", re.MULTILINE | re.IGNORECASE),
}

# Combined pattern for stripping all directives (matches the whole line including newline)
ALL_DIRECTIVES_PATTERN = re.compile(
    r"^\s*%(?:seealso|nodoc)(?:\s+.*)?$\n?", re.MULTILINE | re.IGNORECASE
)


def extract_directives(docstring: str | None) -> DocDirectives:
    """
    Extract Great Docs directives from a docstring.

    Parameters
    ----------
    docstring
        The docstring to parse. Can be None.

    Returns
    -------
    DocDirectives
        A dataclass containing extracted directive values.

    Examples
    --------
    >>> doc = '''
    ... Short description.
    ...
    ... %seealso func_a, func_b
    ...
    ... Parameters
    ... ----------
    ... x : int
    ... '''
    >>> directives = extract_directives(doc)
    >>> directives.seealso
    [('func_a', ''), ('func_b', '')]
    """
    directives = DocDirectives()

    if not docstring:
        return directives

    # Extract %seealso (comma-separated list, each entry may have ": description")
    if match := DIRECTIVE_PATTERNS["seealso"].search(docstring):
        items: list[tuple[str, str]] = []
        for entry in match.group(1).split(","):
            entry = entry.strip()
            if not entry:
                continue
            # Split on first " : " or ": " to get name and optional description
            parts = re.split(r"\s*:\s*", entry, maxsplit=1)
            name = parts[0].strip()
            desc = parts[1].strip() if len(parts) > 1 else ""
            if name:
                items.append((name, desc))
        directives.seealso = items

    # Extract %nodoc
    if DIRECTIVE_PATTERNS["nodoc"].search(docstring):
        directives.nodoc = True

    return directives


def strip_directives(docstring: str | None) -> str:
    """
    Remove all Great Docs directives from a docstring.

    This produces a clean docstring for rendering in documentation,
    while the original docstring with directives remains in source
    code for IDE display.

    Parameters
    ----------
    docstring
        The docstring to clean. Can be None.

    Returns
    -------
    str
        The docstring with all %directive lines removed.

    Examples
    --------
    >>> doc = '''
    ... Short description.
    ...
    ... %seealso func_a
    ...
    ... Parameters
    ... ----------
    ... x : int
    ... '''
    >>> print(strip_directives(doc))
    Short description.
    <BLANKLINE>
    Parameters
    ----------
    x : int
    """
    if not docstring:
        return docstring or ""

    # Remove all directive lines
    cleaned = ALL_DIRECTIVES_PATTERN.sub("", docstring)

    # Clean up resulting multiple blank lines (more than 2 newlines -> 2 newlines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    # Strip leading/trailing whitespace but preserve internal structure
    return cleaned.strip()


def has_directives(docstring: str | None) -> bool:
    """
    Check if a docstring contains any Great Docs directives.

    Parameters
    ----------
    docstring
        The docstring to check.

    Returns
    -------
    bool
        True if any %directive pattern is found.
    """
    if not docstring:
        return False

    return bool(ALL_DIRECTIVES_PATTERN.search(docstring))
