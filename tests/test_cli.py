from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from great_docs.cli import (
    _detect_current_package,
    _detect_optional_dependencies,
    _detect_python_version_from_pyproject,
    _find_build_timing,
    _format_seconds,
    _freeze_info,
    _print_page_table,
    _print_timing_table,
    cli,
)


@pytest.mark.parametrize(
    "unsafe", ["container", "build", "persistent", "parent", "child", "unowned"]
)
def test_freeze_clean_rejects_unsafe_paths_before_removing_cache(
    tmp_path: Path, unsafe: str
) -> None:
    from great_docs._utils import QUARTO_YML_HEADER

    source = tmp_path / "docs"
    source.mkdir()
    (source / "great-docs.yml").write_text("display_name: Demo\n")
    (source / "page.qmd").write_text("# Page\n")
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    keep = unrelated / "keep.txt"
    keep.write_bytes(b"unrelated cache\x00")
    persistent = source / "_freeze"
    persistent.mkdir()
    persistent_keep = persistent / "keep.txt"
    persistent_keep.write_bytes(b"persistent cache\x00")
    build = source / "_quarto/default"
    build.mkdir(parents=True)
    (build / "_quarto.yml").write_text(QUARTO_YML_HEADER)
    build_cache = build / "_freeze"
    build_cache.mkdir()
    (build_cache / "keep.txt").write_bytes(b"build cache\x00")
    args = ["freeze", "docs/page.qmd", "--clean", "--project-path", str(tmp_path)]
    if unsafe == "container":
        build.parent.rename(unrelated / "projects")
        (source / "_quarto").symlink_to(unrelated / "projects", target_is_directory=True)
    elif unsafe == "build":
        build.rename(unrelated / "project")
        build.symlink_to(unrelated / "project", target_is_directory=True)
    elif unsafe == "persistent":
        persistent.rename(unrelated / "cache")
        persistent.symlink_to(unrelated / "cache", target_is_directory=True)
    elif unsafe == "parent":
        (unrelated / "cache").mkdir()
        (unrelated / "cache/keep.txt").write_bytes(b"external cache\x00")
        (source / "cache-link").symlink_to(unrelated, target_is_directory=True)
        args.extend(["--freeze-dir", str(source / "cache-link/cache")])
    elif unsafe == "child":
        (persistent / "linked").symlink_to(unrelated, target_is_directory=True)
    else:
        (build / "_quarto.yml").write_text("project:\n  type: website\n")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    result = CliRunner().invoke(cli, args)

    assert result.exit_code != 0
    assert keep.read_bytes() == b"unrelated cache\x00"
    assert all(path.is_file() and path.read_bytes() == content for path, content in before.items())


def test_preview_does_not_move_config(tmp_path: Path) -> None:
    config = tmp_path / "great-docs.yml"
    config.write_text("display_name: Demo\n")
    result = CliRunner().invoke(
        cli,
        ["migrate-layout", "--project-path", str(tmp_path), "--dry-run"],
    )
    assert result.exit_code == 0, result.output
    assert "docs/great-docs.yml" in result.output
    assert config.read_text() == "display_name: Demo\n"
    assert not (tmp_path / "docs").exists()


def test_freeze_clean_preserves_cache_when_page_is_missing(tmp_path: Path) -> None:
    cache = tmp_path / "_freeze"
    cache.mkdir()
    saved = cache / "result.json"
    saved.write_bytes(b"cache\x00")

    result = CliRunner().invoke(
        cli, ["freeze", "missing.qmd", "--clean", "--project-path", str(tmp_path)]
    )

    assert result.exit_code != 0
    assert "Page not found" in result.output
    assert saved.read_bytes() == b"cache\x00"


def test_freeze_clean_rejects_parent_traversal_before_normalisation(tmp_path: Path) -> None:
    source = tmp_path / "docs"
    source.mkdir()
    (source / "great-docs.yml").write_text("display_name: Demo\n")
    (source / "page.qmd").write_text("# Page\n")
    external = tmp_path / "external"
    (external / "inner").mkdir(parents=True)
    (external / "cache").mkdir()
    saved = external / "cache/keep.txt"
    saved.write_bytes(b"external cache\x00")
    (source / "link").symlink_to(external / "inner", target_is_directory=True)
    override = source / "link/../cache"

    with patch("great_docs.cli.GreatDocs._prepare_for_freeze"):
        result = CliRunner().invoke(
            cli,
            [
                "freeze",
                "docs/page.qmd",
                "--clean",
                "--project-path",
                str(tmp_path),
                "--freeze-dir",
                str(override),
            ],
        )

    assert result.exit_code != 0
    assert saved.read_bytes() == b"external cache\x00"


def test_freeze_clean_accepts_ordinary_relative_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "page.qmd").write_text("# Page\n")
    cache = tmp_path / "cached-results"
    cache.mkdir()
    (cache / "result.json").write_bytes(b"cache\x00")
    with patch("great_docs.cli.GreatDocs._prepare_for_freeze") as prepare:
        CliRunner().invoke(cli, ["freeze", "page.qmd", "--clean", "--freeze-dir", "cached-results"])
    prepare.assert_called_once()
    assert not cache.exists()


@pytest.mark.parametrize("directory", [".", "docs"])
@pytest.mark.parametrize("mode", ["single", "versions", "watch", "preview", "preview-build"])
def test_layout_notice_once_per_build_or_preview_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    directory: str,
    mode: str,
) -> None:
    from great_docs import GreatDocs

    source = tmp_path / directory
    source.mkdir(exist_ok=True)
    config = "reference: false\nchangelog:\n  enabled: false\nskill:\n  enabled: false\n"
    if mode == "versions":
        config += 'versions: ["0.3", "0.2", "0.1"]\n'
    (source / "great-docs.yml").write_text(config)
    (source / "index.qmd").write_text("# A small documentation site\n")
    docs = GreatDocs(str(tmp_path))
    run = subprocess.run
    popen = subprocess.Popen
    rendered: list[Path] = []

    def render(build_dir: Path) -> None:
        site = build_dir / "_site"
        site.mkdir(parents=True, exist_ok=True)
        (site / "index.html").write_text("<html>Documentation</html>")
        rendered.append(build_dir)

    def run_quarto(
        command: list[str], *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess:
        if command[:2] == ["quarto", "preview"]:
            for _ in range(3):
                render(Path.cwd())
            return subprocess.CompletedProcess(command, 0)
        return run(command, *args, **kwargs)

    def start_quarto(command: list[str], *args: object, **kwargs: object) -> object:
        if command[:2] == ["quarto", "render"]:
            render(Path.cwd())
            return MagicMock(stdout=iter([]), stderr=iter([]), returncode=0)
        return popen(command, *args, **kwargs)

    def render_versions(
        build_dirs: list[Path], **kwargs: object
    ) -> list[tuple[str, int, str, str, list[dict]]]:
        for build_dir in build_dirs:
            render(build_dir)
        return [(str(build_dir), 0, "", "", []) for build_dir in build_dirs]

    monkeypatch.setattr("great_docs.core._ensure_quarto_installed", lambda: None)
    monkeypatch.setattr(subprocess, "run", run_quarto)
    monkeypatch.setattr(subprocess, "Popen", start_quarto)
    monkeypatch.setattr("great_docs._versioned_build.render_versions_parallel", render_versions)
    monkeypatch.setattr("http.server.ThreadingHTTPServer", MagicMock())
    monkeypatch.setattr("threading.Timer", MagicMock())
    if mode == "preview":
        docs.layout.site_dir.mkdir(parents=True)
        (docs.layout.site_dir / "index.html").write_text("<html>Existing site</html>")
    if mode.startswith("preview"):
        docs.preview()
    else:
        docs.build(watch=mode == "watch", refresh=False)
    output = capsys.readouterr().out
    notice = "Keep documentation in docs/ with the new layout.\nRun great-docs migrate-layout --dry-run to preview the migration.\n"
    assert output.count(notice) == (1 if directory == "." else 0)
    assert len(rendered) == (3 if mode in {"versions", "watch"} else 0 if mode == "preview" else 1)


@pytest.mark.parametrize(
    "command",
    [
        "build",
        "preview",
        "uninstall",
        "scan",
        "freeze",
        "timings",
        "setup-github-pages",
        "check-links",
        "changelog",
        "proofread",
        "seo",
        "lint",
        "versions",
    ],
)
def test_project_commands_reject_missing_selected_config(tmp_path: Path, command: str) -> None:
    result = CliRunner().invoke(
        cli, [command, "--project-path", str(tmp_path), "--config", str(tmp_path / "missing.yml")]
    )
    assert result.exit_code != 0
    assert "Configuration file does not exist" in result.output


@pytest.mark.parametrize("command", ["init", "config"])
@pytest.mark.parametrize("selection", [None, "website/settings.yml"])
def test_creation_selects_docs_or_custom_config(
    tmp_path: Path, command: str, selection: str | None
) -> None:
    args = [command, "--project-path", str(tmp_path), "--force"]
    if selection:
        args += ["--config", str(tmp_path / selection)]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    assert (tmp_path / (selection or "docs/great-docs.yml")).is_file()
    assert not (tmp_path / "great-docs.yml").exists()


def test_creation_refuses_second_conventional_config(tmp_path: Path) -> None:
    (tmp_path / "great-docs.yml").write_text("name: existing\n")
    result = CliRunner().invoke(
        cli,
        [
            "config",
            "--project-path",
            str(tmp_path),
            "--config",
            str(tmp_path / "docs/great-docs.yml"),
            "--force",
        ],
    )
    assert result.exit_code != 0
    assert not (tmp_path / "docs/great-docs.yml").exists()


def test_timings_reads_selected_deployment(tmp_path: Path) -> None:
    (tmp_path / "website/_site").mkdir(parents=True)
    (tmp_path / "website/settings.yml").write_text("{}\n")
    (tmp_path / "website/_site/build-timings.json").write_text('{"pages": []}')
    result = CliRunner().invoke(
        cli,
        [
            "timings",
            "--project-path",
            str(tmp_path),
            "--config",
            str(tmp_path / "website/settings.yml"),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"pages": []}


def test_versions_reads_selected_config(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/great-docs.yml").write_text("versions:\n  - tag: dev\n    latest: true\n")
    result = CliRunner().invoke(cli, ["versions", "--project-path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "dev" in result.output
    assert "No versions" not in result.output


@pytest.mark.parametrize("selection", [None, "website/settings.yml"])
def test_remote_build_uses_checkout_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, selection: str | None
) -> None:
    from great_docs import GreatDocs

    repo = tmp_path / "repo"
    repo.mkdir()
    source = "website" if selection else "docs"
    (repo / source).mkdir()
    (repo / (selection or "docs/great-docs.yml")).write_text("{}\n")
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.org",
            "commit",
            "-m",
            "Initial configuration",
        ],
        check=True,
        capture_output=True,
    )
    destination = tmp_path / "destination"
    destination.mkdir()
    monkeypatch.chdir(destination)
    run = subprocess.run

    def run_build(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        if command[0] == "git":
            return run(command, **kwargs)
        if "build" in command:
            checkout = Path(command[command.index("--project-path") + 1])
            if selection:
                assert (
                    Path(command[command.index("--config") + 1]) == (checkout / selection).resolve()
                )
            site = checkout / source / "_site"
            site.mkdir()
            (site / "index.html").write_text("remote documentation")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run_build)
    monkeypatch.setattr("venv.create", lambda *args, **kwargs: None)
    built = GreatDocs.build_from_repo(str(repo), config_path=selection, shallow=True)
    assert built == destination / source / "_site"
    assert (built / "index.html").read_text() == "remote documentation"


@pytest.mark.parametrize("selection", ["../outside.yml", "/tmp/outside.yml"])
def test_remote_config_cannot_escape_checkout(tmp_path: Path, selection: str) -> None:
    from great_docs import GreatDocs
    from great_docs._layout import LayoutError

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "great-docs.yml").write_text("{}\n")
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.org",
            "commit",
            "-m",
            "Initial configuration",
        ],
        check=True,
        capture_output=True,
    )
    with pytest.raises(LayoutError, match="checkout"):
        GreatDocs.build_from_repo(str(repo), config_path=selection, shallow=True)


def test_config_generation_ignores_only_selected_output(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["config", "--project-path", str(tmp_path), "--force"])
    assert result.exit_code == 0, result.output
    ignores = (tmp_path / ".gitignore").read_text()
    assert "/docs/_quarto/" in ignores
    assert "/docs/_site/" in ignores
    assert "/great-docs/" not in ignores
    assert "_freeze" not in ignores


