import json
import subprocess
import sys
import textwrap
from pathlib import Path


def _run_python(source: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, "-I", "-c", textwrap.dedent(source)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result


def test_root_exports_and_signatures_in_fresh_interpreter(tmp_path: Path) -> None:
    """Preserve public exports, callable signatures and exception identity"""
    result = _run_python(
        """
        import inspect
        import json
        import great_docs
        from great_docs import cli, mcp

        print(json.dumps({
            "exports": great_docs.__all__,
            "signatures": {
                name: str(inspect.signature(getattr(great_docs, name)))
                for name in great_docs.__all__ if name != "BuildError"
            },
            "exception_identity": (
                great_docs.BuildError is cli.BuildError is mcp.BuildError
            ),
        }))
        """,
        tmp_path,
    )
    observed = json.loads(result.stdout)
    assert observed["exports"] == [
        "BuildError",
        "Config",
        "GreatDocs",
        "check_skill",
        "create_default_config",
        "disable_tbl_preview",
        "enable_tbl_preview",
        "install_skill",
        "list_skills",
        "load_config",
        "main",
        "render_evolution_table",
        "tbl_explorer",
        "tbl_preview",
    ]
    assert observed["signatures"] == {
        "Config": "(project_root: 'Path', *, config_path: 'Path | None' = None, cache_dir: "
        "'Path | None' = None)",
        "GreatDocs": "(project_path: str | os.PathLike[str] | None = None, *, config_path: "
        "str | None = None, create: bool = False) -> None",
        "check_skill": "(*, package: 'str | None' = None, global_: 'bool' = False, local: "
        "'bool' = True, root: 'Path | None' = None, update: 'bool' = False, "
        "quiet: 'bool' = False) -> 'list[dict]'",
        "create_default_config": "(overrides: 'dict[str, str] | None' = None) -> 'str'",
        "disable_tbl_preview": "() -> 'None'",
        "enable_tbl_preview": "(**kwargs: 'Any') -> 'None'",
        "install_skill": "(*, package: 'str | None' = None, url: 'str | None' = None, "
        "skill_content: 'str | None' = None, agent: 'AgentFormat | None' = "
        "None, global_: 'bool' = False, path: 'str | None' = None, root: "
        "'Path | None' = None, detect: 'bool' = False, skill_name: 'str | "
        "None' = None, extra_files: 'dict[str, str] | None' = None, quiet: "
        "'bool' = False) -> 'list[Path]'",
        "list_skills": "(*, package: 'str | None' = None, url: 'str | None' = None, quiet: "
        "'bool' = False) -> 'list[dict]'",
        "load_config": "(project_root: 'Path | str') -> 'Config'",
        "main": "() -> 'None'",
        "render_evolution_table": "(project_path='.', symbol='', **kwargs)",
        "tbl_explorer": "(data: 'Any', columns: 'list[str] | None' = None, show_row_numbers: "
        "'bool' = True, show_dtypes: 'bool' = True, show_dimensions: 'bool' = "
        "True, max_col_width: 'int' = 250, min_tbl_width: 'int' = 500, "
        "caption: 'str | None' = None, highlight_missing: 'bool' = True, "
        "page_size: 'int' = 10, sortable: 'bool' = True, filterable: 'bool' = "
        "True, column_toggle: 'bool' = True, copyable: 'bool' = True, "
        "downloadable: 'bool' = True, resizable: 'bool' = False, "
        "sticky_header: 'bool' = True, search_highlight: 'bool' = True, id: "
        "'str | None' = None) -> 'TblExplorer'",
        "tbl_preview": "(data: 'Any', columns: 'list[str] | None' = None, n_head: 'int' = 5, "
        "n_tail: 'int' = 5, limit: 'int' = 50, show_all: 'bool' = False, "
        "show_row_numbers: 'bool' = True, show_dtypes: 'bool' = True, "
        "show_dimensions: 'bool' = True, max_col_width: 'int' = 250, "
        "min_tbl_width: 'int' = 500, caption: 'str | None' = None, "
        "highlight_missing: 'bool' = True, row_index_offset: 'int' = 0, id: "
        "'str | None' = None) -> 'TblPreview'",
    }
    assert observed["exception_identity"] is True


def test_root_main_shows_cli_help_in_fresh_interpreter(tmp_path: Path) -> None:
    """Expose command help through the root entry point"""
    result = _run_python(
        """
        import sys
        import great_docs

        sys.argv = ["great-docs", "--help"]
        great_docs.main()
        """,
        tmp_path,
    )
    assert result.stderr == ""
    assert result.stdout.startswith("Usage: great-docs [OPTIONS] COMMAND [ARGS]...")
    assert "Great Docs" in result.stdout
    assert "init" in result.stdout
    assert "termshow" in result.stdout


def test_builtin_effects_survive_repeated_imports(tmp_path: Path) -> None:
    """Apply built-in directives and normalisation after ordinary imports"""
    result = _run_python(
        r"""
        import importlib
        import json
        import great_docs
        import griffe as gf
        from great_docs.hooks._object_resolved import emit_object_resolved

        def apply_hooks() -> list[str | bool]:
            visible = gf.Function("visible")
            visible.docstring = gf.Docstring(
                "%note Use :func:`value`.\n\n>>> 1 + 1\n2", parent=visible, parser="sphinx",
            )
            assert emit_object_resolved(visible) is visible
            hidden = gf.Function("hidden")
            hidden.docstring = gf.Docstring("%nodoc", parent=hidden)
            return [visible.docstring.value, emit_object_resolved(hidden) is None]

        before = apply_hooks()
        for _ in range(3):
            importlib.import_module("great_docs")
            importlib.import_module("great_docs._builtin")
        print(json.dumps([before, apply_hooks()]))
        """,
        tmp_path,
    )
    before, after = json.loads(result.stdout)
    expected = [
        "::: {.callout-note}\nUse `value()`.\n:::\n\n```python\n>>> 1 + 1\n2\n```",
        True,
    ]
    assert before == expected
    assert after == expected
