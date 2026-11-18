"""
Presentation of classes and dataclasses

A class shows its constructor signature, docstring sections and member groups. A
dataclass documents each field once, as a constructor parameter, rather than again
as an attribute.
"""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

import griffe as gf

from .._docstring_sections import (
    DCDocstringSectionInitParameters,
    DCDocstringSectionParameterAttributes,
)
from .callables import CallableRendererMixin
from .members import MembersRendererMixin
from .objects import ObjectRenderer

if TYPE_CHECKING:
    from .. import content


class ClassRenderer(MembersRendererMixin, CallableRendererMixin, ObjectRenderer):
    """
    The presentation of a class, with its constructor signature and member groups

    The description shows the subject, then the Usage and source row and the
    constructor signature. The body shows the docstring sections followed by member
    groups. For a dataclass without an authored `Parameters` or `Attributes`
    section, the renderer generates `Parameter Attributes` and
    `Init Parameters` sections from the constructor parameters.
    """

    def __post_init__(self) -> None:
        """Narrow `doc` and `obj` to class documentation"""
        super().__post_init__()
        self.doc: content.DocClass = self.doc
        self.obj: gf.Class = self.obj

    @cached_property
    def is_dataclass(self):
        """
        Whether the class object is a dataclass
        """
        return "dataclass" in self.obj.labels

    @cached_property
    def docstring_sections_content(self):
        """
        The docstring sections, with generated sections for a dataclass's fields

        Nothing is added when an authored `Parameters` or `Attributes` section already
        documents the fields. Otherwise the `Parameter Attributes` and `Init Parameters`
        sections go after the leading text and before the other sections.
        """
        items = super().docstring_sections_content
        titles = set(item[0] for item in items)
        # Authored field sections already cover the same dataclass parameters.
        if (
            not self.is_dataclass
            or "Parameters" in titles
            or "Attributes" in titles
            or not len(self.parameters)
        ):
            return items

        # Create and insert Parameter Attributes
        idx = 1 if items and items[0][0] == "Text" else 0
        if len(self.parameter_attributes):
            lst = [
                gf.DocstringParameter(
                    p.name,
                    description=p.docstring.value if p.docstring else "",
                    annotation=p.annotation,
                    value=p.default,
                )
                for p in self.parameter_attributes
            ]
            params = DCDocstringSectionParameterAttributes(lst, "Parameter Attributes")
            items.insert(idx, (params.title, params))
            idx += 1

        # Create and insert Init Parameters
        if len(self.init_parameters):
            lst = [
                gf.DocstringParameter(
                    p.name,
                    description=p.docstring.value if p.docstring else "",
                    annotation=p.annotation,
                    value=p.default,
                )
                for p in self.init_parameters
            ]
            params = DCDocstringSectionInitParameters(lst, "Init Parameters")
            items.insert(idx, (params.title, params))

        return items

    @cached_property
    def parameter_attributes(self) -> gf.Parameters:
        """
        The dataclass's signature parameters that are also annotated attributes

        An ordinary class has none.
        """
        if not self.is_dataclass:
            return gf.Parameters()

        lst = [
            p for p in self.parameters if p.name in self.obj.attributes and p.annotation is not None
        ]
        return gf.Parameters(*lst)

    @cached_property
    def init_parameters(self) -> gf.Parameters:
        """
        The dataclass's signature parameters that are not attributes

        An ordinary class has none.
        """
        if not self.is_dataclass:
            return gf.Parameters()

        lst = [p for p in self.parameters if p.name not in self.obj.attributes]
        return gf.Parameters(*lst)
