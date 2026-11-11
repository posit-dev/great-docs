"""The built-in `%seealso` section directive"""

from __future__ import annotations

import re

import griffe as gf

from great_docs._source_refs import fenced_lines
from great_docs.hooks import on_object_resolved

_SEEALSO_RE = re.compile(
    r"^[^\S\r\n]*%seealso[^\S\r\n]+(.+?)[^\S\r\n]*$",
    re.MULTILINE,
)

_SEEALSO_LINE_RE = re.compile(r"^[ \t]*%seealso(?:[ \t]+.*)?[ \t]*$")
_EXCESS_GAP_RE = re.compile(r"\n{3,}")
_SEEALSO_ENTRY_NAME_RE = re.compile(r"\s*([\w.]+)")
_SEE_ALSO_HEADER_RE = re.compile(r"(?m)^See Also[ \t]*\n-{3,}[ \t]*$")
_SECTION_HEADER_RE = re.compile(r"(?m)^[^ \t\n].*\n-{3,}[ \t]*$")


def parse(docstring: str) -> list[tuple[str, str]]:
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


@on_object_resolved(priority=0)  # pyright: ignore[reportArgumentType]
def add_seealso(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
    """
    Add canonical cross-references to parser-ready docstring source

    Parameters
    ----------
    obj
        The resolved object.

    Returns
    -------
    The object with `%seealso` entries represented by one top-level section.
    """
    docstring = obj.docstring
    if docstring is not None:
        docstring.value = _normalize_seealso(docstring.value)
    return obj


def _normalize_seealso(text: str) -> str:
    """
    Represent eligible `%seealso` entries in one top-level source section

    Parameters
    ----------
    text
        Docstring source to normalize.

    Returns
    -------
    Source with canonical cross-references in a `See Also` section.
    """
    if "%seealso" not in text:
        return text

    cleaned, entries = _extract_seealso(text)
    if not entries:
        return cleaned
    return _merge_seealso(cleaned, _unique_entries(entries))


def _extract_seealso(text: str) -> tuple[str, list[tuple[str, str]]]:
    """
    Remove eligible directives and return their entries in source order

    Parameters
    ----------
    text
        Docstring source containing `%seealso`.

    Returns
    -------
    Cleaned source and the entries removed from it.
    """
    lines, fenced = fenced_lines(text)
    cleaned: list[str] = []
    entries: list[tuple[str, str]] = []

    for line, is_fenced in zip(lines, fenced):
        candidate = not is_fenced and "%seealso" in line
        if candidate and _SEEALSO_LINE_RE.match(line):
            entries.extend(parse(line))
        else:
            cleaned.append(line)

    value = _EXCESS_GAP_RE.sub("\n\n", "\n".join(cleaned))
    return value.strip(), entries


def _unique_entries(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """
    Keep the first canonical entry for each qualified name

    Parameters
    ----------
    entries
        Cross-references in source order.

    Returns
    -------
    Entries deduplicated by name.
    """
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for name, description in entries:
        if name not in seen:
            seen.add(name)
            unique.append((name, description))
    return unique


def _merge_seealso(text: str, entries: list[tuple[str, str]]) -> str:
    """
    Merge canonical entries into one top-level `See Also` section

    Parameters
    ----------
    text
        Directive-free docstring source.
    entries
        Unique cross-references in source order.

    Returns
    -------
    Source containing the merged top-level section.
    """
    match = _SEE_ALSO_HEADER_RE.search(text) if "See Also\n" in text else None
    if match is None:
        body = "\n".join(_entry_line(name, description) for name, description in entries)
        section = f"See Also\n--------\n{body}"
        return f"{text}\n\n{section}" if text else section

    body_start, body_end = _section_body_span(text, match.end())
    body = text[body_start:body_end].strip()
    seen = _existing_names(body)
    added: list[str] = []
    for name, description in entries:
        if name not in seen:
            seen.add(name)
            added.append(_entry_line(name, description))
    if not added:
        return text

    merged = "\n".join([body, *added]) if body else "\n".join(added)
    suffix = text[body_end:]
    separator = "\n\n" if suffix else ""
    return f"{text[:body_start]}{merged}{separator}{suffix}"


def _section_body_span(text: str, header_end: int) -> tuple[int, int]:
    """
    Locate the body occupied by one top-level NumPy-style section

    Parameters
    ----------
    text
        Complete docstring source.
    header_end
        Offset immediately after the section underline.

    Returns
    -------
    Start and end offsets for the section body.
    """
    body_start = header_end + 1 if text[header_end : header_end + 1] == "\n" else header_end
    next_header = _SECTION_HEADER_RE.search(text, body_start)
    body_end = next_header.start() if next_header is not None else len(text)
    return body_start, body_end


def _entry_line(name: str, description: str) -> str:
    """
    Format a See Also entry with its optional description

    Parameters
    ----------
    name
        The referenced object name.
    description
        An optional description of the referenced object.

    Returns
    -------
    A formatted See Also entry.
    """
    return f"{name} : {description}" if description else name


def _existing_names(contents: str) -> set[str]:
    """
    Collect qualified names already represented in a See Also body

    Parameters
    ----------
    contents
        The contents of a See Also section.

    Returns
    -------
    The qualified names represented in the section.
    """
    names: set[str] = set()
    for line in contents.splitlines():
        name_part = line.split(":", 1)[0]
        for part in name_part.split(","):
            if match := _SEEALSO_ENTRY_NAME_RE.match(part):
                names.add(match.group(1))
    return names
