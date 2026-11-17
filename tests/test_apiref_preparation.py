"""
Verify canonical preparation, alias names and operation-specific parsing
"""

from __future__ import annotations

import gc
import sys
import weakref
from pathlib import Path

import griffe as gf
import pytest

from great_docs._apiref._conversion import griffe_to_doc
from great_docs._apiref._customisation import Extension, ExtensionError
from great_docs._apiref._extension_loading import _ExtensionSource
from great_docs._apiref._settings import Settings
from great_docs._apiref.api_reference import APIReference
from great_docs._apiref.content import DocFunction
from great_docs._apiref.resolve import Resolver


def make_extension(tmp_path: Path, setup: str, *, parser: str = "numpy") -> Extension:
    """Load one small configured semantic extension"""
    entry = tmp_path / "extension.py"
    entry.write_text(setup, encoding="utf-8")
    extension = Extension(Settings(parser=parser), _ExtensionSource(entry, tmp_path, tmp_path))
    extension.load()
    return extension


@pytest.mark.parametrize("order", [("First", "Second"), ("Second", "First")])
def test_aliases_share_one_semantic_preparation(tmp_path: Path, order: tuple[str, str]) -> None:
    extension = make_extension(
        tmp_path,
        "def setup(extension):\n"
        "    extension.cache['objects'] = []\n"
        "    extension.cache['parsed'] = []\n"
        "    @extension.on_object_resolved\n"
        "    def transform(obj):\n"
        "        extension.cache['objects'].append(obj.path)\n"
        "        obj.docstring.value += '\\n\\nSemantic marker'\n"
        "        return obj\n"
        "    @extension.on_docstring_parsed\n"
        "    def parsed(obj, sections):\n"
        "        extension.cache['parsed'].append(obj.path)\n"
        "        return sections\n",
    )
    module = gf.Module(name="example")
    target = gf.Function(name="Original", docstring=gf.Docstring("Original text"))
    module.set_member("Original", target)
    aliases = {name: gf.Alias(name, target, parent=module) for name in order}
    try:
        results = [extension.prepare(aliases[name]) for name in order]
        assert [obj.name for obj in results] == list(order)
        assert all(isinstance(obj, gf.Alias) and obj.final_target is target for obj in results)
        assert extension.cache["objects"] == ["example.Original"]
        assert extension.cache["parsed"] == ["example.Original"]
        assert target.docstring.value.count("Semantic marker") == 1
        assert all(obj.docstring is target.docstring for obj in results)
    finally:
        extension.close()


def test_excluded_aliases_are_memoised_and_original_is_retained(tmp_path: Path) -> None:
    extension = make_extension(
        tmp_path,
        "def setup(extension):\n"
        "    extension.cache['calls'] = 0\n"
        "    @extension.on_object_resolved\n"
        "    def exclude(obj):\n"
        "        extension.cache['calls'] += 1\n"
        "        return None\n",
    )
    target = gf.Function(name="original")
    original = weakref.ref(target)
    first = gf.Alias("First", target)
    second = gf.Alias("Second", target)
    try:
        assert extension.prepare(first) is None
        assert extension.prepare(second) is None
        assert extension.cache["calls"] == 1
        del target, first, second
        gc.collect()
        assert original() is not None
        assert extension.prepare(gf.Function(name="original")) is None
        assert extension.cache["calls"] == 2
    finally:
        extension.close()


def test_replacement_preserves_authored_alias_views(tmp_path: Path) -> None:
    extension = make_extension(
        tmp_path,
        "import griffe as gf\n"
        "def setup(extension):\n"
        "    extension.cache['calls'] = 0\n"
        "    @extension.on_object_resolved\n"
        "    def replace(obj):\n"
        "        extension.cache['calls'] += 1\n"
        "        return gf.Function('replacement', docstring=gf.Docstring('Replacement text'))\n",
    )
    module = gf.Module(name="example")
    target = gf.Function(name="original")
    module.set_member("original", target)
    try:
        first = extension.prepare(gf.Alias("First", target, parent=module))
        second = extension.prepare(gf.Alias("Second", target, parent=module))
        assert isinstance(first, gf.Alias)
        assert isinstance(second, gf.Alias)
        assert first.path == "example.First"
        assert second.path == "example.Second"
        assert first.final_target is second.final_target
        assert first.docstring.value == "Replacement text"
        assert extension.prepare(first.final_target) is first.final_target
        assert extension.cache["calls"] == 1
    finally:
        extension.close()


