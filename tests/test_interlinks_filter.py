"""
Exercise the interlinks Lua filter directly with Pandoc
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_FILTER = (
    Path(__file__).parent.parent
    / "great_docs"
    / "assets"
    / "_extensions"
    / "interlinks"
    / "interlinks.lua"
)


def _run_filter(markdown: str, index_lua: str, tmp_path: Path) -> str:
    """Render Markdown through the real filter and return Pandoc's native AST"""
    project = tmp_path / "proj"
    (project / "_inv").mkdir(parents=True)
    (project / "_inv" / "index.lua").write_text(index_lua, encoding="utf-8")

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
  prefixes = {},
  names = {
    ["Thing"] = {{ uri = "/reference/Thing.html", domain = "py", role = "class", ["local"] = true }},
  },
}
"""


def test_ordinary_link_label_is_not_autolinked(tmp_path):
    """Leave a code span in an ordinary link label unlinked."""
    if not shutil.which("pandoc"):
        pytest.skip("pandoc not available")

    output = _run_filter("See [`Thing`](guide.qmd) for details.\n", _INDEX, tmp_path)

    # Keep the code span inside only the authored link.
    assert output.count("Link") == 1
    assert "/reference/Thing.html" not in output
    assert 'Code ( "" , [] , [] ) "Thing"' in output


def test_explicit_interlink_still_resolves(tmp_path):
    """Continue resolving an explicit interlink target."""
    if not shutil.which("pandoc"):
        pytest.skip("pandoc not available")

    output = _run_filter("See [](`Thing`) for details.\n", _INDEX, tmp_path)

    assert "/reference/Thing.html" in output


_METHOD_INDEX = """
return {
  add_function_parentheses = true,
  prefixes = {},
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
    if not shutil.which("pandoc"):
        pytest.skip("pandoc not available")

    output = _run_filter("See [](:py:meth:`Foo.bar`) for details.\n", _METHOD_INDEX, tmp_path)

    assert "https://ext.example/Foo.html#bar" in output
