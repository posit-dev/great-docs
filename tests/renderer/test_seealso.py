from great_docs._apiref._settings import Settings
import textwrap

import griffe as gf
import pytest

from great_docs._apiref import RenderDocFunction, content
from great_docs._apiref._docstring_sections import DocstringSectionSeeAlso, transform
from great_docs._apiref.api_reference import Settings
from great_docs._apiref.resolve import Resolver
from great_docs._apiref.spec import SpecSection
from great_docs._builtin.directives._seealso import add_seealso


def _obj(doc: str, parser: str = "numpy") -> gf.Function:
    """Build a Griffe function carrying `doc` in the selected parser style"""
    fn = gf.Function("f")
    fn.docstring = gf.Docstring(textwrap.dedent(doc), lineno=1, parent=fn, parser=parser)
    return fn


def _see_also(obj: gf.Object | gf.Alias) -> list[DocstringSectionSeeAlso]:
    """Return the transformed See Also sections for `obj`"""
    assert obj.docstring is not None
    return [
        section
        for section in transform(obj.docstring.parsed)
        if isinstance(section, DocstringSectionSeeAlso)
    ]


def test_seealso_appends_a_source_section():
    obj = _obj(
        """
        Summary.

        %seealso foo : does foo, bar
        """
    )

    result = add_seealso(obj)

    assert result is obj
    assert obj.docstring is not None
    assert obj.docstring.value == "Summary.\n\nSee Also\n--------\nfoo : does foo\nbar"


def test_multiple_seealso_directives_are_combined():
    obj = _obj(
        """
        Summary.

        %seealso foo : does foo
        %seealso bar, baz : does baz
        """
    )

    add_seealso(obj)

    assert obj.docstring is not None
    assert obj.docstring.value.endswith("See Also\n--------\nfoo : does foo\nbar\nbaz : does baz")


def test_bare_seealso_does_not_consume_following_content():
    obj = _obj(
        """
        Summary.

        %seealso
        Important prose.
        """
    )

    add_seealso(obj)

    assert obj.docstring is not None
    assert obj.docstring.value == "Summary.\n\nImportant prose."


def test_bare_seealso_only_leaves_empty_source():
    obj = _obj("%seealso")

    add_seealso(obj)

    assert obj.docstring is not None
    assert obj.docstring.value == ""


def test_seealso_deduplicates_repeated_new_entries():
    obj = _obj(
        """
        Summary.

        %seealso foo : first, foo : second
        %seealso bar, bar
        """
    )

    add_seealso(obj)

    assert obj.docstring is not None
    assert obj.docstring.value.endswith("See Also\n--------\nfoo : first\nbar")


def test_seealso_merges_into_native_source_and_deduplicates():
    obj = _obj(
        """
        Summary.

        %seealso bar : new bar, foo : duplicate

        See Also
        --------
        foo : native description
        """
    )

    add_seealso(obj)

    assert obj.docstring is not None
    assert obj.docstring.value.count("See Also\n--------") == 1
    assert obj.docstring.value.endswith(
        "See Also\n--------\nfoo : native description\nbar : new bar"
    )


def test_seealso_merge_preserves_following_section():
    obj = _obj(
        """
        Summary.

        %seealso bar : Related.

        See Also
        --------
        foo : Native.

        Notes
        -----
        Keep this.
        """
    )

    add_seealso(obj)

    assert obj.docstring is not None
    assert "foo : Native.\nbar : Related.\n\nNotes\n-----\nKeep this." in obj.docstring.value


def test_no_seealso_leaves_docstring_untouched():
    obj = _obj(
        """
        Summary.

        Parameters
        ----------
        x : int
        """
    )
    assert obj.docstring is not None
    before = obj.docstring.value

    result = add_seealso(obj)

    assert result is obj
    assert obj.docstring.value == before


def test_add_seealso_passes_through_an_object_without_a_docstring():
    obj = gf.Function("f")

    assert add_seealso(obj) is obj


def test_seealso_registers_on_object_resolved():
    from great_docs.hooks import _docstring_parsed, _object_resolved

    assert add_seealso in _object_resolved.REGISTRY
    assert add_seealso not in _docstring_parsed.REGISTRY


def test_seealso_handler_does_not_touch_cached_sections():
    obj = _obj("Summary.\n\n%seealso target")
    assert obj.docstring is not None
    sentinel = object()
    obj.docstring.__dict__["parsed"] = sentinel

    add_seealso(obj)

    assert obj.docstring.__dict__["parsed"] is sentinel


def test_nodoc_and_seealso_object_is_dropped():
    from great_docs.hooks._object_resolved import emit_object_resolved

    obj = _obj(
        """
        Internal.

        %nodoc
        %seealso foo
        """
    )

    assert emit_object_resolved(obj) is None


