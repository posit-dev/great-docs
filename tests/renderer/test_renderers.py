"""
Verify renderer choices and the object renderer mixin

Each choice applies wherever its kind is rendered, and declaring a subclass leaves
the default renderers unchanged.
"""

from __future__ import annotations

from typing import Any

import griffe as gf
import pytest

from great_docs._apiref._settings import Settings
from great_docs._apiref.api_reference import APIReference
from great_docs._apiref.content import (
    DocAttribute,
    DocClass,
    DocFunction,
    DocModule,
    DocTypeAlias,
    Page,
    Section,
)
from great_docs.rendering import (
    APIPageRenderer,
    AttributeRenderer,
    ClassRenderer,
    FunctionRenderer,
    ModuleRenderer,
    ObjectRenderer,
    ReferenceIndexRenderer,
    ReferenceSectionRenderer,
    Renderers,
    TypeAliasRenderer,
)


def make_node(slot: str) -> Any:
    """
    Construct a minimal input for the renderer in one slot

    Parameters
    ----------
    slot
        A `Renderers` field name, such as `classes`.

    Returns
    -------
    :
        The documentation node, page, section or reference that the slot's renderer
        accepts.
    """
    if slot == "classes":
        return DocClass(name="Example", obj=gf.Class(name="Example"))
    if slot == "functions":
        return DocFunction(name="example", obj=gf.Function(name="example"))
    if slot == "attributes":
        return DocAttribute(name="VALUE", obj=gf.Attribute(name="VALUE", value="1"))
    if slot == "type_aliases":
        return DocTypeAlias(name="Alias", obj=gf.TypeAlias(name="Alias", value="int"))
    if slot == "modules":
        return DocModule(name="example", obj=gf.Module(name="example"))
    if slot == "api_pages":
        return Page(path="Example", contents=[make_node("classes")])
    if slot == "reference_sections":
        return Section(title="Examples", contents=[])
    if slot == "reference_index":
        return APIReference({"package": "example", "sections": []})
    raise ValueError(slot)


SLOTS = [
    ("classes", ClassRenderer),
    ("functions", FunctionRenderer),
    ("attributes", AttributeRenderer),
    ("type_aliases", TypeAliasRenderer),
    ("modules", ModuleRenderer),
    ("api_pages", APIPageRenderer),
    ("reference_index", ReferenceIndexRenderer),
    ("reference_sections", ReferenceSectionRenderer),
]


@pytest.mark.parametrize("slot, expected", SLOTS)
def test_default_renderer_for_each_kind(slot: str, expected: type):
    choices = Renderers()
    node = make_node(slot)
    kwargs = {"sections": []} if slot == "reference_index" else {}
    renderer = choices.make(node, **kwargs)
    assert type(renderer) is expected
    assert renderer.node is node
    assert renderer.renderers is choices
    assert renderer.settings == Settings()


@pytest.mark.parametrize("slot, expected", SLOTS)
def test_explicit_renderer_for_each_kind(slot: str, expected: type):
    replacement = type("Replacement", (expected,), {})
    choices = Renderers(**{slot: replacement})
    node = make_node(slot)
    kwargs = {"sections": []} if slot == "reference_index" else {}
    assert type(choices.make(node, **kwargs)) is replacement
    assert getattr(Renderers(), slot) is expected


@pytest.mark.parametrize("slot, expected", SLOTS)
@pytest.mark.parametrize("invalid", [object, 3, "ClassRenderer"])
def test_reject_invalid_slot(slot: str, expected: type, invalid: object):
    with pytest.raises(TypeError, match=slot):
        Renderers(**{slot: invalid})


def test_reject_renderer_for_another_kind():
    with pytest.raises(TypeError, match="classes"):
        Renderers(classes=FunctionRenderer)


def test_reject_nonclass_object_renderer_mixin():
    with pytest.raises(TypeError, match="object_renderer_mixin"):
        Renderers(object_renderer_mixin=object())


def test_subclass_declaration_does_not_mutate_defaults():
    before = dict(vars(ClassRenderer))
    default_choices = Renderers()

    class CustomClass(ClassRenderer):
        @property
        def summary_name(self) -> str:
            return "custom " + super().summary_name

    node = make_node("classes")
    custom_choices = Renderers(classes=CustomClass)
    assert dict(vars(ClassRenderer)) == before
    assert custom_choices.make(node).summary_name.startswith("custom ")
    assert not default_choices.make(node).summary_name.startswith("custom ")


def test_object_renderer_mixin_precedes_each_default_object_renderer():
    class SharedMixin:
        @property
        def summary_name(self) -> str:
            return "shared " + super().summary_name

    choices = Renderers(object_renderer_mixin=SharedMixin)
    for slot, expected in SLOTS[:5]:
        renderer = choices.make(make_node(slot))
        assert isinstance(renderer, SharedMixin)
        assert isinstance(renderer, expected)
        assert renderer.summary_name.startswith("shared ")
    assert choices.api_pages is APIPageRenderer
    assert choices.reference_index is ReferenceIndexRenderer
    assert choices.reference_sections is ReferenceSectionRenderer


def test_explicit_renderer_owns_mixin_inheritance():
    class SharedMixin:
        @property
        def summary_name(self) -> str:
            return "shared"

    class CustomClass(ClassRenderer):
        pass

    class MixedFunction(SharedMixin, FunctionRenderer):
        pass

    choices = Renderers(
        object_renderer_mixin=SharedMixin, classes=CustomClass, functions=MixedFunction
    )
    assert type(choices.make(make_node("classes"))) is CustomClass
    assert not isinstance(choices.make(make_node("classes")), SharedMixin)
    assert type(choices.make(make_node("functions"))) is MixedFunction
    assert choices.make(make_node("functions")).summary_name == "shared"


