from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

import griffe as gf

from .._griffe.docstrings import (
    DCDocstringSectionInitParameters,
    DCDocstringSectionParameterAttributes,
)
from .doc import RenderDoc
from .mixin_call import RenderDocCallMixin
from .mixin_members import RenderDocMembersMixin

if TYPE_CHECKING:
    from quartodoc import layout


class __RenderDocClass(RenderDocMembersMixin, RenderDocCallMixin, RenderDoc):
    """
    Render documentation for a class (layout.DocClass)
    """

    def __post_init__(self):
        super().__post_init__()
        # We narrow the type with a TypeAlias since we do not expect
        # any subclasses to have narrower types
        self.doc: layout.DocClass = self.doc
        self.obj: gf.Class = self.obj

    @cached_property
    def is_dataclass(self):
        """
        Return True if the class object is a dataclass
        """
        return "dataclass" in self.obj.labels

    @cached_property
    def attributes(self) -> list[layout.DocAttribute]:
        """
        Override to exclude dataclass parameters
        """
        attributes = super().attributes
        if self.is_dataclass:
            params = {p.name for p in self.parameters}
            attributes = [a for a in attributes if a.name not in params]
        return attributes

    @cached_property
    def sections_content(self):
        items = super().sections_content
        titles = set(item[0] for item in items)
        if not self.is_dataclass or "Parameters" in titles or not len(self.parameters):
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
        if not self.is_dataclass:
            return gf.Parameters()

        lst = [
            p for p in self.parameters if p.name in self.obj.attributes and p.annotation is not None
        ]
        return gf.Parameters(*lst)

    @cached_property
    def init_parameters(self) -> gf.parameters:
        if not self.is_dataclass:
            return gf.Parameters()

        lst = [p for p in self.parameters if p.name not in self.obj.attributes]
        return gf.Parameters(*lst)


class RenderDocClass(__RenderDocClass):
    """
    Extend Rendering of a layout.DocClass object
    """
