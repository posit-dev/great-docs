"""
Our representation of the parts in the api-reference in the config file

i.e The specification of what is to be documented.
Every class here is a `spec`-level node from the `api-reference:` config:
strings and dicts that name an object to document.
"""

from __future__ import annotations

import dataclasses
import re
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from dataclasses import fields as dc_fields
from functools import partial
from typing import Any, Final, Self, cast

from ._walkable import MISSING, MissingType, Walkable
from .introspect import validate_dynamic


def _validate_members(members: list[str] | None, owner: object) -> None:
    """
    Reject member names that contain a module separator

    Parameters
    ----------
    members
        Names relative to the documented object, or `None` for no explicit list.
    owner
        Name of the documented object, or `None` for shared options.

    Raises
    ------
    ValueError
        If a member name contains `:`. Module separators are only valid in
        top-level entry names.
    """
    for member in members or ():
        if ":" in member:
            of_owner = f" of `{owner}`" if owner is not None else ""
            raise ValueError(
                f"Member `{member}`{of_owner} contains `:`. Member names must be "
                "relative to their parent object and cannot include a module separator."
            )


@dataclass(init=False)
class SpecOptions(Walkable):
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
    dynamic: bool | None = None
    members_on_same_page: bool = True
    package: str | MissingType | None = MISSING
    member_order: str = "alphabetical"
    member_options: SpecOptions | None = None

    # Names of fields the caller explicitly supplied — empty when every value
    # comes from a default.  Used by option-merging logic to distinguish
    # "caller set this to False" from "this is the default False".
    _fields_specified: tuple[str, ...] = field(default=(), init=False, repr=False, compare=False)

    def __init__(self, **kwargs: object) -> None:
        if "inline_methods" in kwargs:
            raise ValueError(
                "Use `members_on_same_page` on reference entries. "
                "Use `inline_methods` only as a global setting."
            )
        if "children" in kwargs:
            raise ValueError(
                "`children` is no longer supported. Set `members_on_same_page: false` "
                "to give each member a page, or use `members` to select which members to document."
            )
        if "members_on_same_page" in kwargs and not isinstance(
            kwargs["members_on_same_page"], bool
        ):
            raise ValueError("Per-entry `members_on_same_page` must be true or false.")
        # Custom __init__ to record which fields the caller supplied explicitly.
        # Subclasses must be decorated with `@dataclass(init=False)`; a plain
        # `@dataclass` regenerates `__init__` and leaves `_fields_specified`
        # permanently empty.
        field_names = {f.name for f in dc_fields(self.__class__) if not f.name.startswith("_")}
        if unknown := kwargs.keys() - field_names:
            names = ", ".join(sorted(unknown))
            raise TypeError(
                f"{self.__class__.__name__}() got unexpected keyword argument(s): {names}"
            )
        for f in dc_fields(self.__class__):
            if f.name.startswith("_"):
                continue
            if f.name in kwargs:
                object.__setattr__(self, f.name, kwargs[f.name])
            elif f.default is not dataclasses.MISSING:
                object.__setattr__(self, f.name, f.default)
            elif f.default_factory is not dataclasses.MISSING:
                object.__setattr__(self, f.name, f.default_factory())
            # else: field has no default — it must be in kwargs or will error
        object.__setattr__(self, "_fields_specified", tuple(kwargs.keys()))
        validate_dynamic(self.dynamic, allow_none=True)
        _validate_members(self.members, kwargs.get("name"))

    def replace(self, **changes: object) -> Self:
        """Return a copy with the given fields replaced

        A replaced field counts as caller-specified from then on; the
        untouched fields keep their original specified/default standing.
        (`dataclasses.replace` would instead re-run `__init__` with every
        field and mark them all as specified.)
        """
        if "dynamic" in changes:
            validate_dynamic(changes["dynamic"], allow_none=True)
        if "members_on_same_page" in changes and not isinstance(
            changes["members_on_same_page"], bool
        ):
            raise ValueError("Per-entry `members_on_same_page` must be true or false.")

        new = self.copy()
        for name, value in changes.items():
            object.__setattr__(new, name, value)
        specified = dict.fromkeys((*self._fields_specified, *changes))
        object.__setattr__(new, "_fields_specified", tuple(specified))
        return new

    def with_defaults(self, base: SpecOptions | None) -> Self:
        """
        Default this element's unspecified fields to `base`'s values

        A field the caller set explicitly — even to its default value —
        keeps this element's value; every other field takes the value
        `base` was explicitly given.
        """
        if base is None:
            return self
        inherited = {
            name: getattr(base, name)
            for name in base._fields_specified
            if name not in self._fields_specified
        }
        return self.replace(**inherited)


