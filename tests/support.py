"""
Shared configuration and build setup for `GreatDocs` tests

`write_config` writes and loads `great-docs.yml`. `mock_config` provides a `Config` double
with empty defaults. `stubbed_build` stubs Quarto and build steps while preserving the build's
control flow.
"""

from __future__ import annotations

import types
import typing
from collections.abc import Callable, Generator, Iterable, Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, NonCallableMagicMock, patch

from yaml12 import format_yaml

from great_docs import Config, GreatDocs

if TYPE_CHECKING:
    from pathlib import Path

# Keep these methods in the order `GreatDocs.build()` first calls them.
# Update this list when a build step moves out of `GreatDocs`.
_BUILD_METHODS: tuple[str, ...] = (
    "_validate_build_outputs",
    "_detect_package_name",
    "_griffe_search_paths",
    "_find_user_guide_dir",
    "_prepare_build_directory",
    "_refresh_api_reference_config",
    "_llms_txt_available",
    "_generate_llms_txt",
    "_generate_llms_full_txt",
    "_generate_skill_md",
    "_get_package_metadata",
    "_get_github_repo_info",
    "_generate_changelog_page",
    "_add_changelog_to_navbar",
    "_resolve_importable_name",
    "_discover_click_cli",
    "_generate_cli_reference_pages",
    "_update_sidebar_with_cli",
    "_count_cli_sidebar_items",
    "_detect_module_name",
    "_discover_mcp_server",
    "_update_sidebar_with_mcp",
    "_generate_mcp_manifest",
    "_remove_mcp_from_ref_sections",
    "_process_user_guide",
    "_process_sections",
    "_process_custom_pages",
    "_process_tags",
    "_process_page_statuses",
    "_copy_assets",
    "_update_quarto_config",
    "_get_quarto_env",
    "_write_quarto_yml",
    "_normalize_freeze_shorthand",
    "_write_page_metadata",
    "_prerender_term_player",
    "_print_layout_notice",
    "_default_description",
    "_structured_data",
    "_generate_seo_files",
    "_write_build_timing",
    "_persist_freeze_cache",
    "_auto_save_snapshot",
)

# `great_docs.config` imports these names only while type checking, so its annotations resolve
# only when they are supplied.
_TYPE_CHECKING_NAMES: dict[str, Any] = {"Any": Any, "ConfigDict": dict[str, Any]}

# Public attributes that `Config.__init__` sets and the class does not declare.
_CONFIG_INSTANCE_ATTRIBUTES = ("project_root", "config_path", "cache_dir")


def write_config(root: Path, settings: str | Mapping[str, object] = "") -> Config:
    """
    Write and load a project's `great-docs.yml`

    Parameters
    ----------
    root
        The project directory.
    settings
        YAML text to write unchanged, or a mapping to serialise as YAML.

    Returns
    -------
    :
        The configuration loaded from `root`.
    """
    text = settings if isinstance(settings, str) else format_yaml(dict(settings))
    (root / "great-docs.yml").write_text(text, encoding="utf-8")
    return Config(root)


def mock_config(**values: object) -> NonCallableMagicMock:
    """
    Create a `Config` double with empty defaults

    Each property reads as the empty value of its declared type, and each public method returns
    the empty value of its declared return type. The empty value is `None` when the type admits
    `None`, and otherwise the type's falsy value, such as `False`, `""`, `[]` or `{}`. Reading or
    setting a name that `Config` lacks raises `AttributeError`, so a test fails at its setup when
    a setting it names is renamed.

    Parameters
    ----------
    **values
        Values for properties or attributes, by name.

    Returns
    -------
    :
        A configuration double with the supplied values and empty defaults.
    """
    config = NonCallableMagicMock(spec_set=[*dir(Config), *_CONFIG_INSTANCE_ATTRIBUTES])
    for name, member in vars(Config).items():
        if isinstance(member, property) and member.fget is not None:
            setattr(config, name, _empty(_return_type(member.fget)))
        elif callable(member) and not name.startswith("_"):
            getattr(config, name).return_value = _empty(_return_type(member))
    for name, value in values.items():
        setattr(config, name, value)
    return config


