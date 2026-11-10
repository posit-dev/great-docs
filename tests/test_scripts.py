import json
import re
from pathlib import Path
from typing import Any

import pytest

from great_docs._website import scripts
from tests.support import write_config

ASSETS = Path(scripts.__file__).parents[1] / "assets"


def _includes(quarto_config: dict[str, Any], slot: str) -> list[str]:
    return [str(entry) for entry in quarto_config["format"]["html"].get(slot, [])]


def _position(entries: list[str], marker: str) -> int:
    return next(i for i, entry in enumerate(entries) if marker in entry)


def test_every_file_in_the_table_is_packaged():
    names = [script.name for script in scripts.SCRIPTS]

    assert len(names) == len(set(names))
    for script in scripts.SCRIPTS:
        assert (ASSETS / script.directory / script.name).is_file(), script.name


def test_named_raises_for_a_file_outside_the_table():
    with pytest.raises(KeyError):
        scripts.named("missing.js")


def test_copy_skips_files_the_site_does_not_use(tmp_path: Path):
    config = write_config(tmp_path, {"back_to_top": False})
    build_dir = tmp_path / "build"
    build_dir.mkdir()

    scripts.copy(config, build_dir, has_repository=False)

    assert (build_dir / "gd-lightbox.css").is_file()
    assert (build_dir / "tooltips.js").is_file()
    assert not (build_dir / "back-to-top.js").exists()
    assert not (build_dir / "marimo-islands.js").exists()


def test_add_resources_lists_used_files_in_table_order(tmp_path: Path):
    config = write_config(tmp_path, {"back_to_top": False})
    quarto_config: dict[str, Any] = {"project": {"resources": ["objects.inv"]}}

    scripts.add_resources(config, quarto_config, has_repository=False)

    resources = quarto_config["project"]["resources"]
    order = [script.name for script in scripts.SCRIPTS]
    listed = resources[1:]
    assert resources[0] == "objects.inv"
    assert listed == sorted(listed, key=order.index)
    assert "tooltips.js" in listed
    assert "back-to-top.js" not in listed


def test_include_libraries_loads_font_awesome_then_marimo_then_lightbox(tmp_path: Path):
    config = write_config(tmp_path, {"marimo": {"enabled": True}})
    quarto_config: dict[str, Any] = {}

    scripts.include_libraries(config, quarto_config)

    headers = _includes(quarto_config, "include-in-header")
    assert len(headers) == 10
    assert "font-awesome" in headers[0]
    assert "marimo-team/islands" in headers[1]
    assert "marimo-islands.js" in headers[2]
    assert "gd-lightbox-annotate.js" in headers[-1]


def test_include_libraries_keeps_an_existing_font_awesome_link(tmp_path: Path):
    config = write_config(tmp_path)
    existing = {"text": '<link href="https://example.com/Font-Awesome.css">'}
    quarto_config: dict[str, Any] = {"format": {"html": {"include-in-header": [existing]}}}

    scripts.include_libraries(config, quarto_config)

    headers = _includes(quarto_config, "include-in-header")
    assert sum("font-awesome" in entry.lower() for entry in headers) == 1


def test_include_loads_scripts_in_table_order(tmp_path: Path):
    config = write_config(tmp_path)
    quarto_config: dict[str, Any] = {}

    scripts.include(config, quarto_config, tmp_path, has_repository=True)

    after_body = _includes(quarto_config, "include-after-body")
    expected = [
        script.name
        for script in scripts.SCRIPTS
        if script.slot == "include-after-body" and script.used(config, has_repository=True)
    ]
    assert [_position(after_body, name) for name in expected] == list(range(len(expected)))
    assert len(after_body) == len(expected)
    assert _includes(quarto_config, "include-in-header") == [
        str(scripts.script_include("theme-init.js"))
    ]


def test_include_leaves_out_the_github_widget_without_a_repository(tmp_path: Path):
    config = write_config(tmp_path)
    quarto_config: dict[str, Any] = {}

    scripts.include(config, quarto_config, tmp_path, has_repository=False)

    assert not any(
        "github-widget" in entry for entry in _includes(quarto_config, "include-after-body")
    )


def test_include_puts_data_before_the_script_that_reads_it(tmp_path: Path):
    config = write_config(tmp_path, {"sidebar_filter": {"min_items": 5}, "dark_mode_toggle": False})
    quarto_config: dict[str, Any] = {}

    scripts.include(config, quarto_config, tmp_path, has_repository=False)

    after_body = _includes(quarto_config, "include-after-body")
    data = _position(after_body, "sidebarFilterMinItems")
    assert after_body[data + 1].count("sidebar-filter.js") == 1
    assert sum("sidebarFilterMinItems" in entry for entry in after_body) == 1
    headers = _includes(quarto_config, "include-in-header")
    assert len(headers) == 2
    assert "gd-dark-mode" in headers[0]
    assert "theme-init.js" in headers[1]


@pytest.mark.parametrize("staged", [True, False], ids=["embedded", "linked"])
def test_include_embeds_the_status_script_staged_in_the_build_directory(
    tmp_path: Path, staged: bool
):
    config = write_config(tmp_path, {"page_status": {"enabled": True}})
    if staged:
        (tmp_path / "page-status-badges.js").write_text("function renderPageBadge() {}\n")
    quarto_config: dict[str, Any] = {}

    scripts.include(config, quarto_config, tmp_path, has_repository=False)

    after_body = _includes(quarto_config, "include-after-body")
    status = [
        entry for entry in after_body if scripts.named("page-status-badges.js").is_entry(entry)
    ]
    assert len(status) == 1
    assert ("function renderPageBadge" in status[0]) == staged


