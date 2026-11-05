from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from great_docs._translations import get_translation

from ._settings import Settings

# Parent object's path (as shown on the API page) -> the member, or members,
# of that object to leave out of the generated documentation.
ExclusionMap = dict[str, str | Sequence[str]]


@dataclass
class Exclusions:
    """Members left out of the generated documentation

    Each mapping is keyed by a parent object's path (as shown on the API
    page); the value names the member — or members — of that object to
    leave out: parameters of a callable, or attributes, functions, classes,
    and type aliases of a class or module.
    """

    parameters: ExclusionMap = field(default_factory=ExclusionMap)
    attributes: ExclusionMap = field(default_factory=ExclusionMap)
    functions: ExclusionMap = field(default_factory=ExclusionMap)
    classes: ExclusionMap = field(default_factory=ExclusionMap)
    type_aliases: ExclusionMap = field(default_factory=ExclusionMap)


EXCLUSIONS = Exclusions()


SETTINGS = Settings()
"""The settings of the build in progress, for the render classes to read"""


def translate(key: str) -> str:
    """
    Translate a user-interface label into the current build language

    Parameters
    ----------
    key
        The translation key, such as `parameters`.

    Returns
    -------
    The translated label, with English as the fallback.
    """
    return get_translation(key, SETTINGS.lang)


def translate_versioned(key: str, version: str) -> str:
    """
    Translate a version label and insert the version

    Replace `{v}` when the translated label contains a placeholder; otherwise,
    append the version. Remove the placeholder when the version is empty.

    Parameters
    ----------
    key
        The translation key, such as `added_in_version`.
    version
        The version, or an empty string for a label without one.

    Returns
    -------
    The translated label, including the version when supplied.
    """
    label = translate(key)
    if not version:
        return label.replace(" {v}", "").replace("{v}", "")
    if "{v}" in label:
        return label.replace("{v}", version)
    return f"{label} {version}"