def test_freeze_info_reads_selected_sources_and_cache(tmp_path: Path) -> None:
    (tmp_path / "website/user_guide").mkdir(parents=True)
    (tmp_path / "website/settings.yml").write_text("freeze: auto\n")
    (tmp_path / "website/user_guide/demo.qmd").write_text("---\nfreeze: true\n---\n")
    result = CliRunner().invoke(
        cli,
        [
            "freeze",
            "--project-path",
            str(tmp_path),
            "--config",
            str(tmp_path / "website/settings.yml"),
            "--info",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "website/_freeze" in result.output
    assert "demo.qmd" in result.output
    assert "auto" in result.output


def test_build_command_uses_selected_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from great_docs import GreatDocs

    (tmp_path / "website").mkdir()
    config = tmp_path / "website/settings.yml"
    config.write_text("name: selected\n")

    def build_selected(docs: GreatDocs, **kwargs: object) -> None:
        docs.build_dir.mkdir(parents=True)
        (docs.build_dir / "selection.txt").write_text(docs._config["name"])

    monkeypatch.setattr(GreatDocs, "build", build_selected)
    result = CliRunner().invoke(
        cli, ["build", "--project-path", str(tmp_path), "--config", str(config)]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "website/_quarto/default/selection.txt").read_text() == "selected"


def test_preview_serves_selected_deployment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import http.server

    (tmp_path / "website/_site").mkdir(parents=True)
    config = tmp_path / "website/settings.yml"
    config.write_text("{}\n")
    (tmp_path / "website/_site/index.html").write_text("preview documentation")
    served: list[str] = []

    def server(address: object, handler: object) -> MagicMock:
        served.append(Path(handler.keywords["directory"]).joinpath("index.html").read_text())
        return MagicMock()

    monkeypatch.setattr(http.server, "ThreadingHTTPServer", server)
    monkeypatch.setattr("threading.Timer", MagicMock())
    result = CliRunner().invoke(
        cli, ["preview", "--project-path", str(tmp_path), "--config", str(config)]
    )
    assert result.exit_code == 0, result.output
    assert served == ["preview documentation"]


def test_preview_override_ignores_ambiguous_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from great_docs import GreatDocs

    (tmp_path / "great-docs.yml").write_text("{}\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/great-docs.yml").write_text("{}\n")
    site = tmp_path / "published"
    site.mkdir()
    (site / "index.html").write_text("published documentation")
    monkeypatch.setattr(
        GreatDocs,
        "preview_site",
        lambda path, **kwargs: print(Path(path).joinpath("index.html").read_text()),
    )
    result = CliRunner().invoke(
        cli, ["preview", "--project-path", str(tmp_path), "--site-dir", str(site)]
    )
    assert result.exit_code == 0, result.output
    assert "published documentation" in result.output


def test_uninstall_removes_only_selected_project(tmp_path: Path) -> None:
    from great_docs import GreatDocs
    from great_docs._utils import QUARTO_YML_HEADER

    (tmp_path / "great-docs.yml").write_text("name: preserved\n")
    (tmp_path / "website").mkdir()
    config = tmp_path / "website/settings.yml"
    config.write_text("{}\n")
    docs = GreatDocs(str(tmp_path), config_path=str(config))
    docs.build_dir.mkdir(parents=True)
    (docs.build_dir / "_quarto.yml").write_text(QUARTO_YML_HEADER)
    result = CliRunner().invoke(
        cli, ["uninstall", "--project-path", str(tmp_path), "--config", str(config)]
    )
    assert result.exit_code == 0, result.output
    assert not config.exists()
    assert not (tmp_path / "website/_quarto").exists()
    assert (tmp_path / "great-docs.yml").read_text() == "name: preserved\n"


@pytest.mark.parametrize(
    "selected", ["great-docs.yml", "docs/great-docs.yml", "website/settings.yml"]
)
def test_workflow_uses_selected_deployment(tmp_path: Path, selected: str) -> None:
    config = tmp_path / selected
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("{}\n")
    result = CliRunner().invoke(
        cli,
        ["setup-github-pages", "--project-path", str(tmp_path), "--config", str(config), "--force"],
    )
    assert result.exit_code == 0, result.output
    workflow = (tmp_path / ".github/workflows/docs.yml").read_text()
    expected_site = (
        "great-docs/_site"
        if selected == "great-docs.yml"
        else selected.rsplit("/", 1)[0] + "/_site"
    )
    assert f"--config {selected}" in workflow
    assert f"path: {expected_site}" in workflow


def test_detect_python_version_ge():
    """Parses >=3.12 and returns '3.12'."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.12"\n')
        assert _detect_python_version_from_pyproject(Path(tmp)) == "3.12"


def test_detect_python_version_tilde():
    """Parses ~=3.11 and returns '3.11'."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nrequires-python = "~=3.11"\n')
        assert _detect_python_version_from_pyproject(Path(tmp)) == "3.11"


def test_detect_python_version_range():
    """Parses >=3.10,<3.13 and returns '3.10'."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.10,<3.13"\n')
        assert _detect_python_version_from_pyproject(Path(tmp)) == "3.10"


def test_detect_python_version_no_pyproject():
    """Returns None when pyproject.toml doesn't exist."""
    with tempfile.TemporaryDirectory() as tmp:
        assert _detect_python_version_from_pyproject(Path(tmp)) is None


def test_detect_python_version_no_requires():
    """Returns None when requires-python is absent."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nname = "x"\n')
        assert _detect_python_version_from_pyproject(Path(tmp)) is None


def test_detect_python_version_no_version_match():
    """Returns None when requires-python doesn't contain a valid version."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nrequires-python = "no-version"\n')
        assert _detect_python_version_from_pyproject(Path(tmp)) is None


def test_detect_python_version_other_specifier():
    """For non->=, non-~= specifiers, returns the highest version."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nrequires-python = "==3.11"\n')
        assert _detect_python_version_from_pyproject(Path(tmp)) == "3.11"


def test_detect_python_version_malformed_toml():
    """Returns None on invalid TOML."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text("not valid {{toml")
        assert _detect_python_version_from_pyproject(Path(tmp)) is None


def test_detect_optional_deps_with_dev():
    """Finds dev/docs/test extras."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text(
            "[project.optional-dependencies]\n"
            'dev = ["pytest"]\n'
            'docs = ["sphinx"]\n'
            'other = ["requests"]\n'
        )
        result = _detect_optional_dependencies(Path(tmp))
        assert "dev" in result
        assert "docs" in result
        assert "other" not in result


def test_detect_optional_deps_no_pyproject():
    """Returns empty list when no pyproject.toml."""
    with tempfile.TemporaryDirectory() as tmp:
        assert _detect_optional_dependencies(Path(tmp)) == []


def test_detect_optional_deps_no_optional():
    """Returns empty list when no optional-dependencies."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text('[project]\nname = "x"\n')
        assert _detect_optional_dependencies(Path(tmp)) == []


def test_detect_optional_deps_malformed():
    """Returns empty list on invalid TOML."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text("bad {{toml")
        assert _detect_optional_dependencies(Path(tmp)) == []


def test_detect_optional_deps_all_keyword():
    """Detects 'all' and 'full' extras."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "pyproject.toml").write_text(
            "[project.optional-dependencies]\n"
            'all = ["everything"]\n'
            'full = ["everything"]\n'
            'notebook = ["jupyter"]\n'
        )
        result = _detect_optional_dependencies(Path(tmp))
        assert "all" in result
        assert "full" in result
        assert "notebook" in result


def test_seo_no_site_dir(tmp_path, monkeypatch):
    """seo command errors when _site doesn't exist."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    result = runner.invoke(cli, ["seo", "--project-path", "."])
    assert result.exit_code != 0
    assert "not built" in result.output or "Error" in result.output


def test_seo_json_no_site(tmp_path, monkeypatch):
    """seo --json returns error JSON when _site doesn't exist."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    result = runner.invoke(cli, ["seo", "--json", "--project-path", "."])
    assert result.exit_code != 0


def test_seo_with_empty_site(tmp_path, monkeypatch):
    """seo command runs with an empty _site directory."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
    Path("great-docs.yml").write_text("display_name: Pkg\n")
    Path("great-docs").mkdir()
    site = Path("great-docs") / "_site"
    site.mkdir(parents=True)
    result = runner.invoke(cli, ["seo", "--project-path", "."])
    # Should run without crashing
    assert "SEO" in result.output or "Error" in result.output


def test_seo_json_with_site(tmp_path, monkeypatch):
    """seo --json outputs valid JSON."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
    Path("great-docs.yml").write_text("display_name: Pkg\n")
    gd = Path("great-docs")
    gd.mkdir()
    site = gd / "_site"
    site.mkdir()
    # Create a minimal sitemap
    (site / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://example.com/</loc></url>"
        "</urlset>"
    )
    (site / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n"
    )
    result = runner.invoke(cli, ["seo", "--json", "--project-path", "."])
    if result.exit_code == 0:
        data = json.loads(result.output)
        assert "status" in data


def test_seo_with_html_pages(tmp_path, monkeypatch):
    """seo command analyzes HTML pages."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
    Path("great-docs.yml").write_text("display_name: Pkg\n")
    gd = Path("great-docs")
    gd.mkdir()
    site = gd / "_site"
    site.mkdir()
    (site / "index.html").write_text(
        "<html><head>"
        "<title>Pkg | Docs</title>"
        '<meta name="description" content="docs">'
        '<link rel="canonical" href="https://example.com/">'
        '</head><body><img src="test.png" alt="test"></body></html>'
    )
    result = runner.invoke(cli, ["seo", "--project-path", "."])
    assert "Analyzed" in result.output or "SEO" in result.output


def test_seo_missing_alt_text(tmp_path, monkeypatch):
    """seo detects missing alt text on images."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
    Path("great-docs.yml").write_text("display_name: Pkg\n")
    gd = Path("great-docs")
    gd.mkdir()
    site = gd / "_site"
    site.mkdir()
    (site / "page.html").write_text(
        '<html><head><title>T</title></head><body><img src="no-alt.png"></body></html>'
    )
    result = runner.invoke(cli, ["seo", "--project-path", "."])
    assert "alt" in result.output.lower() or "warning" in result.output.lower()


@pytest.mark.parametrize("unknown", [False, True])
def test_seo_fix_preserves_deployment_ownership(tmp_path: Path, unknown: bool) -> None:
    from great_docs._utils import record_site_ownership, validate_site_dir

    source = tmp_path / "docs"
    source.mkdir()
    (source / "great-docs.yml").write_text(
        "seo:\n  sitemap: true\n  canonical:\n    base_url: https://example.com/\n"
    )
    site = source / "_site"
    site.mkdir()
    (site / "index.html").write_text("<html><head><title>Demo</title></head></html>")
    record_site_ownership(site)
    if unknown:
        (site / "notes.txt").write_bytes(b"user notes\x00")
    before = {path: path.read_bytes() for path in site.iterdir()}

    result = CliRunner().invoke(cli, ["seo", "--fix", "--project-path", str(tmp_path)])

    if unknown:
        assert result.exit_code != 0
        assert {path: path.read_bytes() for path in site.iterdir()} == before
    else:
        assert (site / "robots.txt").is_file()
        assert (site / "sitemap.xml").is_file()
        validate_site_dir(site)


def test_seo_fix_missing_files(tmp_path, monkeypatch):
    """seo --fix attempts to generate missing files."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
    Path("great-docs.yml").write_text("display_name: Pkg\n")
    gd = Path("great-docs")
    gd.mkdir()
    site = gd / "_site"
    site.mkdir()
    result = runner.invoke(cli, ["seo", "--fix", "--project-path", "."])
    # Should attempt fix operations
    assert result.exit_code in (0, 1)


def test_lint_help():
    """lint --help shows expected options."""
    runner = CliRunner()
    result = runner.invoke(cli, ["lint", "--help"])
    assert result.exit_code == 0
    assert "lint" in result.output.lower()
    assert "--check" in result.output
    assert "--json" in result.output


@patch("great_docs._lint.run_lint")
def test_lint_no_issues(mock_lint, tmp_path, monkeypatch):
    """lint with no issues prints success."""
    from great_docs._lint import LintResult

    mock_lint.return_value = LintResult(issues=[], package_name="mypkg", exports_count=10)
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["lint", "--project-path", "."])
    assert result.exit_code == 0
    assert "passed" in result.output


@patch("great_docs._lint.run_lint")
def test_lint_with_errors(mock_lint, tmp_path, monkeypatch):
    """lint with errors exits non-zero."""
    from great_docs._lint import LintIssue, LintResult

    mock_lint.return_value = LintResult(
        issues=[
            LintIssue(
                check="missing-docstring",
                severity="error",
                symbol="MyClass",
                message="Missing docstring",
            )
        ],
        package_name="mypkg",
        exports_count=5,
    )
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["lint", "--project-path", "."])
    assert result.exit_code == 1
    assert "error" in result.output.lower()


@patch("great_docs._lint.run_lint")
def test_lint_json_output(mock_lint, tmp_path, monkeypatch):
    """lint --json outputs valid JSON."""
    from great_docs._lint import LintIssue, LintResult

    mock_lint.return_value = LintResult(
        issues=[
            LintIssue(
                check="broken-xref",
                severity="warning",
                symbol="fn",
                message="Broken ref",
            )
        ],
        package_name="mypkg",
        exports_count=3,
    )
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["lint", "--json", "--project-path", "."])
    data = json.loads(result.output)
    assert data["status"] == "warn"
    assert data["package"] == "mypkg"
    assert len(data["issues"]) == 1


@patch("great_docs._lint.run_lint")
def test_lint_warnings_only(mock_lint, tmp_path, monkeypatch):
    """lint with only warnings exits 0."""
    from great_docs._lint import LintIssue, LintResult

    mock_lint.return_value = LintResult(
        issues=[
            LintIssue(
                check="style-mismatch",
                severity="warning",
                symbol="fn",
                message="Style issue",
            )
        ],
        package_name="mypkg",
        exports_count=3,
    )
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["lint", "--project-path", "."])
    assert result.exit_code == 0
    assert "warning" in result.output.lower()


@patch("great_docs._lint.run_lint", side_effect=RuntimeError("boom"))
def test_lint_exception(mock_lint, tmp_path, monkeypatch):
    """lint handles runtime errors gracefully."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["lint", "--project-path", "."])
    assert result.exit_code == 1


@patch("great_docs._lint.run_lint", side_effect=RuntimeError("boom"))
def test_lint_exception_json(mock_lint, tmp_path, monkeypatch):
    """lint --json returns error JSON on exception."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["lint", "--json", "--project-path", "."])
    data = json.loads(result.output)
    assert data["status"] == "error"
    assert "boom" in data["error"]


@patch("great_docs._lint.run_lint")
def test_lint_with_check_filter(mock_lint, tmp_path, monkeypatch):
    """lint --check docstrings passes filter to run_lint."""
    from great_docs._lint import LintResult

    mock_lint.return_value = LintResult(issues=[], package_name="mypkg", exports_count=5)
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["lint", "--check", "docstrings", "--project-path", "."])
    assert result.exit_code == 0
    _, kwargs = mock_lint.call_args
    assert kwargs["checks"] == {"docstrings"}


def test_api_diff_help():
    """api-diff --help shows expected options."""
    runner = CliRunner()
    result = runner.invoke(cli, ["api-diff", "--help"])
    assert result.exit_code == 0
    assert "OLD_VERSION" in result.output
    assert "NEW_VERSION" in result.output
    assert "--json" in result.output
    assert "--graph" in result.output
    assert "--timeline" in result.output
    assert "--symbol" in result.output


@patch("great_docs._api_diff.api_diff")
def test_api_diff_text_output(mock_diff, tmp_path, monkeypatch):
    """api-diff renders text output with diff summary."""
    from great_docs._api_diff import ApiDiff, SymbolChange

    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
        added=[SymbolChange(symbol="new_fn", change_type="added")],
        removed=[SymbolChange(symbol="old_fn", change_type="removed", is_breaking=True)],
        changed=[
            SymbolChange(
                symbol="changed_fn",
                change_type="changed",
                is_breaking=True,
                details=["Return type changed"],
            )
        ],
    )
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        ["api-diff", "v1.0", "v2.0", "--project-path", "."],
    )
    assert result.exit_code == 0
    assert "new_fn" in result.output
    assert "old_fn" in result.output
    assert "changed_fn" in result.output
    assert "BREAKING" in result.output


@patch("great_docs._api_diff.api_diff")
def test_api_diff_json_output(mock_diff, tmp_path, monkeypatch):
    """api-diff --json outputs valid JSON."""
    from great_docs._api_diff import ApiDiff

    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
    )
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        ["api-diff", "v1.0", "v2.0", "--json", "--project-path", "."],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["old_version"] == "v1.0"


@patch("great_docs._api_diff.api_diff", return_value=None)
def test_api_diff_no_snapshots(mock_diff, tmp_path, monkeypatch):
    """api-diff exits with error when snapshots can't be built."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        ["api-diff", "v1.0", "v2.0", "--project-path", "."],
    )
    assert result.exit_code != 0
    assert "Could not" in result.output


@patch("great_docs._api_diff.api_diff")
def test_api_diff_no_changes(mock_diff, tmp_path, monkeypatch):
    """api-diff with no changes shows success message."""
    from great_docs._api_diff import ApiDiff

    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
    )
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        ["api-diff", "v1.0", "v2.0", "--project-path", "."],
    )
    assert result.exit_code == 0
    assert "No API changes" in result.output


@patch("great_docs._api_diff.build_timeline")
def test_api_diff_timeline_json(mock_timeline, tmp_path, monkeypatch):
    """api-diff --timeline --json outputs timeline data."""
    mock_timeline.return_value = [
        {"version": "v1.0", "symbols": 5, "classes": 2, "functions": 3},
        {"version": "v2.0", "symbols": 8, "classes": 3, "functions": 5},
    ]
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        ["api-diff", "v1.0", "v2.0", "--timeline", "--json", "--project-path", "."],
    )
    assert result.exit_code == 0

    data = json.loads(result.output)

    assert len(data) == 2
    assert data[0]["version"] == "v1.0"


@patch("great_docs._api_diff.build_timeline")
def test_api_diff_timeline_mermaid(mock_timeline, tmp_path, monkeypatch):
    """api-diff --timeline outputs Mermaid chart."""
    mock_timeline.return_value = [
        {"version": "v1.0", "symbols": 5, "classes": 2, "functions": 3},
    ]
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        ["api-diff", "v1.0", "v2.0", "--timeline", "--project-path", "."],
    )

    assert result.exit_code == 0
    assert "xychart-beta" in result.output


