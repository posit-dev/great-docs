"""Reference pages whose paths differ only by case each get their own file.

On case-insensitive filesystems (the macOS and Windows defaults) `foo.qmd` and
`Foo.qmd` are the same file, so a `foo()` function and a `Foo` class used to
overwrite each other's page.
"""

from __future__ import annotations

import tempfile
import warnings

import griffe as gf
import pytest

from great_docs import GreatDocs
from great_docs._apiref import introspect
from great_docs._apiref.api_reference import APIReference
from great_docs._apiref.content import MemberPage
from great_docs._apiref.spec import (
    SpecObject,
    SpecSection,
    SpecText,
    claim_page_path,
    unique_page_paths,
)
from great_docs._reference import sections as reference_sections


def _function(name: str, parent: gf.Object | None = None) -> gf.Function:
    fn = gf.Function(name, parent=parent)
    fn.docstring = gf.Docstring(f"The {name} function.", parent=fn)
    return fn


def _class(name: str, *methods: str) -> gf.Class:
    cls = gf.Class(name)
    cls.docstring = gf.Docstring(f"The {name} class.", parent=cls)
    for method in methods:
        cls.set_member(method, _function(method, parent=cls))
    return cls


def _api_ref(
    monkeypatch: pytest.MonkeyPatch,
    objects: dict[str, gf.Object | gf.Alias],
    contents: list[object],
) -> APIReference:
    """An APIReference for `mypkg` whose objects come from `objects`, not an import"""
    monkeypatch.setattr(introspect, "get_object", lambda path, **kwargs: objects[path])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return APIReference(
            {
                "api-reference": {
                    "package": "mypkg",
                    "sections": [{"title": "API", "contents": contents}],
                }
            }
        )


def _labels(**labels: str):
    """A `label` callback for `unique_page_paths()` that records what it was asked for"""
    asked: list[str] = []

    def label(section: SpecSection, entry: SpecObject) -> str | None:
        asked.append(entry.name)
        return labels.get(entry.name)

    return label, asked


# claim_page_path -------------------------------------------------------------


def test_claim_page_path_suffixes_a_case_variant_with_its_label():
    claimed: dict[str, str] = {}
    assert claim_page_path("mod.Template", claimed, lambda: "class") == "mod.Template"
    with pytest.warns(UserWarning, match="differs from `mod.Template` only by case"):
        assert claim_page_path("mod.template", claimed, lambda: "function") == (
            "mod.template-function"
        )


def test_claim_page_path_slugifies_the_label():
    claimed = {"foo": "foo"}
    with pytest.warns(UserWarning):
        assert claim_page_path("Foo", claimed, lambda: "Type Alias") == "Foo-type-alias"


def test_claim_page_path_numbers_a_taken_or_unknown_label():
    claimed: dict[str, str] = {}
    claim_page_path("Foo", claimed, lambda: "class")
    with pytest.warns(UserWarning):
        assert claim_page_path("FOO", claimed, lambda: "class") == "FOO-class"
    with pytest.warns(UserWarning):
        assert claim_page_path("foo", claimed, lambda: "class") == "foo-class-2"
    with pytest.warns(UserWarning):
        assert claim_page_path("fOO", claimed, lambda: None) == "fOO-2"
    with pytest.warns(UserWarning):
        assert claim_page_path("FoO", claimed) == "FoO-3"


def test_claim_page_path_never_asks_for_a_label_without_a_collision():
    def label() -> str:
        raise AssertionError("label looked up for a page that keeps its name")

    claimed: dict[str, str] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert claim_page_path("Foo", claimed, label) == "Foo"
        assert claim_page_path("Foo", claimed, label) == "Foo"
        assert claim_page_path("Bar", claimed, label) == "Bar"


# unique_page_paths -----------------------------------------------------------


def test_unique_page_paths_moves_the_later_entry_only():
    sections = [
        SpecSection(title="Classes", contents=[SpecObject(name="mod:Template")]),
        SpecSection(title="Functions", contents=[SpecObject(name="mod:template")]),
    ]
    label, asked = _labels(**{"mod:template": "function"})
    with pytest.warns(UserWarning):
        result = unique_page_paths(sections, label)

    assert result[0] is sections[0]
    [cls_entry] = result[0].contents
    [fn_entry] = result[1].contents
    assert isinstance(cls_entry, SpecObject) and isinstance(fn_entry, SpecObject)
    assert cls_entry.page_path == "mod.Template"
    assert fn_entry.page_path == "mod.template-function"
    # The entry still names the object it documents.
    assert fn_entry.name == "mod:template"
    # Only the colliding entry was looked up.
    assert asked == ["mod:template"]


def test_unique_page_paths_is_a_no_op_without_collisions():
    sections = [
        SpecSection(
            title="T",
            contents=[SpecObject(name="a"), SpecText(contents="text"), SpecObject(name="b")],
        )
    ]
    label, asked = _labels()
    assert unique_page_paths(sections, label)[0] is sections[0]
    assert asked == []


