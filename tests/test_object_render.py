"""Verify the object renderer's docstring sections and repository source links"""

from __future__ import annotations

import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import griffe as gf
import pytest

import great_docs._apiref._rendering.objects as objects
from great_docs._apiref._rendering._source_links import source_relative_path
from great_docs._apiref._rendering.objects import ObjectRenderer
from great_docs._apiref._settings import Settings, SourceLinks
from great_docs._project.repository import Repository


def _get_private_cls():
    """
    Look up the object renderer class in its defining module

    Returns
    -------
    :
        The `ObjectRenderer` class of `great_docs._apiref._rendering.objects`.
    """
    return vars(objects)["ObjectRenderer"]


class TestRenderAnnotationTildePrefix:
    def test_tilde_prefix_returns_canonical_name(self):
        """When canonical_path starts with '~', returns canonical_name."""
        cls = _get_private_cls()

        mock_expr = MagicMock(spec=gf.Expr)
        mock_expr.canonical_path = "~mod.sub.Widget"
        mock_expr.canonical_name = "Widget"

        fake_attr = MagicMock(spec=gf.Attribute)
        fake_attr.annotation = mock_expr
        fake_attr.kind = gf.Kind("attribute")

        fake_self = types.SimpleNamespace(obj=fake_attr)

        result = cls.__dict__["render_annotation"](fake_self, annotation=mock_expr)
        assert "Widget" in result


class TestRenderModulesSection:
    def test_modules_section_suppressed(self):
        """render_modules_section returns None."""
        cls = _get_private_cls()
        fake_self = types.SimpleNamespace(_suppress_section=lambda el: None)
        el = MagicMock(spec=gf.DocstringSectionModules)

        result = cls.render_modules_section(fake_self, el)
        assert result is None


class TestRenderExampleFragment:
    def test_unrecognized_fragment_returns_empty(self):
        """When fragment is not ExampleCode or ExampleText, returns ''."""
        cls = _get_private_cls()
        fake_self = types.SimpleNamespace()

        with patch("great_docs._apiref._rendering.objects.transform", return_value="unexpected"):
            result = cls._render_example_fragment(fake_self, MagicMock())

        assert result == ""


class TestRenderAdmonitionSection:
    def test_returns_description(self):
        """render_admonition_section returns el.value.description."""
        cls = _get_private_cls()
        fake_self = types.SimpleNamespace()

        el = MagicMock(spec=gf.DocstringSectionAdmonition)
        el.value = MagicMock()
        el.value.description = "Be careful with this function."

        result = cls.render_admonition_section(fake_self, el)
        assert result == "Be careful with this function."


class TestRenderWarningsSection:
    def test_returns_value(self):
        """render_warnings_section returns el.value."""
        from great_docs._apiref._docstring_sections import DocstringSectionWarnings

        cls = _get_private_cls()
        fake_self = types.SimpleNamespace()

        el = MagicMock(spec=DocstringSectionWarnings)
        el.value = "This may cause data loss."

        result = cls.render_warnings_section(fake_self, el)
        assert result == "This may cause data loss."


class TestRenderNotesSection:
    def test_returns_value(self):
        """render_notes_section returns el.value."""
        from great_docs._apiref._docstring_sections import DocstringSectionNotes

        cls = _get_private_cls()
        fake_self = types.SimpleNamespace()

        el = MagicMock(spec=DocstringSectionNotes)
        el.value = "Implementation uses Cython internally."

        result = cls.render_notes_section(fake_self, el)
        assert result == "Implementation uses Cython internally."


class TestRenderSeeAlsoSectionSkipEmpty:
    def test_empty_lines_skipped(self):
        """Empty lines in see_also content are skipped."""
        cls = _get_private_cls()
        fake_self = types.SimpleNamespace()

        el = MagicMock()
        el.value = [("func_a", "Description A")]
        with patch(
            "great_docs._apiref._rendering.objects.format_see_also",
            return_value="foo:description\n\nbar:other description",
        ):
            result = cls.render_see_also_section(fake_self, el)

        result_str = str(result)

        assert "foo" in result_str
        assert "bar" in result_str


LINKED = SourceLinks(repository=Repository.parse("https://github.com/user/repo"))


@pytest.mark.parametrize(("provider", "anchor"), [("github", "#L3-L8"), ("gitlab", "#L3-8")])
def test_source_links_use_provider_routes(provider: str, anchor: str) -> None:
    repository = Repository.parse(f"https://{provider}.com/team/pkg")
    assert repository is not None
    fake = types.SimpleNamespace(
        settings=Settings(source_links=SourceLinks(repository=repository, ref="feature/docs")),
        obj=types.SimpleNamespace(
            filepath="src/pkg/café code.py",
            relative_package_filepath="src/pkg/café code.py",
            lineno=3,
            endlineno=8,
        ),
    )

    link = _get_private_cls().__dict__["source_link"].func(fake)

    assert link is not None
    assert repository.file_url("src/pkg/café code.py", "feature/docs", 3, 8) in str(link)
    assert anchor in str(link)


class TestSourceLinkCompiledExtension:
    def test_so_extension_returns_none(self):
        """When source path ends with .so, returns None."""

        cls = _get_private_cls()

        fake_self = types.SimpleNamespace(
            obj=types.SimpleNamespace(
                filepath="mymod.cpython-313-x86_64-linux-gnu.so",
                relative_package_filepath="mymod.cpython-313-x86_64-linux-gnu.so",
            ),
            settings=Settings(source_links=LINKED),
        )

        result = cls.__dict__["source_link"].func(fake_self)

        assert result is None

    def test_pyd_extension_returns_none(self):
        """When source path ends with .pyd, returns None."""

        cls = _get_private_cls()

        fake_self = types.SimpleNamespace(
            obj=types.SimpleNamespace(filepath="mymod.pyd", relative_package_filepath="mymod.pyd"),
            settings=Settings(source_links=LINKED),
        )

        result = cls.__dict__["source_link"].func(fake_self)

        assert result is None


class TestSourceRelativePathValueError:
    def test_relative_to_raises_value_error(self):
        """A file outside the repository root uses its package-relative path"""

        obj = types.SimpleNamespace(
            filepath="/unrelated/path/to/mod.py",
            relative_package_filepath="mod.py",
        )
        links = SourceLinks(package_root=Path("/completely/different/root"))
        result = source_relative_path(obj, links)

        assert result == "mod.py"


class TestSourceRelativePathNamespacePackage:
    def test_list_filepath_falls_back_to_package_relative_path(self):
        """Verify that a namespace package uses its package-relative source path"""

        obj = types.SimpleNamespace(
            filepath=[Path("/repo/a/ns"), Path("/repo/b/ns")],
            relative_package_filepath="ns",
        )
        links = SourceLinks(package_root=Path("/repo"))
        result = source_relative_path(obj, links)

        assert result == "ns"
