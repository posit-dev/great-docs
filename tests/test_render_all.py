from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


def test_build_package_reports_site_created_after_init(tmp_path: Path, monkeypatch):
    module_path = Path(__file__).parents[1] / "test-packages" / "render_all.py"
    spec = importlib.util.spec_from_file_location("gauntlet_render_all", module_path)
    assert spec is not None and spec.loader is not None
    render_all = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render_all)

    rendered_dir = tmp_path / "_rendered"
    package_dir = rendered_dir / "gdtest_minimal"

    def generate_package(_spec, _rendered_dir):
        package_dir.mkdir(parents=True)
        (package_dir / "pyproject.toml").write_text(
            '[project]\nname = "gdtest-minimal"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        return package_dir

    def run(command, **_kwargs):
        if command[1] == "init":
            docs = package_dir / "docs"
            docs.mkdir()
            (docs / "great-docs.yml").write_text("", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        site = package_dir / "docs" / "_site"
        site.mkdir(parents=True)
        (site / "index.html").write_text("<html></html>", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(render_all, "RENDERED_DIR", rendered_dir)
    monkeypatch.setattr(render_all, "LOGS_DIR", rendered_dir / "_logs")
    monkeypatch.setattr(render_all, "HUB_DIR", rendered_dir / "_hub")
    monkeypatch.setattr(render_all, "create_hub_page", lambda _results: None)
    monkeypatch.setattr(render_all, "get_spec", lambda _name: {"name": "gdtest_minimal"})
    monkeypatch.setattr(render_all, "generate_package", generate_package)
    monkeypatch.setattr(render_all.subprocess, "run", run)
    monkeypatch.setattr(sys, "path", sys.path.copy())

    result = render_all.build_package("gdtest_minimal")

    expected_site = package_dir / "docs" / "_site"
    assert result["status"] == "ok"
    assert Path(result["site_dir"]) == expected_site
    assert expected_site.is_dir()

    render_all.assemble_hub([result])

    assert (rendered_dir / "_hub" / "gdtest_minimal" / "index.html").is_file()
