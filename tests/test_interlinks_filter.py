"""
Exercise the interlinks Lua filter directly with Pandoc
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from great_docs._interlinks import Index, IndexEntry, write_index

_FILTER = (
    Path(__file__).parent.parent
    / "great_docs"
    / "assets"
    / "_extensions"
    / "interlinks"
    / "interlinks.lua"
)


def _run_filter(markdown: str, index_lua: str, tmp_path: Path) -> str:
    """Render Markdown through the real filter over a hand-written index"""
    project = tmp_path / "proj"
    (project / "_inv").mkdir(parents=True)
    (project / "_inv" / "index.lua").write_text(index_lua, encoding="utf-8")
    return _render(markdown, project, tmp_path)


def _run_filter_over_written_index(markdown: str, index: Index, tmp_path: Path) -> str:
    """Render Markdown through the real filter over an index `write_index` wrote"""
    project = tmp_path / "proj"
    write_index(index, project / "_inv" / "index.lua")
    return _render(markdown, project, tmp_path)


def _render(markdown: str, project: Path, tmp_path: Path) -> str:
    """Run Pandoc with the filter over `markdown` and return its native AST"""
    if not shutil.which("pandoc"):
        pytest.skip("pandoc not available")

    # Quarto supplies these values in its Lua runtime; bare Pandoc needs stubs.
    wrapper = tmp_path / "wrapper.lua"
    wrapper.write_text(
        f"""
