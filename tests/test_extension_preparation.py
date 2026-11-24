"""
Verify the prepared documentation that every consumer of a reference reads

Aliases share one preparation of their canonical object, and exclusions and
replacements are cached. Parsing uses the reference's parser and language, and
failures in object and docstring hooks raise `ExtensionError`. Converting members
respects hook exclusions and authored alias names. Pages, typing pages and the text
export see the same preparation in any order, and the standalone rendering helpers
prepare objects too.
"""

from __future__ import annotations

import gc
import weakref
from contextvars import copy_context
from itertools import permutations

import griffe as gf
import pytest

from great_docs._apiref._conversion import griffe_to_doc
from great_docs._apiref._export import reference_text
from great_docs._apiref._settings import CallableSignatures, Settings
from great_docs._apiref._tools import render_code_variable
from great_docs._apiref.introspect import DEFAULT_OPTIONS
from great_docs._apiref.resolve import Resolver, resolution_lang
from great_docs._apiref.typing_information import TypeInformation
from great_docs.extensions import Extension, ExtensionError
from great_docs.hooks._object_resolved import REGISTRY as OBJECT_HOOKS
from tests.support import MakeReference, WriteExtension

PACKAGE = "preparation_order_example"


@pytest.mark.parametrize("order", [("First", "Second"), ("Second", "First")])
def test_aliases_share_one_preparation(write_extension: WriteExtension, order: tuple[str, str]):
    source = write_extension(
        """
        def setup(extension):
            extension.cache['objects'] = []
            extension.cache['parsed'] = []

            @extension.on_object_resolved
            def transform(obj):
                extension.cache['objects'].append(obj.path)
                obj.docstring.value += '\\n\\nHook marker'
                return obj

            @extension.on_docstring_parsed
            def parsed(obj, sections):
                extension.cache['parsed'].append(obj.path)
                return sections
        """
    )
    extension = Extension(Settings(), source)
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
        assert target.docstring.value.count("Hook marker") == 1
        assert all(obj.docstring is target.docstring for obj in results)
    finally:
        extension.close()


def test_excluded_aliases_are_memoised_and_original_is_retained(write_extension: WriteExtension):
    source = write_extension(
        """
        def setup(extension):
            extension.cache['calls'] = 0

            @extension.on_object_resolved
            def exclude(obj):
                extension.cache['calls'] += 1
                return None
        """
    )
    extension = Extension(Settings(), source)
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


def test_replacement_preserves_authored_alias_views(write_extension: WriteExtension):
    source = write_extension(
        """
        import griffe as gf

        def setup(extension):
            extension.cache['calls'] = 0

            @extension.on_object_resolved
            def replace(obj):
                extension.cache['calls'] += 1
                return gf.Function('replacement', docstring=gf.Docstring('Replacement text'))
        """
    )
    extension = Extension(Settings(), source)
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


def test_shared_replacement_retains_prepared_sections_and_later_hook_state(
    write_extension: WriteExtension,
):
    source = write_extension(
        """
        import griffe as gf

        def setup(extension):
            shared = gf.Function('shared', docstring=gf.Docstring('Shared text'))
            extension.cache['parsed'] = []
            extension.cache['replaced'] = []

            @extension.on_object_resolved
            def replace(obj):
                extension.cache['replaced'].append(obj.name)
                return shared

            @extension.on_object_resolved(priority=1)
            def mutate(obj):
                obj.docstring.value += '!'
                return obj

            @extension.on_docstring_parsed
            def parsed(obj, sections):
                extension.cache['parsed'].append(obj.path)
                return [gf.DocstringSectionText('Transformed section marker')]
        """
    )
    extension = Extension(Settings(), source)
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


def test_shared_replacement_retains_cached_exclusion(write_extension: WriteExtension):
    source = write_extension(
        """
        import griffe as gf

        def setup(extension):
            shared = gf.Function('shared')
            extension.cache['later'] = []
            extension.cache['replaced'] = []

            @extension.on_object_resolved
            def replace(obj):
                extension.cache['replaced'].append(obj.name)
                return shared

            @extension.on_object_resolved(priority=1)
            def exclude(obj):
                extension.cache['later'].append(obj.path)
                return None
        """
    )
    extension = Extension(Settings(), source)
    try:
        assert extension.prepare(gf.Function(name="first")) is None
        second_original = gf.Function(name="second")
        assert extension.prepare(second_original) is None
        assert extension.prepare(second_original) is None
        assert extension.cache["replaced"] == ["first", "second"]
        assert extension.cache["later"] == ["shared"]
    finally:
        extension.close()


