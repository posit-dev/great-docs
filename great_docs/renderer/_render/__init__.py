from __future__ import annotations

from typing import TYPE_CHECKING, overload

from quartodoc.layout import (
    DocAttribute,
    DocClass,
    DocFunction,
    DocModule,
    Layout,
    Page,
    Section,
)

from .api_page import RenderAPIPage
from .docattribute import RenderDocAttribute
from .docclass import RenderDocClass
from .docfunction import RenderDocFunction
from .docmodule import RenderDocModule
from .layout import RenderLayout
from .section import RenderSection

if TYPE_CHECKING:
    from ..typing import Documentable, RenderObjType


_class_mapping: dict[type[Documentable], type[RenderObjType]] = {
    DocAttribute: RenderDocAttribute,
    DocClass: RenderDocClass,
    DocFunction: RenderDocFunction,
    DocModule: RenderDocModule,
    Layout: RenderLayout,
    Page: RenderAPIPage,
    Section: RenderSection,
}


@overload
def get_render_type(obj: DocClass) -> type[RenderDocClass]: ...


@overload
def get_render_type(obj: DocFunction) -> type[RenderDocFunction]: ...


@overload
def get_render_type(obj: DocAttribute) -> type[RenderDocAttribute]: ...


@overload
def get_render_type(obj: DocModule) -> type[RenderDocModule]: ...


@overload
def get_render_type(obj: Layout) -> type[RenderLayout]: ...


@overload
def get_render_type(obj: Page) -> type[RenderAPIPage]: ...


@overload
def get_render_type(obj: Section) -> type[RenderSection]: ...


def get_render_type(obj: Documentable) -> type[RenderObjType]:
    if type(obj) in _class_mapping:
        return _class_mapping[type(obj)]
    else:
        msg = f"Cannot document object of type {type(obj)}"
        raise ValueError(msg)