quarto = {{
  project = {{ offset = {json.dumps(str(project))} }},
  log = {{ warning = function(...) end }},
}}
return dofile({json.dumps(str(_FILTER))})
""",
        encoding="utf-8",
    )

    doc = tmp_path / "doc.md"
    doc.write_text(markdown, encoding="utf-8")

    result = subprocess.run(
        ["pandoc", str(doc), f"--lua-filter={wrapper}", "-t", "native"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


_INDEX = """
return {
  add_function_parentheses = true,
  callable_roles = { ["function"] = true, ["method"] = true },
  prefixes = {},
  names = {
    ["Thing"] = {{ uri = "/reference/Thing.html", domain = "py", role = "class", ["local"] = true }},
  },
}
"""


def test_ordinary_link_label_is_not_autolinked(tmp_path):
    """Leave a code span in an ordinary link label unlinked."""
    output = _run_filter("See [`Thing`](guide.qmd) for details.\n", _INDEX, tmp_path)

    # Keep the code span inside only the authored link.
    assert output.count("Link") == 1
    assert "/reference/Thing.html" not in output
    assert 'Code ( "" , [] , [] ) "Thing"' in output


def test_explicit_interlink_still_resolves(tmp_path):
    """Continue resolving an explicit interlink target."""
    output = _run_filter("See [](`Thing`) for details.\n", _INDEX, tmp_path)

    assert "/reference/Thing.html" in output


def test_ordinary_url_with_encoded_backticks_is_left_alone(tmp_path):
    """A URL that merely contains an encoded backtick pair is not a reference target."""
    url = "https://example.org/search?q=%60Thing%60"
    output = _run_filter(f"See [search here]({url}) for details.\n", _INDEX, tmp_path)

    assert url in output
    assert "/reference/Thing.html" not in output


_METHOD_INDEX = """
return {
  add_function_parentheses = true,
  callable_roles = { ["function"] = true, ["method"] = true },
  prefixes = {},
  role_synonyms = { ["meth"] = "method" },
  names = {
    ["Foo.bar"] = {{
      uri = "https://ext.example/Foo.html#bar",
      domain = "py",
      role = "method",
      source = "extdemo",
    }},
  },
}
"""


def test_meth_role_resolves_a_py_method_inventory_entry(tmp_path):
    """Resolve `:py:meth:` against a `method` inventory entry."""
    output = _run_filter("See [](:py:meth:`Foo.bar`) for details.\n", _METHOD_INDEX, tmp_path)

    assert "https://ext.example/Foo.html#bar" in output


# Shared by both contract tests below. `role_synonyms` maps the Sphinx role
# abbreviations the user guide documents to the role names the index stores;
# an empty string is the generic role, which constrains nothing.
_CONTRACT_INDEX = """
return {
  add_function_parentheses = true,
  callable_roles = { ["function"] = true, ["method"] = true },
  prefixes = { ["np"] = {"numpy"} },
  role_synonyms = { ["func"] = "function", ["meth"] = "method",
                    ["exc"] = "exception", ["obj"] = "" },
  names = {
    ["mypkg.Thing"] = {{ uri = "/reference/Thing.html", domain = "py",
                         role = "class", ["local"] = true }},
    ["mypkg.run"] = {{ uri = "/reference/run.html", domain = "py",
                       role = "function", ["local"] = true }},
    ["mypkg.Thing.flush"] = {{ uri = "/reference/Thing.html#flush", domain = "py",
                               role = "method", ["local"] = true }},
    ["mypkg.Boom"] = {{ uri = "/reference/Boom.html", domain = "py",
                        role = "exception", ["local"] = true }},
    ["numpy.ndarray"] = {{ uri = "https://numpy.org/doc/stable/ndarray.html",
                           domain = "py", role = "class", source = "numpy" }},
  },
}
"""


@pytest.mark.parametrize(
    "markdown,expected",
    [
        # Display forms
        ("[](`mypkg.Thing`)", ["/reference/Thing.html", "mypkg.Thing"]),
        ("[](`~mypkg.Thing`)", ["/reference/Thing.html", "Thing"]),
        ("[named](`mypkg.Thing`)", ["/reference/Thing.html", "named"]),
        # Authored text wins over the `~` shortening marker, not just over the
        # full path: the marker is ignored whenever link text is supplied.
        # (One word, like the "named" row above: Pandoc's native writer
        # tokenizes multi-word text into separate Str/Space nodes, so a
        # multi-word phrase would not appear as one contiguous substring.)
        ("[labelled](`~mypkg.Thing`)", ["/reference/Thing.html", "labelled"]),
        # Callable parentheses
        ("[](`mypkg.run`)", ["/reference/run.html", "mypkg.run()"]),
        # Role forms. Only the name is backtick-quoted; the `:role:` prefix
        # is not, so Pandoc percent-encodes just the backticks around it.
        # (Undocumented but supported quartodoc-era syntax; regression
        # coverage only, not a form the user guide names.)
        ("[](:func:`mypkg.run`)", ["/reference/run.html"]),
        ("[](:py:class:`mypkg.Thing`)", ["/reference/Thing.html"]),
        ("[](:meth:`mypkg.Thing.flush`)", ["/reference/Thing.html#flush"]),
        ("[](:exc:`mypkg.Boom`)", ["/reference/Boom.html"]),
        ("[](:obj:`mypkg.Thing`)", ["/reference/Thing.html"]),
        ("[](:external+numpy:py:class:`numpy.ndarray`)", ["numpy.org/doc/stable/ndarray.html"]),
        # External reference: the canonical unaliased form, and the alias
        # that rewrites a prefix onto the same source.
        ("[](`numpy.ndarray`)", ["numpy.org/doc/stable/ndarray.html"]),
        ("[](`np.ndarray`)", ["numpy.org/doc/stable/ndarray.html"]),
        # Code autolinks
        ("`mypkg.Thing`", ["/reference/Thing.html", "mypkg.Thing"]),
        ("`~~mypkg.Thing`", ["/reference/Thing.html", "Thing"]),
        ("`~~.mypkg.Thing`", ["/reference/Thing.html", ".Thing"]),
        # Author-supplied parentheses are cosmetic: stripped for lookup,
        # preserved in the display text.
        ("`mypkg.run()`", ["/reference/run.html", "mypkg.run()"]),
        ("`~~mypkg.run()`", ["/reference/run.html", "run()"]),
    ],
)
def test_the_filter_resolves_every_documented_form(markdown, expected, tmp_path):
    """Resolve every reference form the user guide promises."""
    out = _run_filter(markdown, _CONTRACT_INDEX, tmp_path)

    for fragment in expected:
        assert fragment in out


@pytest.mark.parametrize(
    "markdown,present,absent",
    [
        # Autolinking never leaves the project
        ("`numpy.ndarray`", ["numpy.ndarray"], ["numpy.org/doc/stable"]),
        # Opt-out
        ("`mypkg.Thing`{.gd-no-link}", ["mypkg.Thing"], ["/reference/Thing.html"]),
        # Unresolved degradations
        ("[](`mypkg.Missing`)", ["mypkg.Missing"], ["Link"]),
        ("[shown](`mypkg.Missing`)", ["shown"], ["Link"]),
        ("`~~mypkg.Missing`", ["Missing"], ["~~"]),
        ("`plain_word`", ["plain_word"], ["Link"]),
    ],
)
def test_the_filter_degrades_without_breaking(markdown, present, absent, tmp_path):
    """Leave an unresolved or opted-out reference readable, never broken."""
    out = _run_filter(markdown, _CONTRACT_INDEX, tmp_path)

    for fragment in present:
        assert fragment in out
    for fragment in absent:
        assert fragment not in out


def test_parentheses_are_omitted_when_configured_off(tmp_path):
    """Respect `add_function_parentheses: false` for an interlink target."""
    index = _CONTRACT_INDEX.replace(
        "add_function_parentheses = true", "add_function_parentheses = false"
    )
    out = _run_filter("[](`mypkg.run`)", index, tmp_path)

    assert "/reference/run.html" in out
    assert "mypkg.run()" not in out


def test_the_written_index_resolves_a_reference_through_the_filter(tmp_path):
    """
    Read an index the build itself wrote

    Every other test here hands the filter a hand-written table, so renaming a
    key in `write_index` would break every real build while they stayed green.
    One reference of each kind pins the keys the filter reads: a local name, an
    alias prefix, a role abbreviation and the roles shown with parentheses.
    """
    index = Index(
        names={
            "mypkg.run": (
                IndexEntry(uri="/reference/run.html", domain="py", role="function", is_local=True),
            ),
            "mypkg.Thing.flush": (
                IndexEntry(
                    uri="/reference/Thing.html#flush",
                    domain="py",
                    role="method",
                    is_local=True,
                ),
            ),
            "numpy.ndarray": (
                IndexEntry(
                    uri="https://numpy.org/doc/stable/ndarray.html",
                    domain="py",
                    role="class",
                    source="numpy",
                ),
            ),
        },
        prefixes={"np": ("numpy",)},
    )

    out = _run_filter_over_written_index(
        "[](`mypkg.run`), [](:meth:`mypkg.Thing.flush`) and [](`np.ndarray`)\n",
        index,
        tmp_path,
    )

    assert "/reference/run.html" in out
    assert "mypkg.run()" in out
    assert "/reference/Thing.html#flush" in out
    assert "numpy.org/doc/stable/ndarray.html" in out


def test_an_index_without_the_callable_roles_adds_no_parentheses(tmp_path):
    """An index missing the key still resolves; only the trailing `()` is lost."""
    index = _CONTRACT_INDEX.replace(
        '  callable_roles = { ["function"] = true, ["method"] = true },\n', ""
    )

    out = _run_filter("[](`mypkg.run`)", index, tmp_path)

    assert "/reference/run.html" in out
    assert "mypkg.run()" not in out
