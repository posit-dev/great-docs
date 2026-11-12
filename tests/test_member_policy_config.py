"""
Validation and generated configuration for member-page placement
"""

from __future__ import annotations

import copy
import warnings
from pathlib import Path

import pytest

from great_docs._apiref._settings import Settings
from great_docs._apiref.api_reference import APIReference
from great_docs.config import Config, ConfigError, create_default_config
from tests.support import write_config


@pytest.mark.parametrize("value", [True, False, None])
def test_reference_block_accepts_global_override(value: bool | None) -> None:
    ref = APIReference({"package": "example", "members_on_same_page": value})
    assert ref.settings.members_on_same_page is value


@pytest.mark.parametrize("value", [0, 1, 5, "true", [], {}])
def test_reference_block_rejects_non_boolean_override(value: object) -> None:
    with pytest.raises(ValueError, match="members_on_same_page.*true, false or null"):
        Settings.make({"members_on_same_page": value})


@pytest.mark.parametrize("value", [True, False, None, -1, 2.5, "5", [], {}])
def test_reference_block_rejects_invalid_limit(value: object) -> None:
    with pytest.raises(ValueError, match="max_members_on_same_page.*non-negative integer"):
        Settings.make({"max_members_on_same_page": value})


_LEGACY_CASES: list[tuple[dict[str, object], bool | None, int]] = [
    ({"inline_methods": True}, True, 5),
    ({"inline_methods": False}, False, 5),
    ({"inline_methods": 8}, None, 8),
    ({"inline_methods": 0}, None, 0),
    ({"inline_methods": -4}, None, 0),
    ({"inline_methods": "8"}, None, 8),
    ({"inline_methods": 3.9}, None, 3),
    ({"inline_methods": "invalid"}, None, 5),
    ({"inline_methods": None}, None, 5),
    ({"inline_methods": []}, None, 5),
    ({"inline_methods": float("inf")}, None, 5),
    ({"inline_methods": 8, "members_on_same_page": True}, True, 8),
    ({"inline_methods": True, "max_members_on_same_page": 2}, True, 2),
    ({"inline_methods": False, "members_on_same_page": None}, None, 5),
    ({"inline_methods": 8, "max_members_on_same_page": 2}, None, 2),
    (
        {"inline_methods": False, "members_on_same_page": True, "max_members_on_same_page": 1},
        True,
        1,
    ),
    (
        {"inline_methods": 8, "members_on_same_page": None, "max_members_on_same_page": 2},
        None,
        2,
    ),
]


@pytest.mark.parametrize(("options", "same_page", "maximum"), _LEGACY_CASES)
def test_global_compatibility_preserves_raw_input_and_warns_once(
    tmp_path: Path, options: dict[str, object], same_page: bool | None, maximum: int
) -> None:
    """
    Preserve explicit settings when translating legacy placement

    Keep the written settings available to lint and warn once per construction.
    """
    with pytest.warns(
        UserWarning, match="inline_methods.*members_on_same_page.*max_members_on_same_page"
    ) as emitted:
        config = write_config(tmp_path, options)
        for _ in range(3):
            assert config.members_on_same_page is same_page
            assert config.max_members_on_same_page == maximum
            assert config.user_settings == options
    assert len(emitted) == 1
    assert "inline_methods" not in config.to_dict()
    with pytest.raises(KeyError):
        _ = config["inline_methods"]


@pytest.mark.parametrize(("options", "same_page", "maximum"), _LEGACY_CASES)
def test_raw_reference_global_compatibility_respects_fieldwise_precedence(
    options: dict[str, object], same_page: bool | None, maximum: int
) -> None:
    """
    Translate legacy placement without changing the supplied reference block

    Explicit current fields take precedence independently, including `null`.
    """
    original = copy.deepcopy(options)
    with pytest.warns(
        UserWarning, match="inline_methods.*members_on_same_page.*max_members_on_same_page"
    ) as emitted:
        settings = Settings.make(options)
        assert settings.members_on_same_page is same_page
        assert settings.max_members_on_same_page == maximum
    assert len(emitted) == 1
    assert options == original


@pytest.mark.parametrize(
    "override", [{"members_on_same_page": 1}, {"max_members_on_same_page": True}]
)
def test_compatibility_input_does_not_relax_new_field_validation(
    tmp_path: Path, override: dict[str, object]
) -> None:
    """
    Reject invalid current fields even when legacy input is present
    """
    options = {"inline_methods": 8, **override}
    with pytest.warns(UserWarning), pytest.raises(ConfigError):
        write_config(tmp_path, options)
    with pytest.warns(UserWarning), pytest.raises(ValueError):
        Settings.make(options)


def test_current_fields_do_not_emit_deprecation_warnings(tmp_path: Path) -> None:
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        config = write_config(
            tmp_path, {"members_on_same_page": None, "max_members_on_same_page": 2}
        )
        assert config.max_members_on_same_page == 2
        assert Settings.make({"members_on_same_page": None}).members_on_same_page is None
    assert not emitted


def test_starter_lists_new_policy_defaults(tmp_path: Path) -> None:
    starter = create_default_config()
    assert "# members_on_same_page: null" in starter
    assert "# max_members_on_same_page: 5" in starter
    assert "inline_methods" not in starter
    (tmp_path / "great-docs.yml").write_text(starter, encoding="utf-8")
    config = Config(tmp_path)
    assert config.members_on_same_page is None
    assert config.max_members_on_same_page == 5
