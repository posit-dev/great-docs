"""
The built-in directive names and handlers available to Great Docs

Importing this package registers `%nodoc` before `%seealso` so exclusion
precedes section enrichment.
"""

from . import _nodoc as _nodoc
from . import _nodoc_param as _nodoc_param
from . import _rst_directives as _rst_directives
from . import _seealso as _seealso  # noqa: E402
from ._callouts import CALLOUT_DIRECTIVES

DIRECTIVES = CALLOUT_DIRECTIVES | {"nodoc", "nodoc_param", "seealso"}

__all__ = ["DIRECTIVES"]
