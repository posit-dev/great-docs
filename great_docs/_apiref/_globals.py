from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal


# Parent object's path (as shown on the API page) -> the member, or members,
# of that object to leave out of the generated documentation.
ExclusionMap = dict[str, str | Sequence[str]]


@dataclass
class Exclusions:
    """Members left out of the generated documentation

    Each mapping is keyed by a parent object's path (as shown on the API
    page); the value names the member — or members — of that object to
    leave out: parameters of a callable, or attributes, functions, and
    classes of a class or module.
    """

    parameters: ExclusionMap = field(default_factory=ExclusionMap)
    attributes: ExclusionMap = field(default_factory=ExclusionMap)
    functions: ExclusionMap = field(default_factory=ExclusionMap)
    classes: ExclusionMap = field(default_factory=ExclusionMap)


EXCLUSIONS = Exclusions()


@lru_cache(4)
def package_info(
    key: Literal["GITHUB_REPO_URL", "GIT_REF", "PACKAGE_ROOT", "SOURCE_PATH"],
) -> str | None:
    """
    Look up a piece of package metadata by `key`

    This information is put into the environment by `GreatDocs.__init__`.

    Returns
    -------
    str | None
        The value from the environment, or None when it is not set.
    """
    return os.environ.get(key, None)
