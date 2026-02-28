"""
Pandoc inline elements.

Specification: https://pandoc.org/lua-filters.html#inline
"""

from __future__ import annotations

import collections.abc as abc
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Union

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    TypeAlias = "TypeAlias"

from great_docs._renderer.pandoc.components import Attr

__all__ = (
    "Code",
    "Emph",
    "Image",
    "Inline",
    "Inlines",
    "Link",
    "Span",
    "Str",
    "Strong",
)

SEP = " "


class Inline:
    """Base class for inline elements."""

    def __str__(self):
        raise NotImplementedError(f"__str__ method not implemented for: {type(self)}")

    @property
    def html(self):
        raise NotImplementedError(f"html property method not implemented for: {type(self)}")

    @property
    def as_list_item(self):
        return str_as_list_item(str(self))


InlineContentItem = Union[str, Inline, None]
InlineContent: TypeAlias = Union[InlineContentItem, Sequence[InlineContentItem]]


@dataclass
class Inlines(Inline):
    elements: Optional[Sequence[InlineContent]] = None

    def __str__(self):
        if not self.elements:
            return ""
        return join_inline_content(self.elements)


@dataclass
class Str(Inline):
    content: Optional[str] = None

    def __str__(self):
        return self.content or ""


@dataclass
class Span(Inline):
    content: Optional[InlineContent] = None
    attr: Optional[Attr] = None

    def __str__(self):
        content = inlinecontent_to_str(self.content)
        attr = self.attr or ""
        return f"[{content}]{{{attr}}}"


@dataclass
class Link(Inline):
    content: Optional[InlineContent] = None
    target: Optional[str] = None
    title: Optional[str] = None
    attr: Optional[Attr] = None

    def __str__(self):
        title = f' "{self.title}"' if self.title else ""
        content = inlinecontent_to_str(self.content)
        attr = f"{{{self.attr}}}" if self.attr else ""
        return f"[{content}]({self.target}{title}){attr}"


@dataclass
class Code(Inline):
    text: Optional[str] = None
    attr: Optional[Attr] = None

    def __str__(self):
        content = self.text or ""
        attr = f"{{{self.attr}}}" if self.attr else ""
        return f"`{content}`{attr}"

    @property
    def html(self):
        content = self.text or ""
        attr = f" {self.attr.html}" if self.attr else ""
        return f"<code{attr}>{content}</code>"


@dataclass
class Strong(Inline):
    content: Optional[InlineContent] = None

    def __str__(self):
        if not self.content:
            return ""
        content = inlinecontent_to_str(self.content)
        return f"**{content}**"


@dataclass
class Emph(Inline):
    content: Optional[InlineContent] = None

    def __str__(self):
        if not self.content:
            return ""
        content = inlinecontent_to_str(self.content)
        return f"*{content}*"


@dataclass
class Image(Inline):
    caption: Optional[str] = None
    src: Optional[Path | str] = None
    title: Optional[str] = None
    attr: Optional[Attr] = None

    def __str__(self):
        caption = self.caption or ""
        src = self.src or ""
        title = f' "{self.title}"' if self.title else ""
        attr = f"{{{self.attr}}}" if self.attr else ""
        return f"![{caption}]({src}{title}){attr}"


# Helper functions


def join_inline_content(content: Sequence[InlineContent]) -> str:
    return SEP.join(inlinecontent_to_str(c) for c in content if c)


def inlinecontent_to_str(content: Optional[InlineContent]):
    if not content:
        return ""
    elif isinstance(content, (str, Inline)):
        return str(content)
    elif isinstance(content, abc.Sequence):
        return join_inline_content(content)
    else:
        raise TypeError(f"Could not process type: {type(content)}")


def str_as_list_item(s: str) -> str:
    return f"{s}\n"
