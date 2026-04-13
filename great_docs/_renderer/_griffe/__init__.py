from __future__ import annotations

try:
    from griffe import (  # noqa: F401
        AliasResolutionError,
        GriffeLoader,
        LinesCollection,
        ModulesCollection,
        Parser,
        parse,
        parse_numpy,
    )
except ImportError:
    # Older griffe versions (< 1.0) don't re-export everything at top level
    from griffe._internal.collections import (  # type: ignore[no-redef]  # noqa: F401,E501
        LinesCollection,
        ModulesCollection,
    )
    from griffe.docstrings.numpy import (
        parse as parse_numpy,  # type: ignore[no-redef]  # noqa: F401,E501
    )
    from griffe.docstrings.parsers import Parser, parse  # type: ignore[no-redef]  # noqa: F401
    from griffe.exceptions import AliasResolutionError  # type: ignore[no-redef]  # noqa: F401
    from griffe.loader import GriffeLoader  # type: ignore[no-redef]  # noqa: F401

from . import (
    dataclasses,  # noqa: F401
    docstrings,  # noqa: F401
    expressions,  # noqa: F401
)
from .docstrings import (
    DCDocstringSectionInitParameters,
    DCDocstringSectionParameterAttributes,
)
from .enumerations import DCDocstringSectionKind

__all__ = (
    "DCDocstringSectionKind",
    "DCDocstringSectionParameterAttributes",
    "DCDocstringSectionInitParameters",
)
