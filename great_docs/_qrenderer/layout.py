from __future__ import annotations

import copy
import logging
from collections.abc import Generator
from dataclasses import dataclass, field
from dataclasses import fields as dc_fields
from enum import Enum
from typing import Any, ClassVar, Literal, Optional, Union

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base classes
# ---------------------------------------------------------------------------


@dataclass
class _Base:
    """Any data class that might appear in the config."""

    def copy(self) -> _Base:
        """Return a shallow copy (mirrors pydantic .copy())."""
        return copy.copy(self)

    def _iter_fields(self) -> "Generator[tuple[str, object], None, None]":
        """Yield (field_name, value) pairs — replaces pydantic __iter__."""
        for f in dc_fields(self):
            yield f.name, getattr(self, f.name)


@dataclass
class _Structural(_Base):
    """A structural element, like an index Section or Page of docs."""


@dataclass
class _Docable(_Base):
    """An element meant to document something about a python object."""


@dataclass
class MISSING(_Base):
    """Represents a missing value.

    Note that this is used in cases where None is meaningful.
    """


@dataclass
class Layout(_Structural):
    """The layout of an API doc, which may include many pages."""

    title: str = "API Reference"
    description: Optional[str] = None
    sections: list[Section] = field(default_factory=list["Section"])
    package: Union[str, None, MISSING] = field(default_factory=MISSING)
    options: Optional[AutoOptions] = None

    def __post_init__(self) -> None:
        """Coerce raw dicts from YAML into proper layout objects.

        When constructed from YAML config, sections arrive as plain dicts.
        Pydantic used to coerce these automatically; with stdlib dataclasses
        we must do it explicitly.
        """
        coerced = []
        for item in self.sections:
            if isinstance(item, dict):
                # Convert contents items: strings/dicts → Auto objects
                raw_contents = item.get("contents", [])
                contents = [_auto_default(c) for c in raw_contents]
                coerced.append(
                    Section(
                        title=item.get("title"),
                        subtitle=item.get("subtitle"),
                        desc=item.get("desc"),
                        package=item.get("package", MISSING()),
                        contents=contents,
                    )
                )
            else:
                coerced.append(item)
        self.sections = coerced


# SubElements -----------------------------------------------------------------


@dataclass
class Section(_Structural):
    """A section of content on the reference index page."""

    kind: str = "section"
    title: Optional[str] = None
    subtitle: Optional[str] = None
    desc: Optional[str] = None
    package: Union[str, None, MISSING] = field(default_factory=MISSING)
    contents: list[Union[DocClass, DocFunction, DocAttribute, DocModule, Page]] = field(
        default_factory=list["Union[DocClass, DocFunction, DocAttribute, DocModule, Page]"]
    )
    options: Optional[AutoOptions] = None

    def __post_init__(self) -> None:
        if self.title is None and self.subtitle is None and not self.contents:
            raise ValueError("Section must specify a title, subtitle, or contents field")
        elif self.title is not None and self.subtitle is not None:
            raise ValueError("Section cannot specify both title and subtitle fields.")


@dataclass
class SummaryDetails(_Base):
    """Details that can be used in a summary table."""

    name: str = ""
    desc: str = ""


@dataclass
class Page(_Structural):
    """A page of documentation."""

    kind: str = "page"
    path: str = ""
    package: Union[str, None, MISSING] = field(default_factory=MISSING)
    summary: Optional[SummaryDetails] = None
    flatten: bool = False
    contents: list[Union[DocClass, DocFunction, DocAttribute, DocModule]] = field(
        default_factory=list["Union[DocClass, DocFunction, DocAttribute, DocModule]"]
    )

    @property
    def obj(self):
        if len(self.contents) == 1:
            return self.contents[0].obj
        raise ValueError(
            f".obj property assumes contents field is length 1, but it is {len(self.contents)}"
        )


@dataclass
class MemberPage(Page):
    """A page created as a result of documenting a member on a class or module."""

    contents: list = field(default_factory=list)


@dataclass
class Interlaced(_Docable):
    """A group of objects, whose documentation will be interlaced."""

    kind: str = "interlaced"
    package: Union[str, None, MISSING] = field(default_factory=MISSING)
    contents: list = field(default_factory=list)

    @property
    def name(self):
        if not self.contents:
            raise AttributeError(
                f"Cannot get property name for object of type {type(self)}."
                " There are no content elements."
            )

        return self.contents[0].name


@dataclass
class Text(_Docable):
    kind: str = "text"
    contents: str = ""