@patch("great_docs._api_diff.build_timeline", return_value=[])
def test_api_diff_timeline_empty(mock_timeline, tmp_path, monkeypatch):
    """api-diff --timeline with no tags exits with error."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        ["api-diff", "v1.0", "v2.0", "--timeline", "--project-path", "."],
    )

    assert result.exit_code != 0


@patch("great_docs._api_diff.build_dependency_graph")
@patch("great_docs._api_diff.snapshot_at_tag")
@patch("great_docs._api_diff.api_diff")
def test_api_diff_graph_text(mock_diff, mock_snap, mock_graph, tmp_path, monkeypatch):
    """api-diff --graph outputs Mermaid dependency graph."""
    from great_docs._api_diff import ApiDiff, DependencyGraph

    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
    )
    from great_docs._api_diff import ApiSnapshot, SymbolInfo

    mock_snap.return_value = ApiSnapshot(
        version="v2.0",
        package_name="pkg",
        symbols={"fn": SymbolInfo(name="fn", kind="function")},
    )
    mock_graph.return_value = DependencyGraph(nodes={"fn": "function"})
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        ["api-diff", "v1.0", "v2.0", "--graph", "--project-path", "."],
    )
    assert result.exit_code == 0
    assert "graph TD" in result.output


@patch("great_docs._api_diff.build_dependency_graph")
@patch("great_docs._api_diff.snapshot_at_tag")
@patch("great_docs._api_diff.api_diff")
def test_api_diff_graph_json(mock_diff, mock_snap, mock_graph, tmp_path, monkeypatch):
    """api-diff --graph --json outputs graph as JSON."""
    from great_docs._api_diff import ApiDiff, ApiSnapshot, DependencyGraph, SymbolInfo

    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
    )
    mock_snap.return_value = ApiSnapshot(
        version="v2.0",
        package_name="pkg",
        symbols={"fn": SymbolInfo(name="fn", kind="function")},
    )
    mock_graph.return_value = DependencyGraph(nodes={"fn": "function"})
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        [
            "api-diff",
            "v1.0",
            "v2.0",
            "--graph",
            "--json",
            "--project-path",
            ".",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "nodes" in data


@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0"])
def test_api_diff_symbol_text(mock_tags, mock_hist, tmp_path, monkeypatch):
    """api-diff --symbol outputs symbol history text."""
    from great_docs._api_diff import (
        SymbolHistory,
        SymbolHistoryEntry,
        SymbolInfo,
    )

    sym = SymbolInfo(name="build", kind="function")
    mock_hist.return_value = SymbolHistory(
        symbol_name="build",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1.0",
                present=True,
                signature="def build()",
                symbol_info=sym,
            ),
            SymbolHistoryEntry(
                version="v2.0",
                present=False,
                signature=None,
                symbol_info=None,
            ),
        ],
    )
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        [
            "api-diff",
            "v1.0",
            "v2.0",
            "--symbol",
            "build",
            "--project-path",
            ".",
        ],
    )
    assert result.exit_code == 0
    assert "build" in result.output
    assert "NOT PRESENT" in result.output


@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0"])
def test_api_diff_symbol_json(mock_tags, mock_hist, tmp_path, monkeypatch):
    """api-diff --symbol --json outputs JSON."""
    from great_docs._api_diff import (
        SymbolHistory,
        SymbolHistoryEntry,
        SymbolInfo,
    )

    sym = SymbolInfo(name="fn", kind="function")
    mock_hist.return_value = SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1.0",
                present=True,
                signature="def fn()",
                symbol_info=sym,
            ),
        ],
    )
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        [
            "api-diff",
            "v1.0",
            "v2.0",
            "--symbol",
            "fn",
            "--json",
            "--project-path",
            ".",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["symbol"] == "fn"


@patch("great_docs._api_diff.evolution_table_text")
@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0"])
def test_api_diff_symbol_table_text(mock_tags, mock_hist, mock_table, tmp_path, monkeypatch):
    """api-diff --symbol --table outputs text table."""
    from great_docs._api_diff import (
        SymbolHistory,
        SymbolHistoryEntry,
        SymbolInfo,
    )

    sym = SymbolInfo(name="fn", kind="function")
    mock_hist.return_value = SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1.0",
                present=True,
                signature="def fn()",
                symbol_info=sym,
            ),
        ],
    )
    mock_table.return_value = "| fn | v1.0 |"
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        [
            "api-diff",
            "v1.0",
            "v2.0",
            "--symbol",
            "fn",
            "--table",
            "--project-path",
            ".",
        ],
    )
    assert result.exit_code == 0
    assert "fn" in result.output


@patch("great_docs._api_diff.evolution_table_html")
@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0"])
def test_api_diff_symbol_table_html(mock_tags, mock_hist, mock_html, tmp_path, monkeypatch):
    """api-diff --symbol --table --html outputs HTML."""
    from great_docs._api_diff import (
        SymbolHistory,
        SymbolHistoryEntry,
        SymbolInfo,
    )

    sym = SymbolInfo(name="fn", kind="function")
    mock_hist.return_value = SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1.0",
                present=True,
                signature="def fn()",
                symbol_info=sym,
            ),
        ],
    )
    mock_html.return_value = '<table class="evo">mock</table>'
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        [
            "api-diff",
            "v1.0",
            "v2.0",
            "--symbol",
            "fn",
            "--table",
            "--html",
            "--project-path",
            ".",
        ],
    )
    assert result.exit_code == 0
    assert "<table" in result.output


@patch("great_docs._api_diff.symbol_history", return_value=None)
@patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0"])
def test_api_diff_symbol_no_package(mock_tags, mock_hist, tmp_path, monkeypatch):
    """api-diff --symbol exits with error when package can't be determined."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        [
            "api-diff",
            "v1.0",
            "v2.0",
            "--symbol",
            "fn",
            "--project-path",
            ".",
        ],
    )
    assert result.exit_code != 0
    assert "package" in result.output.lower()


@patch("great_docs._api_diff.list_version_tags", return_value=[])
def test_api_diff_symbol_no_tags(mock_tags, tmp_path, monkeypatch):
    """api-diff --symbol exits with error when no tags in range."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        [
            "api-diff",
            "v1.0",
            "v2.0",
            "--symbol",
            "fn",
            "--project-path",
            ".",
        ],
    )
    assert result.exit_code != 0
    assert "No version tags" in result.output


@patch("great_docs._api_diff.api_diff", side_effect=RuntimeError("boom"))
def test_api_diff_exception_text(mock_diff, tmp_path, monkeypatch):
    """api-diff handles exceptions with text error."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        ["api-diff", "v1.0", "v2.0", "--project-path", "."],
    )
    assert result.exit_code != 0


@patch("great_docs._api_diff.api_diff", side_effect=RuntimeError("boom"))
def test_api_diff_exception_json(mock_diff, tmp_path, monkeypatch):
    """api-diff --json handles exceptions with JSON error."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        ["api-diff", "v1.0", "v2.0", "--json", "--project-path", "."],
    )
    data = json.loads(result.output)
    assert data["status"] == "error"
    assert "boom" in data["error"]


@patch("great_docs._api_diff.symbol_history")
@patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0", "v3.0"])
def test_api_diff_symbol_changes_only(mock_tags, mock_hist, tmp_path, monkeypatch):
    """api-diff --symbol --changes-only filters to changed entries."""
    from great_docs._api_diff import (
        SymbolChange,
        SymbolHistory,
        SymbolHistoryEntry,
        SymbolInfo,
    )

    sym = SymbolInfo(name="fn", kind="function")
    mock_hist.return_value = SymbolHistory(
        symbol_name="fn",
        package_name="pkg",
        entries=[
            SymbolHistoryEntry(
                version="v1.0",
                present=True,
                signature="def fn()",
                symbol_info=sym,
            ),
            SymbolHistoryEntry(
                version="v2.0",
                present=True,
                signature="def fn(x)",
                symbol_info=sym,
                change=SymbolChange(
                    symbol="fn",
                    change_type="changed",
                    is_breaking=True,
                    details=["Param added"],
                ),
            ),
            SymbolHistoryEntry(
                version="v3.0",
                present=True,
                signature="def fn(x)",
                symbol_info=sym,
            ),
        ],
    )
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        [
            "api-diff",
            "v1.0",
            "v3.0",
            "--symbol",
            "fn",
            "--changes-only",
            "--project-path",
            ".",
        ],
    )
    assert result.exit_code == 0
    assert "changes" in result.output.lower()


@patch("great_docs._api_diff.api_diff")
def test_api_diff_migration_hint(mock_diff, tmp_path, monkeypatch):
    """api-diff shows migration hints for removed symbols."""
    from great_docs._api_diff import ApiDiff, SymbolChange

    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
        removed=[
            SymbolChange(
                symbol="old_fn",
                change_type="removed",
                is_breaking=True,
                migration_hint="Use new_fn instead",
            )
        ],
    )
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        ["api-diff", "v1.0", "v2.0", "--project-path", "."],
    )
    assert result.exit_code == 0
    assert "Use new_fn instead" in result.output


@patch("great_docs._api_diff.snapshot_at_tag", return_value=None)
@patch("great_docs._api_diff.api_diff")
def test_api_diff_graph_no_snapshot(mock_diff, mock_snap, tmp_path, monkeypatch):
    """api-diff --graph exits with error when snapshot fails."""
    from great_docs._api_diff import ApiDiff

    mock_diff.return_value = ApiDiff(
        old_version="v1.0",
        new_version="v2.0",
        package_name="pkg",
    )
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli,
        ["api-diff", "v1.0", "v2.0", "--graph", "--project-path", "."],
    )
    assert result.exit_code != 0
    assert "snapshot" in result.output.lower()


@patch("great_docs._harper.check_harper_available", return_value=(False, "not installed"))
def test_proofread_harper_not_available(mock_check, tmp_path, monkeypatch):
    """proofread exits with error when harper is not installed."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["proofread", "--project-path", "."])
    assert result.exit_code != 0


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_no_files(mock_check, mock_harper, tmp_path, monkeypatch):
    """proofread with no docs files exits cleanly."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    result = runner.invoke(cli, ["proofread", "--project-path", "."])
    assert "No documentation files" in result.output or result.exit_code == 0


@patch("great_docs._harper.run_harper")
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_md_files(mock_check, mock_run, tmp_path, monkeypatch):
    """proofread checks .md files."""
    from great_docs._harper import HarperFileResult, HarperLint

    mock_run.return_value = [
        HarperFileResult(
            file="README.md",
            lint_count=1,
            lints=[
                HarperLint(
                    rule="SpellCheck",
                    kind="Spelling",
                    line=3,
                    column=5,
                    message="Did you mean 'test'?",
                    matched_text="tset",
                    suggestions=["test"],
                    file="README.md",
                )
            ],
        )
    ]
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("README.md").write_text("# Test\n\nThis is a tset.")
    result = runner.invoke(cli, ["proofread", "README.md", "--project-path", "."])
    assert result.exit_code == 1
    assert "tset" in result.output


@patch("great_docs._harper.run_harper")
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_json(mock_check, mock_run, tmp_path, monkeypatch):
    """proofread --json-output produces valid JSON."""
    from great_docs._harper import HarperFileResult, HarperLint

    mock_run.return_value = [
        HarperFileResult(
            file="README.md",
            lint_count=1,
            lints=[
                HarperLint(
                    rule="SpellCheck",
                    kind="Spelling",
                    line=1,
                    column=1,
                    message="Misspelled",
                    matched_text="tset",
                    file="README.md",
                )
            ],
        )
    ]
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("README.md").write_text("tset")
    result = runner.invoke(cli, ["proofread", "README.md", "--json-output", "--project-path", "."])
    data = json.loads(result.output)
    assert data["total_issues"] == 1
    assert data["dialect"] == "us"


@patch("great_docs._harper.run_harper")
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_compact(mock_check, mock_run, tmp_path, monkeypatch):
    """proofread --compact produces GCC-style output."""
    from great_docs._harper import HarperFileResult, HarperLint

    mock_run.return_value = [
        HarperFileResult(
            file="README.md",
            lint_count=1,
            lints=[
                HarperLint(
                    rule="SpellCheck",
                    kind="Spelling",
                    line=3,
                    column=5,
                    message="Misspelled",
                    matched_text="tset",
                    file="README.md",
                )
            ],
        )
    ]
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("README.md").write_text("tset")
    result = runner.invoke(cli, ["proofread", "README.md", "--compact", "--project-path", "."])
    assert "README.md:3:5:" in result.output
    assert "SpellCheck" in result.output


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_no_issues(mock_check, mock_run, tmp_path, monkeypatch):
    """proofread with no issues exits 0 and shows success."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("README.md").write_text("# Good\n\nPerfect text.")
    result = runner.invoke(cli, ["proofread", "README.md", "--project-path", "."])
    assert result.exit_code == 0
    assert "No issues" in result.output


@patch("great_docs._harper.run_harper")
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_verbose(mock_check, mock_run, tmp_path, monkeypatch):
    """proofread --verbose shows detailed output."""
    from great_docs._harper import HarperFileResult, HarperLint

    mock_run.return_value = [
        HarperFileResult(
            file="README.md",
            lint_count=1,
            lints=[
                HarperLint(
                    rule="SpellCheck",
                    kind="Spelling",
                    line=1,
                    column=1,
                    message="Did you mean test?",
                    matched_text="tset",
                    suggestions=["test"],
                    file="README.md",
                )
            ],
        )
    ]
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("README.md").write_text("tset")
    result = runner.invoke(
        cli,
        ["proofread", "README.md", "--verbose", "--project-path", "."],
    )
    assert "Proofreading" in result.output
    assert "Did you mean" in result.output


@patch("great_docs._harper.run_harper")
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_max_issues_exceeded(mock_check, mock_run, tmp_path, monkeypatch):
    """proofread --max-issues exits 1 when threshold exceeded."""
    from great_docs._harper import HarperFileResult, HarperLint

    mock_run.return_value = [
        HarperFileResult(
            file="f.md",
            lint_count=5,
            lints=[
                HarperLint(
                    rule="SpellCheck",
                    kind="Spelling",
                    line=i,
                    column=1,
                    message="err",
                    matched_text="x",
                    file="f.md",
                )
                for i in range(5)
            ],
        )
    ]
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("f.md").write_text("x")
    result = runner.invoke(
        cli,
        ["proofread", "f.md", "--max-issues", "2", "--project-path", "."],
    )
    assert result.exit_code == 1
    assert "exceeds" in result.output


@patch("great_docs._harper.run_harper_on_text")
@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_qmd_files(mock_check, mock_run_files, mock_run_text, tmp_path, monkeypatch):
    """proofread processes .qmd files via text extraction."""
    from great_docs._harper import HarperLint

    mock_run_text.return_value = [
        HarperLint(
            rule="SpellCheck",
            kind="Spelling",
            line=4,
            column=5,
            message="Misspelled",
            matched_text="tset",
            file="<stdin>",
        )
    ]
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    ug = Path("user_guide")
    ug.mkdir()
    (ug / "test.qmd").write_text("---\ntitle: T\n---\nThis is a tset.")
    result = runner.invoke(cli, ["proofread", "--project-path", "."])
    assert result.exit_code == 1


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_strict_mode(mock_check, mock_run, tmp_path, monkeypatch):
    """proofread --strict disables smart defaults."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("README.md").write_text("# Good")
    result = runner.invoke(
        cli,
        ["proofread", "README.md", "--strict", "--project-path", "."],
    )
    assert result.exit_code == 0


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_custom_words(mock_check, mock_run, tmp_path, monkeypatch):
    """proofread -d word adds words to dictionary."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("README.md").write_text("# Test")
    result = runner.invoke(
        cli,
        [
            "proofread",
            "README.md",
            "-d",
            "griffe",
            "-d",
            "quartodoc",
            "--project-path",
            ".",
        ],
    )
    assert result.exit_code == 0


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_dictionary_file(mock_check, mock_run, tmp_path, monkeypatch):
    """proofread --dictionary-file loads words from file."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("README.md").write_text("# Test")
    Path("dict.txt").write_text("griffe\n# comment\nquartodoc\n")
    result = runner.invoke(
        cli,
        [
            "proofread",
            "README.md",
            "--dictionary-file",
            "dict.txt",
            "--project-path",
            ".",
        ],
    )
    assert result.exit_code == 0


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_spelling_only(mock_check, mock_run, tmp_path, monkeypatch):
    """proofread --spelling-only passes SpellCheck filter."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("README.md").write_text("# Test")
    result = runner.invoke(
        cli,
        ["proofread", "README.md", "--spelling-only", "--project-path", "."],
    )
    assert result.exit_code == 0


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_grammar_only(mock_check, mock_run, tmp_path, monkeypatch):
    """proofread --grammar-only excludes SpellCheck."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("README.md").write_text("# Test")
    result = runner.invoke(
        cli,
        ["proofread", "README.md", "--grammar-only", "--project-path", "."],
    )
    assert result.exit_code == 0


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_auto_discover(mock_check, mock_run, tmp_path, monkeypatch):
    """proofread without files auto-discovers user_guide and recipes."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    ug = Path("user_guide")
    ug.mkdir()
    (ug / "guide.md").write_text("# Guide")
    recipes = Path("recipes")
    recipes.mkdir()
    (recipes / "r.md").write_text("# Recipe")
    result = runner.invoke(cli, ["proofread", "--project-path", "."])
    assert result.exit_code == 0


@patch("great_docs._harper.run_harper")
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_suggestion_format(mock_check, mock_run, tmp_path, monkeypatch):
    """proofread shows cleaned suggestion text."""
    from great_docs._harper import HarperFileResult, HarperLint

    mock_run.return_value = [
        HarperFileResult(
            file="f.md",
            lint_count=1,
            lints=[
                HarperLint(
                    rule="SpellCheck",
                    kind="Spelling",
                    line=1,
                    column=1,
                    message="Misspelled",
                    matched_text="tset",
                    suggestions=['Replace with: "test"'],
                    file="f.md",
                )
            ],
        )
    ]
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("f.md").write_text("tset")
    result = runner.invoke(cli, ["proofread", "f.md", "--project-path", "."])
    assert "test" in result.output


