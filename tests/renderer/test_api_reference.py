from __future__ import annotations

from pathlib import Path

from great_docs._apiref import spec
from great_docs._apiref.api_reference import APIReference, Settings


def test_flat_config_routes_into_nested_settings():
    ref = APIReference({"api-reference": {"package": "pkg", "dir": "api", "parser": "google"}})
    assert ref.package == "pkg"
    assert ref.settings.dir == "api"
    assert ref.settings.parser == "google"
    # build keys are NOT attributes of APIReference itself
    assert not hasattr(ref, "dir")


def test_legacy_quartodoc_key_is_accepted():
    ref = APIReference({"quartodoc": {"package": "pkg"}})
    assert ref.package == "pkg"


def test_sidebar_string_is_coerced_to_dict():
    ref = APIReference({"api-reference": {"package": "pkg", "sidebar": "_sb.yml"}})
    assert ref.settings.sidebar == {"file": "_sb.yml"}


def test_sidebar_dict_without_file_gets_default():
    ref = APIReference({"api-reference": {"package": "pkg", "sidebar": {"id": "api"}}})
    assert ref.settings.sidebar is not None
    assert ref.settings.sidebar["file"] == "_api-reference-sidebar.yml"
    assert ref.settings.sidebar["id"] == "api"


def test_sections_and_contents_are_coerced():
    ref = APIReference(
        {"api-reference": {"package": "pkg", "sections": [{"title": "T", "contents": ["a", "b"]}]}}
    )
    section = ref.sections[0]
    assert isinstance(section, spec.SpecSection)
    assert all(isinstance(c, spec.SpecObject) for c in section.contents)


def test_removed_and_dropped_keys_are_ignored():
    # style/renderer/render_interlinks are compatibility-only; interlinks.fast is dropped
    ref = APIReference(
        {
            "api-reference": {"package": "pkg", "style": "x", "renderer": "y"},
            "interlinks": {"fast": True},
        }
    )
    assert ref.package == "pkg"
    assert not hasattr(ref.settings, "fast_inventory")


def test_version_is_not_wired_through():
    # Parity: config `version` never reaches Settings; objects.inv stays "0.0.9999".
    ref = APIReference({"api-reference": {"package": "pkg", "version": "1.2.3"}})
    assert ref.settings.version is None


def test_options_stored_as_is():
    opts = {"include_private": True}
    ref = APIReference({"api-reference": {"package": "pkg", "options": opts}})
    assert ref.options == opts


def test_toc_depth_reads_generated_quarto_config(tmp_path: Path):
    config = tmp_path / "_quarto.yml"
    config.write_text(
        "api-reference:\n  package: pkg\nformat:\n  html:\n    toc-depth: 4\n",
        encoding="utf-8",
    )
    ref = APIReference(config)
    assert ref.site_toc_depth == 4


def test_toc_depth_reads_source_config():
    ref = APIReference(
        {
            "api-reference": {"package": "pkg"},
            "site": {"toc-depth": 5},
        }
    )
    assert ref.site_toc_depth == 5


def test_settings_defaults():
    s = Settings()
    assert s.dir == "reference"
    assert s.parser == "numpy"


def test_the_manifest_is_available_without_building(tmp_path, monkeypatch):
    """Reading the claims must not write pages, an index or an inventory."""
    from great_docs._apiref.api_reference import APIReference

    (tmp_path / "mypkg").mkdir()
    (tmp_path / "mypkg" / "__init__.py").write_text(
        '"""A package."""\n\n\nclass Cache:\n    """A cache."""\n\n'
        "    def flush(self):\n"
        '        """Flush buffered writes."""\n',
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)

    ref = APIReference(
        {"api-reference": {"package": "mypkg", "sections": [{"contents": ["Cache"]}]}}
    )
    names = [item.name for item in ref.items]

    assert "mypkg.Cache" in names
    assert list(tmp_path.glob("objects.inv")) == []
    assert not (tmp_path / "reference").exists()