@dataclass(frozen=True)
class BuildStubs:
    """
    Stubs for build steps and the Quarto render process

    Attributes
    ----------
    steps
        Method stubs keyed by name. Set `side_effect` to an exception to make a step fail.
    render
        The `quarto render` process, which defaults to exit status 0 and no output. Set
        `returncode` and `stderr` to simulate a render failure.
    """

    steps: dict[str, MagicMock]
    render: MagicMock


@contextmanager
def stubbed_build(
    docs: GreatDocs, run: Iterable[str] = (), **returns: object
) -> Generator[BuildStubs]:
    """
    Stub Quarto and the methods `GreatDocs.build()` calls on an instance

    Within the block, `docs.build()` keeps its control flow: the Quarto installation check
    passes, `quarto render` succeeds silently, and build steps are stubbed unless listed in
    `run`. Stubs enforce the real methods' call signatures and return empty values of their
    declared return types unless overridden in `returns`.

    Parameters
    ----------
    docs
        The instance to stub.
    run
        Names of methods to run for real. Also include any build steps these methods need to
        call for real; other steps remain stubbed.
    **returns
        Return values for stubbed methods, by method name.

    Yields
    ------
    :
        The stubs to configure before the build and inspect afterwards.

    Raises
    ------
    ValueError
        If `run` or `returns` names a method that `build()` does not call, or if both name the same
        method.
    AttributeError
        If a method in the build-step list no longer exists on `GreatDocs`.
    """
    real = set(run)
    unknown = sorted((real | set(returns)) - set(_BUILD_METHODS))
    if unknown:
        raise ValueError(f"build() does not call {unknown}")
    both = sorted(real & set(returns))
    if both:
        raise ValueError(f"a method that runs cannot have a stubbed return value: {both}")
    missing = [name for name in _BUILD_METHODS if not hasattr(GreatDocs, name)]
    if missing:
        raise AttributeError(f"GreatDocs has no {missing}; update the method list in {__name__}")

    with ExitStack() as stack:
        stack.enter_context(patch("great_docs.core._ensure_quarto_installed", autospec=True))
        render = stack.enter_context(patch("subprocess.Popen", autospec=True)).return_value
        render.stdout = iter(())
        render.stderr = iter(())
        render.returncode = 0

        steps: dict[str, MagicMock] = {}
        for name in _BUILD_METHODS:
            if name in real:
                continue
            value = (
                returns[name] if name in returns else _empty(_return_type(getattr(GreatDocs, name)))
            )
            steps[name] = stack.enter_context(
                patch.object(docs, name, autospec=True, return_value=value)
            )
        yield BuildStubs(steps=steps, render=render)


def _return_type(function: Callable[..., object]) -> object:
    """
    Resolve the declared return type of a function

    Parameters
    ----------
    function
        An annotated function or method.

    Returns
    -------
    :
        The evaluated return annotation.
    """
    return typing.get_type_hints(function, localns=_TYPE_CHECKING_NAMES)["return"]


def _empty(annotation: object) -> object:
    """
    Create the default empty value for a type annotation

    Parameters
    ----------
    annotation
        An evaluated type annotation.

    Returns
    -------
    :
        `None` for a type that allows it, a tuple of empty values for a fixed-length tuple, or
        the falsy value constructed by calling the type with no arguments.

    Raises
    ------
    TypeError
        If calling the type with no arguments does not produce a falsy value.
    """
    members = (
        typing.get_args(annotation)
        if typing.get_origin(annotation) in (typing.Union, types.UnionType)
        else (annotation,)
    )
    if type(None) in members:
        return None
    first = members[0]
    origin = typing.get_origin(first) or first
    if origin is tuple:
        return tuple(_empty(member) for member in typing.get_args(first))
    value = origin() if isinstance(origin, type) else None
    if value is None or value:
        raise TypeError(f"{annotation!r} has no empty value")
    return value