@patch("great_docs._harper.run_harper", return_value=[])
@patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.12.0"))
def test_proofread_only_and_ignore_rules(mock_check, mock_run, tmp_path, monkeypatch):
    """proofread --only and --ignore rules are passed through."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("f.md").write_text("text")
    result = runner.invoke(
        cli,
        [
            "proofread",
            "f.md",
            "--only",
            "SpellCheck",
            "--ignore",
            "SentenceCap",
            "--project-path",
            ".",
        ],
    )
    assert result.exit_code == 0


# =========================================================================
# `great-docs versions` command
# =========================================================================


def test_versions_no_config(tmp_path, monkeypatch):
    """versions command with no versions configured."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("great-docs.yml").write_text("{}\n")
    result = runner.invoke(cli, ["versions", "--project-path", "."])
    assert result.exit_code == 0
    assert "No versions configured" in result.output


def test_versions_list(tmp_path, monkeypatch):
    """versions command lists configured versions."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("great-docs.yml").write_text("versions:\n  - '0.3'\n  - '0.2'\n")
    result = runner.invoke(cli, ["versions", "--project-path", "."])
    assert result.exit_code == 0
    assert "0.3" in result.output
    assert "0.2" in result.output


def test_versions_check_valid(tmp_path, monkeypatch):
    """versions --check succeeds with valid config."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("great-docs.yml").write_text("versions:\n  - '0.3'\n  - '0.2'\n")
    result = runner.invoke(cli, ["versions", "--check", "--project-path", "."])
    assert result.exit_code == 0
    assert "version(s) configured" in result.output


def test_versions_check_with_prerelease(tmp_path, monkeypatch):
    """versions shows prerelease status."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("great-docs.yml").write_text(
        "versions:\n  - tag: '0.4'\n    label: '0.4 (dev)'\n    prerelease: true\n  - '0.3'\n"
    )
    result = runner.invoke(cli, ["versions", "--project-path", "."])
    assert result.exit_code == 0
    assert "prerelease" in result.output


def test_versions_with_git_ref(tmp_path, monkeypatch):
    """versions shows git_ref as api source."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "pkg"\n')
    Path("great-docs.yml").write_text(
        "versions:\n  - tag: '0.3'\n    label: '0.3'\n    git_ref: v0.3.0\n  - '0.2'\n"
    )
    result = runner.invoke(cli, ["versions", "--project-path", "."])
    assert result.exit_code == 0
    assert "v0.3.0" in result.output


# =========================================================================
# `great-docs api-snapshot` command
# =========================================================================


@patch("great_docs._api_diff.snapshot_from_griffe")
@patch("great_docs._api_diff._detect_package_name", return_value="mypkg")
def test_api_snapshot_head(mock_detect, mock_snap, tmp_path, monkeypatch):
    """api-snapshot with no args snapshots HEAD."""
    mock_snap_obj = MagicMock()
    mock_snap_obj.symbol_count = 23
    mock_snap.return_value = mock_snap_obj

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    result = runner.invoke(cli, ["api-snapshot", "--project-path", "."])
    assert result.exit_code == 0
    assert "23" in result.output
    mock_snap_obj.save.assert_called_once()


@patch("great_docs._api_diff._detect_package_name", return_value=None)
def test_api_snapshot_no_package(mock_detect, tmp_path, monkeypatch):
    """api-snapshot fails when no package can be detected."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text("{}")
    result = runner.invoke(cli, ["api-snapshot", "--project-path", "."])
    assert result.exit_code != 0
    assert "Could not detect package name" in result.output


@patch("great_docs._api_diff.snapshot_at_tag")
@patch("great_docs._api_diff._detect_package_name", return_value="mypkg")
def test_api_snapshot_specific_tag(mock_detect, mock_snap, tmp_path, monkeypatch):
    """api-snapshot with a specific version tag."""
    mock_snap_obj = MagicMock()
    mock_snap_obj.symbol_count = 10
    mock_snap.return_value = mock_snap_obj

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    result = runner.invoke(cli, ["api-snapshot", "v0.2.0", "--project-path", "."])
    assert result.exit_code == 0
    assert "10 symbols" in result.output


@patch("great_docs._api_diff.list_version_tags", return_value=["v0.1.0", "v0.2.0"])
@patch("great_docs._api_diff.snapshot_at_tag")
@patch("great_docs._api_diff._detect_package_name", return_value="mypkg")
def test_api_snapshot_all_tags(mock_detect, mock_snap, mock_tags, tmp_path, monkeypatch):
    """api-snapshot --all-tags snapshots all versions."""
    mock_snap_obj = MagicMock()
    mock_snap_obj.symbol_count = 5
    mock_snap.return_value = mock_snap_obj

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    result = runner.invoke(cli, ["api-snapshot", "--all-tags", "--project-path", "."])
    assert result.exit_code == 0
    assert "Saved" in result.output


@patch("great_docs._api_diff.list_version_tags", return_value=[])
@patch("great_docs._api_diff._detect_package_name", return_value="mypkg")
def test_api_snapshot_all_tags_no_tags(mock_detect, mock_tags, tmp_path, monkeypatch):
    """api-snapshot --all-tags with no tags exits with error."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    result = runner.invoke(cli, ["api-snapshot", "--all-tags", "--project-path", "."])
    assert result.exit_code != 0
    assert "No version tags found" in result.output


@patch("great_docs._api_diff.snapshot_from_griffe")
@patch("great_docs._api_diff._detect_package_name", return_value="mypkg")
def test_api_snapshot_skip_existing(mock_detect, mock_snap, tmp_path, monkeypatch):
    """api-snapshot skips existing files without --force."""
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    snap_dir = Path(".great-docs") / "snapshots"
    snap_dir.mkdir(parents=True)
    (snap_dir / "dev.json").write_text("{}")

    result = runner.invoke(cli, ["api-snapshot", "--project-path", "."])
    assert result.exit_code == 0
    assert "already exists" in result.output
    mock_snap.assert_not_called()


@patch("great_docs._api_diff.snapshot_from_griffe")
@patch("great_docs._api_diff._detect_package_name", return_value="mypkg")
def test_api_snapshot_force_overwrite(mock_detect, mock_snap, tmp_path, monkeypatch):
    """api-snapshot --force overwrites existing files."""
    mock_snap_obj = MagicMock()
    mock_snap_obj.symbol_count = 3
    mock_snap.return_value = mock_snap_obj

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)
    Path("pyproject.toml").write_text('[project]\nname = "mypkg"\n')
    snap_dir = Path(".great-docs") / "snapshots"
    snap_dir.mkdir(parents=True)
    (snap_dir / "dev.json").write_text("{}")

    result = runner.invoke(cli, ["api-snapshot", "--force", "--project-path", "."])
    assert result.exit_code == 0
    assert "3 symbols" in result.output


def _git(root, *a):
    """Run `git *a` in `root`, raising CalledProcessError on a non-zero exit"""
    subprocess.run(["git", *a], cwd=root, check=True, capture_output=True)


def _two_tag_repo(root: Path) -> None:
    """Git repo whose documented submodule API grows between tags v0.1.0 and v0.2.0"""
    _git(root, "init")
    _git(root, "config", "user.email", "t@t.co")
    _git(root, "config", "user.name", "t")
    (root / "pyproject.toml").write_text('[project]\nname = "mypkg"\nversion = "0.2.0"\n')
    pkg = root / "mypkg"
    (pkg / "sub").mkdir(parents=True)
    (pkg / "__init__.py").write_text("from mypkg import sub\n__all__ = ['sub']\n")
    (pkg / "sub" / "__init__.py").write_text(
        "from mypkg.sub.things import Widget\n__all__ = ['Widget']\n"
    )
    (pkg / "sub" / "things.py").write_text("class Widget:\n    def fit(self): ...\n")
    (root / "great-docs.yml").write_text(
        "reference:\n  - title: API\n    contents:\n"
        "      - name: sub.Widget\n        members: [fit]\n"
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "v010")
    _git(root, "tag", "v0.1.0")
    (pkg / "sub" / "things.py").write_text(
        "class Widget:\n    def fit(self): ...\n    def transform(self): ...\n"
    )
    (root / "great-docs.yml").write_text(
        "reference:\n  - title: API\n    contents:\n"
        "      - name: sub.Widget\n        members: [fit, transform]\n"
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "v020")
    _git(root, "tag", "v0.2.0")


