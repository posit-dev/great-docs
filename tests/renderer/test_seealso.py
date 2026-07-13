import textwrap

import griffe as gf

from great_docs._builtin._directives import add_seealso


def _obj(doc: str) -> gf.Function:
    """Build a griffe object carrying a numpy-parsed docstring for `doc`"""
    fn = gf.Function("f")
    fn.docstring = gf.Docstring(textwrap.dedent(doc), lineno=1, parent=fn, parser="numpy")
    return fn


def _see_also(obj: gf.Function) -> gf.DocstringSectionAdmonition | None:
    """Return the object's See Also admonition, or `None`"""
    for section in obj.docstring.parsed:
        if isinstance(section, gf.DocstringSectionAdmonition) and (
            (section.title or "").lower() == "see also"
        ):
            return section
    return None


def test_seealso_only_injects_section():
    obj = _obj(
        """
        Summary.

        %seealso foo : does foo, bar
        """
    )
    result = add_seealso(obj)
    assert result is obj
    assert "%seealso" not in obj.docstring.value
    section = _see_also(obj)
    assert section is not None
    assert section.value.contents == "foo : does foo\nbar"


def test_seealso_merges_into_native_and_dedups():
    obj = _obj(
        """
        Summary.

        %seealso bar : new bar, foo : dup foo

        See Also
        --------
        foo : native desc
        """
    )
    add_seealso(obj)
    sections = [
        s
        for s in obj.docstring.parsed
        if isinstance(s, gf.DocstringSectionAdmonition) and (s.title or "").lower() == "see also"
    ]
    # A single merged section, native entry kept, `foo` not duplicated.
    assert len(sections) == 1
    contents = sections[0].value.contents
    assert "foo : native desc" in contents
    assert "bar : new bar" in contents
    assert contents.count("foo") == 1


def test_no_seealso_leaves_docstring_untouched():
    obj = _obj(
        """
        Summary.

        Parameters
        ----------
        x : int
        """
    )
    before = obj.docstring.value
    result = add_seealso(obj)
    assert result is obj
    assert obj.docstring.value == before
    assert _see_also(obj) is None


def test_object_without_docstring_passes_through():
    fn = gf.Function("f")
    fn.docstring = None
    assert add_seealso(fn) is fn


def test_add_seealso_registers_on_import():
    from great_docs.hooks import _object_resolved

    assert add_seealso in _object_resolved._OBJECT_RESOLVED_HOOKS


def test_nodoc_is_registered_before_seealso():
    # nodoc must short-circuit before seealso runs.
    from great_docs._builtin._directives import exclude_nodoc
    from great_docs.hooks import _object_resolved

    order = _object_resolved._OBJECT_RESOLVED_HOOKS
    assert order.index(exclude_nodoc) < order.index(add_seealso)