def test_unique_page_paths_is_idempotent():
    sections = [SpecSection(title="T", contents=[SpecObject(name="foo"), SpecObject(name="Foo")])]
    label, _ = _labels(Foo="class")
    with pytest.warns(UserWarning):
        once = unique_page_paths(sections, label)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        twice = unique_page_paths(once, label)
    assert [e.page_path for e in twice[0].contents if isinstance(e, SpecObject)] == [
        "foo",
        "Foo-class",
    ]


def test_with_page_path_survives_option_defaults():
    entry = SpecObject(name="Foo").with_page_path("Foo-class")
    assert entry.with_defaults(SpecObject(name="x", include_private=True)).page_path == "Foo-class"


# Every consumer agrees on the moved path -------------------------------------


def test_pages_and_inventory_use_the_labeled_path(monkeypatch: pytest.MonkeyPatch):
    objects: dict[str, gf.Object | gf.Alias] = {
        "mypkg:Template": _class("Template"),
        "mypkg:template": _function("template"),
    }
    ref = _api_ref(monkeypatch, objects, ["Template", "template"])

    assert [page.path for page in ref.manifest.pages] == ["Template", "template-function"]
    uris = {item.uri.split("#")[0] for item in ref.items}
    assert uris == {"reference/Template.html", "reference/template-function.html"}


def test_an_alias_is_labeled_by_its_target(monkeypatch: pytest.MonkeyPatch):
    target = _function("render")
    module = gf.Module("impl")
    module.set_member("render", target)
    objects: dict[str, gf.Object | gf.Alias] = {
        "mypkg:Render": _class("Render"),
        "mypkg:render": gf.Alias("render", target, parent=gf.Module("mypkg")),
    }
    ref = _api_ref(monkeypatch, objects, ["Render", "render"])

    assert ref.sections[0].contents[1].page_path == "render-function"  # type: ignore[union-attr]


def test_an_unfindable_object_falls_back_to_a_number(monkeypatch: pytest.MonkeyPatch):
    objects: dict[str, gf.Object | gf.Alias] = {"mypkg:Foo": _class("Foo")}
    ref = _api_ref(monkeypatch, objects, ["Foo", "foo"])

    assert ref.sections[0].contents[1].page_path == "foo-2"  # type: ignore[union-attr]


def test_an_unresolved_alias_falls_back_to_a_number(monkeypatch: pytest.MonkeyPatch) -> None:
    module = gf.Module("mypkg", modules_collection=gf.ModulesCollection())
    objects: dict[str, gf.Object | gf.Alias] = {
        "mypkg:Foo": _class("Foo"),
        "mypkg:foo": gf.Alias("foo", "missing.target", parent=module),
    }
    ref = _api_ref(monkeypatch, objects, ["Foo", "foo"])

    assert ref.sections[0].contents[1].page_path == "foo-2"  # type: ignore[union-attr]


def test_unexpected_label_lookup_errors_propagate(monkeypatch: pytest.MonkeyPatch) -> None:
    def get_object(path: str, **kwargs: object) -> gf.Object:
        raise RuntimeError("broken label lookup")

    monkeypatch.setattr(introspect, "get_object", get_object)
    with pytest.raises(RuntimeError, match="broken label lookup"):
        APIReference(
            {"package": "mypkg", "sections": [{"title": "API", "contents": ["Foo", "foo"]}]}
        )


def test_sidebar_links_to_the_moved_page():
    """Without an importable package the label is unknown, and the sidebar still agrees"""
    api_block = {
        "package": "mypkg_that_does_not_exist",
        "sections": [{"title": "API", "contents": ["Template", "template"]}],
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs = GreatDocs(project_path=tmp_dir)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sidebar = reference_sections.sidebar(docs._config, api_block)
            ref = APIReference({"api-reference": api_block})

    hrefs = [link["href"] for link in sidebar.contents[1]["contents"]]
    assert hrefs == [f"reference/{e.page_path}.qmd" for e in ref.sections[0].contents]  # type: ignore[union-attr]
    assert hrefs == ["reference/Template.qmd", "reference/template-2.qmd"]


def test_member_pages_get_their_label_as_a_suffix(monkeypatch: pytest.MonkeyPatch):
    widget = _class("Widget", "run", "Run")
    objects: dict[str, gf.Object | gf.Alias] = {
        "mypkg:Widget": widget,
        "mypkg:Widget.run": widget.members["run"],
        "mypkg:Widget.Run": widget.members["Run"],
    }
    ref = _api_ref(
        monkeypatch,
        objects,
        [{"name": "Widget", "members_on_same_page": False, "members": ["run", "Run"]}],
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pages = ref.manifest.pages

    assert [p.path for p in pages if isinstance(p, MemberPage)] == [
        "Widget.run",
        "Widget.Run-method",
    ]