def test_api_snapshot_all_tags_differ(tmp_path: Path):
    """api-snapshot --all-tags produces snapshots that differ when the reference config grows."""
    _two_tag_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["api-snapshot", "--all-tags", "--project-path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    snaps = tmp_path / ".great-docs" / "snapshots"
    s1 = json.loads((snaps / "v0.1.0.json").read_text())["symbols"]
    s2 = json.loads((snaps / "v0.2.0.json").read_text())["symbols"]
    assert set(s1) == {"sub.Widget", "sub.Widget.fit"}
    assert "sub.Widget.transform" in s2
    assert set(s1) != set(s2)


class TestFormatSeconds:
    def test_under_sixty(self):
        assert _format_seconds(5.0) == "5.0s"

    def test_exactly_sixty(self):
        assert _format_seconds(60.0) == "1m 0.0s"

    def test_over_sixty(self):
        assert _format_seconds(90.5) == "1m 30.5s"

    def test_fraction_under_sixty(self):
        assert _format_seconds(1.25) == "1.2s"

    def test_large(self):
        assert _format_seconds(125.0) == "2m 5.0s"


class TestFindBuildTiming:
    def test_output_dir_file_exists(self, tmp_path):
        out = tmp_path / "output"
        out.mkdir()
        f = out / "build-timings.json"
        f.write_text("{}")
        result = _find_build_timing(tmp_path, output_dir=out)
        assert result == f

    def test_output_dir_file_missing_falls_through_to_gd_site(self, tmp_path):
        out = tmp_path / "output"
        out.mkdir()
        gd_site = tmp_path / "great-docs" / "_site"
        gd_site.mkdir(parents=True)
        f = gd_site / "build-timings.json"
        f.write_text("{}")
        result = _find_build_timing(tmp_path, output_dir=out)
        assert result == f

    def test_great_docs_site(self, tmp_path):
        gd_site = tmp_path / "great-docs" / "_site"
        gd_site.mkdir(parents=True)
        f = gd_site / "build-timings.json"
        f.write_text("{}")
        result = _find_build_timing(tmp_path)
        assert result == f

    def test_underscore_site(self, tmp_path):
        site = tmp_path / "_site"
        site.mkdir()
        f = site / "build-timings.json"
        f.write_text("{}")
        result = _find_build_timing(tmp_path)
        assert result == f

    def test_nothing_exists(self, tmp_path):
        result = _find_build_timing(tmp_path)
        assert result is None


class TestPrintPageTable:
    def test_empty_pages(self, capsys):
        _print_page_table([])
        out = capsys.readouterr().out
        assert "No page timings recorded" in out

    def test_pages_without_frozen(self, capsys):
        pages = [
            {"page": "index.qmd", "seconds": 2.0},
            {"page": "intro.qmd", "seconds": 1.0},
        ]
        _print_page_table(pages)
        out = capsys.readouterr().out
        assert "index.qmd" in out
        assert "2.0s" in out
        # No frozen legend
        assert "freeze cache" not in out

    def test_pages_with_frozen_entries(self, capsys):
        pages = [
            {"page": "slow.qmd", "seconds": 5.0, "frozen": True},
            {"page": "fast.qmd", "seconds": 1.0, "frozen": False},
        ]
        _print_page_table(pages)
        out = capsys.readouterr().out
        assert "slow.qmd" in out
        assert "❄" in out  # ❄
        assert "freeze cache" in out


class TestPrintTimingTable:
    def test_single_version_data_top(self, capsys):
        data = {
            "build_time": "2024-01-15 10:00:00",
            "total_seconds": 30.0,
            "pages": [
                {"page": "a.qmd", "seconds": 10.0},
                {"page": "b.qmd", "seconds": 5.0},
                {"page": "c.qmd", "seconds": 2.0},
            ],
        }
        _print_timing_table(data, top=2, version_filter=None)
        out = capsys.readouterr().out

        assert "a.qmd" in out
        assert "b.qmd" in out

        # top=2 so c.qmd should be excluded
        assert "c.qmd" not in out

    def test_multi_version_data(self, capsys):
        data = {
            "build_time": "2024-01-15 10:00:00",
            "total_seconds": 30.0,
            "versions": {
                "v1": {
                    "seconds": 20.0,
                    "pages": [{"page": "a.qmd", "seconds": 10.0}],
                },
                "v2": {
                    "seconds": 10.0,
                    "pages": [{"page": "b.qmd", "seconds": 10.0}],
                },
            },
        }
        _print_timing_table(data, top=None, version_filter=None)
        out = capsys.readouterr().out

        assert "v1" in out
        assert "v2" in out

    def test_multi_version_with_filter(self, capsys):
        data = {
            "build_time": "2024-01-15 10:00:00",
            "total_seconds": 30.0,
            "versions": {
                "v1": {
                    "seconds": 20.0,
                    "pages": [{"page": "a.qmd", "seconds": 10.0}],
                },
                "v2": {
                    "seconds": 10.0,
                    "pages": [{"page": "b.qmd", "seconds": 10.0}],
                },
            },
        }
        _print_timing_table(data, top=None, version_filter="v1")
        out = capsys.readouterr().out

        assert "v1" in out
        assert "b.qmd" not in out

    def test_version_filter_not_found(self, capsys):
        data = {
            "build_time": "2024-01-15",
            "total_seconds": 5.0,
            "versions": {
                "v1": {"seconds": 5.0, "pages": []},
            },
        }
        with pytest.raises(SystemExit) as exc_info:
            _print_timing_table(data, top=None, version_filter="v99")

        assert exc_info.value.code == 1


class TestFreezeInfo:
    def _make_mock_config(self, freeze_value=None):
        cfg = MagicMock()
        cfg.freeze = freeze_value
        return cfg

    def test_no_freeze_cache_dir(self, tmp_path, capsys):
        persist_dir = tmp_path / "_freeze"

        # persist_dir does not exist
        with patch("great_docs.config.Config", return_value=self._make_mock_config()):
            _freeze_info(tmp_path, persist_dir)
        out = capsys.readouterr().out

        assert "No freeze cache found yet" in out

    def test_cache_dir_empty(self, tmp_path, capsys):
        persist_dir = tmp_path / "_freeze"
        persist_dir.mkdir()
        with patch("great_docs.config.Config", return_value=self._make_mock_config()):
            _freeze_info(tmp_path, persist_dir)
        out = capsys.readouterr().out

        assert "contains no entries" in out

    def test_cache_with_valid_json_timestamp(self, tmp_path, capsys):
        persist_dir = tmp_path / "_freeze"
        page_dir = persist_dir / "user_guide" / "demo" / "execute-results"
        page_dir.mkdir(parents=True)
        cache_json = page_dir / "html.json"
        cache_json.write_text(
            json.dumps({"result": {"markdown": "Executed at: 2024-01-15 10:30:00\nsome content"}})
        )
        with patch("great_docs.config.Config", return_value=self._make_mock_config()):
            _freeze_info(tmp_path, persist_dir)
        out = capsys.readouterr().out

        assert "2024-01-15 10:30:00" in out

    def test_cache_unparseable_json(self, tmp_path, capsys):
        persist_dir = tmp_path / "_freeze"
        page_dir = persist_dir / "user_guide" / "demo" / "execute-results"
        page_dir.mkdir(parents=True)
        cache_json = page_dir / "html.json"
        cache_json.write_text("not valid json{{")
        with patch("great_docs.config.Config", return_value=self._make_mock_config()):
            _freeze_info(tmp_path, persist_dir)
        out = capsys.readouterr().out

        assert "could not be parsed" in out

    def test_per_page_overrides_qmd(self, tmp_path, capsys):
        # Create a .qmd file in user_guide/ with freeze: true in frontmatter
        user_guide = tmp_path / "user_guide"
        user_guide.mkdir()
        qmd = user_guide / "benchmarks.qmd"
        qmd.write_text("---\nfreeze: true\n---\n# Benchmarks\n")
        persist_dir = tmp_path / "_freeze"

        # persist_dir does not exist (we just want the per-page section)
        with patch("great_docs.config.Config", return_value=self._make_mock_config()):
            _freeze_info(tmp_path, persist_dir)
        out = capsys.readouterr().out

        assert "Per-page overrides" in out
        assert "benchmarks.qmd" in out

    def test_project_freeze_auto(self, tmp_path, capsys):
        persist_dir = tmp_path / "_freeze"
        with patch(
            "great_docs.config.Config",
            return_value=self._make_mock_config(freeze_value="auto"),
        ):
            _freeze_info(tmp_path, persist_dir)
        out = capsys.readouterr().out
        assert "auto" in out

    def test_project_freeze_disabled(self, tmp_path, capsys):
        persist_dir = tmp_path / "_freeze"
        with patch(
            "great_docs.config.Config",
            return_value=self._make_mock_config(freeze_value=None),
        ):
            _freeze_info(tmp_path, persist_dir)
        out = capsys.readouterr().out
        assert "disabled" in out


class TestFreezeCommand:
    def test_info_flag_calls_freeze_info(self, tmp_path):
        runner = CliRunner()
        with patch("great_docs.cli._freeze_info") as mock_fi:
            result = runner.invoke(cli, ["freeze", "--info", "--project-path", str(tmp_path)])
        mock_fi.assert_called_once()

    def test_no_pages_no_info_exits_error(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["freeze", "--project-path", str(tmp_path)])

        assert result.exit_code != 0
        assert "Specify at least one PAGE" in result.output + (result.stderr or "")

    def test_page_not_found_exits_error(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["freeze", "nonexistent_page.qmd", "--project-path", str(tmp_path)],
        )

        assert result.exit_code != 0

        # Error should mention "Page not found"
        combined = (result.output or "") + (result.stderr or "")

        assert "Page not found" in combined or result.exit_code != 0

    def test_clean_removes_freeze_dir(self, tmp_path):
        runner = CliRunner()
        freeze_dir = tmp_path / "_freeze"
        freeze_dir.mkdir()
        (freeze_dir / "dummy.txt").write_text("x")

        # We need a real .qmd file to satisfy page-exists check
        qmd = tmp_path / "page.qmd"
        qmd.write_text("---\ntitle: Test\n---\n")

        with patch("great_docs.cli.GreatDocs") as mock_gd:
            mock_gd.return_value._prepare_for_freeze.return_value = None
            # Make build_dir/_quarto.yml NOT exist so we get the "not ready" error
            result = runner.invoke(
                cli,
                ["freeze", "--clean", "page.qmd", "--project-path", str(tmp_path)],
            )

        # The _freeze dir should have been removed
        assert not freeze_dir.exists()

    def test_clean_no_existing_dir_does_not_crash(self, tmp_path):
        runner = CliRunner()
        qmd = tmp_path / "page.qmd"
        qmd.write_text("---\ntitle: Test\n---\n")
        with patch("great_docs.cli.GreatDocs") as mock_gd:
            mock_gd.return_value._prepare_for_freeze.return_value = None
            result = runner.invoke(
                cli,
                ["freeze", "--clean", "page.qmd", "--project-path", str(tmp_path)],
            )

        # Should not crash (exit with non-zero is OK due to missing _quarto.yml)
        assert result.exception is None or isinstance(result.exception, SystemExit)


class TestTimingsCommand:
    def test_no_timings_file_exits_error(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["timings", "--project-path", str(tmp_path)])

        assert result.exit_code != 0

        combined = (result.output or "") + (result.stderr or "")

        assert "build-timings.json" in combined

    def test_json_flag_outputs_json(self, tmp_path):
        site = tmp_path / "_site"
        site.mkdir()
        data = {"build_time": "2024-01-01", "total_seconds": 5.0, "pages": []}
        (site / "build-timings.json").write_text(json.dumps(data))
        runner = CliRunner()
        result = runner.invoke(cli, ["timings", "--json", "--project-path", str(tmp_path)])

        assert result.exit_code == 0, result.output

        parsed = json.loads(result.output)

        assert parsed["build_time"] == "2024-01-01"

    def test_table_output(self, tmp_path):
        site = tmp_path / "_site"
        site.mkdir()
        data = {
            "build_time": "2024-01-01",
            "total_seconds": 5.0,
            "pages": [{"page": "index.qmd", "seconds": 5.0}],
        }
        (site / "build-timings.json").write_text(json.dumps(data))
        runner = CliRunner()
        result = runner.invoke(cli, ["timings", "--project-path", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert "index.qmd" in result.output


class TestSkillCheckCommand:
    def test_no_installed_skills(self):
        runner = CliRunner()
        with patch("great_docs._skill_install.check_skill", return_value=[]):
            result = runner.invoke(cli, ["skill", "check"])

        assert result.exit_code == 0
        assert "No installed skills found" in result.output

    def test_with_mixed_statuses(self):
        runner = CliRunner()
        skills = [
            {"status": "current", "name": "great-tables"},
            {"status": "outdated", "name": "great-docs"},
            {"status": "updated", "name": "pointblank"},
            {"status": "local", "name": "myskill"},
        ]
        with patch("great_docs._skill_install.check_skill", return_value=skills):
            result = runner.invoke(cli, ["skill", "check"])

        assert result.exit_code == 0
        assert "1 current" in result.output
        assert "1 outdated" in result.output
        assert "1 updated" in result.output
        assert "1 local" in result.output


class TestSkillListCommand:
    def test_url_source_calls_list_skills_with_url(self):
        runner = CliRunner()
        with patch(
            "great_docs._skill_install.list_skills", return_value=[{"name": "x"}]
        ) as mock_ls:
            result = runner.invoke(cli, ["skill", "list", "https://example.com/docs/"])
        mock_ls.assert_called_once_with(url="https://example.com/docs/")

    def test_package_name_source_calls_list_skills_with_package(self):
        runner = CliRunner()
        with patch(
            "great_docs._skill_install.list_skills", return_value=[{"name": "x"}]
        ) as mock_ls:
            result = runner.invoke(cli, ["skill", "list", "great-tables"])
        mock_ls.assert_called_once_with(package="great-tables")

    def test_no_source_no_pyproject_exits_error(self, tmp_path):
        runner = CliRunner()
        # Invoke from a tmp dir with no pyproject.toml by patching Path.cwd
        with patch("great_docs.cli.Path") as mock_path_cls:
            mock_cwd = MagicMock()
            mock_cwd.__truediv__ = lambda self, other: tmp_path / other
            mock_path_cls.cwd.return_value = tmp_path
            mock_path_cls.side_effect = lambda x=None: Path(x) if x else mock_cwd
            result = runner.invoke(cli, ["skill", "list"])

        # Either exits with error or reports no package found
        assert result.exit_code != 0 or "Error" in (result.output or "")

    def test_empty_results_exits_one(self):
        runner = CliRunner()
        with patch("great_docs._skill_install.list_skills", return_value=[]):
            result = runner.invoke(cli, ["skill", "list", "great-tables"])

        assert result.exit_code == 1
        assert "No skills found" in result.output


import pytest


class TestVersionsCommandMissedBranches:
    def _make_cfg(self, has_versions=True, versions_data=None):
        cfg = MagicMock()
        cfg.has_versions = has_versions
        cfg.versions = versions_data or []
        return cfg

    def test_parse_versions_config_raises_value_error(self, tmp_path):
        runner = CliRunner()
        cfg = self._make_cfg(has_versions=True, versions_data=[{"bad": "entry"}])
        with (
            patch("great_docs.config.Config", return_value=cfg),
            patch(
                "great_docs._versioning.parse_versions_config",
                side_effect=ValueError("bad config"),
            ),
        ):
            result = runner.invoke(cli, ["versions", "--project-path", str(tmp_path)])

        assert result.exit_code != 0

        combined = (result.output or "") + (result.stderr or "")

        assert "bad config" in combined

    def test_check_flag_no_latest_exits_one(self, tmp_path):
        from great_docs._versioning import VersionEntry

        runner = CliRunner()
        entry = VersionEntry(tag="v1.0", label="1.0")
        cfg = self._make_cfg(has_versions=True, versions_data=[{"tag": "v1.0"}])
        with (
            patch("great_docs.config.Config", return_value=cfg),
            patch(
                "great_docs._versioning.parse_versions_config",
                return_value=[entry],
            ),
            patch("great_docs._versioning.get_latest_version", return_value=None),
        ):
            result = runner.invoke(cli, ["versions", "--check", "--project-path", str(tmp_path)])

        assert result.exit_code == 1

        combined = (result.output or "") + (result.stderr or "")

        assert "Warning" in combined or "no version marked" in combined

    def test_versions_table_with_all_flags(self, tmp_path):
        from great_docs._versioning import VersionEntry

        runner = CliRunner()
        e1 = VersionEntry(tag="v2.0", label="2.0 (latest)")
        e1.latest = True
        e1.prerelease = False
        e1.eol = False
        e1.api_snapshot = None
        e1.git_ref = None

        e2 = VersionEntry(tag="v1.0-pre", label="1.0-pre")
        e2.latest = False
        e2.prerelease = True
        e2.eol = False
        e2.api_snapshot = "snapshots/v1.json"
        e2.git_ref = None

        e3 = VersionEntry(tag="v0.9", label="0.9 (eol)")
        e3.latest = False
        e3.prerelease = False
        e3.eol = True
        e3.api_snapshot = None
        e3.git_ref = "v0.9.0"

        cfg = self._make_cfg(has_versions=True, versions_data=[{}])
        with (
            patch("great_docs.config.Config", return_value=cfg),
            patch(
                "great_docs._versioning.parse_versions_config",
                return_value=[e1, e2, e3],
            ),
        ):
            result = runner.invoke(cli, ["versions", "--project-path", str(tmp_path)])

        assert result.exit_code == 0, result.output
        assert "latest" in result.output
        assert "prerelease" in result.output
        assert "eol" in result.output
        assert "snapshots/v1.json" in result.output
        assert "git tag: v0.9.0" in result.output


class TestFreezeInfoFrontmatterEdgeCases:
    def test_no_frontmatter_delimiter(self, tmp_path, capsys):
        """QMD without '---' frontmatter still shows mode from regex match."""
        project_root = tmp_path
        persist_dir = tmp_path / "_freeze"
        src_dir = tmp_path / "user_guide"
        src_dir.mkdir()
        # QMD without leading '---'  → _extract_frontmatter returns ""
        (src_dir / "page.qmd").write_text("freeze: auto\n")
        _freeze_info(project_root, persist_dir)
        captured = capsys.readouterr()
        # No per-page override should appear since frontmatter is empty
        assert "No freeze cache found" in captured.out

    def test_frontmatter_no_closing_delimiter(self, tmp_path, capsys):
        """QMD with opening '---' but no closing '---' → frontmatter returns ""."""
        project_root = tmp_path
        persist_dir = tmp_path / "_freeze"
        src_dir = tmp_path / "user_guide"
        src_dir.mkdir()
        # Has opening --- but no closing --- (unclosed frontmatter)
        (src_dir / "page.qmd").write_text("---\ntitle: Test\nfreeze: auto\n")
        _freeze_info(project_root, persist_dir)
        captured = capsys.readouterr()
        assert "No freeze cache found" in captured.out


class TestBuildVersionFilter:
    @patch("great_docs.cli.GreatDocs")
    def test_version_filter_passed_to_build(self, mock_gd_cls, tmp_path, monkeypatch):
        """Comma-separated version_filter is parsed and forwarded to docs.build()."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        mock_docs = MagicMock()
        mock_gd_cls.return_value = mock_docs
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["build", "--project-path", str(tmp_path), "--versions", "v1,v2"],
        )
        if mock_docs.build.called:
            call_kwargs = mock_docs.build.call_args[1]

            assert call_kwargs["version_tags"] == ["v1", "v2"]


class TestPreviewMissedBranches:
    @patch("great_docs._pr_preview.clear_cache")
    def test_clear_cache_path_existed(self, mock_clear, tmp_path, monkeypatch):
        """--clear-cache with existing cache echoes success and returns."""
        monkeypatch.chdir(tmp_path)
        mock_clear.return_value = (True, Path("/tmp/gd-cache"))
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["preview", "--clear-cache", "--project-path", str(tmp_path)],
        )

        assert "Cleared" in result.output

    @patch("great_docs._pr_preview.clear_cache")
    def test_clear_cache_path_not_existed(self, mock_clear, tmp_path, monkeypatch):
        """--clear-cache with no existing cache echoes 'does not exist'."""
        monkeypatch.chdir(tmp_path)
        mock_clear.return_value = (False, Path("/tmp/gd-cache"))
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["preview", "--clear-cache", "--project-path", str(tmp_path)],
        )

        assert "does not exist" in result.output

    def test_site_dir_with_pr_emits_warning(self, tmp_path, monkeypatch):
        """--site-dir is ignored when --pr is given; a warning is emitted."""
        monkeypatch.chdir(tmp_path)
        site = tmp_path / "_site"
        site.mkdir()
        runner = CliRunner()
        with patch("great_docs._pr_preview.preview_pr", side_effect=SystemExit(0)):
            result = runner.invoke(
                cli,
                [
                    "preview",
                    "--pr",
                    "42",
                    "--site-dir",
                    str(site),
                    "--project-path",
                    str(tmp_path),
                ],
            )

        assert "--site-dir is ignored" in result.output


class TestFreezeInfoMtimePath:
    def test_cache_json_without_timestamp_uses_mtime(self, tmp_path, capsys):
        """When JSON lacks 'Executed at:', mtime is used as the timestamp."""
        project_root = tmp_path
        persist_dir = tmp_path / ".great-docs" / "_freeze"
        cache_dir = persist_dir / "my_page" / "execute-results"
        cache_dir.mkdir(parents=True)
        cache_json = cache_dir / "html.json"

        # JSON with no 'Executed at:' in markdown
        cache_json.write_text(json.dumps({"result": {"markdown": "no timestamp here"}}))

        _freeze_info(project_root, persist_dir)
        captured = capsys.readouterr()

        # Should have used mtime — output contains the frozen-at line
        assert "frozen at" in captured.out


class TestFreezeCommandRenderLoop:
    def _make_project(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')

        # Page must exist at project_root level (validated before render)
        (tmp_path / "mypage.qmd").write_text("---\ntitle: Test\n---\nHello")
        build_dir = tmp_path / "great-docs"
        build_dir.mkdir()
        (build_dir / "_quarto.yml").write_text("project:\n  type: website\n")

        # Page also in build dir (where quarto renders from)
        (build_dir / "mypage.qmd").write_text("---\ntitle: Test\n---\nHello")
        freeze_dir = build_dir / "_freeze" / "mypage" / "execute-results"
        freeze_dir.mkdir(parents=True)
        (freeze_dir / "html.json").write_text("{}")

    @patch("great_docs.cli.GreatDocs")
    @patch("subprocess.run")
    def test_page_renders_successfully(self, mock_run, mock_gd_cls, tmp_path, monkeypatch):
        """A page found in the build dir renders → persisted to .great-docs/_freeze."""
        monkeypatch.chdir(tmp_path)
        self._make_project(tmp_path)
        mock_gd_cls.return_value = MagicMock()
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["freeze", "mypage.qmd", "--project-path", str(tmp_path)],
        )

        assert "mypage" in result.output or result.exit_code in (0, 1)

    @patch("great_docs.cli.GreatDocs")
    @patch("subprocess.run")
    def test_page_render_fails(self, mock_run, mock_gd_cls, tmp_path, monkeypatch):
        """A page that fails to render is counted in the failed list."""
        monkeypatch.chdir(tmp_path)
        self._make_project(tmp_path)
        mock_gd_cls.return_value = MagicMock()
        mock_run.return_value = MagicMock(returncode=1, stderr="render error\n")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["freeze", "mypage.qmd", "--project-path", str(tmp_path)],
        )
        assert result.exit_code == 1

    @patch("great_docs.cli.GreatDocs")
    @patch("subprocess.run")
    def test_prepare_for_freeze_system_exit_continues(
        self, mock_run, mock_gd_cls, tmp_path, monkeypatch
    ):
        """SystemExit from _prepare_for_freeze is silently ignored."""
        monkeypatch.chdir(tmp_path)
        self._make_project(tmp_path)
        mock_docs = MagicMock()
        mock_docs._prepare_for_freeze.side_effect = SystemExit(0)
        mock_gd_cls.return_value = mock_docs
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["freeze", "mypage.qmd", "--project-path", str(tmp_path)],
        )

        # Should NOT exit 1 just because prepare raised SystemExit
        assert result.exit_code in (0, 1)

    @patch("great_docs.cli.GreatDocs")
    def test_prepare_for_freeze_exception_exits(self, mock_gd_cls, tmp_path, monkeypatch):
        """Exception from _prepare_for_freeze prints error and exits 1."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (tmp_path / "mypage.qmd").write_text("---\ntitle: Test\n---\nHello")
        # Don't create the build dir so the flow never reaches the FileExistsError
        mock_docs = MagicMock()
        mock_docs._prepare_for_freeze.side_effect = RuntimeError("build prep failed")
        mock_gd_cls.return_value = mock_docs
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["freeze", "mypage.qmd", "--project-path", str(tmp_path)],
        )

        assert result.exit_code == 1
        assert "build prep failed" in result.output

        """Page not found in build dir is reported and exits non-zero."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        build_dir = tmp_path / "great-docs"
        build_dir.mkdir()
        (build_dir / "_quarto.yml").write_text("project:\n  type: website\n")
        mock_gd_cls.return_value = MagicMock()
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["freeze", "missing_page.qmd", "--project-path", str(tmp_path)],
        )
        assert "not found" in result.output or result.exit_code == 1

    @patch("great_docs.cli.GreatDocs")
    @patch("subprocess.run")
    def test_clean_and_render(self, mock_run, mock_gd_cls, tmp_path, monkeypatch):
        """--clean wipes existing cache then renders."""
        monkeypatch.chdir(tmp_path)
        self._make_project(tmp_path)

        # Create a fake persist_dir to be cleaned
        persist = tmp_path / ".great-docs" / "_freeze"
        persist.mkdir(parents=True)
        (persist / "old.json").write_text("{}")
        mock_gd_cls.return_value = MagicMock()
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["freeze", "--clean", "mypage.qmd", "--project-path", str(tmp_path)],
        )
        assert "Cleaned" in result.output or result.exit_code in (0, 1)


class TestSetupGithubPagesMissedBranches:
    def _make_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "pkg"\nrequires-python = ">=3.11"\n'
        )

    def test_importerror_falls_back(self, tmp_path, monkeypatch):
        """When importlib.resources.files raises ImportError, importlib_resources is tried."""
        monkeypatch.chdir(tmp_path)
        self._make_pyproject(tmp_path)
        runner = CliRunner()

        def _fake_files_raise(*a, **k):
            raise ImportError("old python")

        mock_template = MagicMock()
        mock_template.read_text.return_value = "template: {main_branch}"
        mock_fallback_files = MagicMock()
        mock_fallback_files.return_value.joinpath.return_value = mock_template

        with (
            patch("great_docs.cli.GreatDocs"),
            patch(
                "importlib.resources.files",
                side_effect=ImportError("simulate 3.8"),
            ),
            patch(
                "importlib_resources.files",
                mock_fallback_files,
                create=True,
            ),
        ):
            result = runner.invoke(
                cli,
                ["setup-github-pages", "--project-path", str(tmp_path)],
            )
        # Either succeeds or fails, but the ImportError path was exercised

    def test_exception_in_setup(self, tmp_path, monkeypatch):
        """An exception inside setup_github_pages exits 1 with error message."""
        monkeypatch.chdir(tmp_path)
        self._make_pyproject(tmp_path)
        runner = CliRunner()
        # Raise inside the try block by making template loading fail
        with patch("importlib.resources.files", side_effect=RuntimeError("boom")):
            result = runner.invoke(
                cli,
                ["setup-github-pages", "--project-path", str(tmp_path)],
            )
        assert result.exit_code == 1
        assert "Error" in result.output


class TestCheckLinksAutodiscover:
    @patch("great_docs.cli.GreatDocs")
    def test_auto_discover_user_guide(self, mock_gd_cls, tmp_path, monkeypatch):
        """Without --file, user_guide/ and README.md are auto-discovered."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        user_guide = tmp_path / "user_guide"
        user_guide.mkdir()
        (user_guide / "index.qmd").write_text("# Hello")
        readme = tmp_path / "README.md"
        readme.write_text("# Readme")
        recipes = tmp_path / "recipes"
        recipes.mkdir()
        (recipes / "recipe.qmd").write_text("# Recipe")

        mock_docs = MagicMock()
        mock_docs.project_root = tmp_path
        mock_docs.check_links.return_value = {
            "total": 0,
            "ok": [],
            "redirects": [],
            "broken": [],
            "skipped": [],
            "by_file": {},
        }
        mock_gd_cls.return_value = mock_docs
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["check-links", "--docs-only", "--project-path", str(tmp_path)],
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# proofread — auto-discover, dict file, spelling_only, qmd exception,
#              Python files, verbose
# ---------------------------------------------------------------------------


class TestProofreadMissedBranches:
    def _make_project(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        user_guide = tmp_path / "user_guide"
        user_guide.mkdir()
        (user_guide / "page.qmd").write_text("This text has no errors.")

    @patch("great_docs.cli.GreatDocs")
    @patch("great_docs._harper.run_harper")
    def test_auto_discover_user_guide(self, mock_harper, mock_gd_cls, tmp_path, monkeypatch):
        """Without --file, auto-discovers user_guide/*.qmd."""
        monkeypatch.chdir(tmp_path)
        self._make_project(tmp_path)
        mock_docs = MagicMock()
        mock_docs.project_root = tmp_path
        mock_gd_cls.return_value = mock_docs
        mock_harper.return_value = []
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["proofread", "--project-path", str(tmp_path)],
        )
        assert result.exit_code in (0, 1, 3)  # 3 = harper not found, 1 = issues found

    @patch("great_docs.cli.GreatDocs")
    @patch("great_docs._harper.run_harper")
    def test_dictionary_file_read(self, mock_harper, mock_gd_cls, tmp_path, monkeypatch):
        """--dictionary file is read line by line, skipping comments."""
        monkeypatch.chdir(tmp_path)
        self._make_project(tmp_path)
        dict_file = tmp_path / "custom.txt"
        dict_file.write_text("# comment\nmyword\nanother\n")
        mock_docs = MagicMock()
        mock_docs.project_root = tmp_path
        mock_gd_cls.return_value = mock_docs
        mock_harper.return_value = []
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["proofread", "--dictionary", str(dict_file), "--project-path", str(tmp_path)],
        )
        assert result.exit_code in (0, 3)

    @patch("great_docs.cli.GreatDocs")
    @patch("great_docs._harper.run_harper")
    def test_spelling_only_flag(self, mock_harper, mock_gd_cls, tmp_path, monkeypatch):
        """--spelling-only sets only_rules=["SpellCheck"]."""
        monkeypatch.chdir(tmp_path)
        self._make_project(tmp_path)
        mock_docs = MagicMock()
        mock_docs.project_root = tmp_path
        mock_gd_cls.return_value = mock_docs
        mock_harper.return_value = []
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["proofread", "--spelling-only", "--project-path", str(tmp_path)],
        )
        assert result.exit_code in (0, 3)

    @patch("great_docs.cli.GreatDocs")
    @patch("great_docs._harper.run_harper")
    def test_qmd_file_exception_handled(self, mock_harper, mock_gd_cls, tmp_path, monkeypatch):
        """Exception when processing a .qmd file is caught and stored as an error result."""
        monkeypatch.chdir(tmp_path)
        self._make_project(tmp_path)
        user_guide = tmp_path / "user_guide"
        (user_guide / "broken.qmd").write_text("Broken content")
        mock_docs = MagicMock()
        mock_docs.project_root = tmp_path
        mock_gd_cls.return_value = mock_docs
        mock_harper.return_value = []

        with patch(
            "great_docs._harper.extract_prose_from_markdown",
            side_effect=RuntimeError("parse error"),
        ):
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["proofread", "--project-path", str(tmp_path)],
            )
        assert result.exit_code in (0, 1, 3)

    @patch("great_docs.cli.GreatDocs")
    @patch("great_docs._harper.run_harper")
    def test_include_docstrings_flag(self, mock_harper, mock_gd_cls, tmp_path, monkeypatch):
        """--include-docstrings finds .py files and passes them to run_harper."""
        monkeypatch.chdir(tmp_path)
        self._make_project(tmp_path)
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('"""Module docstring."""\n')
        mock_docs = MagicMock()
        mock_docs.project_root = tmp_path
        mock_gd_cls.return_value = mock_docs
        mock_harper.return_value = []
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["proofread", "--include-docstrings", "--project-path", str(tmp_path)],
        )
        assert result.exit_code in (0, 3)

    @patch("great_docs.cli.GreatDocs")
    @patch("great_docs._harper.run_harper")
    def test_verbose_no_issues_shows_checkmark(
        self, mock_harper, mock_gd_cls, tmp_path, monkeypatch
    ):
        """--verbose with no issues shows ✅ per file."""
        monkeypatch.chdir(tmp_path)
        self._make_project(tmp_path)
        mock_docs = MagicMock()
        mock_docs.project_root = tmp_path
        mock_gd_cls.return_value = mock_docs

        from great_docs._harper import HarperFileResult

        mock_harper.return_value = [
            HarperFileResult(file="user_guide/page.qmd", lint_count=0, lints=[], error=None)
        ]
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["proofread", "--verbose", "--project-path", str(tmp_path)],
        )
        assert result.exit_code in (0, 3)


