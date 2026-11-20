from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from great_docs._apiref.api_reference import APIReference
from great_docs._reference.block import configure
from great_docs.config import ConfigError
from tests.support import MakeReference, WriteExtension, write_config

PACKAGE = "reference_bases_example"
BASES_LABEL = "[Bases:]{.doc-class-bases}"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    package = tmp_path / PACKAGE
    package.mkdir()
    (package / "__init__.py").write_text(
        dedent('''\
        from collections.abc import Sequence
        from ._parents import Parent, _Mixin, _Mixin as PublicMixin, _Hidden
        from .other import OtherChild

        __all__ = ["Parent", "PublicMixin", "Child", "OtherChild", "Container"]

        class Child(Parent, _Mixin[int], Sequence[int], _Hidden):
            """
            A child with several direct bases

            The detailed child description.
            """

        class Root(object):
            """An explicit root"""

        class PrivateChild(_Hidden):
            """A child with only a hidden base"""

        def make_base(value: str) -> type[Parent]:
            """Return a class"""
            return Parent

        class Computed(make_base("`")):
            """A child with a computed base"""

        class Container:
            """A container of nested classes"""

            class Base:
                """A nested base"""

            class NestedChild(Base):
                """A nested child"""
        '''),
        encoding="utf-8",
    )
    (package / "_parents.py").write_text(
        dedent('''\
        from typing import Generic, TypeVar

        T = TypeVar("T")

        class Grandparent:
            """A grandparent"""

        class Parent(Grandparent):
            """A documented direct base"""

            def describe(self) -> None:
                """Describe a parent"""

        class _Mixin(Generic[T]):
            """A mixin with a public re-export"""

        class _Hidden:
            """A private implementation detail"""
        '''),
        encoding="utf-8",
    )
    (package / "other.py").write_text(
        dedent('''\
        class Parent:
            """A separate class with the same short name"""

        class OtherChild(Parent):
            """A child whose parent is missing from the reference"""
        '''),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize("value", [None, "true", 0, []])
def test_show_bases_requires_a_boolean(tmp_path: Path, value: object) -> None:
    with pytest.raises(ConfigError, match=r"reference\.show_bases must be true or false"):
        write_config(tmp_path, {"reference": {"show_bases": value}})
    with pytest.raises(ValueError, match="show_bases.*must be true or false"):
        APIReference({"package": PACKAGE, "show_bases": value})


@pytest.mark.parametrize("enabled", [True, False])
def test_show_bases_with_automatically_discovered_sections(project: Path, enabled: bool) -> None:
    config = write_config(project, {"reference": {"show_bases": enabled}})
    block = configure(config, {}, PACKAGE, config.reference)
    assert ("show_bases" in block) is enabled
    APIReference(block).build()

    child = (project / "reference/Child.qmd").read_text(encoding="utf-8")
    assert (BASES_LABEL in child) is enabled
    assert ("[`Parent`](/reference/Parent.html" in child) is enabled


def test_show_bases_uses_only_published_direct_targets(project: Path) -> None:
    contents = ["Parent", "_Mixin", "OtherChild", "Root", "PrivateChild", "Computed"]
    config = write_config(
        project,
        {
            "dynamic": False,
            "reference": {
                "show_bases": True,
                "sections": [{"title": "API", "contents": [*contents, "PublicMixin", "Child"]}],
            },
        },
    )
    block = configure(config, {}, PACKAGE, config.reference)
    APIReference(block).build()

    reference = project / "reference"
    child = (reference / "Child.qmd").read_text(encoding="utf-8")
    line = next(line for line in child.splitlines() if line.startswith(BASES_LABEL))
    assert line.startswith(f"{BASES_LABEL} [`Parent`](/reference/Parent.html")
    assert ", [`PublicMixin[int]`](/reference/PublicMixin.html" in line
    assert line.endswith(", `Sequence[int]`{.gd-no-link}")
    assert (
        child.index(".doc-signature")
        < child.index(line)
        < child.index("The detailed child description")
    )
    assert "Describe a parent" not in child
    assert "Describe a parent" in (reference / "Parent.qmd").read_text(encoding="utf-8")

    other = (reference / "OtherChild.qmd").read_text(encoding="utf-8")
    assert f"{BASES_LABEL} `Parent`{{.gd-no-link}}" in other
    computed = (reference / "Computed.qmd").read_text(encoding="utf-8")
    assert f"{BASES_LABEL} `` make_base(" in computed
    assert " ``{.gd-no-link}" in computed
    for name in ("Root", "PrivateChild"):
        assert BASES_LABEL not in (reference / f"{name}.qmd").read_text(encoding="utf-8")

    block["sections"] = [
        {"title": "API", "contents": [*contents, {"name": "Child", "include_inherited": True}]}
    ]
    APIReference(block).build()
    child = (reference / "Child.qmd").read_text(encoding="utf-8")
    assert "Describe a parent" in child
    assert "[`_Mixin[int]`](/reference/_Mixin.html" in child


@pytest.mark.parametrize("inline", [True, False])
def test_show_bases_links_to_the_nested_class_location(project: Path, inline: bool) -> None:
    ref = APIReference(
        {
            "package": PACKAGE,
            "show_bases": True,
            "dynamic": False,
            "sections": [
                {
                    "contents": [
                        {"name": "Container", "members_on_same_page": inline},
                    ],
                },
            ],
        }
    )
    ref.build()

    if inline:
        source = "Container.qmd"
        target = f"Container.html#{PACKAGE}.Container.Base"
    else:
        source = f"{PACKAGE}.Container.NestedChild.qmd"
        target = f"{PACKAGE}.Container.Base.html"
    child = (project / "reference" / source).read_text(encoding="utf-8")
    assert f"{BASES_LABEL} [`Base`](/reference/{target})" in child
    if inline:
        assert f"::: {{#{PACKAGE}.Container.Base}}" in child


def test_show_bases_respects_the_reference_extension(
    project: Path, write_extension: WriteExtension, make_reference: MakeReference
) -> None:
    source = write_extension("""
        from griffe import Object

        from great_docs.extensions import Extension
        from great_docs.pandoc.blocks import BlockContent
        from great_docs.rendering import ClassRenderer, Renderers

        class CustomClassRenderer(ClassRenderer):
            def render_description(self) -> BlockContent:
                if self.obj.name == "Parent":
                    return "Custom parent description"
                return super().render_description()

        def setup(extension: Extension) -> None:
            extension.set_renderers(Renderers(classes=CustomClassRenderer))

            @extension.on_object_resolved
            def exclude_mixin(obj: Object) -> Object | None:
                if obj.name == "_Mixin":
                    return None
                return obj
        """)
    ref = make_reference(
        {
            "package": PACKAGE,
            "show_bases": True,
            "dynamic": False,
            "sections": [{"contents": ["Parent", "PublicMixin", "Child"]}],
        },
        source,
        output_root=project,
    )
    ref.build()

    reference = project / "reference"
    child = (reference / "Child.qmd").read_text(encoding="utf-8")
    parent = (reference / "Parent.qmd").read_text(encoding="utf-8")
    assert f"[`Parent`](/reference/Parent.html#{PACKAGE}.Parent)" in child
    assert f"::: {{#{PACKAGE}.Parent}}" in parent
    assert "Custom parent description" in parent
    assert "Mixin" not in child
    assert not (reference / "PublicMixin.qmd").exists()