def test_parsing_uses_operation_settings_after_docstring_replacement(
    write_extension: WriteExtension,
):
    source = write_extension(
        """
        import griffe as gf

        def setup(extension):
            @extension.on_object_resolved
            def replace_docstring(obj):
                obj.docstring = gf.Docstring('Description\\n\\nArgs:\\n    value: Input marker')
                return obj
        """
    )
    extension = Extension(Settings(parser="google"), source)
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


def test_bare_resolver_and_reference_share_preparation_implementation(
    make_reference: MakeReference,
):
    reference = make_reference({"package": "example", "parser": "google"})
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
        resolver.extension.close()


def test_parsed_hook_is_skipped_without_docstring(write_extension: WriteExtension):
    source = write_extension(
        """
        def setup(extension):
            @extension.on_docstring_parsed
            def parsed(obj, sections):
                raise AssertionError('must not run')
        """
    )
    extension = Extension(Settings(), source)
    try:
        obj = gf.Function(name="example")
        assert extension.prepare(obj) is obj
    finally:
        extension.close()


def test_invalid_parsed_result_reports_exact_phase_and_cause(write_extension: WriteExtension):
    source = write_extension(
        """
        def setup(extension):
            extension.on_docstring_parsed(lambda obj, sections: None)
        """
    )
    extension = Extension(Settings(), source)
    with pytest.raises(ExtensionError, match="docstring_parsed for example") as error:
        extension.prepare(gf.Function(name="example", docstring=gf.Docstring("Description")))
    assert isinstance(error.value.__cause__, TypeError)
    extension.close()


def test_configured_hook_failure_is_an_extension_error(
    write_extension: WriteExtension, make_reference: MakeReference
):
    source = write_extension(
        """
        def setup(extension):
            @extension.on_object_resolved
            def transform(obj):
                raise ImportError('configured hook failure')
        """
    )
    reference = make_reference(
        {"package": PACKAGE, "sections": [{"contents": ["public"]}]},
        source,
        package_files={"__init__.py": 'def public():\n    """Original subject"""\n'},
    )
    with pytest.raises(ExtensionError, match="object_resolved") as failure:
        _ = reference.resolved
    # The build treats a bare `ImportError` as a package failure, which it reports as a
    # warning or retries with static analysis.
    assert isinstance(failure.value.__cause__, ImportError)


def test_object_and_docstring_hooks_see_the_operation_language_only_while_preparing():
    extension = Extension(Settings(lang="fr"))
    seen: list[tuple[str, str]] = []

    @extension.on_object_resolved
    def record_object(obj: gf.Object) -> gf.Object:
        seen.append(("object_resolved", resolution_lang.get()))
        return obj

    @extension.on_docstring_parsed
    def record_sections(
        obj: gf.Object, sections: list[gf.DocstringSection]
    ) -> list[gf.DocstringSection]:
        seen.append(("docstring_parsed", resolution_lang.get()))
        return sections

    def prepare() -> str:
        resolution_lang.set("ja")
        extension.prepare(gf.Function(name="example", docstring=gf.Docstring("Description")))
        return resolution_lang.get()

    assert copy_context().run(prepare) == "ja"
    assert seen == [("object_resolved", "fr"), ("docstring_parsed", "fr")]
    extension.close()


def test_recursive_conversion_filters_hook_exclusions(write_extension: WriteExtension):
    source = write_extension(
        """
        def setup(extension):
            extension.on_object_resolved(lambda obj: None if obj.name == 'hidden' else obj)
        """
    )
    extension = Extension(Settings(), source)
    module = gf.Module(name="example")
    module.set_member("visible", gf.Function(name="visible"))
    module.set_member("hidden", gf.Function(name="hidden"))
    try:
        result = griffe_to_doc(module, prepare=extension.prepare)
        assert result is not None
        assert [member.name for member in result.members] == ["visible"]
    finally:
        extension.close()


@pytest.mark.parametrize("kind", ["class", "module"])
def test_alias_conversion_keeps_authored_children_and_skips_source_imports(kind: str):
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


