"""Tests for translated reference headings and labels"""

from __future__ import annotations

import textwrap

import pytest

from great_docs._apiref._settings import Settings, active_settings
from great_docs._apiref._tools import render_code_variable

FUNCTION = '''
def f(x):
    """
    Return one

    Parameters
    ----------
    x
        An unused input.

    Returns
    -------
    int
        The constant value one.

    Notes
    -----
    The result is independent of the input.

    Warnings
    --------
    The input is ignored.

    References
    ----------
    Example reference text.

    See Also
    --------
    g : Related example function.

    Performance Notes
    -----------------
    A custom section title remains in English.
    """
    return 1


def g():
    """Provide a related example"""
'''

CLASS = '''
class Engine:
    """
    An example engine

    Attributes
    ----------
    speed
        The engine speed.
    """

    speed: int = 1

    def start(self):
        """Start the engine"""
'''

MODULE = '''
"""Example engine API"""


class Engine:
    """An example engine"""


def start():
    """Start an engine"""
'''


def _render(source: str, name: str | None, lang: str) -> str:
    """Render an object from source as QMD in the selected language"""
    with active_settings(Settings(lang=lang)):
        return render_code_variable(textwrap.dedent(source), name)


@pytest.mark.parametrize(
    ("slug", "title"),
    [
        ("parameters", "パラメータ"),
        ("returns", "戻り値"),
        ("notes", "注記"),
        ("warnings", "警告"),
        ("references", "参考文献"),
        ("see-also", "関連項目"),
    ],
)
def test_standard_section_headings_are_translated(slug: str, title: str):
    qmd = _render(FUNCTION, "f", "ja")

    assert f"{title} {{.doc-{slug}}}" in qmd


def test_a_custom_section_title_stays_as_written():
    qmd = _render(FUNCTION, "f", "ja")

    assert "Performance Notes {.doc-performance-notes}" in qmd


@pytest.mark.parametrize(
    ("source", "name", "slug", "title"),
    [
        (CLASS, "Engine", "attributes", "属性"),
        (CLASS, "Engine", "methods", "メソッド"),
        (MODULE, None, "classes", "クラス"),
        (MODULE, None, "functions", "関数"),
    ],
)
def test_member_group_headings_are_translated(source: str, name: str | None, slug: str, title: str):
    qmd = _render(source, name, "ja")

    assert f"{title} {{.doc-{slug}}}" in qmd


def test_usage_label_is_translated():
    qmd = _render(FUNCTION, "f", "ja")

    assert "使い方" in qmd
    assert "Usage" not in qmd


def test_source_link_is_translated(monkeypatch: pytest.MonkeyPatch):
    from great_docs._apiref._render import doc

    info = {"GITHUB_REPO_URL": "https://github.com/org/repo", "GIT_REF": "main"}
    monkeypatch.setattr(doc, "package_info", info.get)

    qmd = _render(FUNCTION, "f", "ja")

    assert "[ソースコード](https://github.com/org/repo/blob/main/" in qmd


def test_english_output_is_unchanged():
    """Preserve English output when the language is omitted"""
    with active_settings(Settings()):
        default = render_code_variable(textwrap.dedent(FUNCTION), "f")

    assert _render(FUNCTION, "f", "en") == default
    assert "Parameters {.doc-parameters}" in default
    assert "See Also {.doc-see-also}" in default
    assert "Usage" in default


@pytest.mark.parametrize(
    ("title", "expected"),
    [("Functions", "関数"), ("Data Loaders", "Data Loaders")],
)
def test_index_section_titles_translate_only_standard_names(title: str, expected: str):
    from great_docs._apiref._render import RenderReferenceSection
    from great_docs._apiref.content import Section

    with active_settings(Settings(lang="ja")):
        header = str(RenderReferenceSection(Section(title=title)).render_title())

    assert f"{expected} {{.doc-group}}" in header


DEPRECATED = '''
def f():
    """
    Provide a deprecated example

    Deprecated
    ----------
    2.0
        Use an alternative function.
    """
'''


@pytest.mark.parametrize(
    ("lang", "label"),
    [
        ("en", "Deprecated since version 2.0:"),
        ("fr", "Obsolète depuis la version 2.0:"),
        ("ja", "バージョン 2.0 で非推奨:"),
    ],
)
def test_deprecated_section_label_is_translated(lang: str, label: str):
    qmd = _render(DEPRECATED, "f", lang)

    assert label in qmd
