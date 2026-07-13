"""Low-level helpers shared across great-docs modules, free of import side effects"""

from __future__ import annotations

import re

_SEEALSO_RE = re.compile(
    r"^[^\S\r\n]*%seealso[^\S\r\n]+(.+?)[^\S\r\n]*$",
    re.MULTILINE,
)


def parse_seealso(docstring: str) -> list[tuple[str, str]]:
    """
    Parse the `%seealso` directive of a docstring into `(name, description)` pairs

    The directive is a comma-separated list of entries, each an optionally
    `name : description` pair. Undescribed entries get an empty description;
    entries with a blank name are dropped. Returns an empty list when no
    `%seealso` directive is present.
    """
    entries: list[tuple[str, str]] = []
    for match in _SEEALSO_RE.finditer(docstring):
        for entry in match.group(1).split(","):
            name, _, desc = entry.partition(":")
            name = name.strip()
            if name:
                entries.append((name, desc.strip()))
    return entries