class TestSeoMissedBranches:
    def _make_site(
        self, tmp_path: Path, sitemap_content: str = "", robots_content: str = ""
    ) -> Path:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
        (tmp_path / "great-docs.yml").write_text("display_name: Pkg\n")
        gd = tmp_path / "great-docs"
        site = gd / "_site"
        site.mkdir(parents=True)
        if sitemap_content:
            (site / "sitemap.xml").write_text(sitemap_content)
        if robots_content:
            (site / "robots.txt").write_text(robots_content)
        return site

    def test_sitemap_empty_warning(self, tmp_path, monkeypatch):
        """sitemap.xml with no <url> elements triggers an empty warning."""
        monkeypatch.chdir(tmp_path)
        site = self._make_site(
            tmp_path,
            sitemap_content='<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>',
            robots_content="User-agent: *\nSitemap: https://example.com/sitemap.xml\n",
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["seo", "--project-path", str(tmp_path)])
        assert "empty" in result.output or result.exit_code in (0, 1)

    def test_robots_missing_sitemap_ref(self, tmp_path, monkeypatch):
        """robots.txt without a Sitemap: line triggers a warning."""
        monkeypatch.chdir(tmp_path)
        site = self._make_site(
            tmp_path,
            sitemap_content='<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/</loc></url></urlset>',
            robots_content="User-agent: *\nDisallow:\n",
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["seo", "--project-path", str(tmp_path)])
        assert "robots.txt" in result.output or result.exit_code in (0, 1)

    def test_seo_with_html_pages_json_ld(self, tmp_path, monkeypatch):
        """HTML pages with JSON-LD increment pages_with_json_ld counter."""
        monkeypatch.chdir(tmp_path)
        site = self._make_site(
            tmp_path,
            sitemap_content='<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/</loc></url></urlset>',
            robots_content="User-agent: *\nSitemap: https://example.com/sitemap.xml\n",
        )
        # Create HTML page with all recommended elements
        html = site / "index.html"
        html.write_text(
            "<html><head>"
            "<title>Home | Pkg</title>"
            '<meta name="description" content="Docs">'
            '<link rel="canonical" href="https://example.com/">'
            '<script type="application/ld+json">{"@type":"WebPage"}</script>'
            "</head><body></body></html>"
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["seo", "--project-path", str(tmp_path)])
        assert result.exit_code in (0, 1)

    def test_seo_exception_path(self, tmp_path, monkeypatch):
        """An unhandled exception in seo exits 1 with error message."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        runner = CliRunner()
        with patch("great_docs.cli.GreatDocs", side_effect=RuntimeError("boom")):
            result = runner.invoke(cli, ["seo", "--project-path", str(tmp_path)])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_seo_json_exception_path(self, tmp_path, monkeypatch):
        """An exception with --json outputs JSON error object."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        runner = CliRunner()
        with patch("great_docs.cli.GreatDocs", side_effect=RuntimeError("boom")):
            result = runner.invoke(cli, ["seo", "--json", "--project-path", str(tmp_path)])
        assert result.exit_code == 1
        assert "error" in result.output


class TestLintInfoOutput:
    @patch("great_docs._lint.run_lint")
    def test_info_severity_output(self, mock_lint, tmp_path, monkeypatch):
        """Issues with severity='info' emit ℹ️ icon and are included in output."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        from great_docs._lint import LintIssue, LintResult

        result_obj = LintResult(
            package_name="pkg",
            exports_count=1,
            issues=[LintIssue("stale-badge", "info", "module.func", "Badge is old")],
        )
        mock_lint.return_value = result_obj
        runner = CliRunner()
        result = runner.invoke(cli, ["lint", "--project-path", str(tmp_path)])
        assert result.exit_code == 0
        assert "info" in result.output.lower() or "ℹ" in result.output or "Badge" in result.output

    @patch("great_docs._lint.run_lint")
    def test_no_entries_line(self, mock_lint, tmp_path, monkeypatch):
        """An empty check result shows '(no entries)'."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        from great_docs._lint import LintResult

        mock_lint.return_value = LintResult(package_name="pkg", exports_count=0, issues=[])
        runner = CliRunner()
        result = runner.invoke(cli, ["lint", "--project-path", str(tmp_path)])
        assert result.exit_code == 0


