"""
Resolved (output) shapes of the API-reference tree

Every class here is the fully-built, resolved counterpart of a `spec`
input node: a `Section` here holds rendered `Page`/`Doc` objects rather than
raw YAML, and so on down the tree. Produced by the API-reference resolver from
the input family defined in `spec.py`; consumed by `collect` and `write`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ._walkable import Walkable

if TYPE_CHECKING:
    import griffe as gf


@dataclass
class Doc(Walkable):
    """A resolved Python object ready to be rendered as documentation"""

    obj: gf.Object | gf.Alias
    name: str = ""
    anchor: str = ""
    signature_name: str = "relative"

    @classmethod
    def from_griffe(
        cls,
        name: str,
        obj: gf.Object | gf.Alias,
        members: list[Any] | None = None,
        anchor: str | None = None,
        flat: bool = False,
        signature_name: str = "relative",
    ) -> DocFunction | DocAttribute | DocClass | DocModule:
        if members is None:
            members = []

        kind = obj.kind.value
        anchor_val = obj.path if anchor is None else anchor

        kwargs: dict[str, Any] = {
            "name": name,
            "obj": obj,
            "anchor": anchor_val,
            "signature_name": signature_name,
        }

        if kind == "function":
            return DocFunction(**kwargs)
        elif kind == "attribute":
            return DocAttribute(**kwargs)
        elif kind == "class":
            return DocClass(members=members, flat=flat, **kwargs)
        elif kind == "module":
            return DocModule(members=members, flat=flat, **kwargs)

        raise TypeError(f"Cannot document object of kind: {obj.kind}")


@dataclass
class DocFunction(Doc):
    """Documentation node for a single Python function"""

    kind: str = "function"


@dataclass
class DocClass(Doc):
    """Documentation node for a Python class, including its member list"""

    kind: str = "class"
    members: list[DocClass | DocFunction | DocAttribute] = field(
        default_factory=list["DocClass | DocFunction | DocAttribute"]
    )
    flat: bool = False


@dataclass
class DocAttribute(Doc):
    """Documentation node for a Python attribute or variable"""

    kind: str = "attribute"


@dataclass
class DocModule(Doc):
    """Documentation node for a Python module, including its member list"""

    kind: str = "module"
    members: list[DocClass | DocFunction | DocAttribute | DocModule] = field(
        default_factory=list["DocClass | DocFunction | DocAttribute | DocModule"]
    )
    flat: bool = False


@dataclass
class SummaryItem(Walkable):
    """Name and description line for a summary table entry"""

    name: str = ""
    desc: str = ""


@dataclass
class Page(Walkable):
    """A single rendered page in the API reference"""

    kind: str = "page"
    path: str = ""
    summary: SummaryItem | None = None
    flatten: bool = False
    contents: list[DocClass | DocFunction | DocAttribute | DocModule] = field(
        default_factory=list[DocClass | DocFunction | DocAttribute | DocModule]
    )

    @property
    def obj(self) -> gf.Object | gf.Alias:
        if len(self.contents) == 1:
            return self.contents[0].obj
        raise ValueError(
            f".obj property assumes contents field is length 1, but it is {len(self.contents)}"
        )


@dataclass
class MemberPage(Page):
    """A page produced automatically for a single class or module member"""

    contents: list[Any] = field(default_factory=list[Any])


@dataclass
class Section(Walkable):
    """A section of content on the reference index page"""

    kind: str = "section"
    title: str | None = None
    subtitle: str | None = None
    desc: str | None = None
    contents: list[DocClass | DocFunction | DocAttribute | DocModule | Page] = field(
        default_factory=list[DocClass | DocFunction | DocAttribute | DocModule | Page]
    )


@dataclass
class Text(Walkable):
    """A block of free-form Markdown text embedded in a reference section"""

    kind: str = "text"
    contents: str = ""


@dataclass
class Link(Walkable):
    """A cross-reference link to a documented object"""

    obj: gf.Object | gf.Alias
    name: str = ""


Content = Section | Page | Doc | DocFunction | DocClass | DocAttribute | DocModule | Link | Text
