"""Tests for class signatures and source links of PyO3-style extension classes.

A PyO3 class declares its constructor in `__new__`, and the stub that maturin
installs as `<package>/__init__.pyi` usually pairs it with an `__init__` that
takes only `self`. The installed package's `__init__.py` re-exports the compiled
module, so griffe merges the stub into it.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import griffe as gf

from great_docs._apiref._constructor import class_constructor, parse_class_docstring
from great_docs._apiref._settings import Settings, SourceLinks
from great_docs._project.repository import Repository
from great_docs._apiref._tools import _render

STUB = '''\
from typing import Any, final

@final
class Yaml:
    """
    Tagged node.

    Parameters
    ----------
    value
        The wrapped value.
    tag
        The YAML tag.
    """

    def __new__(cls, value: Any, tag: str | None = None) -> Yaml: ...
    def __init__(self) -> None: ...

    @property
    def value(self) -> Any: ...
'''


def _install(site: Path, name: str, stub: str, init: str = "from .ext import *\n") -> gf.Module:
    """Write an installed extension package to `site` and load it with griffe."""
    pkg = site / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(init)
    (pkg / "__init__.pyi").write_text(stub)
    return gf.load(name, search_paths=[site], docstring_parser="numpy")


def _signature(qmd: str) -> str:
    """The text of the first signature block of a rendered page."""
    match = re.search(r"```pythonsignature\n(.*?)\n```", qmd, re.DOTALL)
    assert match, qmd
    return match.group(1)


def _source_url(qmd: str) -> str | None:
    """The source link of a rendered page, or `None` when it has none."""
    match = re.search(r"\[Source\]\(([^)]*)\)", qmd)
    return match.group(1) if match else None


def test_signature_uses_new_when_init_takes_only_self(tmp_path):
    mod = _install(tmp_path, "pyo3_new", STUB)
    assert _signature(_render(mod["Yaml"])) == "Yaml(\n    value,\n    tag=None,\n)"


def test_signature_uses_new_without_init():
    code = '''
    class Point:
        """A point."""
        def __new__(cls, x: int, /, *, y: int = 0): ...
    '''
    with gf.temporary_visited_package("package", {"__init__.pyi": code}) as m:
        qmd = _render(m["Point"])
    assert _signature(qmd) == "Point(\n    x,\n    /,\n    *,\n    y=0,\n)"


def test_init_with_arguments_wins_over_new():
    code = '''
    class Point:
        """A point."""
        def __new__(cls, *args, **kwargs): ...
        def __init__(self, x: int) -> None: ...
    '''
    with gf.temporary_visited_package("package", {"__init__.py": code}) as m:
        assert class_constructor(m["Point"]).name == "__init__"
        assert _signature(_render(m["Point"])) == "Point(x)"


def test_variadic_init_gives_way_to_new():
    """An `__init__` that only passes `*args`/`**kwargs` on names no arguments."""
    code = '''
    class Point:
        """A point."""
        def __new__(cls, x: int): ...
        def __init__(self, *args, **kwargs) -> None: ...
    '''
    with gf.temporary_visited_package("package", {"__init__.py": code}) as m:
        assert _signature(_render(m["Point"])) == "Point(x)"


def test_variadic_init_kept_when_new_names_nothing():
    code = '''
    class Point:
        """A point."""
        def __init__(self, *args, **kwargs) -> None: ...
    '''
    with gf.temporary_visited_package("package", {"__init__.py": code}) as m:
        assert _signature(_render(m["Point"])) == "Point(\n    *args,\n    **kwargs,\n)"


def test_overloaded_new_renders_each_variant_without_cls_or_return(tmp_path):
    """A stub may declare `__new__` only as overloads, which griffe keeps on the class."""
    stub = '''\
from typing import overload

class Point:
    """A point."""
    @overload
    def __new__(cls, x: int) -> Point: ...
    @overload
    def __new__(cls, x: str, y: int = ...) -> Point: ...
    def __init__(self) -> None: ...
'''
    pkg = tmp_path / "pyo3_overloads"
    pkg.mkdir()
    (pkg / "__init__.pyi").write_text(stub)
    mod = gf.load("pyo3_overloads", search_paths=[tmp_path])

    sig = _signature(_render(mod["Point"]))
    assert sig == "Point(x: int)\nPoint(\n    x: str,\n    y: int = ...,\n)"


def test_overloaded_method_does_not_replace_class_signature():
    code = '''
    from typing import overload

    class Store:
        """A store."""
        def __init__(self, path: str) -> None: ...
        @overload
        def get(self, key: int) -> int: ...
        @overload
        def get(self, key: str) -> str: ...
    '''
    with gf.temporary_visited_package("package", {"__init__.py": code}) as m:
        assert _signature(_render(m["Store"])) == "Store(path)"


def test_class_docstring_parameters_take_annotations_from_new(tmp_path, caplog):
    mod = _install(tmp_path, "pyo3_doc", STUB)
    yaml = mod["Yaml"]

    with caplog.at_level(logging.WARNING, logger="griffe"):
        parse_class_docstring(yaml)
    assert not caplog.records

    params = next(s for s in yaml.docstring.parsed if isinstance(s, gf.DocstringSectionParameters))
    tag = next(p for p in params.value if p.name == "tag")
    assert str(tag.annotation) == "str | None"
    assert tag.value == "None"


def test_google_class_docstring_parameters_take_annotations_from_new(tmp_path, caplog):
    stub = '''\
from typing import Any

class Yaml:
    """Tagged node.

    Args:
        value: The wrapped value.
        tag: The YAML tag.
    """

    def __new__(cls, value: Any, tag: str | None = None) -> Yaml: ...
    def __init__(self) -> None: ...
'''
    pkg = tmp_path / "pyo3_google"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("from .ext import *\n")
    (pkg / "__init__.pyi").write_text(stub)
    yaml = gf.load("pyo3_google", search_paths=[tmp_path], docstring_parser="google")["Yaml"]

    with caplog.at_level(logging.WARNING, logger="griffe"):
        parse_class_docstring(yaml)
    assert not caplog.records

    qmd = _render(yaml)
    assert "[value]{.doc-parameter-name}[:]{.doc-parameter-annotation-sep} [Any]" in qmd
    assert "[tag]{.doc-parameter-name}[:]{.doc-parameter-annotation-sep} [str | None]" in qmd


def test_class_docstring_keeps_warnings_for_unknown_parameters(tmp_path, caplog):
    stub = STUB.replace(
        "        The YAML tag.\n", "        The YAML tag.\n    extra\n        Gone.\n"
    )
    mod = _install(tmp_path, "pyo3_extra", stub)

    with caplog.at_level(logging.WARNING, logger="griffe"):
        parse_class_docstring(mod["Yaml"])

    messages = [r.getMessage() for r in caplog.records]
    assert any("'extra' does not appear in the function signature" in m for m in messages)
    assert not any("'value'" in m or "'tag'" in m for m in messages)


def _linked(root: Path) -> Settings:
    return Settings(
        source_links=SourceLinks(
            repository=Repository.parse("https://github.com/o/r"), package_root=root
        )
    )


def test_installed_stub_links_to_repository_root_stub(tmp_path):
    """maturin installs a Rust-only project's `<package>.pyi` as `<package>/__init__.pyi`."""
    mod = _install(tmp_path / "site", "pyo3_link", STUB)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyo3_link.pyi").write_text(STUB)

    url = _source_url(_render(mod["Yaml"], _linked(repo)))
    assert url == "https://github.com/o/r/blob/main/pyo3_link.pyi#L3-L20"


