"""
Resolved (output) shapes of the API-reference tree

Each node pairs a loaded Griffe object with its configured name, anchor and selected
members, and keeps the prepared documentation apart from how it is rendered.
`Doc.from_griffe` builds one node without finding members; resolution or recursive
conversion adds the members before manifests and renderers read the tree.
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
    """The loaded object, or the alias it is documented under, with its prepared documentation"""
    name: str = ""
    """The name the object is documented under, which the `doc` name format shows"""
    anchor: str = ""
    """The object's anchor on its page"""
    signature_name: str = "relative"
    """How a callable's name is written in its signature"""

    @classmethod
    def from_griffe(
        cls,
        name: str,
        obj: gf.Object | gf.Alias,
        members: list[Any] | None = None,
        anchor: str | None = None,
        signature_name: str = "relative",
        fields: list[DocAttribute] | None = None,
    ) -> DocFunction | DocAttribute | DocTypeAlias | DocClass | DocModule:
        """
        Build a documentation node for a loaded object

        Choose the node class from the object's Griffe kind. A class or module node keeps
        the members it is given. This method finds no members and runs no object or
        docstring hooks, so callers prepare objects and drop exclusions first.

        Parameters
        ----------
        name
            The name to document the object under, which may differ from its canonical
            name.
        obj
            The loaded object or alias.
        members
            The selected members of a class or module node, or `None` for none.
        anchor
            The anchor, or `None` to use the object's qualified path.
        signature_name
            How a callable's name is written in its signature.
        fields
            The attributes a dataclass node documents as constructor parameters, or
            `None` for none.

        Returns
        -------
        :
            A node of the class that matches the object's kind.

        Raises
        ------
        TypeError
            If the object has no supported documentation kind.
        """
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
        elif kind == "type alias":
            return DocTypeAlias(**kwargs)
        elif kind == "class":
            return DocClass(members=members, fields=fields or [], **kwargs)
        elif kind == "module":
            return DocModule(members=members, **kwargs)

        raise TypeError(f"Cannot document object of kind: {obj.kind}")


@dataclass
class DocFunction(Doc):
    """Documentation node for a single Python function"""

    kind: str = "function"


@dataclass
class DocClass(Doc):
    """Documentation node for a Python class, including its member list"""

    kind: str = "class"
    members: list[DocClass | DocFunction | DocAttribute | DocTypeAlias] = field(
        default_factory=list["DocClass | DocFunction | DocAttribute | DocTypeAlias"]
    )
    """The selected members, documented on this page or on member pages of their own"""
    fields: list[DocAttribute] = field(default_factory=list["DocAttribute"])
    """
    The selected attributes that the class documents as constructor parameters

    A dataclass documents each of these fields with its parameter, so they stay on the
    class's page whatever the member placement and are never members.
    """


@dataclass
class DocAttribute(Doc):
    """Documentation node for a Python attribute or variable"""

    kind: str = "attribute"


@dataclass
class DocTypeAlias(Doc):
    """Documentation node for a PEP 695 type alias"""

    kind: str = "type alias"


@dataclass
class DocModule(Doc):
    """Documentation node for a Python module, including its member list"""

    kind: str = "module"
    members: list[DocClass | DocFunction | DocAttribute | DocTypeAlias | DocModule] = field(
        default_factory=list["DocClass | DocFunction | DocAttribute | DocTypeAlias | DocModule"]
    )
    """The selected members, documented on this page or on member pages of their own"""


@dataclass
class SummaryItem(Walkable):
    """Name and description line for a summary table entry"""

    name: str = ""
    """The label shown for a page in an index summary"""
    desc: str = ""
    """The description shown beside the label"""


@dataclass
class Page(Walkable):
    """
    A reference page documenting one or more objects

    A page with one object takes its title from that object. In the index, a page with
    several objects shows its explicit summary or, when flattened, a row for each object.
    """

    kind: str = "page"
    path: str = ""
    """The page's configured path, without a filename suffix"""
    summary: SummaryItem | None = None
    """The page's label and description in the index, or `None` to take them from its objects"""
    flatten: bool = False
    """Whether the index lists each object of a multiple-object page separately"""
    contents: list[DocClass | DocFunction | DocAttribute | DocTypeAlias | DocModule] = field(
        default_factory=list[DocClass | DocFunction | DocAttribute | DocTypeAlias | DocModule]
    )
    """The objects documented on this page"""

    @property
    def obj(self) -> gf.Object | gf.Alias:
        """
        The page's only object

        Raises `ValueError` when the page has no object or several.
        """
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
    """The section heading, or `None`"""
    subtitle: str | None = None
    """The subsection heading, or `None`"""
    desc: str | None = None
    """The section description, or `None`"""
    contents: list[DocClass | DocFunction | DocAttribute | DocModule | Page] = field(
        default_factory=list[DocClass | DocFunction | DocAttribute | DocModule | Page]
    )
    """The section's pages, objects and text, in configured order"""


@dataclass
class Text(Walkable):
    """A block of free-form Markdown text embedded in a reference section"""

    kind: str = "text"
    contents: str = ""


Content = Section | Page | Doc | DocFunction | DocClass | DocAttribute | DocModule | Text
