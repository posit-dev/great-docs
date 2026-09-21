from __future__ import annotations

import os
from pathlib import Path

import pytest

from great_docs._layout import Layout, LayoutError
from great_docs.config import Config


def _write_config(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("display_name: Demo\n", encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("config_relative", "build_relative", "site_relative", "freeze_relative", "cache_relative"),
    [
        ("great-docs.yml", "great-docs", "great-docs/_site", "_freeze", ".great-docs-cache"),
        (
            "docs/great-docs.yml",
            "docs/_quarto/default",
            "docs/_site",
            "docs/_freeze",
            "docs/.cache",
        ),
    ],
)
def test_conventional_config_selects_layout(
    tmp_path: Path,
    config_relative: str,
    build_relative: str,
    site_relative: str,
    freeze_relative: str,
    cache_relative: str,
) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    config = _write_config(tmp_path / config_relative)

    layout = Layout.make(tmp_path)

    assert layout == Layout(
        package_root=tmp_path,
        config_path=config,
        source_dir=config.parent,
        build_dir=tmp_path / build_relative,
        site_dir=tmp_path / site_relative,
        freeze_dir=tmp_path / freeze_relative,
        cache_dir=tmp_path / cache_relative,
    )


def test_custom_config_keeps_package_root(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    config = tmp_path / "website" / "great-docs.yml"
    config.parent.mkdir()
    config.write_text("display_name: Demo\n")
    layout = Layout.make(tmp_path, config)
    assert layout.package_root == tmp_path
    assert layout.source_dir == config.parent
    assert layout.build_dir == config.parent / "_quarto" / "default"
    assert layout.site_dir == config.parent / "_site"
    assert layout.cache_dir == config.parent / ".cache"


def test_automatic_selection_rejects_ambiguous_configs(tmp_path: Path) -> None:
    _write_config(tmp_path / "great-docs.yml")
    _write_config(tmp_path / "docs" / "great-docs.yml")

    with pytest.raises(LayoutError, match="both"):
        Layout.make(tmp_path)


def test_explicit_selection_takes_precedence_over_conventional_configs(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path / "great-docs.yml")
    config = _write_config(tmp_path / "website" / "great-docs.yml")

    assert Layout.make(tmp_path, config).config_path == config


def test_missing_explicit_config_is_rejected(tmp_path: Path) -> None:
    config = tmp_path / "website" / "great-docs.yml"

    with pytest.raises(LayoutError, match="does not exist"):
        Layout.make(tmp_path, config)


def test_create_permits_missing_explicit_config(tmp_path: Path) -> None:
    config = tmp_path / "website" / "great-docs.yml"

    layout = Layout.make(tmp_path, config, create=True)

    assert layout.config_path == config
    assert layout.source_dir == config.parent


def test_python_initialisation_defaults_to_docs(tmp_path: Path) -> None:
    from great_docs import GreatDocs

    docs = GreatDocs(str(tmp_path))
    assert not (tmp_path / "docs").exists()
    docs.install(force=True)
    assert (tmp_path / "docs/great-docs.yml").is_file()
    assert docs.build_dir == tmp_path / "docs/_quarto/default"


def test_creation_constructor_does_not_create_directories(tmp_path: Path) -> None:
    from great_docs import GreatDocs

    docs = GreatDocs(str(tmp_path), config_path=str(tmp_path / "website/settings.yml"), create=True)
    assert docs.layout.config_path == tmp_path / "website/settings.yml"
    assert not (tmp_path / "website").exists()


def test_create_rejects_existing_non_file_destination(tmp_path: Path) -> None:
    config = tmp_path / "great-docs.yml"
    config.mkdir()

    with pytest.raises(LayoutError, match="not a file"):
        Layout.make(tmp_path, config, create=True)


@pytest.mark.parametrize(
    ("existing_relative", "expected_relative"),
    [
        (None, "docs/great-docs.yml"),
        ("great-docs.yml", "great-docs.yml"),
        ("docs/great-docs.yml", "docs/great-docs.yml"),
    ],
)
def test_create_uses_default_only_when_no_config_exists(
    tmp_path: Path,
    existing_relative: str | None,
    expected_relative: str,
) -> None:
    if existing_relative is not None:
        _write_config(tmp_path / existing_relative)

    layout = Layout.make(tmp_path, create=True)

    assert layout.config_path == tmp_path / expected_relative


def test_missing_automatic_config_preserves_root_candidate(tmp_path: Path) -> None:
    layout = Layout.make(tmp_path)

    assert layout.config_path == tmp_path / "great-docs.yml"
    assert layout.source_dir == tmp_path
    assert layout.build_dir == tmp_path / "great-docs"


@pytest.mark.parametrize(
    "manifest",
    ["pyproject.toml", "setup.py", "go.mod", "Cargo.toml"],
)
def test_nested_invocation_discovers_supported_manifest(
    tmp_path: Path,
    manifest: str,
) -> None:
    (tmp_path / manifest).write_text("", encoding="utf-8")
    config = _write_config(tmp_path / "docs" / "great-docs.yml")
    nested = tmp_path / "one" / "two"
    nested.mkdir(parents=True)

    layout = Layout.make(nested)

    assert layout.package_root == tmp_path
    assert layout.config_path == config


def test_manifest_search_falls_back_to_invocation_path(tmp_path: Path) -> None:
    nested = tmp_path / "unrecognised"
    nested.mkdir()

    layout = Layout.make(nested)

    assert layout.package_root == nested
    assert layout.config_path == nested / "great-docs.yml"


def test_relative_explicit_config_resolves_from_invocation_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _write_config(tmp_path / "website" / "great-docs.yml")
    monkeypatch.chdir(tmp_path)

    layout = Layout.make(tmp_path, Path("website/great-docs.yml"))

    assert layout.config_path == config


def test_external_config_is_rejected(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = _write_config(tmp_path / "external" / "great-docs.yml")

    with pytest.raises(LayoutError, match="inside the package root"):
        Layout.make(project, config)


def test_symlinked_config_cannot_escape_package_root(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    external = _write_config(tmp_path / "external" / "great-docs.yml")
    config = project / "great-docs.yml"
    try:
        config.symlink_to(external)
    except OSError as error:
        pytest.skip(f"Cannot create symlinks: {error}")

    with pytest.raises(LayoutError, match="inside the package root"):
        Layout.make(project)


def test_symlinked_create_destination_cannot_escape_package_root(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    destination = project / "website"
    try:
        destination.symlink_to(external, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Cannot create symlinks: {error}")

    with pytest.raises(LayoutError, match="inside the package root"):
        Layout.make(project, destination / "great-docs.yml", create=True)


@pytest.mark.parametrize(
    ("config_relative", "tag", "expected_relative"),
    [
        ("great-docs.yml", "v1.2.3", "great-docs-v1.2.3"),
        ("great-docs.yml", "release/1.0", "great-docs-release-1.0"),
        ("docs/great-docs.yml", "v1.2.3", "docs/_quarto/v1.2.3"),
        ("docs/great-docs.yml", "release/1.0", "docs/_quarto/release-1.0"),
    ],
)
def test_historical_build_directory_preserves_layout(
    tmp_path: Path,
    config_relative: str,
    tag: str,
    expected_relative: str,
) -> None:
    config = _write_config(tmp_path / config_relative)
    layout = Layout.make(tmp_path, config)

    assert layout.build_dir_for(tag, "2.0") == tmp_path / expected_relative
    assert layout.build_dir_for("2.0", "2.0") == layout.build_dir


def test_config_loads_explicit_path_and_keeps_package_cache(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path / "website" / "great-docs.yml")

    config = Config(tmp_path, config_path=config_path)

    assert config.display_name == "Demo"
    assert config.config_path == config_path
    assert config.cache_dir == tmp_path / ".great-docs-cache"


def test_layout_make_does_not_create_directories(tmp_path: Path) -> None:
    config = tmp_path / "website" / "great-docs.yml"

    Layout.make(tmp_path, config, create=True)

    assert os.listdir(tmp_path) == []