@dataclass(init=False)
class SpecObject(SpecOptions):
    """A Python object to be located and documented, specified by name"""

    kind: str = "object"
    name: Final[str] = ""

    # A page path assigned by `unique_page_paths()` when the name-derived one
    # would share a file with another entry on a case-insensitive filesystem.
    _page_path: str | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def page_path(self) -> str:
        """
        Return the entry's reference page path without a directory or suffix

        Replace the module separator in `module:Item` with a dot to produce
        `module.Item`. Keep the entry name unchanged for object lookup. A path
        assigned by `with_page_path()` takes precedence.
        """
        if self._page_path is not None:
            return self._page_path
        return self.name.replace(":", ".")

    def with_page_path(self, path: str) -> Self:
        """Return a copy whose reference page is written to `path`"""
        new = self.copy()
        object.__setattr__(new, "_page_path", path)
        return new


@dataclass
class SpecText(Walkable):
    """A block of free-form Markdown text embedded in a reference section"""

    kind: str = "text"
    contents: str = ""


@dataclass
class SpecSection(Walkable):
    """A section of the reference index page, as written in the config"""

    kind: str = "section"
    title: str | None = None
    subtitle: str | None = None
    desc: str | None = None
    package: str | MissingType | None = MISSING
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
            [c if isinstance(c, Walkable) else _coerce_spec_object(c) for c in raw_contents],
        )


SpecEntry = SpecSection | SpecObject | SpecText


def _coerce_spec_object(value: str | dict[str, Any]) -> SpecObject:
    """Coerce a YAML string or dict entry into a `SpecObject`"""
    if isinstance(value, dict):
        return SpecObject(**value)
    return SpecObject(name=value)


def claim_page_path(
    path: str, claimed: dict[str, str], label: Callable[[], str | None] | None = None
) -> str:
    """
    Claim a reference page path that no other page shares on a case-insensitive filesystem

    Two pages whose paths differ only by case (a `template()` function and a
    `Template` class) would be written to the same file on macOS and Windows,
    so the later page would silently replace the earlier one. The first path
    claimed keeps its name. A later path that matches it case-insensitively is
    suffixed with the label shown on its page (`template-function`), then with
    a number if that is taken too (`FOO-class-2`). Claiming the exact same path
    twice returns it unchanged.

    Parameters
    ----------
    path
        The page path to claim, without a directory or suffix.
    claimed
        Paths claimed so far, keyed by their casefolded form. Updated in place.
    label
        Returns the label of the object documented on the page, or `None` when
        it cannot be determined. Only called when `path` collides, so no object
        is looked up for a page that keeps its name.

    Returns
    -------
    :
        `path`, or `path` with a suffix when its case-insensitive form is
        already claimed by a different path.
    """

    def is_free(candidate: str) -> bool:
        owner = claimed.get(candidate.casefold())
        return owner is None or owner == candidate

    candidate = path
    if not is_free(path):
        kind = label() if label is not None else None
        slug = re.sub(r"[^a-z0-9]+", "-", kind.lower()).strip("-") if kind else ""
        base = f"{path}-{slug}" if slug else path
        candidate = base
        n = 2
        while not is_free(candidate):
            candidate = f"{base}-{n}"
            n += 1
        warnings.warn(
            f"Reference page `{path}` differs from `{claimed[path.casefold()]}` only by "
            f"case; writing it to `{candidate}` so both pages survive on "
            "case-insensitive filesystems.",
            stacklevel=2,
        )
    claimed[candidate.casefold()] = candidate
    return candidate


def unique_page_paths(
    sections: list[SpecSection],
    label: Callable[[SpecSection, SpecObject], str | None] | None = None,
) -> list[SpecSection]:
    """
    Give every documented entry a page path no other entry shares case-insensitively

    Entries are claimed in config order, so the first of two colliding entries
    keeps its usual page and only the later one moves (see `claim_page_path()`).

    Parameters
    ----------
    sections
        The reference sections from the config, in order.
    label
        Returns the label of the object that an entry of a section documents,
        or `None` when it cannot be determined. Only called for an entry whose
        page path collides.

    Returns
    -------
    :
        The sections, with colliding entries carrying their assigned page path.
        Sections without a collision are returned as-is.
    """
    claimed: dict[str, str] = {}

    def visit(section: SpecSection) -> SpecSection:
        contents: list[SpecEntry] = []
        for entry in section.contents:
            if isinstance(entry, SpecSection):
                contents.append(visit(entry))
            elif isinstance(entry, SpecObject):
                entry_label = None if label is None else partial(label, section, entry)
                path = claim_page_path(entry.page_path, claimed, entry_label)
                contents.append(entry if path == entry.page_path else entry.with_page_path(path))
            else:
                contents.append(entry)
        if all(new is old for new, old in zip(contents, section.contents, strict=True)):
            return section
        return section.replace(contents=contents)

    return [visit(section) for section in sections]
