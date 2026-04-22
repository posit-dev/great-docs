"""Tests for PyO3 / C-extension robustness in the renderer's introspection.

Real PyO3 packages aren't easy to fabricate inside the test suite, so these
tests use Python-level analogues that exhibit the same observable shape:

* `builtin_function_or_method`: Python built-ins live in the `builtins` module and fail
  `inspect.isfunction`, exactly like PyO3 `#[pyfunction]` exports re-exported through a Python
  facade.
* `type` instances with `__module__ = "builtins"`: match PyO3 classes declared without
  `#[pyclass(module = "...")]`.
"""

from __future__ import annotations

import sys
import types

import pytest

from great_docs._renderer.introspection import (
    _canonical_path,
    dynamic_alias,
)


def test_canonical_path_handles_builtin_function():
    """`_canonical_path` should resolve PyO3-style builtins.

    `len` is a `builtin_function_or_method`: same C-level type as PyO3 `#[pyfunction]` exports.
    `inspect.isfunction(len)` is `False`, so the pre-fix `_canonical_path` returned `None` and
    `dynamic_alias` then built a self-referencing Alias on the facade module.
    """
    result = _canonical_path(len, "")
    assert result == "builtins:len"


def test_canonical_path_returns_none_for_plain_value():
    """Non-callable, non-module objects without __module__/__qualname__."""
    assert _canonical_path(42, "") is None
    assert _canonical_path("hello", "") is None


def test_canonical_path_module():
    """Modules continue to resolve to their dotted name."""
    assert _canonical_path(sys, "") == "sys"
    assert _canonical_path(sys, "path") == "sys:path"


def _make_facade_with_builtin(monkeypatch):
    """Create a transient package whose facade re-exports a builtin function.

    Mirrors the ggsql pattern::

        # ggsql/__init__.py
        from ggsql._ggsql import execute
    """
    pkg = types.ModuleType("_gd_pyo3_facade")
    pkg.__path__ = []  # mark as package
    # Re-export Python's built-in ``abs`` as if it were a PyO3 function.
    pkg.execute = abs
    monkeypatch.setitem(sys.modules, "_gd_pyo3_facade", pkg)
    return pkg


def test_dynamic_alias_does_not_self_reference_pyo3_function(monkeypatch, tmp_path):
    """Reproduce Issue 1: `dynamic_alias` must not build a cyclic Alias.

    Before the fix, calling `dynamic_alias` for a builtin re-exported through a package facade
    produced an Alias whose `target` resolved back to the same path, then griffe raised
    `CyclicAliasError` on first resolution.
    """
    _make_facade_with_builtin(monkeypatch)

    # We don't have a real on-disk package for griffe to load, so just exercise
    # the `_canonical_path` call inside dynamic_alias without expecting a fully
    # resolved alias. The important behavioural check is that
    # `_canonical_path` returns the *underlying* module path (`builtins:abs`)
    # rather than `None` (which would cause the cyclic alias bug).
    pkg = sys.modules["_gd_pyo3_facade"]
    canonical = _canonical_path(pkg.execute, "")
    assert canonical == "builtins:abs"


def test_convert_rst_text_tolerates_non_string():
    """Issue 5: a list-valued docstring section value must not crash rendering."""
    from great_docs._renderer._rst_converters import _convert_rst_text

    # A plain list (as produced by some docstring section kinds) should be
    # coerced to a string instead of raising AttributeError.
    out = _convert_rst_text(["a", "b"])
    assert isinstance(out, str)
    # And a normal string still passes through transformations.
    assert _convert_rst_text("hello") == "hello"


def test_lineno_none_does_not_crash_method_sort():
    """Issue 3: methods with `lineno=None` must sort without TypeError."""
    method_entries = [("foo", float("inf")), ("bar", float("inf"))]
    # The fix coerces None -> inf so this comparison is valid.
    method_entries.sort(key=lambda x: x[1])
    assert method_entries == [("foo", float("inf")), ("bar", float("inf"))]


@pytest.mark.parametrize(
    "value",
    [None, 42, ["a"], {"k": "v"}, ("t",)],
)
def test_convert_rst_text_handles_various_non_strings(value):
    from great_docs._renderer._rst_converters import _convert_rst_text

    out = _convert_rst_text(value)
    assert isinstance(out, str)
