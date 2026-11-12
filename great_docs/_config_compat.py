"""
Compatibility inputs for member-page placement
"""

from __future__ import annotations

import warnings
from typing import Any


def normalise_member_placement(options: dict[str, Any], *, default_limit: int) -> dict[str, Any]:
    """
    Translate deprecated global placement while preserving explicit current values

    Use `inline_methods` only as a fallback for current fields that are absent.
    Return a copy with the old key removed and all other settings preserved.
    Leave the input mapping unchanged.
    """
    result = options.copy()
    if "inline_methods" not in result:
        return result

    legacy = result.pop("inline_methods")
    warnings.warn(
        "Global `inline_methods` is deprecated. Set `members_on_same_page` "
        "for fixed placement or `max_members_on_same_page` for automatic placement.",
        UserWarning,
        stacklevel=3,
    )
    if isinstance(legacy, bool):
        result.setdefault("members_on_same_page", legacy)
    else:
        try:
            limit = int(legacy)
        except (TypeError, ValueError, OverflowError):
            limit = default_limit
        result.setdefault("max_members_on_same_page", max(0, limit))
    return result
