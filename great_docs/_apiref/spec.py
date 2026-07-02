"""
Our representation of the parts in the api-reference in the config file

i.e The specification of what is to be documented.
Every class here is a `spec`-level node from the `api-reference:` config:
strings and dicts that name an object to document.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import fields as dc_fields
from enum import Enum
from typing import Any, cast

from ._walkable import MISSING, _Walkable  # pyright: ignore[reportPrivateUsage]


class ChildrenStyle(Enum):
    """Rendering style for child members of a class or module"""

    embedded = "embedded"
    flat = "flat"
    separate = "separate"
    linked = "linked"


@dataclass
class SpecOptions(_Walkable):
    """Documentation options that apply to a `SpecObject` element and, optionally, its members"""

    signature_name: str = "relative"
    members: list[str] | None = None
    include_private: bool = False
    include_imports: bool = False
    include_empty: bool = False
    include_inherited: bool = False

    include_attributes: bool = True
    include_classes: bool = True
    include_functions: bool = True

    include: str | None = None
    exclude: list[str] | None = None
    dynamic: bool | str | None = None
    children: ChildrenStyle = ChildrenStyle.embedded
    package: str | MISSING | None = field(default_factory=MISSING)
    member_order: str = "alphabetical"
    member_options: SpecOptions | None = None

    # Names of fields the caller explicitly supplied — empty when every value
    # comes from a default.  Used by option-merging logic to distinguish
    # "caller set this to False" from "this is the default False".
    _fields_specified: tuple[str, ...] = field(default=(), init=False, repr=False, compare=False)

    def __init__(self, **kwargs: object) -> None:
        # Custom __init__ to record which fields the caller supplied explicitly.
        for f in dc_fields(self.__class__):
            if f.name.startswith("_"):
                continue
            if f.name in kwargs:
                object.__setattr__(self, f.name, kwargs[f.name])
            elif f.default is not field().default:
                object.__setattr__(self, f.name, f.default)
            elif f.default_factory is not field().default_factory:
                object.__setattr__(self, f.name, f.default_factory())  # type: ignore[misc]
            # else: field has no default — it must be in kwargs or will error
        object.__setattr__(self, "_fields_specified", tuple(kwargs.keys()))


@dataclass
class SpecObject(SpecOptions):
    """A Python object to be located and documented, specified by name"""

    kind: str = "object"
    name: str = ""


@dataclass
class SpecText(_Walkable):
    """A block of free-form Markdown text embedded in a reference section"""

    kind: str = "text"
    contents: str = ""


@dataclass
class SpecSection(_Walkable):
    """A section of the reference index page, as written in the config"""

    kind: str = "section"
    title: str | None = None
    subtitle: str | None = None
    desc: str | None = None
    package: str | MISSING | None = field(default_factory=MISSING)
    # `SpecEntry` is defined below (it unions this class), so the factory
    # string is required — the name is not yet bound here.
    contents: list[SpecEntry] = field(default_factory=list["SpecEntry"])
    options: SpecOptions | None = None

    def __post_init__(self) -> None:
        if self.title is None and self.subtitle is None and not self.contents:
            raise ValueError("Section must specify a title, subtitle, or contents field")
        elif self.title is not None and self.subtitle is not None:
            raise ValueError("Section cannot specify both title and subtitle fields.")
        # Raw YAML entries (strings/dicts) become `SpecObject`; already-built
        # nodes pass through unchanged.
        raw_contents = cast("list[Any]", self.contents)
        self.contents = cast(
            "list[SpecEntry]",
            [c if isinstance(c, _Walkable) else _coerce_spec_object(c) for c in raw_contents],
        )


SpecEntry = SpecSection | SpecObject | SpecText


def _coerce_spec_object(value: str | dict[str, Any]) -> SpecObject:
    """Coerce a YAML string or dict entry into a `SpecObject`"""
    if isinstance(value, dict):
        return SpecObject(**value)
    return SpecObject(name=value)
