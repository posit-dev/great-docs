#!/usr/bin/env python3
"""
Render all Great Docs Gauntlet (GDG) package sites and serve them with a shared nav bar.

Usage:
    python test-packages/render_all.py              # build all + serve
    python test-packages/render_all.py --build      # build only
    python test-packages/render_all.py --serve      # serve previously built
    python test-packages/render_all.py --only gdtest_minimal gdtest_github_icon
    python test-packages/render_all.py --build --skip-ok   # resume interrupted build

The script:
  1. Generates each synthetic package into _rendered/<name>/
  2. Runs `great-docs init --force` + `great-docs build` on each
  3. Collects all _site/ outputs into the GDG directory
  4. Injects a top navigation bar into every HTML file
  5. Creates a GDG index page at _rendered/_hub/index.html
  6. Starts a local HTTP server on port 3333
"""

from __future__ import annotations

import argparse
import html
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import yaml

# ── Path setup ───────────────────────────────────────────────────────────────

_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent

if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from build_state import (
    is_stale,
    load_state,
    new_run_id,
    record_build,
    reset_for_full_rebuild,
    save_state,
    start_selective_run,
)
from catalog import (
    ALL_PACKAGES,
    AXIS_COLORS,
    DIMENSIONS,
    PACKAGE_DESCRIPTIONS,
    get_spec,
)
from synthetic.generator import generate_package

# ── Constants ────────────────────────────────────────────────────────────────

RENDERED_DIR = _THIS_DIR / "_rendered"
HUB_DIR = RENDERED_DIR / "_hub"
LOGS_DIR = RENDERED_DIR / "_logs"
STATE_FILE = RENDERED_DIR / "_build_state.json"
PORT = 3333

# ── Coverage levels tracked by test_gdg_rendered.py ─────────────────────────
# Each level maps to a parametrized test or dedicated test in the file.
# The score is "how many of these 21 levels does a package participate in?"

_COVERAGE_LEVELS = [
    "R0:idx",
    "R0:srch",
    "R0:ref",
    "R0:nodoc",
    "R0:bigcl",
    "R0:ug",
    "R0:supp",
    "R1:title",
    "R1:badge",
    "R1:sig",
    "R1:desc",
    "R2:param",
    "R2:pmatch",
    "R2:ret",
    "R4:refidx",
    "R4:sechdg",
    "R4:sbar",
    "R4:sbsec",
    "R4:land",
    "R4:hdg",
    "DED",
]

# Package names explicitly referenced in test_gdg_rendered.py (dedicated tests)
_DEDICATED_PACKAGES: set[str] = set()


def _load_dedicated_packages() -> set[str]:
    """Parse test_gdg_rendered.py once for explicitly named packages."""
    global _DEDICATED_PACKAGES  # noqa: PLW0603
    if _DEDICATED_PACKAGES:
        return _DEDICATED_PACKAGES
    test_file = _PROJECT_ROOT / "tests" / "test_gdg_rendered.py"
    if test_file.exists():
        _DEDICATED_PACKAGES = set(re.findall(r"gdtest_[a-z_]+", test_file.read_text()))
    return _DEDICATED_PACKAGES


def _compute_coverage(name: str) -> dict[str, bool]:
    """Compute test coverage levels for a single package.

    Returns a dict mapping each coverage level to True/False.
    """
    result = {level: False for level in _COVERAGE_LEVELS}

    try:
        spec = get_spec(name)
        exp = spec.get("expected", {})
    except Exception:
        # Not in catalog at all
        if name in _load_dedicated_packages():
            result["DED"] = True
        return result

    has_exports = bool(exp.get("export_names"))

    # All catalog packages get basic structural tests
    result["R0:idx"] = True
    result["R0:srch"] = True
    result["R4:land"] = True

    if has_exports:
        result["R0:ref"] = True
        result["R1:title"] = True
        result["R1:badge"] = True
        result["R1:sig"] = True
        result["R2:pmatch"] = True
        result["R4:refidx"] = True

    if exp.get("nodoc_items"):
        result["R0:nodoc"] = True
    if exp.get("big_class_name"):
        result["R0:bigcl"] = True
    if exp.get("user_guide_files"):
        result["R0:ug"] = True
    if any(
        exp.get(k)
        for k in (
            "has_license_page",
            "has_citation_page",
            "has_contributing_page",
            "has_code_of_conduct_page",
        )
    ):
        result["R0:supp"] = True
    if exp.get("section_titles"):
        result["R4:sechdg"] = True
        result["R4:sbsec"] = True

    parser = exp.get("detected_parser", "numpy")
    if has_exports and name != "gdtest_nodocs" and parser in ("numpy", "google", "sphinx"):
        result["R1:desc"] = True
    if has_exports and name != "gdtest_nodocs":
        result["R2:param"] = True
        result["R2:ret"] = True

    # Sidebar check
    ref = RENDERED_DIR / name / "great-docs" / "_site" / "reference"
    if ref.exists() and any(f.name != "index.html" for f in ref.glob("*.html")):
        result["R4:sbar"] = True

    # Heading check (first 20 packages by catalog order)
    try:
        if ALL_PACKAGES.index(name) < 20:
            result["R4:hdg"] = True
    except ValueError:
        pass

    if name in _load_dedicated_packages():
        result["DED"] = True

    return result


def coverage_score(name: str) -> int:
    """Return the test coverage score (0–21) for a package."""
    return sum(_compute_coverage(name).values())


