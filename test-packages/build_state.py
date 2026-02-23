"""
Shared build-state management for the Great Docs Gauntlet (GDG).

Tracks per-package build timestamps, statuses, and a per-run identifier so
the GDG can mark stale (not-rebuilt-this-run) packages.

State file layout (``_build_state.json``):

.. code-block:: json

    {
      "last_run_id": "2026-02-23T14:30:00",
      "packages": {
        "gdtest_minimal": {
          "status": "ok",
          "built_at": "2026-02-23T14:01:23",
          "elapsed_s": 6.4,
          "run_id": "2026-02-23T14:30:00",
          "error": null
        }
      }
    }

A package is **stale** when its ``run_id`` doesn't match ``last_run_id``.
After a full rebuild every package shares the same ``run_id`` (none stale).
After a selective ``--only`` rebuild, only the rebuilt packages are current.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def new_run_id() -> str:
    """Generate a fresh run identifier (ISO-8601 UTC timestamp)."""
    return _now_iso()


def load_state(state_path: Path) -> dict[str, Any]:
    """Load the build state from *state_path*, or return an empty state."""
    if state_path.exists():
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_run_id": None, "packages": {}}


def save_state(state_path: Path, state: dict[str, Any]) -> None:
    """Persist *state* to *state_path* atomically."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=False), encoding="utf-8")
    tmp.replace(state_path)


def record_build(
    state: dict[str, Any],
    name: str,
    *,
    run_id: str,
    status: str,
    elapsed: float = 0.0,
    error: str | None = None,
) -> None:
    """Record a single package build result into *state*."""
    state.setdefault("packages", {})[name] = {
        "status": status,
        "built_at": _now_iso(),
        "elapsed_s": round(elapsed, 1),
        "run_id": run_id,
        "error": error,
    }


def reset_for_full_rebuild(state: dict[str, Any], run_id: str) -> None:
    """Clear all package entries and stamp a new run epoch."""
    state["last_run_id"] = run_id
    state["packages"] = {}


def start_selective_run(state: dict[str, Any], run_id: str) -> None:
    """Advance the run id without clearing packages (selective rebuild)."""
    state["last_run_id"] = run_id


def is_stale(state: dict[str, Any], name: str) -> bool:
    """
    Return ``True`` if the package's ``run_id`` differs from the current
    ``last_run_id`` (i.e. it wasn't rebuilt in the most recent run).
    """
    last_run = state.get("last_run_id")
    if not last_run:
        return False  # no run recorded yet

    pkg = state.get("packages", {}).get(name)
    if not pkg:
        return True  # never built

    return pkg.get("run_id", "") != last_run


def latest_build_ts(state: dict[str, Any]) -> str | None:
    """Return the most-recent ``built_at`` across all packages (or ``None``)."""
    timestamps = [p["built_at"] for p in state.get("packages", {}).values() if p.get("built_at")]
    return max(timestamps) if timestamps else None


def summary(state: dict[str, Any]) -> dict[str, int]:
    """Return counts of ok / failed / stale / total packages."""
    pkgs = state.get("packages", {})
    ok = sum(1 for p in pkgs.values() if p.get("status") == "ok")
    failed = sum(1 for p in pkgs.values() if p.get("status") != "ok")
    stale = sum(1 for n in pkgs if is_stale(state, n))
    return {"ok": ok, "failed": failed, "stale": stale, "total": ok + failed}