def test_existing_object_renderer_mixin_is_not_inserted_twice():
    choices = Renderers(object_renderer_mixin=ObjectRenderer)
    for slot, expected in SLOTS[:5]:
        assert getattr(choices, slot) is expected
        assert isinstance(choices.make(make_node(slot)), ObjectRenderer)


def test_reference_index_requires_resolved_sections():
    with pytest.raises(TypeError, match="sections"):
        Renderers().make(make_node("reference_index"))


def test_reference_index_uses_common_state_and_explicit_sections():
    ref = make_node("reference_index")
    sections = [Section(title="Explicit", contents=[])]
    renderer = Renderers().make(ref, 3, sections=sections)
    assert renderer.node is ref
    assert renderer.settings is ref.settings
    assert renderer.level == 3
    assert renderer.sections is sections
    assert "Explicit" in str(renderer)


def test_choices_reach_index_sections_pages_and_objects():
    from great_docs.pandoc.blocks import BlockContent, Blocks, Header, Para

    class CustomClass(ClassRenderer):
        @property
        def summary_name(self) -> str:
            return "class summary marker"

        def render_body(self) -> BlockContent:
            return Para("class body marker")

    class CustomPage(APIPageRenderer):
        def render_body(self) -> BlockContent:
            return Blocks([Para("page body marker"), super().render_body()])

    class CustomSection(ReferenceSectionRenderer):
        def render_title(self) -> BlockContent:
            return Header(2, "section title marker")

    class CustomIndex(ReferenceIndexRenderer):
        def render_description(self) -> BlockContent:
            return Para("index description marker")

    choices = Renderers(
        classes=CustomClass,
        api_pages=CustomPage,
        reference_sections=CustomSection,
        reference_index=CustomIndex,
    )
    page = Page(path="Example", contents=[make_node("classes")])
    section = Section(title="Classes", contents=[page])
    reference = make_node("reference_index")
    index = str(choices.make(reference, sections=[section]))
    assert "index description marker" in index
    assert "section title marker" in index
    assert "class summary marker" in index
    assert "class body marker" not in index
    output = str(choices.make(page))
    assert "page body marker" in output
    assert "class body marker" in output
    assert "class body marker" not in str(Renderers().make(page))


@pytest.mark.parametrize("separate", [False, True])
def test_choices_reach_embedded_bodies_and_separate_member_summaries(separate: bool):
    from great_docs._apiref.content import MemberPage
    from great_docs.pandoc.blocks import BlockContent, Para

    class CustomFunction(FunctionRenderer):
        @property
        def summary_name(self) -> str:
            return "function summary marker"

        def render_body(self) -> BlockContent:
            return Para("function body marker")

    module = gf.Module(name="example")
    klass = gf.Class(name="Example")
    function = gf.Function(name="run", docstring=gf.Docstring("Run the example"))
    module.set_member("Example", klass)
    klass.set_member("run", function)
    member = DocFunction(name="run", obj=function)
    if separate:
        member = MemberPage(path="Example.run", contents=[member])
    doc = DocClass(name="Example", obj=klass, members=[member])
    output = str(Renderers(functions=CustomFunction).make(doc))
    assert "function summary marker" in output
    assert ("function body marker" in output) is not separate
    assert "function summary marker" not in str(Renderers().make(doc))


def test_choices_reach_typing_categories():
    from great_docs._apiref.inventory import InventoryItem
    from great_docs._apiref.typing_information import TypeSections
    from great_docs.extensions import Extension
    from great_docs.pandoc.blocks import BlockContent, Para

    class CustomClass(ClassRenderer):
        def render_body(self) -> BlockContent:
            return Para("protocol body marker")

    class CustomAttribute(AttributeRenderer):
        def render_body(self) -> BlockContent:
            return Para("typing attribute body marker")

    class CustomTypeAlias(TypeAliasRenderer):
        def render_body(self) -> BlockContent:
            return Para("typing alias body marker")

    protocol = InventoryItem(name="Protocol", obj=gf.Class(name="Protocol"))
    variable = InventoryItem(name="T", obj=gf.Attribute(name="T", value="TypeVar('T')"))
    alias = InventoryItem(name="Alias", obj=gf.TypeAlias(name="Alias", value="int"))
    sections = TypeSections(
        protocols_items=[protocol],
        typevars_items=[variable],
        typealiases_items=[alias],
        renderers=Renderers(
            classes=CustomClass, attributes=CustomAttribute, type_aliases=CustomTypeAlias
        ),
        extension=Extension(Settings()),
    )
    output = str(sections)
    assert "protocol body marker" in output
    assert "typing attribute body marker" in output
    assert "typing alias body marker" in output


def test_omitted_member_presentation_keeps_inventory():
    from great_docs._apiref.collect import build_manifest

    class CustomClass(ClassRenderer):
        def render_members(self) -> list:
            return []

    module = gf.Module(name="example")
    klass = gf.Class(name="Example")
    function = gf.Function(name="run", docstring=gf.Docstring("Run the example"))
    module.set_member("Example", klass)
    klass.set_member("run", function)
    doc = DocClass(name="Example", obj=klass, members=[DocFunction(name="run", obj=function)])
    page = Page(path="Example", contents=[doc])
    manifest = build_manifest([Section(title="Classes", contents=[page])], dir="reference")
    before = [(item.name, item.uri) for item in manifest.items]
    assert any(name.endswith(".run") for name, _ in before)
    output = str(Renderers(classes=CustomClass).make(page))
    assert "Methods" not in output
    assert [(item.name, item.uri) for item in manifest.items] == before
