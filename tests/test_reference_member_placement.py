"""
Reference member placement and rejection of unsupported options
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

from great_docs import GreatDocs
from great_docs._apiref.api_reference import APIReference
from great_docs._apiref.spec import SpecObject, SpecOptions
from great_docs._build import reference
from great_docs._build.log import BuildLog
from great_docs._interlinks.sphinx_inventory import decode
from great_docs._reference import sections
from tests.support import StubRemote, make_run, prepare_build_directory, write_config


@pytest.mark.parametrize("value", ["embedded", "separate", "linked", "flat"])
@pytest.mark.parametrize("block", ["api-reference", "quartodoc"])
def test_legacy_children_has_migration_error(value: str, block: str) -> None:
    """
    Reject `children` with guidance on selecting and placing members
    """
    with pytest.raises(ValueError, match="children.*members_on_same_page.*members"):
        APIReference(
            {
                block: {
                    "package": "unused",
                    "sections": [
                        {"title": "API", "contents": [{"name": "Widget", "children": value}]}
                    ],
                }
            }
        )


@pytest.mark.parametrize("value", [None, "false", 0, 1, 5])
def test_entry_members_on_same_page_requires_boolean(value: object) -> None:
    """
    Require a boolean for an entry's member placement
    """
    with pytest.raises(ValueError, match="members_on_same_page.*true or false"):
        SpecObject(name="Widget", members_on_same_page=value)
    with pytest.raises(ValueError, match="members_on_same_page.*true or false"):
        SpecOptions().replace(members_on_same_page=value)


def test_entry_members_on_same_page_overrides_inherited_options() -> None:
    """
    Inherit member placement unless the entry sets its own value
    """
    base = SpecOptions(members_on_same_page=False)
    assert SpecObject(name="Widget").members_on_same_page is True
    assert SpecObject(name="Widget").with_defaults(base).members_on_same_page is False
    assert (
        SpecObject(name="Widget", members_on_same_page=True)
        .with_defaults(base)
        .members_on_same_page
        is True
    )


def test_entry_rejects_global_threshold_name() -> None:
    """
    Reject a global setting used on an individual reference entry
    """
    with pytest.raises(ValueError, match="members_on_same_page.*inline_methods.*global"):
        SpecObject(name="Widget", inline_methods=False)


@pytest.mark.parametrize("discovery", [False, True])
@pytest.mark.parametrize("members", [True, False, ["load"]])
def test_reference_translators_keep_members_on_same_page(
    tmp_path: Path, discovery: bool, members: bool | list[str]
) -> None:
    """
    Preserve explicit page placement alongside member selection
    """
    config = GreatDocs(project_path=str(tmp_path))._config
    entry = {"name": "DataProcessor", "members": members, "members_on_same_page": False}
    authored = [{"title": "API", "contents": [entry]}]
    result = (
        sections.from_explicit_config(config, authored, {})
        if discovery
        else sections.from_reference_config(authored)
    )
    expected = {"name": "DataProcessor", "members_on_same_page": False}
    if members is not True:
        expected["members"] = [] if members is False else members
    assert result[0]["contents"] == [expected]


@pytest.mark.parametrize("discovery", [False, True])
def test_reference_translators_reject_children(tmp_path: Path, discovery: bool) -> None:
    """
    Reject `children` in the authored reference configuration
    """
    config = GreatDocs(project_path=str(tmp_path))._config
    authored = [{"title": "API", "contents": [{"name": "Widget", "children": "linked"}]}]
    with pytest.raises(ValueError, match="children.*members_on_same_page.*members"):
        if discovery:
            sections.from_explicit_config(config, authored, {})
        else:
            sections.from_reference_config(authored)


@pytest.mark.parametrize("discovery", [False, True])
def test_reference_translators_reject_global_threshold_name(
    tmp_path: Path, discovery: bool
) -> None:
    """
    Reject `inline_methods` on an individual reference entry
    """
    config = GreatDocs(project_path=str(tmp_path))._config
    authored = [{"title": "API", "contents": [{"name": "Widget", "inline_methods": False}]}]
    with pytest.raises(ValueError, match="members_on_same_page.*inline_methods.*global"):
        if discovery:
            sections.from_explicit_config(config, authored, {})
        else:
            sections.from_reference_config(authored)


@pytest.mark.parametrize("members_on_same_page", [True, False, None])
@pytest.mark.parametrize("global_policy", [True, False, 5, 10])
@pytest.mark.parametrize("members", [False, ["load", "summary"]])
@pytest.mark.parametrize("dynamic", [False, True])
def test_authored_yaml_places_synthetic_methods_on_requested_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    members_on_same_page: bool | None,
    global_policy: bool | int,
    members: bool | list[str],
    dynamic: bool,
) -> None:
    """
    Preserve selected members and page placement through the build
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "test-packages"))
    from synthetic.catalog import get_spec
    from synthetic.generator import generate_package

    package_root = generate_package(get_spec("gdtest_big_class"), tmp_path)
    monkeypatch.syspath_prepend(str(package_root))
    monkeypatch.delitem(sys.modules, "gdtest_big_class", raising=False)
    entry: dict[str, object] = {"name": "DataProcessor", "members": members}
    if members_on_same_page is not None:
        entry["members_on_same_page"] = members_on_same_page
    write_config(
        package_root,
        {
            "dynamic": dynamic,
            "inline_methods": global_policy,
            "reference": [{"title": "API", "contents": [entry]}],
        },
    )
    docs = GreatDocs(project_path=str(package_root))
    docs._remote = StubRemote()
    monkeypatch.chdir(package_root)
    run = make_run(docs)
    prepare_build_directory(docs, run)
    configured_entry = run.api_block["sections"][0]["contents"][0]
    if members_on_same_page is None:
        derived_split = members is not False and global_policy is not True and global_policy != 10
        if derived_split:
            assert configured_entry["members_on_same_page"] is False
        else:
            assert "members_on_same_page" not in configured_entry
    monkeypatch.chdir(docs.layout.build_dir)
    outcome, ref = reference.api(run, docs._config, docs.layout, BuildLog(stream=io.StringIO()))

    assert outcome == "API reference generated"
    assert ref is not None
    reference_dir = docs.layout.build_dir / "reference"
    class_page = (reference_dir / "DataProcessor.qmd").read_text(encoding="utf-8")
    method_pages = {page.path for page in ref.manifest.pages if page.path != "DataProcessor"}
    entries = decode((docs.layout.build_dir / "objects.inv").read_bytes()).entries
    if members is False:
        assert method_pages == set()
        assert {entry.name for entry in entries} == {"gdtest_big_class.DataProcessor"}
        return
    load_entry = next(
        entry for entry in entries if entry.name == "gdtest_big_class.DataProcessor.load"
    )
    expected_same_page = (
        members_on_same_page
        if members_on_same_page is not None
        else global_policy is True or global_policy == 10
    )
    if expected_same_page:
        assert method_pages == set()
        assert "Load data from a file path" in class_page
        assert load_entry.uri.startswith("reference/DataProcessor.html#")
    else:
        assert len(method_pages) == 2
        load_page = next(path for path in method_pages if path.endswith("DataProcessor.load"))
        assert f"{load_page}.qmd)" in class_page
        assert f"{load_page}.qmd#" not in class_page
        assert "Path to the data file" not in class_page
        assert "Path to the data file" in (reference_dir / f"{load_page}.qmd").read_text(
            encoding="utf-8"
        )
        assert load_entry.uri == f"reference/{load_page}.html"
    assert "DataProcessor Methods" not in (reference_dir / "index.qmd").read_text(encoding="utf-8")
