from pathlib import Path
from typing import Any

import pytest

from great_docs._layout import Layout
from great_docs._website.project_pages import package_info
from great_docs._yaml import split_front_matter
from tests.support import StubRemote, mock_config


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    """Create a project layout with an existing build directory"""
    (tmp_path / "great-docs.yml").write_text("", encoding="utf-8")
    layout = Layout.make(tmp_path)
    layout.build_dir.mkdir(parents=True)
    return layout


def _dep(name: str, specifier: str = "", marker: str = "") -> dict[str, Any]:
    """
    Create a dependency entry in the project metadata format

    Parameters
    ----------
    name
        The package name.
    specifier
        The version constraint.
    marker
        The environment marker.

    Returns
    -------
    :
        The dependency, with a `marker` key only when `marker` is not empty.
    """
    dep: dict[str, Any] = {"name": name, "specifier": specifier}
    if marker:
        dep["marker"] = marker
    return dep


def _metadata(
    runtime: list[dict[str, Any]] | None = None,
    optional: dict[str, list[dict[str, Any]]] | None = None,
    requires_python: str = "",
) -> dict[str, Any]:
    """
    Create dependency metadata for the package-info page

    Parameters
    ----------
    runtime
        The runtime dependencies.
    optional
        The optional dependency groups, by name.
    requires_python
        The Python requirement.

    Returns
    -------
    :
        The runtime dependencies, optional groups and Python requirement under their
        project metadata keys.
    """
    return {
        "dependencies": runtime or [],
        "optional_dependencies": optional or {},
        "requires_python": requires_python,
    }


def _config(**values: object) -> Any:
    """
    Create a configuration with the package-info page enabled for a Python project

    Parameters
    ----------
    **values
        Settings that replace the defaults.

    Returns
    -------
    :
        A configuration double with the supplied settings overriding the defaults.
    """
    settings: dict[str, object] = {
        "package_info_page": True,
        "package_info_page_release_dates": True,
        "is_python_project": True,
        "lang": "en",
    }
    return mock_config(**(settings | values))


def test_package_info_lists_runtime_dependencies(layout: Layout):
    """Check runtime dependency details, PyPI links, release dates and summary counts"""
    metadata = _metadata(
        [_dep("numpy", ">=1.24"), _dep("pandas", ">=2.0,<3.0")], requires_python=">=3.11"
    )
    remote = StubRemote(release_dates={"numpy": "2026-05-01", "pandas": "2026-06-15"})
    reported: list[str] = []

    path = package_info.write_page(_config(), layout, metadata, remote, report=reported.append)

    assert path == layout.build_dir / "package-info.qmd"
    assert reported == [f"Created {path}"]
    content = (layout.build_dir / "package-info.qmd").read_text(encoding="utf-8")
    assert split_front_matter(content)[0].string("title") == "Package Info"
    assert "## Runtime Dependencies" in content
    assert 'class="gd-no-link">numpy</code>' in content
    assert "<code>&gt;=1.24</code>" in content
    assert 'href="https://pypi.org/project/pandas/"' in content
    assert "<svg" in content
    assert "Last Published" in content
    assert "2026-05-01" in content
    assert "2026-06-15" in content
    assert "Environment Marker" not in content
    assert "- **Requires:** Python `>=3.11`" in content
    assert "- **Runtime Dependencies:** 2" in content
    assert "- **Total unique dependencies:** 2" in content


def test_package_info_lists_optional_groups(layout: Layout):
    """Check optional groups, empty-group messages and unique dependency counts"""
    metadata = _metadata(
        [_dep("click", ">=8.0")],
        {"dev": [_dep("pytest", ">=7.0"), _dep("click")], "empty": []},
    )

    path = package_info.write_page(_config(), layout, metadata, StubRemote(), report=print)

    assert path is not None
    content = path.read_text(encoding="utf-8")
    assert "## Optional Dependencies" in content
    assert "### `dev`" in content
    assert "### `empty`\n\n*No dependencies declared.*" in content
    assert "- **Optional Dependencies:** 2 groups (2 unique packages)" in content
    assert "- **Total unique dependencies:** 2" in content


def test_package_info_shows_markers_only_in_tables_that_have_them(layout: Layout):
    """Check that each table includes a marker column only when its dependencies need one"""
    metadata = _metadata(
        [_dep("numpy")],
        {"dev": [_dep("typing-extensions", ">=4.0", "python_version<'3.12'")]},
    )

    path = package_info.write_page(_config(), layout, metadata, StubRemote(), report=print)

    assert path is not None
    content = path.read_text(encoding="utf-8")
    runtime, optional = content.split("## Optional Dependencies")
    assert "Environment Marker" not in runtime
    assert "Environment Marker" in optional
    assert "<code>python_version&lt;&#x27;3.12&#x27;</code>" in optional


def test_package_info_shows_a_dash_for_unknown_dates(layout: Layout):
    """Check that an unknown PyPI release date appears as a dash"""
    metadata = _metadata([_dep("numpy", ">=1.24")])

    path = package_info.write_page(_config(), layout, metadata, StubRemote(), report=print)

    assert path is not None
    assert "<td>—</td>" in path.read_text(encoding="utf-8")


def test_package_info_without_release_dates_skips_pypi(layout: Layout):
    """Check that disabling release dates omits PyPI requests and the date column"""
    metadata = _metadata(
        [_dep("numpy", ">=1.24")],
        {"dev": [_dep("typing-extensions", ">=4.0", "python_version<'3.12'")]},
    )
    remote = StubRemote(release_dates={"numpy": "2026-05-01"})

    path = package_info.write_page(
        _config(package_info_page_release_dates=False), layout, metadata, remote, report=print
    )

    assert path is not None
    content = path.read_text(encoding="utf-8")
    runtime, optional = content.split("## Optional Dependencies")
    assert remote.calls == []
    assert "Last Published" not in content
    assert "2026-05-01" not in content
    assert "<td>—</td>" not in content
    assert runtime.count("<th ") == 3
    assert optional.count("<th ") == 4
    assert 'href="https://pypi.org/project/numpy/"' in runtime
    assert "Environment Marker" in optional


def test_package_info_is_skipped_when_disabled_or_empty(layout: Layout):
    """Check that disabled, non-Python and empty pages leave no file or remote calls"""
    remote = StubRemote()
    metadata = _metadata([_dep("numpy")])

    for config, page_metadata in [
        (_config(package_info_page=False), metadata),
        (_config(is_python_project=False), metadata),
        (_config(), _metadata()),
    ]:
        assert package_info.write_page(config, layout, page_metadata, remote, report=print) is None

    assert not (layout.build_dir / "package-info.qmd").exists()
    assert remote.calls == []


def test_package_info_title_survives_yaml_syntax(layout: Layout, monkeypatch: pytest.MonkeyPatch):
    """Check that YAML front matter preserves quotes and a colon in a translated title"""
    title = 'Package "Info": details'
    translate = package_info.translate
    monkeypatch.setattr(
        package_info,
        "translate",
        lambda key, lang: title if key == "package_info" else translate(key, lang),
    )

    path = package_info.write_page(
        _config(), layout, _metadata([_dep("numpy")]), StubRemote(), report=print
    )

    assert path is not None
    front_matter, _ = split_front_matter(path.read_text(encoding="utf-8"))
    assert front_matter.string("title") == title
    assert front_matter.string("body-classes") == "gd-package-info-page"