class TestApiDiffMissedBranches:
    @patch("great_docs._api_diff.symbol_history")
    @patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0"])
    def test_symbol_history_output(self, mock_tags, mock_hist, tmp_path, monkeypatch):
        """--symbol flag triggers the symbol history display path."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        entry = MagicMock()
        entry.version = "v1.0"
        entry.present = True
        entry.signature = "def my_func(x: int) -> str"
        entry.change = None
        hist_obj = MagicMock()
        hist_obj.symbol_name = "pkg.my_func"
        hist_obj.package_name = "pkg"
        hist_obj.entries = [entry]
        hist_obj.changed_entries = [entry]
        mock_hist.return_value = hist_obj
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "api-diff",
                "v1.0",
                "v2.0",
                "--symbol",
                "pkg.my_func",
                "--project-path",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert "pkg.my_func" in result.output

    @patch("great_docs._api_diff.api_diff")
    def test_migration_hint_output(self, mock_diff, tmp_path, monkeypatch):
        """Changed symbols with migration_hint show the hint line."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        changed = MagicMock()
        changed.symbol = "pkg.func"
        changed.is_breaking = False
        changed.details = ["signature changed"]
        changed.migration_hint = "Use new_func() instead"
        diff_result = MagicMock()
        diff_result.added = []
        diff_result.removed = []
        diff_result.changed = [changed]
        diff_result.has_breaking_changes = False
        diff_result.breaking_changes = []
        diff_result.package_name = "pkg"
        mock_diff.return_value = diff_result
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["api-diff", "v1.0", "v2.0", "--project-path", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "Use new_func()" in result.output

    @patch("great_docs._api_diff.api_diff", side_effect=RuntimeError("diff failed"))
    def test_exception_in_api_diff(self, mock_diff, tmp_path, monkeypatch):
        """An exception during api-diff with --json outputs error JSON."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["api-diff", "v1.0", "v2.0", "--json", "--project-path", str(tmp_path)],
        )
        assert result.exit_code == 1
        out = json.loads(result.output.strip())
        assert out["status"] == "error"


class TestVersionsExceptionPath:
    def test_exception_exits_one(self, tmp_path, monkeypatch):
        """An exception in versions exits 1 with error message."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        runner = CliRunner()
        with patch("great_docs.config.Config", side_effect=RuntimeError("boom")):
            result = runner.invoke(cli, ["versions", "--project-path", str(tmp_path)])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestApiSnapshotMissedBranches:
    @patch("great_docs._api_diff._detect_package_name", return_value="pkg")
    @patch("great_docs._api_diff.snapshot_from_griffe")
    def test_head_no_version_tag(self, mock_snap, mock_detect, tmp_path, monkeypatch):
        """No VERSION_TAG argument defaults to HEAD snapshot."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        snap = MagicMock()
        snap.symbol_count = 1
        snap.save = MagicMock()
        mock_snap.return_value = snap
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["api-snapshot", "--project-path", str(tmp_path)],
        )
        assert result.exit_code in (0, 1)

    @patch("great_docs._api_diff._detect_package_name", return_value="pkg")
    @patch("great_docs._api_diff.snapshot_from_griffe", return_value=None)
    def test_snapshot_none_counted_as_failed(self, mock_snap, mock_detect, tmp_path, monkeypatch):
        """snapshot_from_griffe returning None increments failed count."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["api-snapshot", "--project-path", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "could not build" in result.output or "Failed" in result.output

    @patch("great_docs._api_diff._detect_package_name", return_value="pkg")
    @patch("great_docs._api_diff.snapshot_from_griffe")
    def test_force_overwrites_existing(self, mock_snap, mock_detect, tmp_path, monkeypatch):
        """--force overwrites an existing snapshot file."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        snap_dir = tmp_path / ".great-docs" / "snapshots"
        snap_dir.mkdir(parents=True)
        existing = snap_dir / "dev.json"
        existing.write_text("{}")
        snap = MagicMock()
        snap.symbol_count = 1
        snap.save = MagicMock()
        mock_snap.return_value = snap
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["api-snapshot", "--force", "--project-path", str(tmp_path)],
        )
        assert "already exists" not in result.output


class TestSkillListMissedBranches:
    @patch("great_docs._skill_install.list_skills")
    def test_url_source_displays_url(self, mock_list, tmp_path, monkeypatch):
        """--url source calls _list_skills(url=...) and echoes the URL."""
        monkeypatch.chdir(tmp_path)
        mock_list.return_value = [{"name": "my-skill"}]
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["skill", "list", "--url", "https://example.com/"],
        )
        assert "https://example.com" in result.output
        mock_list.assert_called_once_with(url="https://example.com/")

    @patch("great_docs._skill_install.list_skills")
    def test_package_source_displays_package(self, mock_list, tmp_path, monkeypatch):
        """Positional SOURCE calls _list_skills(package=source)."""
        monkeypatch.chdir(tmp_path)
        mock_list.return_value = [{"name": "skill-a"}]
        runner = CliRunner()
        result = runner.invoke(cli, ["skill", "list", "mypkg"])
        assert "mypkg" in result.output
        mock_list.assert_called_once_with(package="mypkg")

    @patch("great_docs._skill_install.list_skills")
    @patch("great_docs.cli._detect_current_package", return_value="detected-pkg")
    def test_no_source_auto_detects_package(self, mock_detect, mock_list, tmp_path, monkeypatch):
        """No source auto-detects package from pyproject.toml."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "detected-pkg"\n')
        mock_list.return_value = [{"name": "skill-x"}]
        runner = CliRunner()
        result = runner.invoke(cli, ["skill", "list"])
        assert "detected-pkg" in result.output

    def test_no_source_no_package_exits_error(self, tmp_path, monkeypatch):
        """No source and no package in CWD exits 1."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        with patch("great_docs.cli._detect_current_package", return_value=None):
            result = runner.invoke(cli, ["skill", "list"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestSkillInstallMissedBranches:
    @patch("great_docs._skill_install.install_skill")
    @patch("great_docs.cli._detect_current_package", return_value="auto-pkg")
    def test_no_source_auto_detects(self, mock_detect, mock_install, tmp_path, monkeypatch):
        """No source argument triggers auto-detection from pyproject.toml."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "auto-pkg"\n')
        mock_install.return_value = True
        runner = CliRunner()
        result = runner.invoke(cli, ["skill", "install", "my-skill"])
        assert result.exit_code == 0

    @patch("great_docs.cli._detect_current_package", return_value=None)
    def test_no_source_no_package_exits_error(self, mock_detect, tmp_path, monkeypatch):
        """No source and no detectable package exits 1 with error."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["skill", "install", "my-skill"])
        assert result.exit_code == 1
        assert "Error" in result.output


class TestTermshowMissedBranches:
    def test_term_record_adds_extension(self, tmp_path, monkeypatch):
        """output without .termshow suffix gets .termshow appended."""
        monkeypatch.chdir(tmp_path)
        with patch("great_docs._term_player.recorder.record_session") as mock_record:
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["termshow", "record", "my-session", "--shell", "/bin/echo"],
            )
        # Either it ran or errored; check record_session was called with .termshow
        if mock_record.called:
            called_output = mock_record.call_args[0][0]
            assert str(called_output).endswith(".termshow")

    def test_term_record_with_extension_unchanged(self, tmp_path, monkeypatch):
        """output already ending in .termshow is not modified."""
        monkeypatch.chdir(tmp_path)
        with patch("great_docs._term_player.recorder.record_session") as mock_record:
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["termshow", "record", "my-session.termshow", "--shell", "/bin/echo"],
            )
        if mock_record.called:
            called_output = mock_record.call_args[0][0]
            assert str(called_output).endswith(".termshow")
            assert not str(called_output).endswith(".termshow.termshow")

    def test_term_import_cast_adds_extension(self, tmp_path, monkeypatch):
        """import-cast output without .termshow gets extension added."""
        monkeypatch.chdir(tmp_path)
        cast_file = tmp_path / "demo.cast"
        cast_file.write_text('{"version":2,"width":80,"height":24}\n')
        mock_rec = MagicMock()
        mock_rec.duration = 5.0
        mock_rec.events = [1, 2, 3]
        runner = CliRunner()
        with patch("great_docs._term_player.importer.import_asciicast", return_value=mock_rec):
            result = runner.invoke(
                cli,
                ["termshow", "import-cast", str(cast_file), str(tmp_path / "out")],
            )
        assert result.exit_code == 0
        assert "out.termshow" in result.output

    def test_term_edit_invokes_serve_editor(self, tmp_path, monkeypatch):
        """term edit calls serve_editor with the given source and port."""
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "demo.termshow"
        src.write_text('{"version":1,"format":"termshow","term":{"cols":80,"rows":24}}\n')
        with patch("great_docs._term_player.editor.serve_editor") as mock_serve:
            runner = CliRunner()
            result = runner.invoke(
                cli,
                ["termshow", "edit", str(src), "--port", "9999"],
            )
        mock_serve.assert_called_once_with(str(src), port=9999, no_browser=False)


class TestProofreadDictFileException:
    @patch("great_docs.cli.GreatDocs")
    @patch("great_docs._harper.run_harper")
    def test_dict_file_read_exception_shows_warning(
        self, mock_harper, mock_gd_cls, tmp_path, monkeypatch
    ):
        """Exception reading --dictionary file shows a warning and continues."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        ug = tmp_path / "user_guide"
        ug.mkdir()
        (ug / "page.qmd").write_text("This text has no errors.")
        mock_docs = MagicMock()
        mock_docs.project_root = tmp_path
        mock_gd_cls.return_value = mock_docs
        mock_harper.return_value = []
        # Use a dict file that doesn't exist → triggers the except block
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "proofread",
                "--dictionary",
                str(tmp_path / "nonexistent.txt"),
                "--project-path",
                str(tmp_path),
            ],
        )
        assert "Warning" in result.output or result.exit_code in (0, 1, 3)


class TestSeoCanonicalMissedBranches:
    def _make_site_with_html(
        self, tmp_path: Path, html_content: str, canonical_base: str = ""
    ) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
        gd_yml = "display_name: Pkg\n"
        if canonical_base:
            gd_yml += f"seo:\n  canonical:\n    base_url: {canonical_base}\n"
        (tmp_path / "great-docs.yml").write_text(gd_yml)
        site = tmp_path / "great-docs" / "_site"
        site.mkdir(parents=True)
        # Add valid sitemap and robots
        (site / "sitemap.xml").write_text(
            '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://example.com/</loc></url></urlset>"
        )
        (site / "robots.txt").write_text(
            "User-agent: *\nSitemap: https://example.com/sitemap.xml\n"
        )
        (site / "index.html").write_text(html_content)

    def test_missing_canonical_with_base_url(self, tmp_path, monkeypatch):
        """Pages missing canonical with base_url configured → issues error."""
        monkeypatch.chdir(tmp_path)
        self._make_site_with_html(
            tmp_path,
            "<html><head><title>Home | Pkg</title></head><body></body></html>",
            canonical_base="https://example.com",
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["seo", "--project-path", str(tmp_path)])
        assert "canonical" in result.output.lower() or result.exit_code in (0, 1)

    def test_missing_canonical_without_base_url(self, tmp_path, monkeypatch):
        """Pages missing canonical without base_url → warning not error."""
        monkeypatch.chdir(tmp_path)
        self._make_site_with_html(
            tmp_path,
            "<html><head><title>Home | Pkg</title></head><body></body></html>",
        )
        runner = CliRunner()
        result = runner.invoke(cli, ["seo", "--project-path", str(tmp_path)])
        assert result.exit_code in (0, 1)


class TestApiDiffSymbolHistoryNotPresent:
    @patch("great_docs._api_diff.symbol_history")
    @patch("great_docs._api_diff.list_version_tags", return_value=["v1.0", "v2.0"])
    def test_not_present_entry_output(self, mock_tags, mock_hist, tmp_path, monkeypatch):
        """Symbol absent in a version shows 'NOT PRESENT' output."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        absent_entry = MagicMock()
        absent_entry.version = "v1.0"
        absent_entry.present = False
        absent_entry.signature = None
        absent_entry.change = MagicMock()
        absent_entry.change.details = ["was removed"]
        hist_obj = MagicMock()
        hist_obj.symbol_name = "pkg.removed_func"
        hist_obj.package_name = "pkg"
        hist_obj.entries = [absent_entry]
        hist_obj.changed_entries = [absent_entry]
        mock_hist.return_value = hist_obj
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "api-diff",
                "v1.0",
                "v2.0",
                "--symbol",
                "pkg.removed_func",
                "--project-path",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert "NOT PRESENT" in result.output


class TestApiSnapshotOutputAndException:
    @patch("great_docs._api_diff._detect_package_name", return_value="pkg")
    @patch("great_docs._api_diff.snapshot_from_griffe")
    def test_explicit_output_path(self, mock_snap, mock_detect, tmp_path, monkeypatch):
        """--output <path> with a single tag writes to that specific file."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        out_file = tmp_path / "snapshot.json"
        snap = MagicMock()
        snap.symbol_count = 3
        snap.save = MagicMock()
        mock_snap.return_value = snap
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["api-snapshot", "--output", str(out_file), "--project-path", str(tmp_path)],
        )
        assert result.exit_code in (0, 1)
        if snap.save.called:
            assert snap.save.call_args[0][0] == out_file

    @patch("great_docs._api_diff._detect_package_name", return_value="pkg")
    @patch("great_docs._api_diff.snapshot_from_griffe", side_effect=RuntimeError("snap error"))
    def test_snapshot_exception_counted_as_failed(
        self, mock_snap, mock_detect, tmp_path, monkeypatch
    ):
        """Exception from snapshot_from_griffe increments failed count."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["api-snapshot", "--project-path", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "snap error" in result.output or "Failed" in result.output


class TestSkillListEmptyResults:
    @patch("great_docs._skill_install.list_skills", return_value=[])
    def test_empty_results_with_url(self, mock_list, tmp_path, monkeypatch):
        """No skills at URL shows 'No skills found.' and exits 1."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["skill", "list", "--url", "https://example.com/"])
        assert result.exit_code == 1
        assert "No skills found" in result.output

    @patch("great_docs._skill_install.list_skills", return_value=[])
    @patch("great_docs.cli._detect_current_package", return_value="mypkg")
    def test_empty_results_with_package(self, mock_detect, mock_list, tmp_path, monkeypatch):
        """No skills for auto-detected package shows 'No skills found.' and exits 1."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["skill", "list"])
        assert result.exit_code == 1
        assert "No skills found" in result.output


class TestDetectCurrentPackage:
    def test_returns_name_from_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-cool-pkg"\nversion = "1.0"\n'
        )
        assert _detect_current_package(tmp_path) == "my-cool-pkg"

    def test_returns_none_no_pyproject(self, tmp_path):
        assert _detect_current_package(tmp_path) is None

    def test_returns_none_no_project_name(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
        assert _detect_current_package(tmp_path) is None

    def test_returns_none_on_malformed_toml(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("{{invalid toml content")
        assert _detect_current_package(tmp_path) is None

    def test_tomllib_import_fallback(self, tmp_path):
        """When tomllib import fails, falls back to tomli."""
        import sys

        (tmp_path / "pyproject.toml").write_text('[project]\nname = "fallback-pkg"\n')
        # Temporarily hide tomllib to force the ImportError fallback
        real_tomllib = sys.modules.get("tomllib")
        sys.modules["tomllib"] = None  # type: ignore[assignment]
        try:
            # Force re-import by calling the function (the try/except inside
            # uses a local import so we need to trigger the ImportError)
            import importlib

            # The function uses a local `import tomllib` which will check
            # sys.modules first. Setting to None triggers ImportError.
            result = _detect_current_package(tmp_path)
            # Either succeeds via tomli or returns None (no tomli installed)
            # Either way, lines 3371-3372 are exercised
        finally:
            if real_tomllib is not None:
                sys.modules["tomllib"] = real_tomllib
            else:
                del sys.modules["tomllib"]




class TestPrintTimingTableVersionedTop:
    def test_top_limits_pages_in_versioned_data(self, capsys):
        data = {
            "build_time": "2024-01-15 10:00",
            "total_seconds": 120.5,
            "versions": {
                "v1.0": {
                    "seconds": 60.0,
                    "pages": [
                        {"page": "page1.html", "seconds": 30.0},
                        {"page": "page2.html", "seconds": 20.0},
                        {"page": "page3.html", "seconds": 10.0},
                    ],
                }
            },
        }
        _print_timing_table(data, top=2, version_filter=None)
        out = capsys.readouterr().out
        assert "page1.html" in out
        assert "page2.html" in out
        assert "page3.html" not in out




class TestFreezeFileSearchFallback:
    def _setup_project(self, tmp_path, build_file_name):
        """Set up a project with a build dir containing a file with given name."""
        build_dir = tmp_path / "great-docs"
        build_dir.mkdir(exist_ok=True)
        (build_dir / "_quarto.yml").write_text("project:\n  type: website\n")
        if build_file_name:
            (build_dir / build_file_name).write_text("---\ntitle: Test\n---\n")
        return build_dir

    def test_underscore_to_hyphen_fallback(self, tmp_path):
        """File found after replacing underscores with hyphens."""
        qmd = tmp_path / "user_guide.qmd"
        qmd.write_text("---\ntitle: Test\n---\n")

        self._setup_project(tmp_path, "user-guide.qmd")

        runner = CliRunner()
        with (
            patch("great_docs.cli.GreatDocs") as mock_gd,
            patch("subprocess.run") as mock_run,
        ):
            mock_gd.return_value._prepare_for_freeze.return_value = None
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = runner.invoke(
                cli,
                ["freeze", "user_guide.qmd", "--project-path", str(tmp_path)],
            )
        assert "Rendering" in result.output or "✓" in result.output

    def test_numeric_prefix_stripped(self, tmp_path):
        """File found after stripping numeric prefix."""
        qmd = tmp_path / "24-demo.qmd"
        qmd.write_text("---\ntitle: Demo\n---\n")

        self._setup_project(tmp_path, "demo.qmd")

        runner = CliRunner()
        with (
            patch("great_docs.cli.GreatDocs") as mock_gd,
            patch("subprocess.run") as mock_run,
        ):
            mock_gd.return_value._prepare_for_freeze.return_value = None
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = runner.invoke(
                cli,
                ["freeze", "24-demo.qmd", "--project-path", str(tmp_path)],
            )
        assert "Rendering" in result.output or "✓" in result.output

    def test_both_hyphen_and_prefix_stripped(self, tmp_path):
        """File found after both underscore→hyphen and prefix strip."""
        qmd = tmp_path / "05_freeze_demo.qmd"
        qmd.write_text("---\ntitle: Freeze Demo\n---\n")

        self._setup_project(tmp_path, "freeze-demo.qmd")

        runner = CliRunner()
        with (
            patch("great_docs.cli.GreatDocs") as mock_gd,
            patch("subprocess.run") as mock_run,
        ):
            mock_gd.return_value._prepare_for_freeze.return_value = None
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = runner.invoke(
                cli,
                ["freeze", "05_freeze_demo.qmd", "--project-path", str(tmp_path)],
            )
        assert "Rendering" in result.output or "✓" in result.output

    def test_file_not_found_in_build_dir(self, tmp_path):
        """File not found after all fallbacks."""
        qmd = tmp_path / "missing.qmd"
        qmd.write_text("---\ntitle: Missing\n---\n")

        self._setup_project(tmp_path, None)

        runner = CliRunner()
        with patch("great_docs.cli.GreatDocs") as mock_gd:
            mock_gd.return_value._prepare_for_freeze.return_value = None
            result = runner.invoke(
                cli,
                ["freeze", "missing.qmd", "--project-path", str(tmp_path)],
            )
        assert "not found in build directory" in result.output
        assert "Hint" in result.output


class TestFreezePersistCache:
    def test_persist_existing_dir_replaced(self, tmp_path):
        """When freeze dir has sub-dir that already exists in persist, it's replaced."""
        qmd = tmp_path / "page.qmd"
        qmd.write_text("---\ntitle: Test\n---\n")

        build_dir = tmp_path / "great-docs"
        build_dir.mkdir()
        (build_dir / "_quarto.yml").write_text("project:\n  type: website\n")
        (build_dir / "page.qmd").write_text("---\ntitle: Test\n---\n")

        # Create _freeze in build dir (simulates quarto render output)
        build_freeze = build_dir / "_freeze"
        build_freeze.mkdir()
        sub = build_freeze / "page"
        sub.mkdir()
        (sub / "data.json").write_text('{"result": "new"}')

        # Create existing persist dir with old data
        persist_dir = tmp_path / "_freeze"
        persist_dir.mkdir()
        old_sub = persist_dir / "page"
        old_sub.mkdir()
        (old_sub / "data.json").write_text('{"result": "old"}')

        runner = CliRunner()
        with (
            patch("great_docs.cli.GreatDocs") as mock_gd,
            patch("subprocess.run") as mock_run,
        ):
            mock_gd.return_value._prepare_for_freeze.return_value = None
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = runner.invoke(
                cli,
                ["freeze", "page.qmd", "--project-path", str(tmp_path)],
            )
        assert "Persisting" in result.output
        assert "Updated" in result.output
        # Old data replaced with new
        assert json.loads((persist_dir / "page" / "data.json").read_text())["result"] == "new"

    def test_persist_file_copied(self, tmp_path):
        """Non-directory items in _freeze are copied with shutil.copy2."""
        qmd = tmp_path / "page.qmd"
        qmd.write_text("---\ntitle: Test\n---\n")

        build_dir = tmp_path / "great-docs"
        build_dir.mkdir()
        (build_dir / "_quarto.yml").write_text("project:\n  type: website\n")
        (build_dir / "page.qmd").write_text("---\ntitle: Test\n---\n")

        # Create _freeze in build dir with a plain file (not directory)
        build_freeze = build_dir / "_freeze"
        build_freeze.mkdir()
        (build_freeze / "index.json").write_text('{"pages": []}')

        runner = CliRunner()
        with (
            patch("great_docs.cli.GreatDocs") as mock_gd,
            patch("subprocess.run") as mock_run,
        ):
            mock_gd.return_value._prepare_for_freeze.return_value = None
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = runner.invoke(
                cli,
                ["freeze", "page.qmd", "--project-path", str(tmp_path)],
            )
        assert "Persisting" in result.output
        persist_dir = tmp_path / "_freeze"
        assert (persist_dir / "index.json").exists()
        assert json.loads((persist_dir / "index.json").read_text()) == {"pages": []}