@pytest.mark.parametrize(
    "doc",
    [
        """
        Summary.

        Parameters
        ----------
        value : int
            %seealso target : Related.
        """,
        """
        Summary.

        Examples
        --------
        Explanation.
        %seealso target : Related.
        """,
        """
        Summary.

        Notes
        -----
        %seealso target : Related.
        """,
    ],
)
def test_nested_seealso_moves_to_a_top_level_source_section(doc: str):
    obj = _obj(doc)

    add_seealso(obj)

    assert obj.docstring is not None
    assert "%seealso" not in obj.docstring.value
    assert obj.docstring.value.endswith("See Also\n--------\ntarget : Related.")
    assert "\n    See Also\n" not in obj.docstring.value


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_fenced_seealso_remains_literal(fence: str):
    obj = _obj(
        f"""
        Summary.

        {fence}text
        %seealso target : Literal example.
        {fence}
        """
    )
    assert obj.docstring is not None
    before = obj.docstring.value

    add_seealso(obj)

    assert obj.docstring.value == before


def test_seealso_normalization_is_idempotent():
    obj = _obj("Summary.\n\n%seealso target : Related.")

    add_seealso(obj)
    assert obj.docstring is not None
    first = obj.docstring.value
    add_seealso(obj)

    assert obj.docstring.value == first


@pytest.mark.parametrize("parser", ["numpy", "google", "sphinx"])
def test_generated_seealso_is_recognized_for_every_parser(parser: str):
    obj = _obj("Summary.\n\n%seealso target : Related.", parser=parser)

    add_seealso(obj)

    sections = _see_also(obj)
    assert len(sections) == 1
    assert sections[0].value == "target : Related."


def test_resolving_the_same_object_twice_keeps_seealso():
    from great_docs.hooks._docstring_parsed import emit_docstring_parsed
    from great_docs.hooks._object_resolved import emit_object_resolved

    obj = _obj("Summary.\n\n%seealso target : Related.")

    for _ in range(2):
        assert emit_object_resolved(obj) is obj
        emit_docstring_parsed(obj)
        sections = _see_also(obj)
        assert len(sections) == 1
        assert sections[0].value == "target : Related."


def test_duplicate_reference_entries_keep_seealso():
    obj = _obj("Summary.\n\n%seealso target : Related.")
    resolver = Resolver(Settings(parser="numpy"))
    resolver.current_package = "pkg"
    resolver.get_object = lambda *_args, **_kwargs: obj
    section = SpecSection(title="Functions", contents=["f", "f"])

    [resolved] = resolver.resolve_sections([section])

    assert len(resolved.contents) == 2
    for page in resolved.contents:
        assert isinstance(page, content.Page)
        sections = _see_also(page.obj)
        assert len(sections) == 1
        assert sections[0].value == "target : Related."


def test_alias_and_target_share_idempotent_seealso_source():
    module = gf.Module("pkg")
    target = gf.Function("f", parent=module)
    target.docstring = gf.Docstring(
        "Summary.\n\n%seealso related",
        parent=target,
        parser="numpy",
    )
    alias = gf.Alias("alias", target, parent=module)

    add_seealso(alias)
    assert target.docstring is not None
    first = target.docstring.value
    add_seealso(target)

    assert target.docstring.value == first
    assert first.endswith("See Also\n--------\nrelated")


def test_empty_docstring_value_has_no_subject():
    obj = _obj("")
    assert obj.docstring is not None
    obj.docstring.__dict__["parsed"] = [gf.DocstringSectionText("")]
    renderer = RenderDocFunction(content.Doc.from_griffe(obj.name, obj), settings=Settings())

    assert renderer.docstring_subject is None


def test_directive_only_seealso_renders_every_reference_without_a_subject():
    obj = _obj("%seealso first : First reference, second : Second reference")
    add_seealso(obj)
    renderer = RenderDocFunction(content.Doc.from_griffe(obj.name, obj), settings=Settings())

    body = str(renderer.render_body())

    assert renderer.docstring_subject is None
    assert "first" in body
    assert "second" in body


def test_add_seealso_noop_when_all_entries_already_present():
    """add_seealso returns the text unchanged when all entries are already in the section."""
    from great_docs._builtin.directives._seealso import add_seealso

    # Pre-seed the object with a docstring that already contains the seealso entries
    obj = _obj("%seealso existing_func")
    add_seealso(obj)

    # Call add_seealso again (all entries already present, nothing to add)
    text_before = obj.docstring.value if obj.docstring else ""
    add_seealso(obj)
    text_after = obj.docstring.value if obj.docstring else ""

    # The docstring content should not have grown with duplicate entries
    assert text_after.count("existing_func") == text_before.count("existing_func")


def test_existing_names_unmatched_part_is_silently_skipped():
    """_existing_names silently skips parts that don't match the name regex."""
    from great_docs._builtin.directives._seealso import _existing_names

    # "!!!" is not a valid identifier, so the regex won't match
    contents = "valid_func\n!!!"
    names = _existing_names(contents)

    assert "valid_func" in names
    assert "!!!" not in names


def test_merge_seealso_no_new_entries_returns_text_unchanged():
    """_merge_seealso returns text unchanged when all entries are already present."""
    from great_docs._builtin.directives._seealso import _merge_seealso

    # Text already has a See Also section with 'existing_func'
    text = "Summary.\n\nSee Also\n--------\nexisting_func\n"

    # Entries list has only names already in the section
    result = _merge_seealso(text, [("existing_func", "")])

    assert result == text
