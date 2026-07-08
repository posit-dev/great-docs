from __future__ import annotations

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
    # Parity: config `version` never reaches Settings; objects.json stays "0.0.9999".
    ref = APIReference({"api-reference": {"package": "pkg", "version": "1.2.3"}})
    assert ref.settings.version is None


def test_options_stored_as_is():
    opts = {"include_private": True}
    ref = APIReference({"api-reference": {"package": "pkg", "options": opts}})
    assert ref.options == opts


def test_settings_defaults():
    s = Settings()
    assert s.dir == "reference"
    assert s.out_inventory == "objects.json"
    assert s.parser == "numpy"