def test_parsing_uses_operation_settings_after_docstring_replacement(tmp_path: Path) -> None:
    extension = make_extension(
        tmp_path,
        "import griffe as gf\n"
        "def setup(extension):\n"
        "    @extension.on_object_resolved\n"
        "    def replace_docstring(obj):\n"
        "        obj.docstring = gf.Docstring('Description\\n\\nArgs:\\n    value: Input marker')\n"
        "        return obj\n",
        parser="google",
    )
    obj = gf.Function(name="example", parameters=gf.Parameters(gf.Parameter("value")))
    try:
        prepared = extension.prepare(obj)
        assert prepared is obj
        assert obj.docstring.parser is gf.Parser.google
        parameters = next(
            section
            for section in obj.docstring.parsed
            if section.kind is gf.DocstringSectionKind.parameters
        )
        assert parameters.value[0].name == "value"
        assert parameters.value[0].description == "Input marker"
    finally:
        extension.close()


def test_parsed_hook_is_skipped_without_docstring(tmp_path: Path) -> None:
    extension = make_extension(
        tmp_path,
        "def setup(extension):\n"
        "    @extension.on_docstring_parsed\n"
        "    def parsed(obj, sections):\n        raise AssertionError('must not run')\n",
    )
    try:
        obj = gf.Function(name="example")
        assert extension.prepare(obj) is obj
    finally:
        extension.close()


def test_invalid_parsed_result_reports_exact_phase_and_cause(tmp_path: Path) -> None:
    extension = make_extension(
        tmp_path,
        "def setup(extension):\n    extension.on_docstring_parsed(lambda obj, sections: None)\n",
    )
    with pytest.raises(ExtensionError, match="docstring_parsed for example") as error:
        extension.prepare(gf.Function(name="example", docstring=gf.Docstring("Description")))
    assert isinstance(error.value.__cause__, TypeError)
    extension.close()


def test_recursive_conversion_filters_semantic_exclusions(tmp_path: Path) -> None:
    extension = make_extension(
        tmp_path,
        "def setup(extension):\n"
        "    extension.on_object_resolved(lambda obj: None if obj.name == 'hidden' else obj)\n",
    )
    module = gf.Module(name="example")
    module.set_member("visible", gf.Function(name="visible"))
    module.set_member("hidden", gf.Function(name="hidden"))
    try:
        result = griffe_to_doc(module, prepare=extension.prepare)
        assert result is not None
        assert [member.name for member in result.members] == ["visible"]
    finally:
        extension.close()


def test_bare_resolver_and_reference_share_preparation_implementation(tmp_path: Path) -> None:
    reference = APIReference({"package": "example", "parser": "google"})
    resolver = Resolver(Settings(parser="google"))
    source = "Description\n\nArgs:\n    value: Input marker"
    first = gf.Function(
        name="first",
        parameters=gf.Parameters(gf.Parameter("value")),
        docstring=gf.Docstring(source),
    )
    second = gf.Function(
        name="second",
        parameters=gf.Parameters(gf.Parameter("value")),
        docstring=gf.Docstring(source),
    )
    try:
        reference.prepare(first)
        resolver.prepare(second)
        first_parameters = next(
            section
            for section in first.docstring.parsed
            if isinstance(section, gf.DocstringSectionParameters)
        )
        second_parameters = next(
            section
            for section in second.docstring.parsed
            if isinstance(section, gf.DocstringSectionParameters)
        )
        assert (
            [(item.name, item.description) for item in first_parameters.value]
            == [(item.name, item.description) for item in second_parameters.value]
            == [("value", "Input marker")]
        )
    finally:
        reference.close()
        resolver.extension.close()


