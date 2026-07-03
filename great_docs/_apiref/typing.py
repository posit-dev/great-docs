from __future__ import annotations

from typing import Literal, TypeAlias

import griffe as gf

from ._griffe.docstrings import DCDocstringSection
from ._render.api_page import RenderAPIPage
from ._render.doc import RenderDoc
from ._render.docattribute import RenderDocAttribute
from ._render.docclass import RenderDocClass
from ._render.docfunction import RenderDocFunction
from ._render.docmodule import RenderDocModule
from ._render.reference_page import RenderReferencePage
from ._render.reference_section import RenderReferenceSection
from .content import (
    Doc,
    DocAttribute,
    DocClass,
    DocFunction,
    DocModule,
    MemberPage,
    Page,
    Section,
)

Annotation: TypeAlias = str | gf.Expr
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

DocstringDefinitionType: TypeAlias = (
    gf.DocstringParameter
    | gf.DocstringAttribute
    | gf.DocstringReturn
    | gf.DocstringYield
    | gf.DocstringReceive
    | gf.DocstringRaise
    | gf.DocstringWarn
)

Documentable: TypeAlias = DocClass | DocFunction | DocAttribute | DocModule | Page | Section

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