def _coverage_badge_html(score: int) -> str:
    """Return an HTML badge for a test coverage score."""
    max_score = len(_COVERAGE_LEVELS)
    pct = score / max_score
    if pct >= 0.7:
        color = "#a6e3a1"  # green
    elif pct >= 0.4:
        color = "#f9e2af"  # yellow
    else:
        color = "#f38ba8"  # red
    return (
        f'<span style="display:inline-block;padding:1px 6px;margin:1px;'
        f"border-radius:3px;font-size:10px;font-weight:600;"
        f"background:{color}22;color:{color};border:1px solid {color}40;"
        f'font-family:&quot;SF Mono&quot;,monospace;"'
        f' title="Test coverage: {score}/{max_score} levels">'
        f"\U0001f9ea {score}/{max_score}</span>"
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _spec_file_exists(name: str) -> bool:
    """Check whether the spec module exists on disk for *name*."""
    return (_THIS_DIR / "synthetic" / "specs" / f"{name}.py").exists()


# ── Build pipeline ───────────────────────────────────────────────────────────


def build_package(name: str) -> dict:
    """
    Build a single synthetic package site.

    Returns a result dict with status info.
    """
    spec = get_spec(name)
    pkg_build_dir = RENDERED_DIR / name
    site_dir = pkg_build_dir / "great-docs" / "_site"

    _common: dict = {
        "name": name,
        "description": spec.get("description", ""),
        "long_description": PACKAGE_DESCRIPTIONS.get(name, ""),
        "dimensions": spec.get("dimensions", []),
    }

    # Clean and regenerate from scratch
    if pkg_build_dir.exists():
        shutil.rmtree(pkg_build_dir)

    # Generate package files
    pkg_dir = generate_package(spec, RENDERED_DIR)

    # Enrich README.md with the long description from the catalog so it
    # appears on the landing page of the built site.
    long_desc = PACKAGE_DESCRIPTIONS.get(name, "")
    if long_desc:
        readme = pkg_dir / "README.md"
        if readme.exists():
            original = readme.read_text(encoding="utf-8")
            readme.write_text(
                original.rstrip() + "\n\n" + long_desc + "\n",
                encoding="utf-8",
            )

    # For packages without pyproject.toml (e.g., setup.cfg-only), create a
    # minimal pyproject.toml as a "root barrier" so that _find_package_root()
    # doesn't walk up into the great-docs repo itself.
    pyproject = pkg_dir / "pyproject.toml"
    if not pyproject.exists():
        detected_name = spec.get("expected", {}).get("detected_name", name)
        pyproject.write_text(
            f'[project]\nname = "{detected_name}"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )

    # Add to sys.path for griffe
    if str(pkg_dir) not in sys.path:
        sys.path.insert(0, str(pkg_dir))
    for subdir in ("src", "python", "lib"):
        sub = pkg_dir / subdir
        if sub.is_dir() and str(sub) not in sys.path:
            sys.path.insert(0, str(sub))

    # Run great-docs init + build using subprocess with the installed CLI
    great_docs_cli = str(Path(sys.executable).parent / "great-docs")
    env = os.environ.copy()
    pythonpath_parts = [str(pkg_dir)]
    for subdir in ("src", "python", "lib"):
        sub = pkg_dir / subdir
        if sub.is_dir():
            pythonpath_parts.append(str(sub))
    existing = env.get("PYTHONPATH", "")
    if existing:
        pythonpath_parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    # Prepare log file
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"{name}.log"
    log_lines: list[str] = []
    log_lines.append(f"{'=' * 70}")
    log_lines.append(f"Package: {name}")
    log_lines.append(f"Build dir: {pkg_dir}")
    log_lines.append(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log_lines.append(f"{'=' * 70}")

    try:
        # Init: only run when no great-docs.yml exists yet (specs that
        # provide their own config already have it written by
        # generate_package).  Running init on a pre-configured package
        # would overwrite the spec's custom settings.
        has_config = (pkg_dir / "great-docs.yml").exists()

        if not has_config:
            log_lines.append("\n--- great-docs init ---")
            init_result = subprocess.run(
                [great_docs_cli, "init", "--force", "--project-path", str(pkg_dir)],
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            log_lines.append(f"exit code: {init_result.returncode}")
            if init_result.stdout:
                log_lines.append(f"stdout:\n{init_result.stdout}")
            if init_result.stderr:
                log_lines.append(f"stderr:\n{init_result.stderr}")

            if init_result.returncode != 0:
                log_lines.append("\nRESULT: init_failed")
                log_path.write_text("\n".join(log_lines), encoding="utf-8")
                return {
                    **_common,
                    "status": "init_failed",
                    "error": init_result.stderr or init_result.stdout,
                    "log": str(log_path),
                }
        else:
            log_lines.append("\n--- great-docs init SKIPPED (config exists) ---")

        # Build
        log_lines.append("\n--- great-docs build ---")
        build_result = subprocess.run(
            [great_docs_cli, "build", "--project-path", str(pkg_dir)],
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        log_lines.append(f"exit code: {build_result.returncode}")
        if build_result.stdout:
            log_lines.append(f"stdout:\n{build_result.stdout}")
        if build_result.stderr:
            log_lines.append(f"stderr:\n{build_result.stderr}")

        if build_result.returncode != 0:
            log_lines.append("\nRESULT: build_failed")
            log_path.write_text("\n".join(log_lines), encoding="utf-8")
            return {
                **_common,
                "status": "build_failed",
                "error": build_result.stderr or build_result.stdout,
                "log": str(log_path),
            }

        # ----------------------------------------------------------
        # Enrich the rendered landing page (_site/index.html) AFTER
        # build. The build step regenerates index.qmd, so we must
        # inject directly into the final HTML output.
        # ----------------------------------------------------------
        site_index = site_dir / "index.html"
        gd_yml = pkg_dir / "great-docs.yml"
        if site_index.exists():
            extras: list[str] = []

            # Interactive file tree viewer
            try:
                tree_html = _build_file_tree_html(
                    spec,
                    config_path=gd_yml,
                )
                extras.append(
                    '<details style="margin-top:1em">\n'
                    '<summary style="cursor:pointer;font-weight:600;'
                    'font-size:14px">Source files</summary>\n'
                    f"{_FILE_TREE_CSS}\n"
                    f"{tree_html}\n"
                    "</details>\n"
                )
            except Exception:
                pass  # non-fatal

            if extras:
                extras_block = "\n".join(extras)
                site_html = site_index.read_text(encoding="utf-8")
                site_html = site_html.replace(
                    "</main>",
                    f"{extras_block}\n</main>",
                    1,
                )
                site_index.write_text(site_html, encoding="utf-8")

        log_lines.append("\nRESULT: ok")
        log_path.write_text("\n".join(log_lines), encoding="utf-8")
        return {
            **_common,
            "status": "ok",
            "site_dir": str(site_dir),
            "log": str(log_path),
        }

    except subprocess.TimeoutExpired:
        log_lines.append("\nRESULT: timeout")
        log_path.write_text("\n".join(log_lines), encoding="utf-8")
        return {**_common, "status": "timeout", "log": str(log_path)}
    except Exception as e:
        log_lines.append(f"\nRESULT: error\n{e}")
        log_path.write_text("\n".join(log_lines), encoding="utf-8")
        return {**_common, "status": "error", "error": str(e), "log": str(log_path)}


def build_all(
    packages: list[str] | None = None,
    *,
    run_id: str | None = None,
    state: dict | None = None,
    skip_ok: bool = False,
) -> list[dict]:
    """Build all (or selected) synthetic packages.

    When *run_id* and *state* are supplied each result is recorded into the
    state dict (caller is responsible for saving to disk).

    When *skip_ok* is ``True``, packages whose status in *state* is already
    ``"ok"`` are skipped. This lets an interrupted full build resume quickly.
    """
    names = packages or ALL_PACKAGES
    results = []

    # Filter to specs that exist on disk
    available = []
    for name in names:
        if _spec_file_exists(name):
            available.append(name)
        else:
            print(f"  SKIP {name} (no spec file)")

    total = len(available)
    print(f"\n{'=' * 70}")
    print(f"  Building {total} synthetic package sites")
    print(f"{'=' * 70}\n")

    skipped = 0
    for i, name in enumerate(available, 1):
        # Resume support: skip packages already built successfully
        if skip_ok and state is not None:
            pkg_state = state.get("packages", {}).get(name, {})
            if pkg_state.get("status") == "ok":
                print(f"[{i:3d}/{total}] {name} ... SKIP (already ok)")
                # Advance run_id so this package isn't marked stale
                if run_id is not None:
                    pkg_state["run_id"] = run_id
                skipped += 1
                continue

        print(f"[{i:3d}/{total}] {name} ... ", end="", flush=True)
        t0 = time.monotonic()
        result = build_package(name)
        elapsed = time.monotonic() - t0
        status = result["status"]
        result["elapsed_s"] = round(elapsed, 1)

        if status == "ok":
            print(f"OK ({elapsed:.1f}s)")
        else:
            print(f"FAILED ({status})")
            if "error" in result:
                for line in result["error"].strip().splitlines()[:3]:
                    print(f"         {line}")

        # Record into state
        if state is not None and run_id is not None:
            record_build(
                state,
                name,
                run_id=run_id,
                status=status,
                elapsed=elapsed,
                error=result.get("error"),
            )

        results.append(result)

    logged = [r for r in results if "log" in r]
    if logged:
        print(f"\n  Build logs saved to: {LOGS_DIR}/")
        print(f"  ({len(logged)} log files written)")
    if skipped:
        print(f"  ({skipped} packages skipped — already ok)")

    return results


# ── Nav bar injection ────────────────────────────────────────────────────────


def _dimension_badges(dims: list[str]) -> str:
    """Generate HTML badge spans for dimension codes."""
    badges = []
    for code in dims:
        meta = DIMENSIONS.get(code, {})
        axis = meta.get("axis", "")
        label = meta.get("label", code)
        color = AXIS_COLORS.get(axis, "#6b7280")
        badges.append(
            f'<span style="display:inline-block;padding:1px 6px;margin:1px;'
            f"border-radius:3px;font-size:11px;font-weight:500;"
            f"background:{color}18;color:{color};border:1px solid {color}40;"
            f'"title="{html.escape(label)}">{html.escape(code)}</span>'
        )
    return " ".join(badges)


# ── Hub navigation categories ────────────────────────────────────────────────

CATEGORIES = {
    # Suite A: Layout & structure (001–100)
    "Docstrings (001–005)": (0, 5),
    "Layouts (006–013)": (5, 13),
    "Exports (014–017)": (13, 17),
    "Object Types (018–027)": (17, 27),
    "Directives (028–032)": (27, 32),
    "User Guide (033–038)": (32, 38),
    "Landing Pages (039–043)": (38, 43),
    "Extras & Config (044–050)": (43, 50),
    "Cross-Dimension (051–065)": (50, 65),
    "API Patterns (066–077)": (65, 77),
    "Scale & Stress (078–082)": (77, 82),
    "Build Systems (083–088)": (82, 88),
    "Edge Cases (089–095)": (88, 95),
    "Config Matrix (096–100)": (95, 100),
    # Suite B: Config & docstring richness (101–200)
    "Config Options (101–125)": (100, 125),
    "Docstring Richness (126–150)": (125, 150),
    "UG Variations (151–165)": (150, 165),
    "Custom Sections (166–175)": (165, 175),
    "Reference Config (176–185)": (175, 185),
    "Site Theming (186–195)": (185, 195),
    "Stress Tests (196–200)": (195, 200),
}


def _build_nav_html(
    results: list[dict],
    current_name: str,
    hub_prefix: str = "..",
    state: dict | None = None,
) -> str:
    """Build the top navigation bar HTML to inject into every page."""

    categories: dict[str, list[dict]] = {k: [] for k in CATEGORIES}
    cat_keys = list(categories.keys())
    cat_ranges = list(CATEGORIES.values())

    for r in results:
        name = r["name"]
        idx = ALL_PACKAGES.index(name) if name in ALL_PACKAGES else -1
        placed = False
        for ci, (lo, hi) in enumerate(cat_ranges):
            if lo <= idx < hi:
                categories[cat_keys[ci]].append(r)
                placed = True
                break
        if not placed:
            categories[cat_keys[-1]].append(r)

    # Build dropdown items
    dropdown_items = []
    for cat_name, cat_results in categories.items():
        if not cat_results:
            continue
        dropdown_items.append(f'<div class="gd-nav-category">{html.escape(cat_name)}</div>')
        for r in cat_results:
            name = r["name"]
            status = r["status"]
            is_current = name == current_name
            stale = is_stale(state, name) if state else False
            num = ALL_PACKAGES.index(name) + 1 if name in ALL_PACKAGES else 0
            desc = r.get("description", "")

            stale_badge = '<span class="gd-nav-badge-stale">STALE</span>' if stale else ""

            if status == "ok":
                href = f"{hub_prefix}/{name}/index.html"
                cls = "gd-nav-item" + (" gd-nav-current" if is_current else "")
                icon = "●" if is_current else ""
                dropdown_items.append(
                    f'<a href="{href}" class="{cls}" title="{html.escape(desc)}">'
                    f'<span class="gd-nav-num">#{num:03d}</span> '
                    f"{html.escape(name)}"
                    f"{'<span class=gd-nav-dot>' + icon + '</span>' if icon else ''}"
                    f"{stale_badge}"
                    f"</a>"
                )
            else:
                dropdown_items.append(
                    f'<div class="gd-nav-item gd-nav-disabled" title="{html.escape(status)}">'
                    f'<span class="gd-nav-num">#{num:03d}</span> '
                    f"{html.escape(name)} "
                    f'<span class="gd-nav-badge-fail">FAIL</span>'
                    f"{stale_badge}"
                    f"</div>"
                )

    dropdown_html = "\n".join(dropdown_items)
    current_num = ALL_PACKAGES.index(current_name) + 1 if current_name in ALL_PACKAGES else 0
    ok_count = sum(1 for r in results if r["status"] == "ok")
    stale_count = sum(1 for r in results if is_stale(state, r["name"])) if state else 0
    current_is_stale = is_stale(state, current_name) if state else False

    # Elapsed build time for the current package
    current_result = next((r for r in results if r["name"] == current_name), None)
    elapsed_s = current_result.get("elapsed_s") if current_result else None
    if elapsed_s is not None:
        if elapsed_s >= 60:
            mins = int(elapsed_s // 60)
            secs = elapsed_s % 60
            elapsed_str = f"{mins}m\u2009{secs:.0f}s"
        else:
            elapsed_str = f"{elapsed_s:.1f}s"
        elapsed_html = f'<span class="gd-nav-elapsed">\u23f1 {elapsed_str}</span>'
    else:
        elapsed_html = ""

    # Test coverage score for the current package
    cov = coverage_score(current_name)
    max_cov = len(_COVERAGE_LEVELS)
    cov_pct = cov / max_cov
    cov_color = "#a6e3a1" if cov_pct >= 0.7 else "#f9e2af" if cov_pct >= 0.4 else "#f38ba8"
    coverage_html = (
        f'<span class="gd-nav-coverage" style="color:{cov_color}"'
        f' title="Test coverage: {cov}/{max_cov} levels">'
        f"\U0001f9ea {cov}/{max_cov}</span>"
    )

    # Prev/Next navigation
    ok_names = [r["name"] for r in results if r["status"] == "ok"]
    if current_name in ok_names:
        ci = ok_names.index(current_name)
        if ci > 0:
            prev_name = ok_names[ci - 1]
            prev_link = (
                f'<a href="{hub_prefix}/{prev_name}/index.html" '
                f'class="gd-nav-arrow" title="{prev_name}">&#9664;</a>'
            )
        else:
            prev_link = '<span class="gd-nav-arrow-disabled" title="First package">&#9664;</span>'
        if ci < len(ok_names) - 1:
            next_name = ok_names[ci + 1]
            next_link = (
                f'<a href="{hub_prefix}/{next_name}/index.html" '
                f'class="gd-nav-arrow" title="{next_name}">&#9654;</a>'
            )
        else:
            next_link = '<span class="gd-nav-arrow-disabled" title="Last package">&#9654;</span>'
    else:
        prev_link = '<span class="gd-nav-arrow-disabled">&#9664;</span>'
        next_link = '<span class="gd-nav-arrow-disabled">&#9654;</span>'

    stale_trigger_badge = (
        ' <span class="gd-nav-badge-stale" style="margin-left:4px">STALE</span>'
        if current_is_stale
        else ""
    )

    stale_stat = (
        f'<span class="gd-nav-stale-stat">{stale_count} stale</span>' if stale_count else ""
    )

    return textwrap.dedent(f"""\
    <!-- GD-NAV-START -->
    <style>
    .gd-topnav {{
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 99999;
        height: 40px;
        background: #1e1e2e;
        color: #cdd6f4;
        display: flex;
        align-items: center;
        padding: 0 16px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
        font-size: 13px;
        box-shadow: 0 1px 3px rgba(0,0,0,.3);
        gap: 8px;
    }}
    .gd-topnav a {{ color: #89b4fa; text-decoration: none; }}
    .gd-topnav a:hover {{ color: #b4d0fb; text-decoration: underline; }}
    .gd-nav-hub {{ font-weight: 600; font-size: 14px; color: #cba6f7; margin-right: 8px; }}
    .gd-nav-hub:hover {{ color: #d8bff8 !important; }}
    .gd-nav-sep {{ color: #585b70; margin: 0 4px; }}
    .gd-nav-dropdown {{ position: relative; }}
    .gd-nav-trigger {{
        background: #313244;
        border: 1px solid #45475a;
        border-radius: 6px;
        color: #cdd6f4;
        padding: 4px 28px 4px 10px;
        font-size: 13px;
        cursor: pointer;
        min-width: 520px;
        text-align: left;
        position: relative;
    }}
    .gd-nav-trigger::after {{
        content: "▾";
        position: absolute;
        right: 10px;
        top: 50%;
        transform: translateY(-50%);
        font-size: 11px;
        color: #a6adc8;
    }}
    .gd-nav-trigger:hover {{ background: #45475a; border-color: #585b70; }}
    .gd-nav-panel {{
        display: none;
        position: absolute;
        top: 100%;
        left: 0;
        margin-top: 4px;
        background: #1e1e2e;
        border: 1px solid #45475a;
        border-radius: 8px;
        width: 400px;
        max-height: 80vh;
        overflow-y: auto;
        box-shadow: 0 8px 24px rgba(0,0,0,.4);
        padding: 6px 0;
    }}
    .gd-nav-dropdown.open .gd-nav-panel {{ display: block; }}
    .gd-nav-category {{
        padding: 6px 12px 3px;
        font-size: 11px;
        font-weight: 600;
        color: #a6adc8;
        text-transform: uppercase;
        letter-spacing: .5px;
        border-top: 1px solid #313244;
        margin-top: 2px;
    }}
    .gd-nav-category:first-child {{ border-top: none; margin-top: 0; }}
    .gd-nav-item {{
        display: flex;
        align-items: center;
        padding: 5px 12px;
        color: #cdd6f4;
        font-size: 12px;
        font-family: "SF Mono", "Fira Code", monospace;
        gap: 6px;
        text-decoration: none !important;
    }}
    a.gd-nav-item:hover {{ background: #313244; color: #cdd6f4; text-decoration: none !important; }}
    .gd-nav-current {{ background: #313244; font-weight: 600; }}
    .gd-nav-disabled {{ opacity: .45; cursor: default; }}
    .gd-nav-num {{ color: #6c7086; font-size: 10px; min-width: 32px; }}
    .gd-nav-dot {{ color: #89b4fa; margin-left: auto; font-size: 10px; }}
    .gd-nav-badge-fail {{
        font-size: 9px;
        background: #f38ba8;
        color: #1e1e2e;
        padding: 0 4px;
        border-radius: 3px;
        font-weight: 700;
        margin-left: auto;
    }}
    .gd-nav-badge-stale {{
        font-size: 9px;
        background: #f9e2af;
        color: #1e1e2e;
        padding: 0 4px;
        border-radius: 3px;
        font-weight: 700;
        margin-left: 4px;
    }}
    .gd-nav-arrow {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        border-radius: 6px;
        background: #313244;
        color: #cdd6f4 !important;
        font-size: 12px;
        text-decoration: none !important;
        border: 1px solid #45475a;
    }}
    .gd-nav-arrow:hover {{ background: #45475a; }}
    .gd-nav-arrow-disabled {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        border-radius: 6px;
        background: #313244;
        color: #585b70 !important;
        font-size: 12px;
        border: 1px solid #45475a;
        cursor: default;
        opacity: 0.4;
    }}
    .gd-nav-stats {{
        margin-left: auto;
        font-size: 11px;
        color: #a6adc8;
        display: flex;
        gap: 8px;
    }}
    .gd-nav-stale-stat {{
        color: #f9e2af;
    }}
    .gd-nav-elapsed {{
        color: #94e2d5;
        font-family: "SF Mono", "Fira Code", monospace;
        font-size: 11px;
    }}
    .gd-nav-coverage {{
        font-family: "SF Mono", "Fira Code", monospace;
        font-size: 11px;
    }}
    body {{ margin-top: 40px !important; }}
    #quarto-header {{ top: 40px !important; }}
    </style>

    <div class="gd-topnav" id="gd-topnav">
        <a href="{hub_prefix}/index.html" class="gd-nav-hub">&#9776; GDG</a>
        <span class="gd-nav-sep">/</span>

        {prev_link}

        <div class="gd-nav-dropdown" id="gd-nav-dropdown">
            <button class="gd-nav-trigger" id="gd-nav-trigger">
                #{current_num:03d} {html.escape(current_name)}{stale_trigger_badge}
            </button>
            <div class="gd-nav-panel" id="gd-nav-panel">
                {dropdown_html}
            </div>
        </div>

        {next_link}

        <span class="gd-nav-stats">
            <span>{ok_count}/{len(results)} built</span>
            {stale_stat}
            {elapsed_html}
            {coverage_html}
        </span>
    </div>

    <script>
    (function() {{
        const dd = document.getElementById('gd-nav-dropdown');
        const trigger = document.getElementById('gd-nav-trigger');
        const panel = document.getElementById('gd-nav-panel');

        trigger.addEventListener('click', function(e) {{
            e.stopPropagation();
            dd.classList.toggle('open');
            if (dd.classList.contains('open')) {{
                const cur = panel.querySelector('.gd-nav-current');
                if (cur) cur.scrollIntoView({{ block: 'center' }});
            }}
        }});

        document.addEventListener('click', function(e) {{
            if (!dd.contains(e.target)) dd.classList.remove('open');
        }});

        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') dd.classList.remove('open');
        }});
    }})();
    </script>
    <!-- GD-NAV-END -->
    """)


def inject_nav_into_html(html_path: Path, nav_html: str) -> None:
    """Inject the navigation bar HTML right after <body...>.

    If the file already contains a `<!-- GD-NAV-START -->` block it is
    stripped first so that re-injection is idempotent.
    """
    content = html_path.read_text(encoding="utf-8")

    # Strip any previously-injected nav block
    content = re.sub(
        r"\n?<!-- GD-NAV-START -->.*?<!-- GD-NAV-END -->\n?",
        "",
        content,
        flags=re.DOTALL,
    )

    body_match = re.search(r"(<body[^>]*>)", content)
    if body_match:
        insert_pos = body_match.end()
        content = content[:insert_pos] + "\n" + nav_html + "\n" + content[insert_pos:]
        html_path.write_text(content, encoding="utf-8")


# ── Hub pages ────────────────────────────────────────────────────────────────


def _create_log_page(name: str, log_path: str | None) -> str:
    """Create an HTML page that displays the build log for a package."""
    log_content = ""
    if log_path and Path(log_path).exists():
        log_content = html.escape(Path(log_path).read_text(encoding="utf-8"))
    else:
        log_content = "(no build log available)"

    return textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Build Log — {html.escape(name)}</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                background: #0d1117; color: #e6edf3; min-height: 100vh;
            }}
            .topbar {{
                background: #1e1e2e; border-bottom: 1px solid #30363d;
                padding: 12px 24px; display: flex; align-items: center; gap: 12px;
            }}
            .topbar a {{ color: #89b4fa; text-decoration: none; font-size: 13px; }}
            .topbar a:hover {{ text-decoration: underline; }}
            .topbar .sep {{ color: #585b70; }}
            .topbar h1 {{ font-size: 15px; font-weight: 600; color: #cba6f7; }}
            .log-container {{ max-width: 1100px; margin: 24px auto; padding: 0 24px; }}
            .log-pre {{
                background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                padding: 20px 24px; font-family: "SF Mono", "Fira Code", monospace;
                font-size: 12px; line-height: 1.5; color: #c9d1d9;
                overflow-x: auto; white-space: pre-wrap; word-wrap: break-word;
            }}
        </style>
    </head>
    <body>
        <div class="topbar">
            <a href="index.html">&larr; GDG</a>
            <span class="sep">/</span>
            <a href="_detail_{name}.html">{html.escape(name)}</a>
            <span class="sep">/</span>
            <h1>Build Log</h1>
        </div>
        <div class="log-container">
            <pre class="log-pre">{log_content}</pre>
        </div>
    </body>
    </html>
    """)


# ── Coverage-level descriptions (for the test coverage page) ──────────────

_COVERAGE_LEVEL_INFO: dict[str, tuple[str, str]] = {
    # level: (test function name, description)
    "R0:idx": ("test_R0_site_index_exists", "Site has an index.html landing page"),
    "R0:srch": ("test_R0_search_json_exists", "Site has a search.json for site search"),
    "R0:ref": ("test_R0_reference_index_exists", "Reference index.html exists"),
    "R0:nodoc": ("test_R0_nodoc_items_excluded", "Items marked %nodoc are excluded"),
    "R0:bigcl": ("test_R0_big_class_has_method_pages", "Big class has separate method pages"),
    "R0:ug": ("test_R0_user_guide_pages_exist", "User guide pages exist"),
    "R0:supp": ("test_R0_supporting_pages_exist", "Supporting pages (license, etc.) exist"),
    "R1:title": ("test_R1_reference_pages_have_title", "Reference pages have an <h1> title"),
    "R1:badge": ("test_R1_reference_pages_have_type_badge", "Reference pages show a type badge"),
    "R1:sig": ("test_R1_function_pages_have_signature", "Function pages show a call signature"),
    "R1:desc": ("test_R1_pages_have_doc_description", "Pages include a docstring description"),
    "R2:param": ("test_R2_parameters_section_renders", "Parameters section is rendered"),
    "R2:pmatch": ("test_R2_parameter_names_match_signature", "Param names match the signature"),
    "R2:ret": ("test_R2_returns_section_renders", "Returns section is rendered"),
    "R4:refidx": ("test_R4_reference_index_lists_exports", "Reference index lists all exports"),
    "R4:sechdg": (
        "test_R4_reference_index_has_section_headings",
        "Reference index has section headings",
    ),
    "R4:sbar": ("test_R4_sidebar_has_reference_section", "Sidebar has a Reference section"),
    "R4:sbsec": ("test_R4_sidebar_lists_section_titles", "Sidebar lists section titles"),
    "R4:land": ("test_R4_landing_page_has_title", "Landing page has a package title"),
    "R4:hdg": ("test_R4_no_broken_heading_attributes", "No broken heading attributes"),
    "DED": ("(dedicated tests)", "Has one or more dedicated/feature-specific tests"),
}


def _create_test_coverage_page(name: str) -> str:
    """Create an HTML page showing test coverage details for a single package."""
    coverage = _compute_coverage(name)
    score = sum(coverage.values())
    max_score = len(_COVERAGE_LEVELS)
    pct = score / max_score
    num = ALL_PACKAGES.index(name) + 1 if name in ALL_PACKAGES else 0

    if pct >= 0.7:
        color = "#a6e3a1"
    elif pct >= 0.4:
        color = "#f9e2af"
    else:
        color = "#f38ba8"

    # Build the coverage table rows
    rows = []
    for level in _COVERAGE_LEVELS:
        covered = coverage.get(level, False)
        info = _COVERAGE_LEVEL_INFO.get(level, (level, ""))
        test_fn, desc = info
        icon = "✅" if covered else "❌"
        row_class = "cov-pass" if covered else "cov-miss"
        rows.append(
            f'<tr class="{row_class}">'
            f"<td>{icon}</td>"
            f'<td class="cov-level">{html.escape(level)}</td>'
            f'<td class="cov-fn">{html.escape(test_fn)}</td>'
            f'<td class="cov-desc">{html.escape(desc)}</td>'
            f"</tr>"
        )
    table_rows = "\n            ".join(rows)
    covered_count = score
    missing_count = max_score - score

    # Suggestions for improving coverage
    suggestions = []
    if not coverage.get("R0:nodoc"):
        suggestions.append(
            "Add <code>nodoc_items</code> to the spec's <code>expected</code> dict "
            "to enable %nodoc exclusion testing."
        )
    if not coverage.get("R0:bigcl"):
        suggestions.append(
            "Add <code>big_class_name</code> and <code>big_class_method_count</code> "
            "to the spec to enable big-class method page testing."
        )
    if not coverage.get("R0:ug"):
        suggestions.append(
            "Add <code>user_guide_files</code> to the spec's <code>expected</code> dict "
            "to enable user guide page existence testing."
        )
    if not coverage.get("R0:supp"):
        suggestions.append(
            "Set <code>has_license_page</code>, <code>has_citation_page</code>, etc. in the "
            "spec to enable supporting page tests."
        )
    if not coverage.get("R4:sechdg"):
        suggestions.append(
            "Add <code>section_titles</code> to the spec's <code>expected</code> dict "
            "to enable section heading and sidebar section tests."
        )
    if not coverage.get("DED"):
        suggestions.append(
            "Write a dedicated test in <code>test_gdg_rendered.py</code> that asserts "
            "a feature specific to this package (e.g., config behavior, badge presence, "
            "decorator handling). See the <code>gdg-add-tests</code> skill."
        )
    if not coverage.get("R4:hdg"):
        suggestions.append(
            "This package is not in the first 20 by catalog order, so heading attribute "
            "checks don't run on it. This is by design (performance)."
        )

    suggestions_html = ""
    if suggestions:
        items = "\n".join(f"<li>{s}</li>" for s in suggestions)
        suggestions_html = f"""\
        <div class="section">
            <h2>How to Improve Coverage</h2>
            <ul class="suggestions">{items}</ul>
        </div>"""

    return textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Test Coverage — {html.escape(name)}</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                background: #0d1117; color: #e6edf3; min-height: 100vh;
            }}
            .topbar {{
                background: #1e1e2e; border-bottom: 1px solid #30363d;
                padding: 12px 24px; display: flex; align-items: center; gap: 12px;
            }}
            .topbar a {{ color: #89b4fa; text-decoration: none; font-size: 13px; }}
            .topbar a:hover {{ text-decoration: underline; }}
            .topbar .sep {{ color: #585b70; }}
            .topbar h1 {{ font-size: 15px; font-weight: 600; color: #cba6f7; }}
            .content {{ max-width: 900px; margin: 32px auto; padding: 0 24px; }}
            .score-header {{
                display: flex; align-items: center; gap: 16px;
                margin-bottom: 24px; padding: 16px 20px;
                background: #161b22; border: 1px solid #30363d; border-radius: 8px;
            }}
            .score-num {{
                font-size: 36px; font-weight: 800; color: {color};
                font-family: "SF Mono", monospace;
            }}
            .score-detail {{ font-size: 14px; color: #a6adc8; }}
            .score-bar {{
                height: 8px; background: #21262d; border-radius: 4px;
                margin-top: 8px; overflow: hidden; width: 200px;
            }}
            .score-fill {{
                height: 100%; background: {color}; border-radius: 4px;
                width: {pct * 100:.0f}%;
            }}
            .section {{ margin-bottom: 28px; }}
            .section h2 {{
                font-size: 16px; font-weight: 600; color: #cba6f7;
                margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid #30363d;
            }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{
                text-align: left; padding: 8px 10px; font-size: 12px;
                color: #6e7681; border-bottom: 1px solid #30363d; text-transform: uppercase;
            }}
            td {{ padding: 6px 10px; font-size: 13px; border-bottom: 1px solid #161b2280; }}
            .cov-pass td {{ color: #c9d1d9; }}
            .cov-miss td {{ color: #6e7681; }}
            .cov-level {{ font-family: "SF Mono", monospace; font-weight: 600; }}
            .cov-fn {{ font-family: "SF Mono", monospace; font-size: 11px; color: #89b4fa; }}
            .cov-miss .cov-fn {{ color: #484e58; }}
            .cov-desc {{ max-width: 300px; }}
            .counter {{ display: flex; gap: 16px; margin-bottom: 16px; }}
            .counter-item {{
                padding: 4px 12px; border-radius: 4px; font-size: 13px; font-weight: 600;
            }}
            .counter-pass {{ background: #a6e3a122; color: #a6e3a1; border: 1px solid #a6e3a140; }}
            .counter-miss {{ background: #f38ba822; color: #f38ba8; border: 1px solid #f38ba840; }}
            .suggestions {{ list-style: none; }}
            .suggestions li {{
                padding: 8px 12px; margin-bottom: 6px; font-size: 13px;
                background: #161b22; border: 1px solid #30363d; border-radius: 6px;
                color: #c9d1d9; line-height: 1.5;
            }}
            .suggestions code {{
                background: #21262d; padding: 1px 5px; border-radius: 3px;
                font-family: "SF Mono", monospace; font-size: 11px; color: #f9e2af;
            }}
        </style>
    </head>
    <body>
        <div class="topbar">
            <a href="index.html">&larr; GDG</a>
            <span class="sep">/</span>
            <a href="_detail_{name}.html">{html.escape(name)}</a>
            <span class="sep">/</span>
            <h1>Test Coverage</h1>
        </div>
        <div class="content">
            <div class="score-header">
                <div>
                    <div class="score-num">{score}/{max_score}</div>
                    <div class="score-bar"><div class="score-fill"></div></div>
                </div>
                <div class="score-detail">
                    <strong>#{num:03d} {html.escape(name)}</strong><br>
                    {covered_count} coverage levels hit, {missing_count} missing
                </div>
            </div>

            <div class="section">
                <h2>Coverage Levels</h2>
                <div class="counter">
                    <span class="counter-item counter-pass">✅ {covered_count} covered</span>
                    <span class="counter-item counter-miss">❌ {missing_count} missing</span>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th></th><th>Level</th><th>Test</th><th>Description</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>

            {suggestions_html}
        </div>
    </body>
    </html>
    """)


def _create_test_coverage_summary_page(results: list[dict]) -> str:
    """Create an HTML page showing test coverage summary for all packages."""
    # Build per-package data
    pkg_data = []
    for r in results:
        name = r["name"]
        cov = _compute_coverage(name)
        score = sum(cov.values())
        pkg_data.append(
            {
                "name": name,
                "score": score,
                "coverage": cov,
                "status": r["status"],
            }
        )

    max_score = len(_COVERAGE_LEVELS)
    total_pkgs = len(pkg_data)
    avg_score = sum(p["score"] for p in pkg_data) / max(total_pkgs, 1)
    full_cov = sum(1 for p in pkg_data if p["score"] == max_score)
    zero_cov = sum(1 for p in pkg_data if p["score"] == 0)
    with_ded = sum(1 for p in pkg_data if p["coverage"].get("DED"))

    # Per-level stats
    level_rows = []
    for level in _COVERAGE_LEVELS:
        info = _COVERAGE_LEVEL_INFO.get(level, (level, ""))
        test_fn, desc = info
        count = sum(1 for p in pkg_data if p["coverage"].get(level))
        pct = count / max(total_pkgs, 1) * 100
        bar_w = pct
        level_rows.append(
            f"<tr>"
            f'<td class="lvl-code">{html.escape(level)}</td>'
            f'<td class="lvl-fn">{html.escape(test_fn)}</td>'
            f"<td>{count}/{total_pkgs}</td>"
            f'<td><div class="lvl-bar"><div class="lvl-fill" style="width:{bar_w:.0f}%"></div>'
            f"</div></td>"
            f"<td>{pct:.0f}%</td>"
            f"</tr>"
        )
    level_table = "\n            ".join(level_rows)

    # Per-package rows sorted by score ascending (worst first)
    pkg_data_sorted = sorted(pkg_data, key=lambda p: (p["score"], p["name"]))
    pkg_rows = []
    for p in pkg_data_sorted:
        name = p["name"]
        score = p["score"]
        pct = score / max_score
        if pct >= 0.7:
            color = "#a6e3a1"
        elif pct >= 0.4:
            color = "#f9e2af"
        else:
            color = "#f38ba8"
        num = ALL_PACKAGES.index(name) + 1 if name in ALL_PACKAGES else 0
        ded_icon = "✓" if p["coverage"].get("DED") else ""

        # Level dots
        dots = []
        for level in _COVERAGE_LEVELS:
            if p["coverage"].get(level):
                dots.append('<span class="dot dot-pass">●</span>')
            else:
                dots.append('<span class="dot dot-miss">·</span>')
        dots_html = "".join(dots)

        pkg_rows.append(
            f"<tr>"
            f'<td class="pkg-num">#{num:03d}</td>'
            f'<td class="pkg-lnk"><a href="_tests_{name}.html">{html.escape(name)}</a></td>'
            f'<td style="color:{color};font-weight:700;font-family:SF Mono,monospace">'
            f"{score}/{max_score}</td>"
            f'<td class="dot-row">{dots_html}</td>'
            f'<td class="ded-icon">{ded_icon}</td>'
            f"</tr>"
        )
    pkg_table = "\n            ".join(pkg_rows)

    # Score distribution histogram
    from collections import Counter

    score_dist = Counter(p["score"] for p in pkg_data)
    hist_max = max(score_dist.values()) if score_dist else 1
    hist_bars = []
    for s in range(max_score + 1):
        cnt = score_dist.get(s, 0)
        bar_h = cnt / hist_max * 100 if cnt > 0 else 0
        if s / max_score >= 0.7:
            color = "#a6e3a1"
        elif s / max_score >= 0.4:
            color = "#f9e2af"
        else:
            color = "#f38ba8"
        cnt_label = f'<div class="hist-cnt">{cnt}</div>' if cnt > 0 else ""
        hist_bars.append(
            f'<div class="hist-col" title="Score {s}: {cnt} packages">'
            f"{cnt_label}"
            f'<div class="hist-bar-area">'
            f'<div class="hist-bar" style="height:{bar_h:.0f}%;background:{color}"></div>'
            f"</div>"
            f'<div class="hist-label">{s}</div>'
            f"</div>"
        )
    hist_html = "\n            ".join(hist_bars)

    return textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Test Coverage Summary — GDG</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                background: #0d1117; color: #e6edf3; min-height: 100vh;
            }}
            .topbar {{
                background: #1e1e2e; border-bottom: 1px solid #30363d;
                padding: 12px 24px; display: flex; align-items: center; gap: 12px;
            }}
            .topbar a {{ color: #89b4fa; text-decoration: none; font-size: 13px; }}
            .topbar a:hover {{ text-decoration: underline; }}
            .topbar h1 {{ font-size: 15px; font-weight: 600; color: #cba6f7; }}
            .content {{ max-width: 1100px; margin: 32px auto; padding: 0 24px; }}
            .summary-header {{
                display: flex; gap: 20px; flex-wrap: wrap;
                margin-bottom: 28px;
            }}
            .sum-card {{
                background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                padding: 16px 24px; min-width: 140px; text-align: center;
            }}
            .sum-num {{ font-size: 28px; font-weight: 800; font-family: "SF Mono", monospace; }}
            .sum-label {{ font-size: 12px; color: #6e7681; margin-top: 4px; text-transform: uppercase; }}
            .section {{ margin-bottom: 32px; }}
            .section h2 {{
                font-size: 18px; font-weight: 600; color: #cba6f7;
                margin-bottom: 14px; padding-bottom: 6px; border-bottom: 1px solid #30363d;
            }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{
                text-align: left; padding: 8px 10px; font-size: 11px;
                color: #6e7681; border-bottom: 1px solid #30363d; text-transform: uppercase;
            }}
            td {{ padding: 5px 10px; font-size: 13px; border-bottom: 1px solid #161b2280; }}
            .lvl-code {{ font-family: "SF Mono", monospace; font-weight: 600; color: #cba6f7; }}
            .lvl-fn {{ font-family: "SF Mono", monospace; font-size: 11px; color: #6e7681; }}
            .lvl-bar {{
                height: 10px; background: #21262d; border-radius: 3px;
                overflow: hidden; width: 120px; display: inline-block;
            }}
            .lvl-fill {{ height: 100%; background: #89b4fa; border-radius: 3px; }}
            .pkg-num {{ font-family: "SF Mono", monospace; color: #6e7681; font-size: 12px; }}
            .pkg-lnk a {{ color: #58a6ff; text-decoration: none; }}
            .pkg-lnk a:hover {{ text-decoration: underline; }}
            .dot-row {{ font-family: "SF Mono", monospace; letter-spacing: 1px; font-size: 10px; }}
            .dot-pass {{ color: #a6e3a1; }}
            .dot-miss {{ color: #30363d; }}
            .ded-icon {{ color: #a6e3a1; font-weight: 700; text-align: center; }}
            .hist-container {{
                display: flex; align-items: flex-end; gap: 4px;
                padding: 0 4px;
            }}
            .hist-col {{ display: flex; flex-direction: column; align-items: center; flex: 1; justify-content: flex-end; }}
            .hist-bar-area {{ height: 100px; width: 100%; display: flex; align-items: flex-end; }}
            .hist-bar {{ width: 100%; min-width: 8px; border-radius: 3px 3px 0 0; transition: height .3s; }}
            .hist-cnt {{ font-size: 10px; color: #ffffff; margin-bottom: 2px; font-family: "SF Mono", monospace; font-weight: 600; }}
            .hist-label {{ font-size: 10px; color: #ffffff; margin-top: 4px; font-family: "SF Mono", monospace; }}
        </style>
    </head>
    <body>
        <div class="topbar">
            <a href="index.html">&larr; GDG</a>
            <span class="sep">|</span>
            <h1>\U0001f9ea Test Coverage Summary</h1>
        </div>
        <div class="content">
            <div class="summary-header">
                <div class="sum-card">
                    <div class="sum-num" style="color:#cdd6f4">{total_pkgs}</div>
                    <div class="sum-label">Packages</div>
                </div>
                <div class="sum-card">
                    <div class="sum-num" style="color:#89b4fa">{avg_score:.1f}/{max_score}</div>
                    <div class="sum-label">Avg Score</div>
                </div>
                <div class="sum-card">
                    <div class="sum-num" style="color:#a6e3a1">{with_ded}</div>
                    <div class="sum-label">With Dedicated Tests</div>
                </div>
                <div class="sum-card">
                    <div class="sum-num" style="color:#a6e3a1">{full_cov}</div>
                    <div class="sum-label">Full Coverage</div>
                </div>
                <div class="sum-card">
                    <div class="sum-num" style="color:#f38ba8">{zero_cov}</div>
                    <div class="sum-label">Zero Coverage</div>
                </div>
            </div>

            <div class="section">
                <h2>Score Distribution</h2>
                <div class="hist-container">
                    {hist_html}
                </div>
            </div>

            <div class="section">
                <h2>Coverage by Test Level</h2>
                <table>
                    <thead><tr>
                        <th>Level</th><th>Test</th><th>Packages</th><th>Bar</th><th>%</th>
                    </tr></thead>
                    <tbody>
                        {level_table}
                    </tbody>
                </table>
            </div>

            <div class="section">
                <h2>Per-Package Coverage (sorted by score)</h2>
                <table>
                    <thead><tr>
                        <th>#</th><th>Package</th><th>Score</th><th>Levels</th><th>DED</th>
                    </tr></thead>
                    <tbody>
                        {pkg_table}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """)


# ── File-tree CSS (shared between landing pages and detail pages) ─────────

_FILE_TREE_CSS = """\
<style>
.file-tree { font-family: "SF Mono", "Fira Code", monospace; font-size: 12px; padding-top: 7px; }
.file-tree details { margin-left: 8px; }
.file-tree > details, .file-tree > .tree-file { margin-left: 0; }
.file-tree summary {
    cursor: pointer; border-radius: 4px;
    color: #c9d1d9; list-style: none; user-select: none;
    padding: 0; margin: 0; line-height: 1.4;
}
.file-tree summary::-webkit-details-marker { display: none; }
.file-tree summary::before {
    content: "▸ "; color: #6e7681; font-size: 10px; margin-right: 2px;
}
.file-tree details[open] > summary::before { content: "▾ "; }
.file-tree summary:hover { background: #161b22; }
.tree-icon { margin-right: 4px; font-size: 13px; }
.tree-dir > summary { color: #79c0ff; }
.tree-file > summary { color: #c9d1d9; }
.tree-children { border-left: 1px solid #21262d; margin-left: 9px; padding-left: 4px; }
.tree-code {
    background: #161b22; border: 1px solid #30363d; border-radius: 6px;
    padding: 12px 16px; margin: 4px 0 8px 0; font-size: 11px;
    line-height: 1.5; color: #c9d1d9; overflow-x: auto;
    white-space: pre-wrap; word-wrap: break-word; max-height: 500px;
}
</style>"""


def _build_file_tree_html(spec: dict, config_path: Path | None = None) -> str:
    """Build an interactive file-tree viewer from a package spec.

    Returns an HTML fragment with `<details>` elements for progressive
    disclosure of directory structure and file contents.

    Parameters
    ----------
    spec
        The package spec dict.
    config_path
        Optional path to the actual `great-docs.yml` on disk. If provided
        and the file exists, its contents are used (capturing any defaults
        that `great-docs init` created). Falls back to the spec's `config` dict.
    """
    all_files: dict[str, str] = {}

    # Source files from the spec
    for path, content in spec.get("files", {}).items():
        all_files[path] = textwrap.dedent(content)

    # great-docs.yml: prefer the on-disk version (includes init defaults)
    if config_path and config_path.exists():
        all_files["great-docs.yml"] = config_path.read_text(encoding="utf-8")
    elif "config" in spec:
        all_files["great-docs.yml"] = yaml.dump(
            spec["config"], default_flow_style=False, sort_keys=False
        )

    if not all_files:
        return "<p>No source files in spec.</p>"

    # Build a nested tree structure: each dict key is a segment name,
    # leaf values are file-content strings, branch values are sub-dicts.
    tree: dict = {}
    for path in sorted(all_files.keys()):
        parts = path.split("/")
        node = tree
        for part in parts[:-1]:
            if part not in node or not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = all_files[path]

    # Language hint for syntax highlighting (cosmetic class)
    ext_lang = {
        "py": "python",
        "yml": "yaml",
        "yaml": "yaml",
        "toml": "toml",
        "md": "markdown",
        "cfg": "ini",
        "txt": "text",
        "json": "json",
        "js": "javascript",
        "css": "css",
        "html": "html",
        "qmd": "quarto",
    }

    def _render(name: str, value, depth: int = 0) -> str:
        indent = "  " * depth
        if isinstance(value, dict):
            children = "\n".join(
                _render(k, v, depth + 1)
                for k, v in sorted(
                    value.items(), key=lambda kv: (not isinstance(kv[1], dict), kv[0])
                )
            )
            return (
                f'{indent}<details class="tree-dir">'
                f'<summary><span class="tree-icon">\U0001f4c1</span> {html.escape(name)}/</summary>'
                f'<div class="tree-children">\n{children}\n{indent}</div>'
                f"</details>"
            )
        else:
            ext = name.rsplit(".", 1)[-1] if "." in name else ""
            lang = ext_lang.get(ext, "")
            lang_attr = f' data-lang="{lang}"' if lang else ""
            content = html.escape(str(value).rstrip())
            return (
                f'{indent}<details class="tree-file">'
                f'<summary><span class="tree-icon">\U0001f4c4</span> {html.escape(name)}</summary>'
                f'<pre class="tree-code"{lang_attr}>{content}</pre>'
                f"</details>"
            )

    # Render top-level entries (dirs first, then files)
    items = "\n".join(
        _render(k, v)
        for k, v in sorted(tree.items(), key=lambda kv: (not isinstance(kv[1], dict), kv[0]))
    )
    return f'<div class="file-tree">\n{items}\n</div>'


def _create_detail_page(r: dict, results: list[dict]) -> str:
    """Create a detail/info page for a single package."""
    name = r["name"]
    num = ALL_PACKAGES.index(name) + 1 if name in ALL_PACKAGES else 0
    desc = html.escape(r.get("description", ""))
    long_desc = html.escape(r.get("long_description", ""))
    status = r["status"]
    dims = r.get("dimensions", [])
    badges = _dimension_badges(dims)

    # Build the file tree from the spec
    try:
        spec = get_spec(name)
        file_tree_html = _build_file_tree_html(
            spec,
            config_path=RENDERED_DIR / name / "great-docs.yml",
        )
    except Exception:
        file_tree_html = "<p>Spec not available.</p>"

    if status == "ok":
        status_badge = (
            '<span style="background:#a6e3a1;color:#1e1e2e;padding:2px 8px;'
            'border-radius:4px;font-size:12px;font-weight:600;">OK</span>'
        )
        site_link = (
            f'<a href="{name}/index.html" class="action-btn action-primary">View Site &rarr;</a>'
        )
    else:
        status_badge = (
            f'<span style="background:#f38ba8;color:#1e1e2e;padding:2px 8px;'
            f'border-radius:4px;font-size:12px;font-weight:600;">'
            f"FAILED ({html.escape(status)})</span>"
        )
        site_link = ""

    log_link = f'<a href="_log_{name}.html" class="action-btn action-secondary">Build Log</a>'
    tests_link = f'<a href="_tests_{name}.html" class="action-btn action-secondary">\U0001f9ea Test Coverage</a>'

    error_section = ""
    if "error" in r:
        error_text = html.escape(r["error"][:2000])
        error_section = f"""\
        <div class="section">
            <h2>Error Output</h2>
            <pre class="error-pre">{error_text}</pre>
        </div>"""

    dim_details = []
    for code in dims:
        meta = DIMENSIONS.get(code, {})
        axis = meta.get("axis", "")
        label = meta.get("label", code)
        color = AXIS_COLORS.get(axis, "#6b7280")
        dim_details.append(
            f'<div class="dim-row">'
            f'<span class="dim-code" style="color:{color}">{html.escape(code)}</span>'
            f'<span class="dim-label">{html.escape(label)}</span>'
            f'<span class="dim-axis">{html.escape(axis)}</span>'
            f"</div>"
        )
    dim_html = "\n".join(dim_details) if dim_details else "<p>None</p>"

    return textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{html.escape(name)} — Synthetic Package Details</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                background: #0d1117; color: #e6edf3; min-height: 100vh;
            }}
            .topbar {{
                background: #1e1e2e; border-bottom: 1px solid #30363d;
                padding: 12px 24px; display: flex; align-items: center; gap: 12px;
            }}
            .topbar a {{ color: #89b4fa; text-decoration: none; font-size: 13px; }}
            .topbar a:hover {{ text-decoration: underline; }}
            .topbar .sep {{ color: #585b70; }}
            .topbar h1 {{ font-size: 15px; font-weight: 600; color: #cba6f7; }}
            .content {{ max-width: 800px; margin: 32px auto; padding: 0 24px; }}
            .pkg-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
            .pkg-num {{ font-size: 14px; color: #6e7681; font-family: "SF Mono", monospace; }}
            .pkg-name {{ font-size: 24px; font-weight: 700; font-family: "SF Mono", monospace; color: #58a6ff; }}
            .pkg-short {{ font-size: 15px; color: #a6adc8; margin-bottom: 16px; font-style: italic; }}
            .pkg-long {{ font-size: 14px; color: #c9d1d9; line-height: 1.65; margin-bottom: 24px; }}
            .actions {{ display: flex; gap: 10px; margin-bottom: 28px; }}
            .action-btn {{
                display: inline-block; padding: 8px 18px; border-radius: 6px;
                font-size: 13px; font-weight: 600; text-decoration: none !important;
                transition: all .15s;
            }}
            .action-primary {{ background: #238636; color: #fff !important; border: 1px solid #2ea043; }}
            .action-primary:hover {{ background: #2ea043; }}
            .action-secondary {{ background: #21262d; color: #c9d1d9 !important; border: 1px solid #30363d; }}
            .action-secondary:hover {{ background: #30363d; }}
            .section {{ margin-bottom: 24px; }}
            .section h2 {{
                font-size: 16px; font-weight: 600; color: #cba6f7;
                margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid #30363d;
            }}
            .dim-row {{
                display: flex; gap: 12px; padding: 5px 0; font-size: 13px;
                border-bottom: 1px solid #161b2280;
            }}
            .dim-code {{ font-family: "SF Mono", monospace; font-weight: 600; min-width: 40px; }}
            .dim-label {{ color: #c9d1d9; flex: 1; }}
            .dim-axis {{ color: #6e7681; font-size: 11px; text-transform: uppercase; }}
            .error-pre {{
                background: #1c0d0d; border: 1px solid #f38ba830; border-radius: 6px;
                padding: 14px 18px; font-family: "SF Mono", monospace; font-size: 12px;
                color: #f38ba8; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word;
            }}
            .badges-row {{ line-height: 1.8; }}
            .file-tree {{ font-family: "SF Mono", "Fira Code", monospace; font-size: 12px; }}
            .file-tree details {{ margin-left: 8px; }}
            .file-tree > details, .file-tree > .tree-file {{ margin-left: 0; }}
            .file-tree summary {{
                cursor: pointer; border-radius: 4px;
                color: #c9d1d9; list-style: none; user-select: none;
                padding: 0; margin: 0; line-height: 1.4;
            }}
            .file-tree summary::-webkit-details-marker {{ display: none; }}
            .file-tree summary::before {{
                content: "▸ "; color: #6e7681; font-size: 10px; margin-right: 2px;
            }}
            .file-tree details[open] > summary::before {{ content: "▾ "; }}
            .file-tree summary:hover {{ background: #161b22; }}
            .tree-icon {{ margin-right: 4px; font-size: 13px; }}
            .tree-dir > summary {{ color: #79c0ff; }}
            .tree-file > summary {{ color: #c9d1d9; }}
            .tree-children {{ border-left: 1px solid #21262d; margin-left: 9px; padding-left: 4px; }}
            .tree-code {{
                background: #161b22; border: 1px solid #30363d; border-radius: 6px;
                padding: 12px 16px; margin: 4px 0 8px 0; font-size: 11px;
                line-height: 1.5; color: #c9d1d9; overflow-x: auto;
                white-space: pre-wrap; word-wrap: break-word; max-height: 500px;
            }}
        </style>
    </head>
    <body>
        <div class="topbar">
            <a href="index.html">&larr; GDG</a>
            <span class="sep">/</span>
            <h1>#{num:03d} {html.escape(name)}</h1>
        </div>
        <div class="content">
            <div class="pkg-header">
                <span class="pkg-num">#{num:03d}</span>
                <span class="pkg-name">{html.escape(name)}</span>
                {status_badge}
            </div>
            <div class="pkg-short">{desc}</div>
            <div class="pkg-long">{long_desc}</div>
            <div class="actions">
                {site_link}
                {log_link}
                {tests_link}
            </div>
            {error_section}
            <div class="section">
                <h2>Dimensions</h2>
                <div class="badges-row">{badges}</div>
                <div style="margin-top:12px">{dim_html}</div>
            </div>
            <div class="section">
                <h2>Source Files</h2>
                {file_tree_html}
            </div>
        </div>
    </body>
    </html>
    """)


def create_hub_page(results: list[dict]) -> None:
    """Create the hub index page with cards for each package."""
    HUB_DIR.mkdir(parents=True, exist_ok=True)

    ok_results = [r for r in results if r["status"] == "ok"]
    fail_results = [r for r in results if r["status"] != "ok"]

    cards_html = []
    for r in results:
        name = r["name"]
        num = ALL_PACKAGES.index(name) + 1 if name in ALL_PACKAGES else 0
        desc = html.escape(r.get("description", ""))
        long_desc = html.escape(r.get("long_description", ""))
        dims = r.get("dimensions", [])
        badges = _dimension_badges(dims)
        status = r["status"]

        card_long = long_desc[:140] + "..." if len(long_desc) > 140 else long_desc

        links = (
            f'<div class="card-links">'
            f'<a href="_detail_{name}.html" class="card-link" '
            f'onclick="event.stopPropagation()">Details</a>'
            f'<a href="_log_{name}.html" class="card-link" '
            f'onclick="event.stopPropagation()">Build Log</a>'
            f'<a href="_tests_{name}.html" class="card-link" '
            f'onclick="event.stopPropagation()">Tests</a>'
            f"</div>"
        )

        cov_score = coverage_score(name)
        cov_badge = _coverage_badge_html(cov_score)

        if status == "ok":
            cards_html.append(f"""\
            <div class="card card-ok" data-href="{name}/index.html">
                <div class="card-header">
                    <span class="card-num">#{num:03d}</span>
                    <span class="card-name">{html.escape(name)}</span>
                </div>
                <div class="card-desc">{desc}</div>
                <div class="card-long">{card_long}</div>
                <div class="card-dims">{badges} {cov_badge}</div>
                {links}
            </div>""")
        else:
            error = html.escape(r.get("error", status)[:120])
            cards_html.append(f"""\
            <div class="card card-fail">
                <div class="card-header">
                    <span class="card-num">#{num:03d}</span>
                    <span class="card-name">{html.escape(name)}</span>
                    <span class="card-status">FAILED</span>
                </div>
                <div class="card-desc">{desc}</div>
                <div class="card-long">{card_long}</div>
                <div class="card-error">{error}</div>
                <div class="card-dims">{badges} {cov_badge}</div>
                {links}
            </div>""")

    # Collect all unique axis names for filter buttons
    all_axes = sorted(set(AXIS_COLORS.keys()))
    filter_buttons = ['<button class="filter-btn active" data-filter="all">All</button>']
    axis_labels = {
        "layout": "Layout",
        "exports": "Exports",
        "objects": "Objects",
        "docstrings": "Doc Format",
        "directives": "Directives",
        "user_guide": "User Guide",
        "landing": "Landing",
        "extras": "Extras",
        "config": "Config",
        "docstring": "Doc Richness",
        "sections": "Sections",
        "reference": "Reference",
        "theme": "Theming",
    }
    for axis in all_axes:
        label = axis_labels.get(axis, axis.replace("_", " ").title())
        filter_buttons.append(f'<button class="filter-btn" data-filter="{axis}">{label}</button>')
    filter_buttons.append('<button class="filter-btn" data-filter="failed">Failed</button>')
    filter_html = "\n            ".join(filter_buttons)

    hub_html = textwrap.dedent(f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Great Docs Gauntlet</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
                background: #0d1117; color: #e6edf3; min-height: 100vh;
            }}
            .header {{
                background: linear-gradient(135deg, #1e1e2e 0%, #181825 100%);
                border-bottom: 1px solid #30363d;
                padding: 32px 24px; text-align: center;
            }}
            .header h1 {{ font-size: 28px; font-weight: 700; color: #cba6f7; margin-bottom: 8px; }}
            .header p {{ color: #8b949e; font-size: 15px; max-width: 700px; margin: 0 auto; }}
            .stats {{ display: flex; gap: 24px; justify-content: center; margin-top: 16px; }}
            .stat {{ display: flex; align-items: center; gap: 6px; font-size: 14px; }}
            .stat-num {{ font-size: 22px; font-weight: 700; }}
            .stat-ok .stat-num {{ color: #a6e3a1; }}
            .stat-fail .stat-num {{ color: #f38ba8; }}
            .stat-total .stat-num {{ color: #89b4fa; }}
            .stat-cov {{
                background: #1e3a3a; border: 1px solid #94e2d5; border-radius: 20px;
                padding: 4px 14px; color: #fff; transition: background 0.2s;
            }}
            .stat-cov:hover {{ background: #264d4d; }}
            .stat-cov .stat-num {{ color: #94e2d5; }}
            .stat-cov .chevron {{ margin-left: 2px; font-size: 16px; color: #94e2d5; }}

            .filter-bar {{
                max-width: 1200px; margin: 20px auto 0; padding: 0 24px;
                display: flex; gap: 8px; flex-wrap: wrap;
            }}
            .filter-btn {{
                background: #21262d; border: 1px solid #30363d; border-radius: 20px;
                color: #8b949e; padding: 5px 14px; font-size: 12px;
                cursor: pointer; transition: all .15s;
            }}
            .filter-btn:hover {{ background: #30363d; color: #e6edf3; }}
            .filter-btn.active {{ background: #1f6feb22; border-color: #1f6feb; color: #58a6ff; }}

            .grid {{
                max-width: 1200px; margin: 20px auto; padding: 0 24px 40px;
                display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 12px;
            }}
            .card {{
                background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                padding: 14px 16px; display: flex; flex-direction: column; gap: 6px;
                transition: border-color .15s, box-shadow .15s;
                text-decoration: none !important; color: inherit !important;
            }}
            .card-ok {{ cursor: pointer; }}
            .card-ok:hover {{ border-color: #58a6ff; box-shadow: 0 0 0 1px #58a6ff40; }}
            .card-fail {{ opacity: .65; }}
            .card-header {{ display: flex; align-items: center; gap: 8px; }}
            .card-num {{ font-size: 11px; color: #6e7681; font-family: "SF Mono", monospace; min-width: 32px; }}
            .card-name {{ font-size: 14px; font-weight: 600; font-family: "SF Mono", monospace; color: #58a6ff; }}
            .card-fail .card-name {{ color: #f38ba8; }}
            .card-status {{
                margin-left: auto; font-size: 10px; background: #f38ba8; color: #1e1e2e;
                padding: 1px 6px; border-radius: 3px; font-weight: 700;
            }}
            .card-desc {{ font-size: 12px; color: #8b949e; line-height: 1.4; }}
            .card-long {{ font-size: 12px; color: #6e7681; line-height: 1.45; margin-top: 2px; }}
            .card-error {{
                font-size: 11px; color: #f38ba8; font-family: monospace;
                white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
            }}
            .card-dims {{ margin-top: 4px; line-height: 1.6; }}
            .card-links {{
                display: flex; gap: 12px; margin-top: 6px; padding-top: 6px;
                border-top: 1px solid #21262d;
            }}
            .card-link {{ font-size: 11px; color: #58a6ff !important; text-decoration: none !important; }}
            .card-link:hover {{ text-decoration: underline !important; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Great Docs Gauntlet</h1>
            <p>
                Rendered documentation sites for all {len(results)} synthetic test packages,
                covering layouts, config options, docstring patterns, user guides, and more.
            </p>
            <div class="stats">
                <div class="stat stat-ok"><span class="stat-num">{len(ok_results)}</span> built</div>
                <div class="stat stat-fail"><span class="stat-num">{len(fail_results)}</span> failed</div>
                <div class="stat stat-total"><span class="stat-num">{len(results)}</span> total</div>
                <a href="_tests_summary.html" class="stat stat-cov" style="text-decoration:none;cursor:pointer"><span class="stat-num">{sum(coverage_score(r["name"]) for r in results) // max(len(results), 1)}</span> / 21 avg cov<span class="chevron">&#8250;</span></a>
            </div>
        </div>

        <div class="filter-bar">
            {filter_html}
        </div>

        <div class="grid" id="card-grid">
            {"".join(cards_html)}
        </div>

        <script>
        (function() {{
            const btns = document.querySelectorAll('.filter-btn');
            const cards = document.querySelectorAll('.card');
            const dimData = {json.dumps({r["name"]: r.get("dimensions", []) for r in results})};
            const dimMeta = {json.dumps(DIMENSIONS)};
            const statuses = {json.dumps({r["name"]: r["status"] for r in results})};

            btns.forEach(btn => {{
                btn.addEventListener('click', () => {{
                    btns.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    const filter = btn.dataset.filter;

                    cards.forEach(card => {{
                        const name = card.querySelector('.card-name')?.textContent || '';
                        if (filter === 'all') {{
                            card.style.display = '';
                        }} else if (filter === 'failed') {{
                            card.style.display = (statuses[name] !== 'ok') ? '' : 'none';
                        }} else {{
                            const dims = dimData[name] || [];
                            const match = dims.some(d => {{
                                const meta = dimMeta[d];
                                return meta && meta.axis === filter;
                            }});
                            card.style.display = match ? '' : 'none';
                        }}
                    }});
                }});
            }});

            document.querySelectorAll('.card[data-href]').forEach(card => {{
                card.addEventListener('click', (e) => {{
                    if (e.target.closest('.card-link')) return;
                    window.location.href = card.dataset.href;
                }});
            }});
        }})();
        </script>
    </body>
    </html>
    """)

    (HUB_DIR / "index.html").write_text(hub_html, encoding="utf-8")
    print(f"\n  Hub page: {HUB_DIR / 'index.html'}")


# ── Assemble hub ─────────────────────────────────────────────────────────────


def assemble_hub(
    results: list[dict],
    *,
    state: dict | None = None,
    rebuilt_names: set[str] | None = None,
) -> None:
    """Copy built _site/ dirs into _hub/<name>/ and inject nav bars.

    Parameters
    ----------
    results
        Result dicts for **all** packages (freshly-built + historical).
    state
        Build-state dict, used to mark stale packages in the nav bar.
    rebuilt_names
        When given (selective rebuild), only these packages' `_site/` dirs
        are re-copied. `None` means copy everything (full rebuild).
    """
    print(f"\n{'=' * 70}")
    print("  Assembling hub")
    print(f"{'=' * 70}\n")

    HUB_DIR.mkdir(parents=True, exist_ok=True)

    ok_results = [r for r in results if r["status"] == "ok"]

    # Copy _site/ dirs → GDG/<name>/
    for r in ok_results:
        name = r["name"]
        site_dir = Path(r["site_dir"]) if r.get("site_dir") else None

        # For selective rebuilds, only copy freshly-built packages
        if rebuilt_names is not None and name not in rebuilt_names:
            if (HUB_DIR / name).exists():
                continue  # already present from a previous build
            if site_dir and site_dir.exists():
                pass  # fall through to copy
            else:
                print(f"  SKIP {name} (no _site/ dir)")
                continue

        target = HUB_DIR / name
        if target.exists():
            shutil.rmtree(target)

        if site_dir and site_dir.exists():
            shutil.copytree(site_dir, target)
            print(f"  Copied {name}")

    # Inject nav bar into ALL packages in GDG
    print("\n  Injecting navigation bar ...")
    nav_count = 0
    for r in ok_results:
        name = r["name"]
        target = HUB_DIR / name
        if not target.exists():
            continue

        for html_file in target.rglob("*.html"):
            depth = len(html_file.relative_to(target).parts)
            hub_prefix = "/".join([".."] * depth)
            nav_html = _build_nav_html(results, name, hub_prefix=hub_prefix, state=state)
            inject_nav_into_html(html_file, nav_html)
            nav_count += 1

    print(f"  Injected nav into {nav_count} pages")

    create_hub_page(results)

    # Per-package detail & log pages
    print("\n  Creating detail and log pages ...")
    for r in results:
        name = r["name"]
        log_page = _create_log_page(name, r.get("log"))
        (HUB_DIR / f"_log_{name}.html").write_text(log_page, encoding="utf-8")
        detail_page = _create_detail_page(r, results)
        (HUB_DIR / f"_detail_{name}.html").write_text(detail_page, encoding="utf-8")
        tests_page = _create_test_coverage_page(name)
        (HUB_DIR / f"_tests_{name}.html").write_text(tests_page, encoding="utf-8")
    print(f"  Created {len(results)} detail + log + test coverage pages")

    # Test coverage summary page
    summary_page = _create_test_coverage_summary_page(results)
    (HUB_DIR / "_tests_summary.html").write_text(summary_page, encoding="utf-8")
    print("  Created test coverage summary page")

    # Save results manifest
    manifest = {
        r["name"]: {
            "status": r["status"],
            "description": r.get("description", ""),
            "long_description": r.get("long_description", ""),
            "dimensions": r.get("dimensions", []),
        }
        for r in results
    }
    (HUB_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


# ── Server ───────────────────────────────────────────────────────────────────


def serve(port: int = PORT) -> None:
    """Serve the hub directory with a simple HTTP server."""
    if not HUB_DIR.exists():
        print(f"ERROR: Hub directory not found at {HUB_DIR}")
        print("  Run with --build first.")
        sys.exit(1)

    os.chdir(HUB_DIR)

    handler = http.server.SimpleHTTPRequestHandler
    handler.extensions_map.update(
        {
            ".js": "application/javascript",
            ".css": "text/css",
            ".json": "application/json",
        }
    )

    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.allow_reuse_address = True
        url = f"http://localhost:{port}"
        print(f"\n{'=' * 70}")
        print(f"  Serving synthetic package hub at {url}")
        print("  Press Ctrl+C to stop")
        print(f"{'=' * 70}\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server stopped.")


# ── CLI ──────────────────────────────────────────────────────────────────────


def _result_from_state(name: str, pkg_state: dict) -> dict:
    """Reconstruct a result dict from persisted state + catalog data."""
    spec = get_spec(name)
    site_dir = RENDERED_DIR / name / "great-docs" / "_site"
    status = pkg_state.get("status", "unknown")
    result: dict = {
        "name": name,
        "description": spec.get("description", ""),
        "long_description": PACKAGE_DESCRIPTIONS.get(name, ""),
        "dimensions": spec.get("dimensions", []),
        "status": status,
    }
    if status == "ok" and site_dir.exists():
        result["site_dir"] = str(site_dir)
    err = pkg_state.get("error")
    if err:
        result["error"] = err
    log_path = LOGS_DIR / f"{name}.log"
    if log_path.exists():
        result["log"] = str(log_path)
    elapsed = pkg_state.get("elapsed_s")
    if elapsed is not None:
        result["elapsed_s"] = elapsed
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Render all Great Docs Gauntlet (GDG) package sites and serve via the GDG.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              python render_all.py                     # full build + serve
              python render_all.py --build             # full build only
              python render_all.py --build --skip-ok   # resume interrupted build
              python render_all.py --serve             # serve previously built hub
              python render_all.py --only gdtest_minimal gdtest_github_icon
        """),
    )
    parser.add_argument("--build", action="store_true", help="Build only (don't start server)")
    parser.add_argument("--serve", action="store_true", help="Serve previously built hub only")
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="NAME",
        help="Selective rebuild of these packages",
    )
    parser.add_argument("--port", type=int, default=PORT, help=f"Server port (default: {PORT})")
    parser.add_argument("--no-serve", action="store_true", help="Alias for --build")
    parser.add_argument(
        "--skip-ok",
        action="store_true",
        help="Skip packages already built successfully (resume interrupted build)",
    )
    args = parser.parse_args()

    if args.serve:
        serve(args.port)
        return

    # ── Load / initialise build state ────────────────────────────────────
    state = load_state(STATE_FILE)
    rid = new_run_id()

    if args.only:
        # ── Selective rebuild ────────────────────────────────────────────
        start_selective_run(state, rid)
        fresh_results = build_all(packages=args.only, run_id=rid, state=state)
        save_state(STATE_FILE, state)

        # Merge: fresh results + historical results from state
        rebuilt_set = {r["name"] for r in fresh_results}
        fresh_by_name = {r["name"]: r for r in fresh_results}

        combined: list[dict] = []
        for name in ALL_PACKAGES:
            if name in fresh_by_name:
                combined.append(fresh_by_name[name])
            elif name in state.get("packages", {}):
                combined.append(_result_from_state(name, state["packages"][name]))
            # else: package never built, skip

        assemble_hub(combined, state=state, rebuilt_names=rebuilt_set)

        ok = sum(1 for r in fresh_results if r["status"] == "ok")
        fail = sum(1 for r in fresh_results if r["status"] != "ok")
        stale_n = sum(1 for n in state.get("packages", {}) if is_stale(state, n))
        print(f"\n  Selective rebuild: {ok} OK, {fail} failed")
        print(f"  State: {len(state.get('packages', {}))} tracked, {stale_n} stale")

    else:
        # ── Full rebuild ─────────────────────────────────────────────────
        if args.skip_ok and state.get("packages"):
            # Resume mode: keep existing state, only rebuild non-ok packages
            start_selective_run(state, rid)
            results = build_all(run_id=rid, state=state, skip_ok=True)
            save_state(STATE_FILE, state)

            # Combine fresh results with historical ok results
            built_set = {r["name"] for r in results}
            combined: list[dict] = []
            for name in ALL_PACKAGES:
                if name in built_set:
                    combined.append(next(r for r in results if r["name"] == name))
                elif name in state.get("packages", {}):
                    combined.append(_result_from_state(name, state["packages"][name]))

            assemble_hub(combined, state=state)

            total_ok = sum(1 for r in combined if r["status"] == "ok")
            total_fail = sum(1 for r in combined if r["status"] != "ok")
            freshly_built = len(results)
            skipped_n = len(combined) - freshly_built
            print(f"\n  Summary: {total_ok} OK, {total_fail} failed out of {len(combined)}")
            print(f"  ({skipped_n} skipped, {freshly_built} built)")
        else:
            reset_for_full_rebuild(state, rid)
            results = build_all(run_id=rid, state=state)
            save_state(STATE_FILE, state)

            assemble_hub(results, state=state)

            ok = sum(1 for r in results if r["status"] == "ok")
            fail = sum(1 for r in results if r["status"] != "ok")
            print(f"\n  Summary: {ok} OK, {fail} failed out of {len(results)}")

    print(f"  State saved: {STATE_FILE}")

    if not args.build and not args.no_serve:
        serve(args.port)


if __name__ == "__main__":
    main()
