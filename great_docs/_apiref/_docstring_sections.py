"""
great-docs extensions to griffe's docstring model

Docstring sections for documenting dataclasses (the `DC` prefix); for
everything griffe already provides, import `griffe` directly.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import griffe as gf

__all__ = (
    "DCDocstringSection",
    "DCDocstringSectionInitParameters",
    "DCDocstringSectionKind",
    "DCDocstringSectionParameterAttributes",
)


class DCDocstringSectionKind(str, Enum):
    """
    Enumeration of the docstring section kinds specific to dataclasses
    """

    init_parameters = "init parameters"
    """Init only parameters of a dataclass"""

    parameter_attributes = "parameter attributes"
    """Parameters and at the same time attributes of a dataclass"""


class DCDocstringSection:
    """
    A docstring section specific to dataclasses
    """

    kind: DCDocstringSectionKind  # pragma: no cover
    """The section kind."""

    def __init__(self, value: list[gf.DocstringParameter], title: str):
        self.value = value
        self.title = title

    def __bool__(self) -> bool:
        """Whether this section has a true-ish value."""
        return bool(self.value)


class DCDocstringSectionParameterAttributes(DCDocstringSection):
    """
    A parameter attributes section (of a dataclass)
    """

    kind: DCDocstringSectionKind = DCDocstringSectionKind.parameter_attributes


class DCDocstringSectionInitParameters(DCDocstringSection):
    """
    An init parameters section (of a dataclass)
    """

    kind: DCDocstringSectionKind = DCDocstringSectionKind.init_parameters