@pytest.mark.parametrize(
    ("settings", "has_repository"),
    [
        ({}, True),
        ({}, False),
        ({"sidebar_filter": {"enabled": False}, "dark_mode_toggle": False}, True),
        ({"github_style": "icon", "marimo": {"enabled": True}, "cli": {"enabled": True}}, True),
        ({"webmcp": True}, True),
    ],
    ids=["defaults", "no-repository", "opt-outs", "icon-marimo-cli", "webmcp"],
)
def test_a_file_is_copied_and_listed_exactly_when_it_is_used(
    tmp_path: Path, settings: dict[str, Any], has_repository: bool
):
    config = write_config(tmp_path, settings)
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    quarto_config: dict[str, Any] = {}

    scripts.copy(config, build_dir, has_repository=has_repository)
    scripts.add_resources(config, quarto_config, has_repository=has_repository)
    scripts.include_libraries(config, quarto_config)
    scripts.include(config, quarto_config, build_dir, has_repository=has_repository)

    copied = {path.name for path in build_dir.iterdir()}
    listed = set(quarto_config["project"]["resources"])
    included = " ".join(
        _includes(quarto_config, "include-in-header")
        + _includes(quarto_config, "include-after-body")
    )
    for script in scripts.SCRIPTS:
        used = script.used(config, has_repository=has_repository)
        assert (script.name in copied) == used, script.name
        assert (script.name in listed) == used, script.name
        if script.slot is not None:
            assert (script.name in included) == used, script.name


def _webmcp_headers(
    tmp_path: Path,
    settings: dict[str, Any],
    *,
    has_api_reference: bool = True,
    has_cli_reference: bool = False,
) -> list[str]:
    config = write_config(tmp_path, settings)
    quarto_config: dict[str, Any] = {}
    scripts.include(config, quarto_config, tmp_path, has_repository=False)
    scripts.include_webmcp_settings(
        config,
        quarto_config,
        has_api_reference=has_api_reference,
        has_cli_reference=has_cli_reference,
    )
    return [entry["text"] for entry in quarto_config["format"]["html"]["include-in-header"]]


def _webmcp_settings(headers: list[str]) -> dict[str, Any]:
    entry = headers[_position(headers, "gd-webmcp-settings")]
    match = re.search(r'id="gd-webmcp-settings">(.*)</script>', entry)
    assert match is not None
    return json.loads(match.group(1))


def test_webmcp_is_off_by_default(tmp_path: Path):
    headers = _webmcp_headers(tmp_path, {})

    assert not any("webmcp" in entry for entry in headers)


def test_webmcp_loads_deferred_in_the_header_after_its_settings(tmp_path: Path):
    headers = _webmcp_headers(tmp_path, {"webmcp": True})

    script = _position(headers, "webmcp.js")
    assert 'defer src="/webmcp.js"' in headers[script]
    assert _position(headers, "gd-webmcp-settings") == script - 1
    assert sum("webmcp.js" in entry for entry in headers) == 1


def test_webmcp_settings_carry_the_configuration(tmp_path: Path):
    from great_docs import __version__

    headers = _webmcp_headers(
        tmp_path,
        {
            "webmcp": {
                "enabled": True,
                "actions": False,
                "js_api": False,
                "exclude_tools": ["get_page"],
            },
            "markdown_pages": False,
        },
    )

    assert _webmcp_settings(headers) == {
        "schema": 1,
        "generator": f"great-docs {__version__}",
        "markdown_pages": False,
        "features": {"api": True, "cli": False},
        "actions": False,
        "js_api": False,
        "exclude": ["get_page"],
    }


@pytest.mark.parametrize(("has_api_reference", "has_cli_reference"), [(True, False), (False, True)])
def test_webmcp_settings_name_the_reference_features(
    tmp_path: Path, has_api_reference: bool, has_cli_reference: bool
):
    headers = _webmcp_headers(
        tmp_path,
        {"webmcp": True},
        has_api_reference=has_api_reference,
        has_cli_reference=has_cli_reference,
    )

    assert _webmcp_settings(headers)["features"] == {
        "api": has_api_reference,
        "cli": has_cli_reference,
    }


def test_webmcp_settings_are_added_once(tmp_path: Path):
    config = write_config(tmp_path, {"webmcp": True})
    quarto_config: dict[str, Any] = {}
    scripts.include(config, quarto_config, tmp_path, has_repository=False)
    for _ in range(2):
        scripts.include_webmcp_settings(
            config, quarto_config, has_api_reference=True, has_cli_reference=False
        )

    headers = _includes(quarto_config, "include-in-header")
    assert sum("gd-webmcp-settings" in entry for entry in headers) == 1


def test_webmcp_settings_cannot_close_their_script_element(tmp_path: Path):
    headers = _webmcp_headers(
        tmp_path, {"webmcp": {"enabled": True, "exclude_tools": ["</script><b>"]}}
    )

    entry = headers[_position(headers, "gd-webmcp-settings")]
    assert entry.count("</script>") == 1
    assert _webmcp_settings(headers)["exclude"] == ["</script><b>"]


def test_webmcp_origin_trial_tags_appear_only_with_tokens(tmp_path: Path):
    without = _webmcp_headers(tmp_path, {"webmcp": True})
    with_tokens = _webmcp_headers(
        tmp_path, {"webmcp": {"enabled": True, "origin_trials": ["TOKEN-A", ' "B&C" ']}}
    )

    assert not any("origin-trial" in entry for entry in without)
    entry = with_tokens[_position(with_tokens, "gd-webmcp-settings")]
    assert entry.splitlines()[:2] == [
        '<meta http-equiv="origin-trial" content="TOKEN-A">',
        '<meta http-equiv="origin-trial" content="&quot;B&amp;C&quot;">',
    ]