def test_shared_replacement_retains_prepared_sections_and_later_hook_state(tmp_path: Path) -> None:
    extension = make_extension(
        tmp_path,
        "import griffe as gf\n"
        "def setup(extension):\n"
        "    shared = gf.Function('shared', docstring=gf.Docstring('Shared text'))\n"
        "    extension.cache['parsed'] = []\n"
        "    extension.cache['replaced'] = []\n"
        "    @extension.on_object_resolved\n"
        "    def replace(obj):\n"
        "        extension.cache['replaced'].append(obj.name)\n"
        "        return shared\n"
        "    @extension.on_object_resolved(priority=1)\n"
        "    def mutate(obj):\n"
        "        obj.docstring.value += '!'\n"
        "        return obj\n"
        "    @extension.on_docstring_parsed\n"
        "    def parsed(obj, sections):\n"
        "        extension.cache['parsed'].append(obj.path)\n"
        "        return [gf.DocstringSectionText('Transformed section marker')]\n",
    )
    try:
        first = extension.prepare(gf.Function(name="first"))
        prepared_sections = first.docstring.parsed
        second_original = gf.Function(name="second")
        second = extension.prepare(second_original)
        assert extension.prepare(second_original) is second
        assert extension.cache["replaced"] == ["first", "second"]
        assert first is second
        assert second.docstring.value == "Shared text!"
        assert second.docstring.parsed is prepared_sections
        assert second.docstring.parsed[0].value == "Transformed section marker"
        assert extension.cache["parsed"] == ["shared"]
    finally:
        extension.close()


def test_shared_replacement_retains_cached_exclusion(tmp_path: Path) -> None:
    extension = make_extension(
        tmp_path,
        "import griffe as gf\n"
        "def setup(extension):\n"
        "    shared = gf.Function('shared')\n"
        "    extension.cache['later'] = []\n"
        "    extension.cache['replaced'] = []\n"
        "    @extension.on_object_resolved\n"
        "    def replace(obj):\n"
        "        extension.cache['replaced'].append(obj.name)\n"
        "        return shared\n"
        "    @extension.on_object_resolved(priority=1)\n"
        "    def exclude(obj):\n"
        "        extension.cache['later'].append(obj.path)\n"
        "        return None\n",
    )
    try:
        assert extension.prepare(gf.Function(name="first")) is None
        second_original = gf.Function(name="second")
        assert extension.prepare(second_original) is None
        assert extension.prepare(second_original) is None
        assert extension.cache["replaced"] == ["first", "second"]
        assert extension.cache["later"] == ["shared"]
    finally:
        extension.close()


def test_dynamic_inherited_instance_declarations_remain_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = tmp_path / "inherited_instance_declarations.py"
    module_path.write_text(
        "class Shape:\n"
        "    def __init__(self, colour='red'):\n"
        "        self.colour = colour\n"
        "class Circle(Shape):\n"
        "    def __init__(self, radius, colour='blue'):\n"
        "        super().__init__(colour)\n"
        "        self.radius = radius\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    reference = APIReference(
        {
            "package": "inherited_instance_declarations",
            "dynamic": True,
            "sections": [{"contents": [{"name": "Circle", "include_inherited": True}]}],
        }
    )
    try:
        acquired = reference.get_object("inherited_instance_declarations:Circle.colour")
        assert acquired.docstring is None
        assert "instance-attribute" in acquired.labels
        assert reference.resolved[0].contents[0].contents[0].name == "Circle"
    finally:
        reference.close()
        sys.modules.pop("inherited_instance_declarations", None)


@pytest.mark.parametrize("kind", ["class", "module"])
def test_alias_conversion_keeps_authored_children_and_skips_source_imports(kind: str) -> None:
    root = gf.Module(name="example")
    source = gf.Class(name="Original") if kind == "class" else gf.Module(name="Original")
    root.set_member("Original", source)
    method = gf.Function(name="run", docstring=gf.Docstring("Concrete member marker"))
    source.set_member("run", method)
    external = gf.Module(name="external")
    imported = gf.Function(name="imported", docstring=gf.Docstring("Imported member marker"))
    external.set_member("imported", imported)
    source.set_member("imported", gf.Alias("imported", imported, parent=source))
    appearance = gf.Alias("Authored", source, parent=root)
    converted = griffe_to_doc(appearance, inherited=False, skip_aliases=True)
    assert converted.name == "Authored"
    assert [member.name for member in converted.members] == ["run"]
    assert converted.members[0].obj.path == "example.Authored.run"
    assert converted.members[0].obj.docstring.value == "Concrete member marker"