@pytest.mark.parametrize("order", list(permutations(["export", "page", "typing"])))
@pytest.mark.parametrize("dynamic", [False, True])
def test_consumers_share_preparation_regardless_of_order(
    write_extension: WriteExtension,
    make_reference: MakeReference,
    order: tuple[str, ...],
    dynamic: bool,
):
    source = write_extension(
        """
        import griffe as gf
        from great_docs.extensions import Extension

        def setup(extension: Extension) -> None:
            calls: list[str] = []
            seen: dict[str, str | None] = {}
            extension.cache["calls"] = calls
            extension.cache["seen"] = seen

            @extension.on_object_resolved
            def prepare(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
                calls.append(obj.path)
                seen[obj.path] = obj.docstring.value if obj.docstring is not None else None
                if obj.name == "Document":
                    obj.docstring = gf.Docstring("Prepared subject\\n\\nPREPARED_DOCUMENT_BODY", parent=obj)
                return obj
        """
    )
    ref = make_reference(
        {
            "package": PACKAGE,
            "dynamic": dynamic,
            "sections": [{"title": "API", "contents": ["Document", "Alias"]}],
        },
        source,
        package_files={
            "__init__.py": "from .types import Document\nfrom .types import Document as Alias\n",
            "types.py": '''
                from typing import Protocol

                class Document(Protocol):
                    """Original subject"""

                    def render(self, text: str = "default") -> str:
                        """Render subject"""

                Document.__doc__ = "Runtime subject"
                Document.render.__doc__ = "Runtime render subject"
            ''',
        },
    )
    outputs: dict[str, str] = {}
    for consumer in order:
        if consumer == "export":
            outputs[consumer] = reference_text(ref)
        elif consumer == "page":
            outputs[consumer] = str(
                ref.renderers.make(ref.resolved[0].contents[0], extension=Extension(ref.settings))
            )
        else:
            outputs[consumer] = str(TypeInformation(f"{ref.package}.types", ref))
    assert all("PREPARED_DOCUMENT_BODY" in output for output in outputs.values())
    assert all("Original subject" not in output for output in outputs.values())
    calls = ref.extension.cache["calls"]
    assert isinstance(calls, list)
    assert calls.count(f"{ref.package}.types.Document") == 1
    assert calls.count(f"{ref.package}.types.Document.render") == 1
    seen = ref.extension.cache["seen"]
    assert isinstance(seen, dict)
    assert seen[f"{ref.package}.types.Document"] == (
        "Runtime subject" if dynamic else "Original subject"
    )
    assert seen[f"{ref.package}.types.Document.render"] == (
        "Runtime render subject" if dynamic else "Render subject"
    )
    assert {"Document", "Alias", "Document.render", "Alias.render"} <= set(ref.documented_symbols)


