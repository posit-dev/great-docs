"""
Built-in handlers for great-docs `%`-directives, registered on the pipeline events

`%nodoc` skips an object; `%seealso` (later) resolves cross-references and emits
a See Also section. The directive regexes are copied from
`great_docs._directives` — only the pattern is needed here, not that module's
fuller `DocDirectives` extraction.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from great_docs.hooks import on_object_resolved

if TYPE_CHECKING:
    import griffe as gf

_NODOC_RE = re.compile(r"^\s*%nodoc(?:\s+(true|yes|1))?\s*$", re.MULTILINE | re.IGNORECASE)


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