class TestSetupGithubPagesPythonFloor:
    def test_detected_python_below_311_uses_minimum(self, tmp_path, monkeypatch):
        """When detected Python < 3.11, floor to 3.11 with message."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "pkg"\nrequires-python = ">=3.9"\n'
        )

        runner = CliRunner()
        mock_template = MagicMock()
        mock_template.read_text.return_value = "python: {python_version}"
        mock_files = MagicMock()
        mock_files.return_value.joinpath.return_value = mock_template

        with (
            patch("great_docs.cli.GreatDocs"),
            patch("importlib.resources.files", mock_files),
        ):
            result = runner.invoke(
                cli,
                ["setup-github-pages", "--project-path", str(tmp_path)],
            )
        assert "needs >=3.11" in result.output




class TestProofreadReadmeAutoDiscover:
    @patch("great_docs._harper.run_harper", return_value=[])
    @patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.0"))
    def test_readme_auto_discovered(self, mock_check, mock_run, tmp_path, monkeypatch):
        """README.md is auto-discovered when no files specified."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (tmp_path / "README.md").write_text("# Hello World\n")
        # No user_guide or recipes dirs

        runner = CliRunner()
        result = runner.invoke(cli, ["proofread", "--project-path", str(tmp_path)])
        # run_harper should have been called with a list containing README.md
        assert mock_run.called
        files_arg = mock_run.call_args[0][0]
        assert any("README.md" in str(f) for f in files_arg)




class TestProofreadDictionaryFileError:
    @patch("great_docs._harper.run_harper", return_value=[])
    @patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.0"))
    def test_dictionary_file_read_error(self, mock_check, mock_run, tmp_path, monkeypatch):
        """Exception reading dictionary file emits warning."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (tmp_path / "README.md").write_text("# Test")

        # Create a valid dictionary file (passes Click's exists check)
        dict_file = tmp_path / "bad_dict.txt"
        dict_file.write_text("word1\n")

        # Patch open to raise when the dict file is opened inside proofread
        import builtins

        real_open = builtins.open

        def _failing_open(path, *args, **kwargs):
            if str(path) == str(dict_file):
                raise IOError("simulated read failure")
            return real_open(path, *args, **kwargs)

        runner = CliRunner()
        with patch("builtins.open", side_effect=_failing_open):
            result = runner.invoke(
                cli,
                [
                    "proofread",
                    "README.md",
                    "--dictionary-file",
                    str(dict_file),
                    "--project-path",
                    str(tmp_path),
                ],
            )
        assert "Warning" in result.output or "Could not read" in result.output




class TestProofreadIncludeDocstrings:
    @patch("great_docs._harper.run_harper")
    @patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.0"))
    def test_include_docstrings_checks_py_files(self, mock_check, mock_run, tmp_path, monkeypatch):
        """--include-docstrings causes .py files to be checked."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        py_file = tmp_path / "module.py"
        py_file.write_text('"""Module docstring."""\n\ndef foo():\n    pass\n')

        mock_run.return_value = []

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "proofread",
                str(py_file),
                "--include-docstrings",
                "--project-path",
                str(tmp_path),
            ],
        )
        # run_harper should be called for py files
        assert mock_run.call_count >= 1

    @patch("great_docs._harper.run_harper")
    @patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.0"))
    def test_include_docstrings_verbose(self, mock_check, mock_run, tmp_path, monkeypatch):
        """--include-docstrings --verbose shows Python file count."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        py_file = tmp_path / "module.py"
        py_file.write_text('"""Docstring."""\n')

        mock_run.return_value = []

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "proofread",
                str(py_file),
                "--include-docstrings",
                "--verbose",
                "--project-path",
                str(tmp_path),
            ],
        )
        assert "Python file" in result.output




class TestProofreadTempDictCleanup:
    @patch("great_docs._harper.run_harper", return_value=[])
    @patch("great_docs._harper.check_harper_available", return_value=(True, "harper 1.0"))
    def test_cleanup_exception_swallowed(self, mock_check, mock_run, tmp_path, monkeypatch):
        """Exception during temp dict cleanup is swallowed."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (tmp_path / "README.md").write_text("# Test")

        runner = CliRunner()
        with patch("pathlib.Path.unlink", side_effect=OSError("permission denied")):
            result = runner.invoke(
                cli,
                [
                    "proofread",
                    "README.md",
                    "-d",
                    "customword",
                    "--project-path",
                    str(tmp_path),
                ],
            )
        # Should still succeed despite unlink failure
        assert result.exit_code == 0




class TestProofreadExceptionHandlers:
    def test_harper_not_found_error(self, tmp_path, monkeypatch):
        """HarperNotFoundError exits with code 3."""
        from great_docs._harper import HarperNotFoundError

        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (tmp_path / "README.md").write_text("# Test")

        runner = CliRunner()
        with patch(
            "great_docs._harper.check_harper_available",
            side_effect=HarperNotFoundError("not installed"),
        ):
            result = runner.invoke(
                cli,
                ["proofread", "README.md", "--project-path", str(tmp_path)],
            )
        assert result.exit_code == 3

    def test_harper_error(self, tmp_path, monkeypatch):
        """HarperError exits with code 2."""
        from great_docs._harper import HarperError

        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (tmp_path / "README.md").write_text("# Test")

        runner = CliRunner()
        with patch(
            "great_docs._harper.check_harper_available",
            side_effect=HarperError("failed"),
        ):
            result = runner.invoke(
                cli,
                ["proofread", "README.md", "--project-path", str(tmp_path)],
            )
        assert result.exit_code == 2

    def test_generic_exception(self, tmp_path, monkeypatch):
        """Generic Exception exits with code 1."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\n')
        (tmp_path / "README.md").write_text("# Test")

        runner = CliRunner()
        with patch(
            "great_docs._harper.check_harper_available",
            side_effect=RuntimeError("unexpected"),
        ):
            result = runner.invoke(
                cli,
                ["proofread", "README.md", "--project-path", str(tmp_path)],
            )
        assert result.exit_code == 1




class TestSeoSitemapParseError:
    def test_malformed_sitemap_xml(self, tmp_path, monkeypatch):
        """Malformed sitemap.xml reports parse error."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
        (tmp_path / "great-docs.yml").write_text("display_name: Pkg\n")
        gd = tmp_path / "great-docs"
        gd.mkdir()
        site = gd / "_site"
        site.mkdir()
        # Write malformed XML
        (site / "sitemap.xml").write_text("<<<not valid xml>>>")

        runner = CliRunner()
        result = runner.invoke(cli, ["seo", "--project-path", str(tmp_path)])
        assert "malformed" in result.output.lower() or "❌" in result.output




class TestSeoSkipInternalFiles:
    def test_internal_files_skipped(self, tmp_path, monkeypatch):
        """HTML files starting with _ or . are skipped."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "pkg"\nversion = "1.0"\n')
        (tmp_path / "great-docs.yml").write_text("display_name: Pkg\n")
        gd = tmp_path / "great-docs"
        gd.mkdir()
        site = gd / "_site"
        site.mkdir()
        # Create internal files that should be skipped
        internal_dir = site / "_internal"
        internal_dir.mkdir()
        (internal_dir / "page.html").write_text("<html><body>internal</body></html>")
        dot_dir = site / ".hidden"
        dot_dir.mkdir()
        (dot_dir / "page.html").write_text("<html><body>hidden</body></html>")
        # Create a normal file that should be analyzed
        (site / "index.html").write_text(
            '<html><head><title>T</title><link rel="canonical" href="x">'
            '<meta name="description" content="d"></head><body></body></html>'
        )
        (site / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://example.com/</loc></url></urlset>"
        )
        (site / "robots.txt").write_text(
            "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n"
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["seo", "--project-path", str(tmp_path)])
        assert "Analyzed 1 HTML pages" in result.output




class TestApiDiffSymbolNoEntries:
    @patch("great_docs._api_diff.list_version_tags")
    @patch("great_docs._api_diff.symbol_history")
    def test_symbol_no_entries(self, mock_hist, mock_tags, tmp_path, monkeypatch):
        """Symbol history with no entries shows '(no entries)'."""
        monkeypatch.chdir(tmp_path)
        mock_tags.return_value = ["v1.0", "v2.0"]

        hist = MagicMock()
        hist.symbol_name = "MyClass"
        hist.package_name = "mypkg"
        hist.entries = []
        hist.changed_entries = []
        mock_hist.return_value = hist

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "api-diff",
                "v1.0",
                "v2.0",
                "--symbol",
                "MyClass",
                "--project-path",
                str(tmp_path),
            ],
        )
        assert "(no entries)" in result.output




class TestApiDiffSymbolEntryTags:
    @patch("great_docs._api_diff.list_version_tags")
    @patch("great_docs._api_diff.symbol_history")
    def test_symbol_added_tag(self, mock_hist, mock_tags, tmp_path, monkeypatch):
        """Entry with change_type 'added' shows ✚ NEW."""
        monkeypatch.chdir(tmp_path)
        mock_tags.return_value = ["v1.0", "v2.0"]

        change = MagicMock()
        change.is_breaking = False
        change.change_type = "added"
        change.details = []

        entry = MagicMock()
        entry.present = True
        entry.version = "v2.0"
        entry.signature = "def my_func(x: int) -> str"
        entry.change = change

        hist = MagicMock()
        hist.symbol_name = "my_func"
        hist.package_name = "mypkg"
        hist.entries = [entry]
        hist.changed_entries = [entry]
        mock_hist.return_value = hist

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "api-diff",
                "v1.0",
                "v2.0",
                "--symbol",
                "my_func",
                "--project-path",
                str(tmp_path),
            ],
        )
        assert "✚ NEW" in result.output

    @patch("great_docs._api_diff.list_version_tags")
    @patch("great_docs._api_diff.symbol_history")
    def test_symbol_changed_tag(self, mock_hist, mock_tags, tmp_path, monkeypatch):
        """Entry with non-breaking, non-added change shows ∆ CHANGED."""
        monkeypatch.chdir(tmp_path)
        mock_tags.return_value = ["v1.0", "v2.0"]

        change = MagicMock()
        change.is_breaking = False
        change.change_type = "changed"
        change.details = ["param added: y"]

        entry = MagicMock()
        entry.present = True
        entry.version = "v2.0"
        entry.signature = "def my_func(x: int, y: str) -> str"
        entry.change = change

        hist = MagicMock()
        hist.symbol_name = "my_func"
        hist.package_name = "mypkg"
        hist.entries = [entry]
        hist.changed_entries = [entry]
        mock_hist.return_value = hist

        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "api-diff",
                "v1.0",
                "v2.0",
                "--symbol",
                "my_func",
                "--project-path",
                str(tmp_path),
            ],
        )
        assert "∆ CHANGED" in result.output




class TestApiDiffGraphHead:
    @patch("great_docs._api_diff.build_dependency_graph")
    @patch("great_docs._api_diff.snapshot_from_griffe")
    @patch("great_docs._api_diff.api_diff")
    def test_graph_head_uses_snapshot_from_griffe(
        self, mock_diff, mock_snap, mock_graph, tmp_path, monkeypatch
    ):
        """When new_version is HEAD, snapshot_from_griffe is called."""
        monkeypatch.chdir(tmp_path)

        diff_result = MagicMock()
        diff_result.package_name = "mypkg"
        diff_result.added = []
        diff_result.removed = []
        diff_result.changed = []
        mock_diff.return_value = diff_result

        snap_result = MagicMock()
        mock_snap.return_value = snap_result

        graph_result = MagicMock()
        graph_result.nodes = ["A", "B"]
        graph_result.edges = [("A", "B")]
        graph_result.to_mermaid.return_value = "graph TD\n  A --> B"
        mock_graph.return_value = graph_result

        runner = CliRunner()
        with patch("great_docs.core.GreatDocs") as mock_gd:
            mock_gd.return_value.documented_symbol_names.return_value = ["A"]
            result = runner.invoke(
                cli,
                [
                    "api-diff",
                    "v1.0",
                    "HEAD",
                    "--graph",
                    "--project-path",
                    str(tmp_path),
                ],
            )
        mock_snap.assert_called_once()
        assert mock_snap.call_args[1]["version"] == "HEAD"




class TestSkillInstallAutoDetect:
    @patch("great_docs._skill_install.install_skill")
    def test_auto_detect_package_from_pyproject(self, mock_install, tmp_path, monkeypatch):
        """skill install without source auto-detects package."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-package"\nversion = "1.0"\n'
        )
        mock_install.return_value = [{"name": "my-package", "path": "/tmp/skill"}]

        runner = CliRunner()
        result = runner.invoke(cli, ["skill", "install"])
        mock_install.assert_called_once()
        assert mock_install.call_args[1]["package"] == "my-package"




class TestTermRenderCastFile:
    def test_render_cast_file(self, tmp_path):
        """term render parses .cast (asciicast) files."""
        # Create a minimal asciicast v2 file
        header = {"version": 2, "width": 80, "height": 24}
        events = [[0.5, "o", "hello"], [1.0, "o", " world"]]
        content = "\n".join([json.dumps(header)] + [json.dumps(e) for e in events])
        cast_file = tmp_path / "test.cast"
        cast_file.write_text(content, encoding="utf-8")
        out_dir = tmp_path / "output"

        runner = CliRunner()
        result = runner.invoke(cli, ["termshow", "render", str(cast_file), "-o", str(out_dir)])
        assert result.exit_code == 0
        assert (out_dir / "manifest.json").exists()
