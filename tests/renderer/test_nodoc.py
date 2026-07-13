from types import SimpleNamespace

from great_docs._builtin._directives import exclude_nodoc


def _obj(doc: str | None) -> SimpleNamespace:
    """Build a minimal stand-in for a griffe object exposing a docstring"""
    docstring = SimpleNamespace(value=doc) if doc is not None else None
    return SimpleNamespace(docstring=docstring)


def test_object_tagged_nodoc_is_skipped():
    assert exclude_nodoc(_obj("Internal.\n\n%nodoc\n")) is None


def test_plain_object_passes_through_unchanged():
    obj = _obj("A normal docstring.")
    assert exclude_nodoc(obj) is obj


def test_object_without_docstring_passes_through():
    obj = _obj(None)
    assert exclude_nodoc(obj) is obj


def test_exclude_nodoc_registers_on_import():
    # exclude_nodoc registered via this module's top-level import (the decorator).
    from great_docs.hooks import _object_resolved

    assert exclude_nodoc in _object_resolved._OBJECT_RESOLVED_HOOKS


import textwrap


def _all_paths(sections) -> set[str]:
    """Collect every documented object path reachable in a resolved section list"""
    from great_docs._apiref.content import Doc, Page, Section

    found: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, Doc):
            found.add(node.obj.path)
            for m in getattr(node, "members", []):
                walk(m)
        elif isinstance(node, (Section, Page)):
            for c in node.contents:
                walk(c)

    for s in sections:
        walk(s)
    return found


def test_resolver_skips_nodoc_objects(tmp_path, monkeypatch):
    pkg = tmp_path / "gdnodoc"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        textwrap.dedent(
            """
            from gdnodoc.mod import Visible, Hidden
            __all__ = ["Visible", "Hidden"]
            """
        )
    )
    (pkg / "mod.py").write_text(
        textwrap.dedent(
            '''
            class Visible:
                """A visible class."""

            class Hidden:
                """Internal.

                %nodoc
                """
            '''
        )
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    from great_docs._apiref import spec
    from great_docs._apiref.resolve import resolve

    sections = [spec.SpecSection(title="API", contents=["Visible", "Hidden"])]
    resolved = resolve(sections, package="gdnodoc")

    paths = _all_paths(resolved)
    assert any(p.endswith("Visible") for p in paths)
    assert not any(p.endswith("Hidden") for p in paths)


def test_importing_great_docs_registers_builtin_handlers():
    """Importing `great_docs` in a fresh interpreter registers the built-in handlers

    Runs in a subprocess: the parent process's test imports pull in the handler
    module directly (registering it), which would otherwise mask the
    `great_docs/__init__` auto-load this asserts.
    """
    import subprocess
    import sys
    import textwrap

    code = textwrap.dedent(
        """
        import great_docs  # noqa: F401
        from great_docs.hooks import _object_resolved

        modules = {h.__module__ for h in _object_resolved._OBJECT_RESOLVED_HOOKS}
        assert "great_docs._builtin._directives" in modules, modules
        """
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_resolve_drops_section_left_empty_by_nodoc(tmp_path, monkeypatch):
    pkg = tmp_path / "gdempty"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("from gdempty.mod import Hidden\n__all__ = ['Hidden']\n")
    (pkg / "mod.py").write_text('class Hidden:\n    """Internal.\n\n    %nodoc\n    """\n')
    monkeypatch.syspath_prepend(str(tmp_path))

    from great_docs._apiref import spec
    from great_docs._apiref.resolve import resolve

    sections = [spec.SpecSection(title="Only", contents=["Hidden"])]
    assert resolve(sections, package="gdempty") == []


def test_apireference_documented_symbols_includes_documented_members(tmp_path, monkeypatch):
    pkg = tmp_path / "gddisc"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("from gddisc.mod import Widget\n__all__ = ['Widget']\n")
    (pkg / "mod.py").write_text(
        'class Widget:\n'
        '    """A widget."""\n'
        '    def fit(self):\n'
        '        """Fit it."""\n'
        '    def _priv(self): ...\n'
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    from great_docs._apiref.api_reference import APIReference

    ref = APIReference(
        {"api-reference": {"package": "gddisc", "sections": [{"title": "API", "contents": ["Widget"]}]}}
    )
    # `fit` discovered AND documented -> included; `_priv` private -> excluded.
    assert ref.documented_symbols == ["Widget", "Widget.fit"]
