"""The built-in `%nodoc` exclusion directive"""

from __future__ import annotations

import re

import griffe as gf

from great_docs.hooks import on_object_resolved

_NODOC_RE = re.compile(r"^\s*%nodoc(?:\s+(true|yes|1))?\s*$", re.MULTILINE | re.IGNORECASE)


@on_object_resolved(priority=-100)  # pyright: ignore[reportArgumentType]
def exclude_nodoc(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias | None:
    """
    Skip an object whose docstring carries the `%nodoc` directive

    Parameters
    ----------
    obj
        The resolved object.

    Returns
    -------
    :
        The object, or `None` when its docstring carries `%nodoc`.
    """
    docstring = obj.docstring
    text = docstring.value if docstring is not None else None
    if text is not None and _NODOC_RE.search(text):
        return None
    return obj
