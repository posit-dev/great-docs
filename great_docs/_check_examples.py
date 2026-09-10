from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable

# Reuse the fence/hashpipe regexes from _mock_code
_EXEC_FENCE_RE = re.compile(r"^```\{python\}\s*$")
_CLOSE_FENCE_RE = re.compile(r"^```\s*$")
_HASHPIPE_RE = re.compile(r"^#\|\s*(\S+?):\s*(.*)$")

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# HTML parsing patterns for Quarto output
_HTML_CELL_SPLIT_RE = re.compile(r'(<div[^>]*class="cell"[^>]*>)')
_HTML_SOURCE_RE = re.compile(
    r'<code class="sourceCode python">(.*?)</code>',
    re.DOTALL,
)
_HTML_ERROR_RE = re.compile(
    r'<div class="cell-output cell-output-error">.*?<pre>(.*?)</pre>',
    re.DOTALL,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Cell:
    index: int
    source: str
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class CellError:
    cell_index: int
    source: str
    error_type: str
    error_message: str
    traceback: str


@dataclass
class PageResult:
    path: str
    status: str  # "pass", "fail", "skip", "error"
    cells_checked: int = 0
    errors: list[CellError] = field(default_factory=list)
    message: str | None = None


@dataclass
class CheckResult:
    pages_checked: int = 0
    pages_passed: int = 0
    pages_failed: int = 0
    pages_skipped: int = 0
    cells_checked: int = 0
    cells_passed: int = 0
    cells_failed: int = 0
    pages: list[PageResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# QMD cell extraction
# ---------------------------------------------------------------------------


def _page_opted_out(text: str) -> bool:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return False
    frontmatter = m.group(1)
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("check-examples:"):
            val = stripped.split(":", 1)[1].strip().lower()
            if val in ("false", "no", "off"):
                return True
    return False


def extract_cells(text: str) -> list[Cell]:
    lines = text.split("\n")
    cells: list[Cell] = []
    cell_index = 0
    i = 0

    while i < len(lines):
        if not _EXEC_FENCE_RE.match(lines[i]):
            i += 1
            continue

        i += 1
        cell_body: list[str] = []
        found_close = False
        while i < len(lines):
            if _CLOSE_FENCE_RE.match(lines[i]):
                found_close = True
                i += 1
                break
            cell_body.append(lines[i])
            i += 1

        if not found_close:
            continue

        options: dict[str, str] = {}
        code_start = 0
        for j, bline in enumerate(cell_body):
            m = _HASHPIPE_RE.match(bline)
            if m:
                options[m.group(1)] = m.group(2).strip()
                code_start = j + 1
            else:
                break

        if options.get("eval", "").lower() in ("false", "no"):
            cell_index += 1
            continue
        if options.get("check", "").lower() in ("false", "no"):
            cell_index += 1
            continue

        source = "\n".join(cell_body[code_start:]).strip()
        if source:
            cells.append(Cell(index=cell_index, source=source, options=options))

        cell_index += 1

    return cells


# ---------------------------------------------------------------------------
# Docstring example extraction
# ---------------------------------------------------------------------------


def extract_docstring_examples(
    project_root: Path,
) -> list[tuple[str, list[Cell]]]:
    try:
        from great_docs.config import Config
    except ImportError:
        return []

    config_path = project_root / "great-docs.yml"
    if not config_path.exists():
        return []

    config = Config(project_root)

    if not config.reference_enabled:
        return []

    reference_sections = config.reference
    if not reference_sections:
        return []

    package_name = _detect_package(project_root)
    if not package_name:
        return []

    try:
        import griffe as gf

        from great_docs._apiref.introspect import make_loader
    except ImportError:
        return []

    loader = make_loader("numpy")
    object_names = _collect_object_names(reference_sections)

    results: list[tuple[str, list[Cell]]] = []

    for obj_name in object_names:
        full_name = f"{package_name}.{obj_name}" if "." not in obj_name else obj_name
        try:
            obj = loader.load(package_name)
            member = _resolve_member(obj, obj_name)
            if member is None:
                continue
        except Exception:
            continue

        if not hasattr(member, "docstring") or member.docstring is None:
            continue

        parsed = member.docstring.parsed
        cells: list[Cell] = []
        cell_idx = 0

        for section in parsed:
            if not isinstance(section, gf.DocstringSectionExamples):
                continue
            for kind, value in section.value:
                if kind.value == "examples" and value.strip():
                    cells.append(Cell(index=cell_idx, source=value.strip()))
                    cell_idx += 1

        if cells:
            results.append((f"docstring:{full_name}", cells))

    return results


def _detect_package(project_root: Path) -> str | None:
    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib  # type: ignore[no-redefine]
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
            name = data.get("project", {}).get("name")
            if name:
                return name.replace("-", "_")
    return None


def _collect_object_names(sections: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for section in sections:
        contents = section.get("contents", [])
        for item in contents:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                if "name" in item:
                    names.append(item["name"])
                elif "contents" in item:
                    names.extend(_collect_object_names([item]))
    return names


def _resolve_member(
    package: Any,
    dotted_name: str,
) -> Any:
    parts = dotted_name.split(".")
    current = package
    for part in parts:
        if hasattr(current, "members") and part in current.members:
            current = current.members[part]
        else:
            return None
    return current


# ---------------------------------------------------------------------------
# Quarto execution
# ---------------------------------------------------------------------------


def _check_quarto_available() -> str | None:
    if shutil.which("quarto") is None:
        return "Quarto is not installed or not on PATH. Install it from https://quarto.org/docs/get-started/"
    try:
        proc = subprocess.run(
            ["quarto", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            return f"Quarto check failed: {proc.stderr.strip()}"
    except Exception as e:
        return f"Could not verify Quarto installation: {e}"
    return None


def _prepare_qmd_for_check(text: str, timeout: int = 30) -> str:
    check_false_re = re.compile(r"^(#\|\s*check:\s*)(?:false|no)\s*$", re.IGNORECASE)

    lines = text.split("\n")
    result_lines: list[str] = []
    for line in lines:
        m = check_false_re.match(line)
        if m:
            result_lines.append("#| eval: false")
        else:
            result_lines.append(line)

    text = "\n".join(result_lines)

    execute_block = f"execute:\n  error: true\n  timeout: {timeout}"

    fm = _FRONTMATTER_RE.match(text)
    if fm:
        frontmatter = fm.group(1)
        has_execute = any(line.strip().startswith("execute:") for line in frontmatter.splitlines())
        if has_execute:
            new_fm_lines: list[str] = []
            in_execute = False
            for line in frontmatter.splitlines():
                if line.strip().startswith("execute:"):
                    in_execute = True
                    new_fm_lines.append("execute:")
                    new_fm_lines.append("  error: true")
                    new_fm_lines.append(f"  timeout: {timeout}")
                elif in_execute and line.startswith("  "):
                    key = line.strip().split(":")[0]
                    if key not in ("error", "timeout"):
                        new_fm_lines.append(line)
                else:
                    in_execute = False
                    new_fm_lines.append(line)
            new_frontmatter = "\n".join(new_fm_lines)
        else:
            new_frontmatter = frontmatter.rstrip() + "\n" + execute_block
        text = f"---\n{new_frontmatter}\n---\n" + text[fm.end() :]
    else:
        text = f"---\n{execute_block}\n---\n" + text

    return text


def _strip_html_tags(html: str) -> str:
    return _HTML_TAG_RE.sub("", html)


def _parse_errors_from_html(html: str, cells: list[Cell]) -> list[CellError]:
    errors: list[CellError] = []

    cell_source_map: dict[str, Cell] = {}
    for cell in cells:
        normalized = cell.source.strip()
        cell_source_map[normalized] = cell

    parts = _HTML_CELL_SPLIT_RE.split(html)
    cell_chunks: list[str] = []
    for i, part in enumerate(parts):
        if _HTML_CELL_SPLIT_RE.match(part) and i + 1 < len(parts):
            cell_chunks.append(part + parts[i + 1])

    for cell_html in cell_chunks:
        err_match = _HTML_ERROR_RE.search(cell_html)
        if not err_match:
            continue

        src_match = _HTML_SOURCE_RE.search(cell_html)
        raw_source = _strip_html_tags(src_match.group(1)).strip() if src_match else ""

        matched_cell = cell_source_map.get(raw_source)

        # Cells with `#| error: true` intentionally error — don't report them
        if matched_cell and matched_cell.options.get("error", "").lower() in (
            "true",
            "yes",
        ):
            continue

        error_text = _strip_html_tags(err_match.group(1)).strip()
        error_lines = [l for l in error_text.splitlines() if l.strip()]

        error_line = error_lines[-1] if error_lines else "UnknownError"
        if ": " in error_line:
            error_type, error_message = error_line.split(": ", 1)
        else:
            error_type = error_line
            error_message = ""

        traceback_text = "\n".join(error_lines)

        cell_index = matched_cell.index if matched_cell else -1
        cell_source = matched_cell.source if matched_cell else raw_source

        errors.append(
            CellError(
                cell_index=cell_index,
                source=cell_source,
                error_type=error_type,
                error_message=error_message,
                traceback=traceback_text,
            )
        )

    return errors


def _render_page_with_quarto(
    qmd_path: Path,
    page_label: str,
    cells: list[Cell],
    timeout: int,
    project_root: Path | None = None,
) -> PageResult:
    text = qmd_path.read_text(encoding="utf-8")
    prepared = _prepare_qmd_for_check(text, timeout)

    # Render in an isolated temp directory so Quarto doesn't detect the real
    # project's _quarto.yml (which would create _freeze/, .gitignore, etc.).
    # --execute-dir points at the original file's parent so relative paths
    # (e.g. ../assets/data.csv) resolve identically to a real build.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_qmd = Path(tmpdir) / qmd_path.name
        tmp_qmd.write_text(prepared, encoding="utf-8")

        try:
            proc = subprocess.run(
                [
                    "quarto",
                    "render",
                    str(tmp_qmd),
                    "--to",
                    "html",
                    "--execute-dir",
                    str(qmd_path.parent),
                ],
                capture_output=True,
                text=True,
                timeout=timeout * len(cells) + 60,
                cwd=tmpdir,
            )
        except subprocess.TimeoutExpired:
            return PageResult(
                path=page_label,
                status="error",
                cells_checked=len(cells),
                message=f"Quarto render timed out after {timeout * len(cells) + 60}s",
            )
        except Exception as e:
            return PageResult(
                path=page_label,
                status="error",
                cells_checked=0,
                message=f"{type(e).__name__}: {e}",
            )

        output_html = tmp_qmd.with_suffix(".html")
        if not output_html.exists():
            if proc.returncode != 0:
                stderr = proc.stderr.strip()
                return PageResult(
                    path=page_label,
                    status="error",
                    cells_checked=0,
                    message=f"Quarto render failed (exit {proc.returncode}): {stderr[:500]}",
                )
            return PageResult(
                path=page_label,
                status="error",
                cells_checked=0,
                message="No HTML output produced by Quarto",
            )

        html = output_html.read_text(encoding="utf-8")
        errors = _parse_errors_from_html(html, cells)

        return PageResult(
            path=page_label,
            status="fail" if errors else "pass",
            cells_checked=len(cells),
            errors=errors,
        )


def _build_docstring_qmd(cells: list[Cell]) -> str:
    lines = ["---", "execute:", "  error: true", "---", ""]
    for cell in cells:
        lines.append("```{python}")
        lines.append(cell.source)
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def _run_page(
    page_path: str,
    cells_json: str,
    timeout: int,
    project_root_str: str,
    is_docstring: bool = False,
) -> str:
    cells_data = json.loads(cells_json)
    cells = [Cell(**c) for c in cells_data]
    project_root = Path(project_root_str)

    try:
        if is_docstring:
            qmd_content = _build_docstring_qmd(cells)
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_qmd = Path(tmpdir) / "docstring_check.qmd"
                tmp_qmd.write_text(qmd_content, encoding="utf-8")
                result = _render_page_with_quarto(tmp_qmd, page_path, cells, timeout, project_root)
        else:
            qmd_path = project_root / page_path
            result = _render_page_with_quarto(qmd_path, page_path, cells, timeout, project_root)
    except Exception as e:
        result = PageResult(
            path=page_path,
            status="error",
            cells_checked=0,
            message=f"{type(e).__name__}: {e}",
        )

    return json.dumps(asdict(result))


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def discover_qmd_files(
    project_root: Path,
    paths: tuple[str, ...] | None = None,
    include: str | None = None,
    exclude: str | None = None,
) -> list[Path]:
    if paths:
        targets: list[Path] = []
        for p in paths:
            target = Path(p) if Path(p).is_absolute() else project_root / p
            if target.is_file() and target.suffix == ".qmd":
                targets.append(target)
            elif target.is_dir():
                targets.extend(sorted(target.rglob("*.qmd")))
        files = targets
    else:
        files = sorted(project_root.rglob("*.qmd"))

    # Exclude build directory and hidden directories
    filtered: list[Path] = []
    for f in files:
        rel = str(f.relative_to(project_root))
        if rel.startswith("great-docs/") or rel.startswith("."):
            continue
        if include and not fnmatch(rel, include):
            continue
        if exclude and fnmatch(rel, exclude):
            continue
        filtered.append(f)

    return filtered


# ---------------------------------------------------------------------------
# Section grouping for progress
# ---------------------------------------------------------------------------

# progress_setup is called once with an ordered dict of {section: total_pages}
# progress_callback is called per page: (section, page_path, section_current, section_total)
ProgressSetup = Callable[[dict[str, int]], None]
ProgressCallback = Callable[[str, str, int, int], None]

_DOCSTRING_SECTION = "docstrings"


def _section_for_page(page_path: str, is_docstring: bool) -> str:
    if is_docstring:
        return _DOCSTRING_SECTION
    parts = page_path.split("/")
    return parts[0] if len(parts) > 1 else "."


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def check_examples(
    project_root: Path,
    paths: tuple[str, ...] | None = None,
    timeout: int = 30,
    include: str | None = None,
    exclude: str | None = None,
    no_docstrings: bool = False,
    docstrings_only: bool = False,
    parallel: bool = False,
    jobs: int = 1,
    progress_callback: ProgressCallback | None = None,
    progress_setup: ProgressSetup | None = None,
) -> CheckResult:
    err = _check_quarto_available()
    if err:
        return CheckResult(pages=[PageResult(path="(setup)", status="error", message=err)])

    # Collect pages to check
    page_cells: list[tuple[str, list[Cell], bool]] = []

    if not docstrings_only:
        qmd_files = discover_qmd_files(project_root, paths, include, exclude)
        for qmd_path in qmd_files:
            text = qmd_path.read_text(encoding="utf-8")
            if _page_opted_out(text):
                continue
            cells = extract_cells(text)
            if cells:
                rel = str(qmd_path.relative_to(project_root))
                page_cells.append((rel, cells, False))

    if not no_docstrings and not paths:
        docstring_pages = extract_docstring_examples(project_root)
        for page_path, cells in docstring_pages:
            page_cells.append((page_path, cells, True))

    if not page_cells:
        return CheckResult()

    # Build per-section totals for progress tracking (preserve insertion order)
    section_totals: dict[str, int] = {}
    section_done: dict[str, int] = {}
    for page_path, _cells, is_docstring in page_cells:
        sec = _section_for_page(page_path, is_docstring)
        section_totals[sec] = section_totals.get(sec, 0) + 1
        section_done.setdefault(sec, 0)

    if progress_setup is not None:
        progress_setup(section_totals)

    def _notify_progress(page_path: str, is_docstring: bool) -> None:
        if progress_callback is None:
            return
        sec = _section_for_page(page_path, is_docstring)
        section_done[sec] += 1
        progress_callback(sec, page_path, section_done[sec], section_totals[sec])

    # Determine concurrency
    use_parallel = parallel or jobs > 1
    max_workers = max(jobs, 1) if use_parallel else 1

    # Execute
    result = CheckResult()

    if max_workers > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for page_path, cells, is_docstring in page_cells:
                cells_json = json.dumps([asdict(c) for c in cells])
                future = executor.submit(
                    _run_page,
                    page_path,
                    cells_json,
                    timeout,
                    str(project_root),
                    is_docstring,
                )
                futures[future] = (page_path, is_docstring)

            for future in as_completed(futures):
                f_page_path, f_is_docstring = futures[future]
                try:
                    page_result_json = future.result()
                    page_result_dict = json.loads(page_result_json)
                    page_result = _dict_to_page_result(page_result_dict)
                except Exception as e:
                    page_result = PageResult(
                        path=f_page_path,
                        status="error",
                        message=f"Subprocess error: {e}",
                    )
                result.pages.append(page_result)
                _notify_progress(f_page_path, f_is_docstring)
    else:
        for page_path, cells, is_docstring in page_cells:
            try:
                if is_docstring:
                    qmd_content = _build_docstring_qmd(cells)
                    with tempfile.TemporaryDirectory() as tmpdir:
                        tmp_qmd = Path(tmpdir) / "docstring_check.qmd"
                        tmp_qmd.write_text(qmd_content, encoding="utf-8")
                        page_result = _render_page_with_quarto(
                            tmp_qmd, page_path, cells, timeout, project_root
                        )
                else:
                    qmd_path = project_root / page_path
                    page_result = _render_page_with_quarto(
                        qmd_path, page_path, cells, timeout, project_root
                    )
            except Exception as e:
                page_result = PageResult(
                    path=page_path,
                    status="error",
                    message=f"{type(e).__name__}: {e}",
                )
            result.pages.append(page_result)
            _notify_progress(page_path, is_docstring)

    # Sort pages by path for stable output
    result.pages.sort(key=lambda p: p.path)

    # Tally
    for page in result.pages:
        if page.status == "skip":
            result.pages_skipped += 1
            continue
        result.pages_checked += 1
        result.cells_checked += page.cells_checked
        if page.status == "pass":
            result.pages_passed += 1
            result.cells_passed += page.cells_checked
        elif page.status in ("fail", "error"):
            result.pages_failed += 1
            n_errors = len(page.errors)
            result.cells_failed += n_errors
            result.cells_passed += page.cells_checked - n_errors

    return result


def _dict_to_page_result(d: dict[str, Any]) -> PageResult:
    errors = [CellError(**e) for e in d.get("errors", [])]
    return PageResult(
        path=d["path"],
        status=d["status"],
        cells_checked=d.get("cells_checked", 0),
        errors=errors,
        message=d.get("message"),
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_console(result: CheckResult, verbose: bool = False) -> str:
    lines: list[str] = []

    for page in result.pages:
        if page.status == "pass":
            lines.append(f"  ✓ {page.path} ({page.cells_checked} cells)")
        elif page.status == "error":
            lines.append(f"  ✗ {page.path}")
            if page.message:
                lines.append(f"    {page.message}")
        elif page.status == "fail":
            lines.append(f"  ✗ {page.path}")
            for err in page.errors:
                source_preview = err.source
                if len(source_preview) > 120:
                    source_preview = source_preview[:117] + "..."
                lines.append(f"    Cell {err.cell_index}:")
                for src_line in source_preview.splitlines():
                    lines.append(f"      {src_line}")
                lines.append(f"    {err.error_type}: {err.error_message}")
                if verbose and err.traceback:
                    lines.append("")
                    for tb_line in err.traceback.splitlines():
                        lines.append(f"      {tb_line}")
                lines.append("")

    lines.append("")
    lines.append(
        f"Results: {result.pages_passed} passed, {result.pages_failed} failed "
        f"({result.cells_checked} cells checked)"
    )

    return "\n".join(lines)


def format_json(result: CheckResult) -> str:
    data = {
        "summary": {
            "pages_checked": result.pages_checked,
            "pages_passed": result.pages_passed,
            "pages_failed": result.pages_failed,
            "cells_checked": result.cells_checked,
            "cells_passed": result.cells_passed,
            "cells_failed": result.cells_failed,
        },
        "pages": [asdict(p) for p in result.pages],
    }
    return json.dumps(data, indent=2)


def write_log_file(result: CheckResult, log_path: Path) -> bool:
    entries: list[str] = []

    for page in result.pages:
        if page.status != "fail":
            continue
        for err in page.errors:
            entries.append(f"{'=' * 60}")
            entries.append(f"Page: {page.path} | Cell {err.cell_index}")
            entries.append(f"{'=' * 60}")
            entries.append(f"Source:\n{err.source}")
            entries.append(f"\n{err.error_type}: {err.error_message}")
            if err.traceback:
                entries.append(f"\nFull traceback:\n{err.traceback}")
            entries.append("")

    if not entries:
        return False

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(entries), encoding="utf-8")
    return True
