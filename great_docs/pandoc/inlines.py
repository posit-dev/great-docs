"""Pandoc inline elements.

Specification: https://pandoc.org/lua-filters.html#inline
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, TypeAlias

from .components import Attr

__all__ = (
    "Code",
    "Emph",
    "Image",
    "Inline",
    "Inlines",
    "Inlines0",
    "Link",
    "Span",
    "Str",
    "Strong",
)

SEP = " "
_BACKTICK_RUN = re.compile(r"`+")


class Inline:
    """Base class for inline elements."""

    def __str__(self) -> str:
        raise NotImplementedError(f"__str__ method not implemented for: {type(self)}")

    @property
    def html(self) -> str:
        raise NotImplementedError(f"html property method not implemented for: {type(self)}")

    @property
    def as_list_item(self) -> str:
        return str_as_list_item(str(self))


InlineContentItem = str | Inline | None
InlineContent: TypeAlias = InlineContentItem | Sequence[InlineContentItem]


@dataclass
class Inlines(Inline):
    elements: Sequence[InlineContent] | None = None

    def __str__(self):
        if not self.elements:
            return ""
        return join_inline_content(self.elements)


@dataclass
class Inlines0(Inline):
    """
    Tight Inline (rendered without space in-between)
    """

    elements: Sequence[InlineContent] | None = None

    def __str__(self):
        if not self.elements:
            return ""
        return join_inline_content(self.elements, "")


@dataclass
class Str(Inline):
    content: str | None = None

    def __str__(self):
        return self.content or ""


@dataclass
class Span(Inline):
    content: InlineContent | None = None
    attr: Attr | None = None

    def __str__(self):
        content = inlinecontent_to_str(self.content)
        attr = self.attr or ""
        return f"[{content}]{{{attr}}}"


@dataclass
class Link(Inline):
    content: InlineContent | None = None
    target: str | None = None
    title: str | None = None
    attr: Attr | None = None

    def __str__(self):
        title = f' "{self.title}"' if self.title else ""
        content = inlinecontent_to_str(self.content)
        attr = f"{{{self.attr}}}" if self.attr else ""
        return f"[{content}]({self.target}{title}){attr}"


@dataclass
class Code(Inline):
    text: str | None = None
    attr: Attr | None = None

    def __str__(self) -> str:
        content = self.text or ""
        fence = "`" * (1 + max((len(run) for run in _BACKTICK_RUN.findall(content)), default=0))
        if len(fence) > 1:
            content = f" {content} "
        attr = f"{{{self.attr}}}" if self.attr else ""
        return f"{fence}{content}{fence}{attr}"

    @property
    def html(self):
        content = self.text or ""
        attr = f" {self.attr.html}" if self.attr else ""
        return f"<code{attr}>{content}</code>"


@dataclass
class Strong(Inline):
    content: InlineContent | None = None

    def __str__(self):
        if not self.content:
            return ""
        content = inlinecontent_to_str(self.content)
        return f"**{content}**"


@dataclass
class Emph(Inline):
    content: InlineContent | None = None

    def __str__(self):
        if not self.content:
            return ""
        content = inlinecontent_to_str(self.content)
        return f"*{content}*"


@dataclass
class Image(Inline):
    caption: str | None = None
    src: Path | str | None = None
    title: str | None = None
    attr: Attr | None = None

    def __str__(self):
        caption = self.caption or ""
        src = self.src or ""
        title = f' "{self.title}"' if self.title else ""
        attr = f"{{{self.attr}}}" if self.attr else ""
        return f"![{caption}]({src}{title}){attr}"


# Helper functions


def join_inline_content(content: Sequence[InlineContent], sep: str = SEP) -> str:
    return sep.join(inlinecontent_to_str(c) for c in content if c)


def inlinecontent_to_str(content: InlineContent | None):
    if not content:
        return ""
    elif isinstance(content, (str, Inline)):
        return str(content)
    else:
        return join_inline_content(content)


def str_as_list_item(s: str) -> str:
    return f"{s}\n"


# Custom inlines (great-docs extensions) ----------------------------------------


@dataclass
class InterLink(Link):
    """
    Link with target enclosed in colons

    These targets of these links are interlink references
    that are finally resolved by the interlinks filter.
    """

    def __post_init__(self):
        self.target = f"`{self.target}`"


class shortcode(Inline):
    """
    A quarto shortcode

    Parameters
    ----------
    name :
        Name of the shortcode
    *args :
        Arguments to the shortcode
    **kwargs :
        Named arguments for the shortcode

    References
    ----------
    https://quarto.org/docs/extensions/shortcodes.html
    """

    def __init__(self, name: str, *args: str, **kwargs: str):
        self.name = name
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        _args = " ".join(self.args)
        _kwargs = " ".join(f"{k}={v}" for k, v in self.kwargs.items())
        content = f"{self.name} {_args} {_kwargs}".strip()
        return f"{{{{< {content} >}}}}"
