from __future__ import annotations

from typing import Literal, TypeAlias

import griffe as gf

from . import (
    RenderAPIPage,
    RenderDoc,
    RenderDocAttribute,
    RenderDocClass,
    RenderDocFunction,
    RenderDocModule,
    RenderReferencePage,
    RenderReferenceSection,
)
from ._griffe.docstrings import DCDocstringSection
from .layout import (
    Doc,
    DocAttribute,
    DocClass,
    DocFunction,
    DocModule,
    Layout,
    MemberPage,
    Page,
    Section,
)

DisplayNameFormat: TypeAlias = Literal["doc", "full", "name", "short", "relative", "canonical"]
DocObjectKind: TypeAlias = Literal[
    "module",
    "class",
    "method",
    "property",
    "function",
    "attribute",
    "alias",
    "type",
    "typevar",
    "type alias",
]

Documentable: TypeAlias = (
    DocClass | DocFunction | DocAttribute | DocModule | Page | Section | Layout
)

RenderObjType: TypeAlias = (
    RenderDoc
    | RenderDocClass
    | RenderDocFunction
    | RenderDocAttribute
    | RenderDocModule
    | RenderReferencePage
    | RenderAPIPage
    | RenderReferenceSection
)

AnyDocstringSection: TypeAlias = gf.DocstringSection | DCDocstringSection

DocType: TypeAlias = DocClass | DocFunction | DocAttribute | DocModule

DocMemberType: TypeAlias = MemberPage | Doc