def test_installed_stub_links_to_package_stub_in_python_dir(tmp_path):
    mod = _install(tmp_path / "site", "pyo3_pydir", STUB)
    repo = tmp_path / "repo"
    (repo / "python" / "pyo3_pydir").mkdir(parents=True)
    (repo / "python" / "pyo3_pydir" / "__init__.pyi").write_text(STUB)

    url = _source_url(_render(mod["Yaml"], _linked(repo)))
    assert url == "https://github.com/o/r/blob/main/python/pyo3_pydir/__init__.pyi#L3-L20"


def test_stub_installed_in_repository_venv_links_to_repository_stub(tmp_path):
    repo = tmp_path / "repo"
    mod = _install(repo / ".venv" / "lib" / "python3.13" / "site-packages", "pyo3_venv", STUB)
    (repo / "pyo3_venv.pyi").write_text(STUB)

    url = _source_url(_render(mod["Yaml"], _linked(repo)))
    assert url == "https://github.com/o/r/blob/main/pyo3_venv.pyi#L3-L20"


def test_installed_stub_without_repository_copy_has_no_link(tmp_path):
    mod = _install(tmp_path / "site", "pyo3_nolink", STUB)
    repo = tmp_path / "repo"
    repo.mkdir()

    assert _source_url(_render(mod["Yaml"], _linked(repo))) is None


def test_stub_inside_repository_keeps_its_path(tmp_path):
    repo = tmp_path / "repo"
    mod = _install(repo / "src", "pyo3_local", STUB)

    url = _source_url(_render(mod["Yaml"], _linked(repo)))
    assert url == "https://github.com/o/r/blob/main/src/pyo3_local/__init__.pyi#L3-L20"


def test_type_checking_class_without_stub_links_to_module(tmp_path):
    """Griffe also marks `if TYPE_CHECKING:` objects as absent at runtime."""
    repo = tmp_path / "repo"
    pkg = repo / "tc_pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        'from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    class Hint:\n        """A hint."""\n'
    )
    mod = gf.load("tc_pkg", search_paths=[repo])

    url = _source_url(_render(mod["Hint"], _linked(repo)))
    assert url == "https://github.com/o/r/blob/main/tc_pkg/__init__.py#L4-L5"
