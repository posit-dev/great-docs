from __future__ import annotations

from pathlib import Path

import pytest

from great_docs._apiref import spec
from great_docs._apiref.api_reference import APIReference, Settings
from tests.support import write_config


def test_reference_reads_the_documentation_config(tmp_path: Path) -> None:
    config = write_config(
        tmp_path,
        {
            "parser": "google",
            "dynamic": True,
            "members_on_same_page": False,
            "max_members_on_same_page": 4,
            "reference": {"title": "My API", "desc": "Tools", "show_bases": True},
            "site": {"lang": "fr", "toc-depth": 5},
        },
    )
    reference = APIReference(config, spec.ReferenceSpec("pkg", []))

    assert reference.package == "pkg"
    assert reference.title == "My API"
    assert reference.desc == "Tools"
    assert reference.site_toc_depth == 5
    assert reference.settings.parser == "google"
    assert reference.settings.lang == "fr"
    assert reference.settings.dynamic is True
    assert reference.settings.members_on_same_page is False
    assert reference.settings.max_members_on_same_page == 4
    assert reference.settings.show_bases is True


def test_a_static_attempt_does_not_change_the_documentation_config(tmp_path: Path) -> None:
    config = write_config(tmp_path, {"dynamic": True})
    reference = APIReference(config, spec.ReferenceSpec("pkg", []), dynamic=False)

    assert reference.settings.dynamic is False
    assert config.dynamic is True


def test_sections_and_contents_are_coerced(tmp_path: Path) -> None:
    ref = APIReference(
        write_config(tmp_path),
        spec.ReferenceSpec("pkg", [{"title": "T", "contents": ["a", "b"]}]),
    )
    section = ref.sections[0]
    assert isinstance(section, spec.SpecSection)
    assert all(isinstance(c, spec.SpecObject) for c in section.contents)


@pytest.mark.parametrize("site", [{}, {"toc-depth": "invalid"}])
def test_toc_depth_defaults_to_two(tmp_path: Path, site: dict[str, object]) -> None:
    ref = APIReference(write_config(tmp_path, {"site": site}), spec.ReferenceSpec("pkg", []))
    assert ref.site_toc_depth == 2
    assert ref.settings.lang == "en"


def test_resolution_sees_the_reference_lang(tmp_path, monkeypatch):
    """
    Use the reference language in hooks before the build starts

    Listing documented objects resolves the reference before the build binds
    its settings.
    """
    (tmp_path / "langpkg").mkdir()
    (tmp_path / "langpkg" / "__init__.py").write_text(
        'def grow():\n    """\n    Grow.\n\n    %versionadded 2.0\n    """\n',
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.chdir(tmp_path)

    ref = APIReference(
        write_config(tmp_path, {"site": {"lang": "fr"}}),
        spec.ReferenceSpec("langpkg", [{"contents": ["grow"]}]),
    )
    (page,) = ref.resolved[0].contents
    (doc,) = page.contents

    assert 'title="Ajouté dans la version 2.0"' in doc.obj.docstring.value


def test_settings_defaults():
    s = Settings()
    assert s.dir == "reference"
    assert s.parser == "numpy"


def test_the_manifest_is_available_without_building(tmp_path, monkeypatch):
    """Reading the claims must not write pages, an index or an inventory."""
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
        write_config(tmp_path), spec.ReferenceSpec("mypkg", [{"contents": ["Cache"]}])
    )
    names = [item.name for item in ref.items]

    assert "mypkg.Cache" in names
    assert list(tmp_path.glob("objects.inv")) == []
    assert not (tmp_path / "reference").exists()
