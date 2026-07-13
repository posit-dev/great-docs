"""
Built-in handlers for great-docs `%`-directives, registered on the pipeline events

`%nodoc` skips an object; `%seealso` merges its entries into the object's
See Also section. The `%nodoc` pattern is copied from `great_docs._directives`
(only the regex is needed); `%seealso` parsing and directive stripping reuse
that module's `extract_directives` / `strip_directives`.
"""

from __future__ import annotations

import re

import griffe as gf

from great_docs._directives import extract_directives, strip_directives
from great_docs.hooks import on_object_resolved

_NODOC_RE = re.compile(r"^\s*%nodoc(?:\s+(true|yes|1))?\s*$", re.MULTILINE | re.IGNORECASE)
_SEEALSO_TITLE = "see also"


@on_object_resolved
def exclude_nodoc(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias | None:
    """
    Skip an object whose docstring carries the `%nodoc` directive

    Parameters
    ----------
    obj
        The object just resolved from its reference.

    Returns
    -------
    The object, or `None` when its docstring carries `%nodoc`.
    """
    docstring = obj.docstring
    text = docstring.value if docstring is not None else None
    if text is not None and _NODOC_RE.search(text):
        return None
    return obj


@on_object_resolved
def add_seealso(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
    """
    Merge an object's `%seealso` entries into its See Also section

    Parameters
    ----------
    obj
        The object just resolved from its reference.

    Returns
    -------
    The same object. When its docstring carries `%seealso`, the directive line
    is removed and its entries are folded into the object's See Also section
    (merged with an existing one, deduped by name, or added as a new section).
    """
    docstring = obj.docstring
    if docstring is None:
        return obj

    entries = extract_directives(docstring.value).seealso
    if not entries:
        return obj

    # Drop the directive line(s), then reparse the cleaned prose so the parsed
    # sections match the value the renderer will read.
    docstring.value = strip_directives(docstring.value)
    docstring.__dict__.pop("parsed", None)
    sections = docstring.parsed

    existing = _find_see_also(sections)
    seen = _existing_names(existing.value.contents) if existing is not None else set()
    added: list[str] = []
    for name, desc in entries:
        if name in seen:
            continue
        seen.add(name)
        added.append(_entry_line(name, desc))

    if existing is not None:
        if added:
            existing.value.contents = "\n".join([existing.value.contents, *added])
    else:
        body = "\n".join(added)
        sections.append(gf.DocstringSectionAdmonition(kind="see-also", text=body, title="See Also"))

    return obj


def _entry_line(name: str, desc: str) -> str:
    """Format one See Also entry as a `name : desc` line, or bare `name` when undescribed"""
    return f"{name} : {desc}" if desc else name


def _find_see_also(
    sections: list[gf.DocstringSection],
) -> gf.DocstringSectionAdmonition | None:
    """Return the first See Also admonition among `sections`, or `None`"""
    for section in sections:
        if (
            isinstance(section, gf.DocstringSectionAdmonition)
            and (section.title or "").lower() == _SEEALSO_TITLE
        ):
            return section
    return None


def _existing_names(contents: str) -> set[str]:
    """Collect the leading qualified names already present in a See Also body"""
    names: set[str] = set()
    for line in contents.splitlines():
        name_part = line.split(":", 1)[0]
        for part in name_part.split(","):
            if match := re.match(r"\s*([\w.]+)", part):
                names.add(match.group(1))
    return names
