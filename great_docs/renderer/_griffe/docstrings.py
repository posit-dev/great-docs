from __future__ import annotations

from typing import TYPE_CHECKING

from .enumerations import DCDocstringSectionKind

if TYPE_CHECKING:
    import griffe as gf


class DCDocstringSection:
    """
    This class represents a docstring section specific to dataclasses
    """

    kind: DCDocstringSectionKind
    """The section kind."""

    def __init__(self, value: list[gf.DocstringParameter], title: str):
        self.value = value
        self.title = title

    def __bool__(self) -> bool:
        """Whether this section has a true-ish value."""
        return bool(self.value)


class DCDocstringSectionParameterAttributes(DCDocstringSection):
    """
    This class represents a parameter attributes section (of a dataclass)
    """

    kind: DCDocstringSectionKind = DCDocstringSectionKind.parameter_attributes


class DCDocstringSectionInitParameters(DCDocstringSection):
    """
    This class represents an init parameters section (of a dataclass)
    """

    kind: DCDocstringSectionKind = DCDocstringSectionKind.init_parameters
