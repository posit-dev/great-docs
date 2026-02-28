"""
Pandoc block elements.

Specification: https://pandoc.org/lua-filters.html#block
"""

from __future__ import annotations

import collections.abc as abc
import itertools
import sys
from dataclasses import dataclass
from textwrap import indent
from typing import Literal, Optional, Sequence, Union

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    TypeAlias = "TypeAlias"

from great_docs._renderer.pandoc.components import Attr
from great_docs._renderer.pandoc.inlines import (
    Inline,
    InlineContent,
    InlineContentItem,
    inlinecontent_to_str,
    str_as_list_item,
)

__all__ = (
    "Block",
    "Blocks",
    "BulletList",
    "CodeBlock",
    "DefinitionList",
    "Div",
    "Header",
    "OrderedList",
    "Para",
    "Plain",
)

INDENT = " " * 4
SEP = "\n"


class Block:
    """Base class for block elements."""

    def __str__(self):
        raise NotImplementedError(f"__str__ method not implemented for: {type(self)}")

    @property
    def html(self):
        raise NotImplementedError(f"html property method not implemented for: {type(self)}")

    @property
    def as_list_item(self):
        return f"{self}\n\n"


BlockContentItem: TypeAlias = Union[InlineContentItem, Block]
BlockContent: TypeAlias = Union[BlockContentItem, Sequence[BlockContentItem]]
DefinitionItem: TypeAlias = tuple[InlineContent, BlockContent]


@dataclass
class Blocks(Block):
    elements: Optional[Sequence[BlockContent]] = None

    def __str__(self):
        if not self.elements:
            return ""
        return join_block_content(self.elements)


Div_TPL = """\
::: {{{attr}}}
{content}
:::\
"""


@dataclass
class Div(Block):
    content: Optional[BlockContent] = None
    attr: Optional[Attr] = None

    def __str__(self):
        content = blockcontent_to_str(self.content)
        attr = self.attr or ""
        return Div_TPL.format(content=content, attr=attr)


DefinitionItem_TPL = """\
{term}
{definitions}\
"""

Definition_TPL = """
:   {definition}
"""


@dataclass
class DefinitionList(Block):
    content: Optional[Sequence[DefinitionItem]] = None

    def __str__(self):
        if not self.content:
            return ""

        tfmt = DefinitionItem_TPL.format
        dfmt = Definition_TPL.format
        items = []
        for term, definitions in self.content:
            term, defs = inlinecontent_to_str(term), []

            if isinstance(definitions, (str, Inline, Block)):
                definitions = [definitions]
            elif definitions is None:
                definitions = [""]

            for definition in definitions:
                s = blockcontent_to_str(definition)
                defs.append(dfmt(definition=indent(s, INDENT).strip()))

            items.append(tfmt(term=term, definitions="".join(defs)))

        return join_block_content(items)


@dataclass
class Plain(Block):
    content: Optional[InlineContent] = None

    def __str__(self):
        return inlinecontent_to_str(self.content)


@dataclass
class Para(Block):
    content: Optional[InlineContent] = None

    def __str__(self):
        content = inlinecontent_to_str(self.content)
        return f"{SEP}{content}{SEP}"

    @property
    def as_list_item(self):
        content = inlinecontent_to_str(self.content)
        return f"{content}\n\n"


@dataclass
class Header(Block):
    level: int
    content: Optional[InlineContent] = None
    attr: Optional[Attr] = None

    def __str__(self):
        hashes = "#" * self.level
        content = inlinecontent_to_str(self.content)
        attr = f" {{{self.attr}}}" if self.attr else ""
        return f"{hashes} {content}{attr}"


CodeBlock_TPL = """\
```{attr}
{content}
```\
"""
CodeBlockHTML_TPL = """\
<pre{attr}>
<code>{content}</code>
</pre>\
"""


@dataclass
class CodeBlock(Block):
    content: Optional[str] = None
    attr: Optional[Attr] = None

    def __str__(self):
        content = self.content or ""
        if self.attr:
            no_curly_braces = (
                self.attr.classes and len(self.attr.classes) == 1 and not self.attr.attributes
            )

            if self.attr.classes and no_curly_braces:
                attr = self.attr.classes[0]
            else:
                attr = f" {{{self.attr}}}"
        else:
            attr = ""

        return CodeBlock_TPL.format(content=content, attr=attr)

    @property
    def html(self):
        content = self.content or ""
        attr = f" {self.attr.html}" if self.attr else ""
        return CodeBlockHTML_TPL.format(content=content, attr=attr)

    @property
    def as_list_item(self):
        return f"\n{self}\n\n"


@dataclass
class BulletList(Block):
    content: Optional[BlockContent] = None

    def __str__(self):
        if not self.content:
            return ""
        return blockcontent_to_str_items(self.content, "bullet")


@dataclass
class OrderedList(Block):
    content: Optional[BlockContent] = None

    def __str__(self):
        if not self.content:
            return ""
        return blockcontent_to_str_items(self.content, "ordered")


# Helper functions


def join_block_content(content: Sequence[BlockContent]) -> str:
    return f"{SEP}{SEP}".join(blockcontent_to_str(c) for c in content if c)


def blockcontent_to_str(content: Optional[BlockContent]) -> str:
    if not content:
        return ""
    elif isinstance(content, (str, Inline, Block)):
        return str(content).rstrip(SEP)
    elif isinstance(content, abc.Sequence):
        return join_block_content(content)
    else:
        raise TypeError(f"Could not process type: {type(content)}")


def blockcontent_to_str_items(
    content: Optional[BlockContent], kind: Literal["bullet", "ordered"]
) -> str:
    def fmt(s: str, pfx: str):
        if not s:
            return ""

        space = ""
        indent_size = len(pfx) + 1
        s_indented = indent(s, " " * indent_size)
        if s[0] != "\n":
            space = " "
            s_indented = s_indented[indent_size:]
        return f"{pfx}{space}{s_indented}"

    if not content:
        return ""

    if kind == "bullet":
        pfx_it = itertools.cycle("*")
    else:
        pfx_it = (f"{i}." for i in itertools.count(1))

    if isinstance(content, str):
        return fmt(str_as_list_item(content), next(pfx_it))
    elif isinstance(content, (Inline, Block)):
        return fmt(content.as_list_item, next(pfx_it))
    elif isinstance(content, abc.Sequence):
        it = (str_as_list_item(c) if isinstance(c, str) else c.as_list_item for c in content if c)
        items = (fmt(s, next(pfx_it)) for s in it)
        return "".join(items).strip()
    else:
        raise TypeError(f"Could not process type: {type(content)}")