def test_prepared_callable_alias_keeps_its_docstring(make_reference: MakeReference) -> None:
    ref = make_reference(
        {"package": PACKAGE, "dynamic": True},
        package_files={
            "__init__.py": '''
                def render():
                    """Render the document"""

                show = render
                """Show the document"""
            ''',
        },
    )

    @ref.extension.on_object_resolved
    def prepare(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
        obj.docstring = gf.Docstring("Show the prepared document")
        return obj

    path = f"{PACKAGE}:show"
    alias = ref.get_object(path)
    assert isinstance(alias, gf.Function)
    assert alias.docstring.value == "Show the document"
    assert ref.prepare(alias) is alias

    reacquired = ref.get_object(path)
    assert reacquired.docstring.value == "Show the prepared document"


def test_prepared_reexposed_class_keeps_its_docstring(make_reference: MakeReference) -> None:
    ref = make_reference(
        {"package": PACKAGE, "dynamic": True},
        package_files={
            "__init__.py": '''
                class Document:
                    """Render a document"""

                Report = Document
                """Render a report"""
            ''',
        },
    )

    @ref.extension.on_object_resolved
    def prepare(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
        obj.docstring = gf.Docstring("Render a prepared report")
        return obj

    path = f"{PACKAGE}:Report"
    report = ref.get_object(path)
    assert isinstance(report, gf.Class)
    assert report.docstring.value == "Render a report"
    assert ref.prepare(report) is report

    reacquired = ref.get_object(path)
    assert reacquired.docstring.value == "Render a prepared report"
    assert reacquired is report


def test_object_hooks_run_before_documented_dunder_selection(
    write_extension: WriteExtension, make_reference: MakeReference
):
    source = write_extension(
        """
        import griffe as gf
        from great_docs.extensions import Extension

        def setup(extension: Extension) -> None:
            @extension.on_object_resolved
            def document(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
                if obj.name == "__iter__":
                    obj.docstring = gf.Docstring("Iterate over the contents", parent=obj)
                return obj
        """
    )
    ref = make_reference(
        {
            "package": PACKAGE,
            "dynamic": False,
            "sections": [{"title": "API", "contents": ["Container"]}],
        },
        source,
        package_files={"__init__.py": "class Container:\n    def __iter__(self):\n        pass\n"},
    )
    assert "Container.__iter__" in ref.documented_symbols


def test_hook_added_parameter_directive_affects_pages_and_export(
    write_extension: WriteExtension, make_reference: MakeReference
):
    source = write_extension(
        """
        import griffe as gf
        from great_docs.extensions import Extension

        def setup(extension: Extension) -> None:
            @extension.on_object_resolved(priority=-200)
            def exclude_parameter(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
                if obj.name == "call" and obj.docstring is not None:
                    obj.docstring.value += "\\n\\n%nodoc_param hidden"
                return obj
        """
    )
    ref = make_reference(
        {
            "package": PACKAGE,
            "dynamic": False,
            "sections": [{"title": "API", "contents": ["call"]}],
        },
        source,
        package_files={
            "__init__.py": '''
                def call(visible: int, hidden: str = "secret"):
                    """Call subject

                    Parameters
                    ----------
                    visible
                        Visible parameter.
                    hidden
                        Hidden parameter.
                    """
            '''
        },
    )
    page = str(ref.renderers.make(ref.resolved[0].contents[0], extension=Extension(ref.settings)))
    for output in (page, reference_text(ref)):
        assert "visible" in output
        assert "hidden" not in output
        assert "%nodoc_param" not in output


def test_unselected_imports_do_not_require_optional_dependencies(
    write_extension: WriteExtension, make_reference: MakeReference
):
    source = write_extension(
        """
        from great_docs.extensions import Extension

        def setup(extension: Extension) -> None:
            pass
        """
    )
    ref = make_reference(
        {
            "package": PACKAGE,
            "dynamic": False,
            "sections": [{"title": "API", "contents": ["module"]}],
        },
        source,
        package_files={
            "__init__.py": "",
            "module.py": '''
                from unavailable_optional_dependency import External

                def visible():
                    """Visible function"""
            ''',
        },
    )
    assert "module.visible" in ref.documented_symbols
    assert "module.External" not in ref.documented_symbols


def test_dynamic_inherited_instance_declarations_remain_available(make_reference: MakeReference):
    reference = make_reference(
        {
            "package": "inherited_instance_declarations",
            "dynamic": True,
            "sections": [{"contents": [{"name": "Circle", "include_inherited": True}]}],
        },
        package_files={
            "__init__.py": """
                class Shape:
                    def __init__(self, colour='red'):
                        self.colour = colour

                class Circle(Shape):
                    def __init__(self, radius, colour='blue'):
                        super().__init__(colour)
                        self.radius = radius
            """
        },
    )
    acquired = reference.get_object("inherited_instance_declarations:Circle.colour")
    assert acquired.docstring is None
    assert "instance-attribute" in acquired.labels
    assert reference.resolved[0].contents[0].contents[0].name == "Circle"


def test_helper_applies_parser_defaults_and_presentation_settings(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setitem(DEFAULT_OPTIONS, "google", {"warn_missing_types": False})
    snapshot = OBJECT_HOOKS.snapshot()
    seen: dict[str, object] = {}

    @OBJECT_HOOKS.register
    def record(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
        assert obj.docstring is not None
        seen["parser"] = obj.docstring.parser
        seen["options"] = dict(obj.docstring.parser_options)
        return obj

    source = '''
def run(value):
    """Run the helper

    Args:
        value (int): A Google-style parameter.
    """
'''
    settings = Settings(parser="google", callable_signatures=CallableSignatures(style="plain"))
    try:
        rendered = render_code_variable(source, "run", settings)
    finally:
        OBJECT_HOOKS.restore(snapshot)
    assert "A Google-style parameter." in rendered
    assert "[run]{.sig-name}" in rendered
    assert "```pythonsignature" not in rendered
    assert seen["parser"] == "google"
    assert seen["options"] == {"warn_missing_types": False}


def test_standalone_helper_uses_template_preparation():
    snapshot = OBJECT_HOOKS.snapshot()

    @OBJECT_HOOKS.register
    def transform(obj: gf.Object | gf.Alias) -> gf.Object | gf.Alias:
        if obj.docstring is not None:
            obj.docstring.value = "Prepared helper documentation"
        return obj

    try:
        rendered = render_code_variable('def run():\n    """Original documentation"""\n', "run")
        assert "Prepared helper documentation" in rendered
        assert "Original documentation" not in rendered
    finally:
        OBJECT_HOOKS.restore(snapshot)
