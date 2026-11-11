"""Low-level helpers shared across great-docs modules, free of import side effects"""

from __future__ import annotations

import re

_SEEALSO_RE = re.compile(
    r"^[^\S\r\n]*%seealso[^\S\r\n]+(.+?)[^\S\r\n]*$",
    re.MULTILINE,
)
_FENCE_RE = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})(?P<info>.*)$")


def fenced_lines(text: str) -> tuple[list[str], list[bool]]:
    """
    Split source text and identify lines contained by Markdown code fences

    Parameters
    ----------
    text
        Source text to classify.

    Returns
    -------
    Source lines and a mask marking opening fences, fenced content, and
    closing fences.
    """
    lines = text.splitlines()
    if "```" not in text and "~~~" not in text:
        return lines, [False] * len(lines)

    fenced: list[bool] = []
    fence_char = ""
    fence_length = 0

    for line in lines:
        may_be_fence = "`" in line or "~" in line
        match = _FENCE_RE.match(line) if may_be_fence else None
        if not fence_char:
            if match is None:
                fenced.append(False)
                continue
            fence = match.group("fence")
            if fence.startswith("`") and "`" in match.group("info"):
                fenced.append(False)
                continue
            fence_char = fence[0]
            fence_length = len(fence)
            fenced.append(True)
            continue

        fenced.append(True)
        stripped = line.lstrip()
        closing_length = len(stripped) - len(stripped.lstrip(fence_char))
        if closing_length >= fence_length and not stripped[closing_length:].strip():
            fence_char = ""
            fence_length = 0

    return lines, fenced


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