class ChoicesChildren(Enum):
    """Options for how child members of a class or module should be documented."""

    embedded = "embedded"
    flat = "flat"
    separate = "separate"
    linked = "linked"


SignatureOptions = Literal["full", "short", "relative"]


@dataclass
class AutoOptions(_Base):
    """Options available for Auto content layout element."""

    signature_name: str = "relative"
    members: Optional[list[str]] = None
    include_private: bool = False
    include_imports: bool = False
    include_empty: bool = False
    include_inherited: bool = False

    include_attributes: bool = True
    include_classes: bool = True
    include_functions: bool = True

    include: Optional[str] = None
    exclude: Optional[list[str]] = None
    dynamic: Union[None, bool, str] = None
    children: ChoicesChildren = ChoicesChildren.embedded
    package: Union[str, None, MISSING] = field(default_factory=MISSING)
    member_order: str = "alphabetical"
    member_options: Optional[AutoOptions] = None

    # Tracks which fields were explicitly passed (replaces pydantic PrivateAttr)
    _fields_specified: tuple = field(default=(), init=False, repr=False, compare=False)

    # Class-level defaults used by _non_default_entries
    _field_defaults: ClassVar[dict[str, Any]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Will be populated after class is fully defined
        cls._field_defaults = {}

    def __init__(self, **kwargs):
        # We need a custom __init__ to track which fields were specified
        # First, get defaults for all fields
        for f in dc_fields(self.__class__):
            if f.name.startswith("_"):
                continue
            if f.name in kwargs:
                object.__setattr__(self, f.name, kwargs[f.name])
            elif f.default is not field().default:
                object.__setattr__(self, f.name, f.default)
            elif f.default_factory is not field().default_factory:
                object.__setattr__(self, f.name, f.default_factory())
            # else: field has no default — it must be in kwargs or will error
        object.__setattr__(self, "_fields_specified", tuple(kwargs.keys()))


@dataclass
class Auto(AutoOptions):
    """Configure a python object to document."""

    kind: str = "auto"
    name: str = ""


def _auto_default(value: Union[str, dict]) -> Auto:
    """Factory replacing pydantic __root__ model _AutoDefault.

    Coerce a string or dict from YAML config into an Auto instance.
    """
    if isinstance(value, dict):
        return Auto(**value)
    return Auto(name=value)


# For backwards compat — users of the old _AutoDefault can call this instead
_AutoDefault = _auto_default


@dataclass
class Link(_Docable):
    """A link to an object."""

    name: str = ""
    obj: Any = None  # dc.Object | dc.Alias


@dataclass
class Doc(_Docable):
    """A python object to be documented."""

    name: str = ""
    obj: Any = None  # dc.Object | dc.Alias
    anchor: str = ""
    signature_name: str = "relative"

    @classmethod
    def from_griffe(
        cls,
        name,
        obj,
        members=None,
        anchor: str = None,
        flat: bool = False,
        signature_name: str = "relative",
    ):
        if members is None:
            members = []

        kind = obj.kind.value
        anchor = obj.path if anchor is None else anchor

        kwargs = {
            "name": name,
            "obj": obj,
            "anchor": anchor,
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

        raise TypeError(f"Cannot handle auto for object kind: {obj.kind}")


@dataclass
class DocFunction(Doc):
    """Document a python function."""

    kind: str = "function"


@dataclass
class DocClass(Doc):
    """Document a python class."""

    kind: str = "class"
    members: list[Union[DocClass, DocFunction, DocAttribute]] = field(
        default_factory=list["Union[DocClass, DocFunction, DocAttribute]"]
    )
    flat: bool = False


@dataclass
class DocAttribute(Doc):
    """Document a python attribute."""

    kind: str = "attribute"


@dataclass
class DocModule(Doc):
    """Document a python module."""

    kind: str = "module"
    members: list[Union[DocClass, DocFunction, DocAttribute, DocModule]] = field(
        default_factory=list["Union[DocClass, DocFunction, DocAttribute, DocModule]"]
    )
    flat: bool = False


# Type aliases (no discriminator needed without pydantic) ---------------------

SectionElement = Union[Section, Page]
"""Entry in the sections list."""

ContentElement = Union[Page, Section, Interlaced, Text, Auto]
"""Entry in the contents list."""

ContentList = list

# Item ----


@dataclass
class Item(_Base):
    """Information about a documented object, including a URI to its location."""

    name: str = ""
    obj: Any = None  # dc.Object | dc.Alias
    uri: Optional[str] = None
    dispname: Optional[str] = None
