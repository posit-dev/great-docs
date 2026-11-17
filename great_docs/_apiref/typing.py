from __future__ import annotations

from typing import Literal, TypeAlias

import griffe as gf

from ._docstring_sections import (
    DCDocstringSection,
    DCDocstringSectionInitParameters,
    DCDocstringSectionParameterAttributes,
)
from ._rendering.api_pages import APIPageRenderer
from ._rendering.attributes import AttributeRenderer
from ._rendering.classes import ClassRenderer
from ._rendering.functions import FunctionRenderer
from ._rendering.modules import ModuleRenderer
from ._rendering.objects import ObjectRenderer
from ._rendering.reference_index import ReferenceIndexRenderer
from ._rendering.reference_sections import ReferenceSectionRenderer
from ._rendering.type_aliases import TypeAliasRenderer
from .content import (
    Doc,
    DocAttribute,
    DocClass,
    DocFunction,
    DocModule,
    DocTypeAlias,
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

DocstringSectionWithDefinitions: TypeAlias = (
    gf.DocstringSectionParameters
    | gf.DocstringSectionOtherParameters
    | gf.DocstringSectionTypeParameters
    | gf.DocstringSectionReturns
    | gf.DocstringSectionYields
    | gf.DocstringSectionReceives
    | gf.DocstringSectionRaises
    | gf.DocstringSectionWarns
    | gf.DocstringSectionAttributes
    | DCDocstringSectionParameterAttributes
    | DCDocstringSectionInitParameters
)

DocstringDefinitionType: TypeAlias = (
    gf.DocstringParameter
    | gf.DocstringTypeParameter
    | gf.DocstringAttribute
    | gf.DocstringReturn
    | gf.DocstringYield
    | gf.DocstringReceive
    | gf.DocstringRaise
    | gf.DocstringWarn
)

Documentable: TypeAlias = (
    DocClass | DocFunction | DocAttribute | DocTypeAlias | DocModule | Page | Section
)

RenderObjType: TypeAlias = (
    ObjectRenderer
    | ClassRenderer
    | FunctionRenderer
    | AttributeRenderer
    | TypeAliasRenderer
    | ModuleRenderer
    | ReferenceIndexRenderer
    | APIPageRenderer
    | ReferenceSectionRenderer
)

AnyDocstringSection: TypeAlias = gf.DocstringSection | DCDocstringSection

DocType: TypeAlias = DocClass | DocFunction | DocAttribute | DocTypeAlias | DocModule

DocMemberType: TypeAlias = MemberPage | Doc
