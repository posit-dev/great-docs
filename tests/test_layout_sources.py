from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import quote, unquote, urlsplit

import pytest
from yaml12 import read_yaml, write_yaml

from great_docs import GreatDocs
from great_docs._layout import Layout
from great_docs._utils import QUARTO_YML_HEADER
from great_docs._versioned_build import assemble_site, run_versioned_build
from great_docs._versioning import VersionEntry, build_version_map, parse_versions_config


@pytest.fixture(params=[".", "docs", "website"])
def source_project(tmp_path: Path, request: pytest.FixtureRequest) -> tuple[Path, Path]:
    root = tmp_path
    source = root / request.param
    source.mkdir(exist_ok=True)
    (root / "pyproject.toml").write_text('[project]\nname = "sample"\nversion = "1.0"\n')
    (source / "great-docs.yml").write_text("module: sample\n")
    return root, source


def make_docs(root: Path, source: Path) -> GreatDocs:
    return GreatDocs(str(root), config_path=str(source / "great-docs.yml"))


def test_git_ref_does_not_rename_build(tmp_path: Path) -> None:
    config = tmp_path / "docs" / "great-docs.yml"
    config.parent.mkdir()
    config.write_text("display_name: Demo\n")
    layout = Layout.make(tmp_path, config)
    entry = VersionEntry(tag="1.5.0", label="1.5", git_ref="v1.5.0")
    assert layout.build_dir_for(entry.tag, "2.0.0") == tmp_path / "docs/_quarto/1.5.0"
    assert layout.build_dir_for("2.0.0", "2.0.0") == layout.build_dir


@pytest.mark.parametrize(
    "tag,segment",
    [
        ("v1.5.0", "1.5.0"),
        ("1.5.0", "1.5.0"),
        ("v1.5rc1", "1.5rc1"),
        ("version-next", "version-next"),
    ],
)
def test_layout_version_assembly(source_project: tuple[Path, Path], tag: str, segment: str) -> None:
    root, source = source_project
    layout = make_docs(root, source).layout
    versions = parse_versions_config(["2.0", tag])
    for entry in versions:
        build = layout.build_dir_for(entry.tag, "2.0")
        assert build.parent == layout.build_dir.parent
        (build / "_site").mkdir(parents=True)
        (build / "_quarto.yml").write_text(QUARTO_YML_HEADER)
        (build / "_site/index.html").write_text(entry.tag)
    assemble_site(layout.build_dir, versions, "2.0", layout.site_dir, layout=layout)
    assert (layout.site_dir / "index.html").read_text() == "2.0"
    assert (layout.site_dir / "v" / segment / "index.html").read_text() == tag
    assert (layout.build_dir_for(tag, "2.0") / "_site/index.html").read_text() == tag
    manifest = build_version_map(versions, {tag: ["index.html"]})
    assert manifest["versions"][1]["tag"] == tag
    assert manifest["versions"][1]["path_prefix"] == f"v/{segment}"
    if source != root:
        assemble_site(layout.build_dir, versions[:1], "2.0", layout.site_dir, layout=layout)
        assert not (layout.site_dir / "v").exists()


@pytest.mark.parametrize(
    "tags", [["v1.5.0", "1.5.0"], ["2.0", "v1.5.0", "1.5.0"], ["2.0", "release/1", "release-1"]]
)
@pytest.mark.parametrize("latest_only", [True, False])
def test_version_collisions_precede_output(
    source_project: tuple[Path, Path], tags: list[str], latest_only: bool
) -> None:
    root, source = source_project
    gd = make_docs(root, source)
    with pytest.raises(ValueError):
        run_versioned_build(gd.build_dir, root, tags, latest_only=latest_only, layout=gd.layout)
    assert not gd.build_dir.exists()
    assert not gd.layout.site_dir.exists()


@pytest.mark.parametrize("tag", [".", "..", "default"])
def test_unsafe_historical_build_names(source_project: tuple[Path, Path], tag: str) -> None:
    root, source = source_project
    if root == source:
        pytest.skip("Legacy sibling prefixes keep these names within the package")
    gd = make_docs(root, source)
    with pytest.raises(ValueError):
        run_versioned_build(gd.build_dir, root, ["2.0", tag], latest_only=True, layout=gd.layout)
    assert not gd.build_dir.parent.exists()


def test_freeze_round_trip(
    source_project: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    import runpy

    root, source = source_project
    gd = make_docs(root, source)
    for tag, files in [
        ("1.0", {"guide/old.json": "old", "guide/shared.json": "historical"}),
        ("2.0", {"guide/new.json": "new", "guide/shared.json": "latest"}),
    ]:
        build = gd.layout.build_dir_for(tag, "2.0")
        build.mkdir(parents=True)
        (build / "_quarto.yml").write_text(QUARTO_YML_HEADER)
        for name, content in files.items():
            cache = build / "_freeze" / name
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(content)
    assert gd._persist_freeze_cache() == 3
    assert (gd.layout.freeze_dir / "guide/old.json").read_text() == "old"
    assert (gd.layout.freeze_dir / "guide/shared.json").read_text() == "latest"
    assert gd._persist_freeze_cache() == 3
    monkeypatch.chdir(gd.layout.build_dir_for("1.0", "2.0"))
    runpy.run_path(str(gd.assets_path / "restore-freeze.py"))
    assert (Path.cwd() / "_freeze/guide/shared.json").read_text() == "latest"
    if root != source:
        assert not (root / "_freeze").exists()


@pytest.mark.parametrize("symlink", [False, True])
def test_latest_collision_preserves_source(
    source_project: tuple[Path, Path], symlink: bool
) -> None:
    root, source = source_project
    gd = make_docs(root, source)
    original = source / "original"
    original.mkdir()
    (original / "keep.txt").write_text("keep")
    gd.build_dir.parent.mkdir(parents=True, exist_ok=True)
    if symlink:
        gd.build_dir.symlink_to(original, target_is_directory=True)
    else:
        gd.build_dir.mkdir()
        (gd.build_dir / "keep.txt").write_text("keep")
    with pytest.raises(ValueError):
        gd._prepare_build_directory()
    assert (original / "keep.txt").read_text() == "keep"
    assert (gd.build_dir / "keep.txt").read_text() == "keep"


def test_unowned_deployment_is_preserved(source_project: tuple[Path, Path]) -> None:
    root, source = source_project
    if root == source:
        pytest.skip("Legacy output belongs to its Quarto project")
    gd = make_docs(root, source)
    gd.layout.site_dir.mkdir()
    (gd.layout.site_dir / "keep.txt").write_text("keep")
    with pytest.raises(ValueError):
        assemble_site(gd.build_dir, [], "", gd.layout.site_dir, layout=gd.layout)
    assert (gd.layout.site_dir / "keep.txt").read_text() == "keep"


def test_nonversion_assembly_and_uninstall(source_project: tuple[Path, Path]) -> None:
    root, source = source_project
    gd = make_docs(root, source)
    gd._prepare_build_directory()
    local_site = gd.build_dir / "_site"
    local_site.mkdir()
    (local_site / "index.html").write_text("home")
    assemble_site(gd.build_dir, [], "", gd.layout.site_dir, layout=gd.layout)
    assert (gd.layout.site_dir / "index.html").read_text() == "home"
    assert (local_site / "index.html").read_text() == "home"
    unrelated = gd.build_dir.parent / "great-docs-notes"
    unrelated.mkdir()
    (unrelated / "notes.qmd").write_text("source")
    gd.uninstall()
    assert not gd.build_dir.exists()
    assert not gd.layout.site_dir.exists()
    assert (unrelated / "notes.qmd").read_text() == "source"


@pytest.mark.parametrize("operation", ["build", "uninstall"])
def test_site_inventory_protects_added_content(
    source_project: tuple[Path, Path], operation: str
) -> None:
    root, source = source_project
    if source == root:
        pytest.skip("Legacy deployment remains inside the generated project")
    gd = make_docs(root, source)
    gd._prepare_build_directory()
    (gd.build_dir / "_site").mkdir()
    (gd.build_dir / "_site/index.html").write_text("home")
    assemble_site(gd.build_dir, [], "", gd.layout.site_dir, layout=gd.layout)
    (gd.layout.site_dir / "added.txt").write_text("keep")
    with pytest.raises(ValueError, match="unrecognised"):
        if operation == "build":
            gd._prepare_build_directory()
        else:
            gd.uninstall()
    assert (gd.layout.site_dir / "added.txt").read_text() == "keep"
    assert gd.layout.config_path.is_file()
    assert (gd.build_dir / "_site/index.html").read_text() == "home"


def test_build_collision_precedes_config_refresh(source_project: tuple[Path, Path]) -> None:
    root, source = source_project
    config = source / "great-docs.yml"
    text = "module: sample\nversions: [v1.5.0, 1.5.0]\n"
    config.write_text(text)
    gd = make_docs(root, source)
    with patch("great_docs.core._ensure_quarto_installed", side_effect=AssertionError("too late")):
        with pytest.raises(ValueError, match="URL segment"):
            gd.build(latest_only=True)
    assert config.read_text() == text
    assert not gd.build_dir.exists()


def test_freeze_custom_config_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import runpy

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "sample"\nversion = "1.0"\n')
    source = tmp_path / "website"
    source.mkdir()
    config = source / "custom.yml"
    config.write_text("module: sample\n")
    (source / "_freeze").mkdir()
    (source / "_freeze/result.json").write_text("cached")
    gd = GreatDocs(str(tmp_path), config_path=str(config))
    gd._prepare_build_directory()
    monkeypatch.chdir(gd.build_dir)
    runpy.run_path(str(gd.build_dir / "scripts/restore-freeze.py"))
    assert (gd.build_dir / "_freeze/result.json").read_text() == "cached"


@pytest.mark.parametrize("explicit", [False, True])
def test_documentation_sources(source_project: tuple[Path, Path], explicit: bool) -> None:
    root, source = source_project
    guide = "user_guide" if explicit else "manual"
    for directory in (guide, "recipes", "custom", "assets", "hooks", "notebooks"):
        (source / directory).mkdir()
    for name in (f"{guide}/01-start.qmd", "recipes/start.qmd", "custom/about.qmd"):
        (source / name).write_text("---\ntitle: Start\n---\nHello\n")
    for name in ("references.bib", "citation.csl", "style.css", "hooks/prepare.py", "header.html"):
        (source / name).write_text("fixture")
    (source / "assets/logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    (source / "README.md").write_text("# Local documentation\n![Logo](assets/logo.svg)\n")
    write_yaml(
        {
            "module": "sample",
            "user_guide": [{"section": "Guide", "contents": ["01-start.qmd"]}]
            if explicit
            else guide,
            "sections": [{"title": "Recipes", "dir": "recipes"}],
            "custom_pages": [{"dir": "custom", "output": "custom"}],
            "bibliography": "references.bib",
            "csl": "citation.csl",
            "site": {"css": "style.css"},
            "pre_render": ["hooks/prepare.py"],
            "logo": "assets/logo.svg",
            "hero": False,
            "favicon": "assets/logo.svg",
            "include_in_header": [{"file": "header.html"}],
            "authors": [{"name": "Example", "image": "assets/logo.svg"}],
        },
        source / "great-docs.yml",
    )
    gd = make_docs(root, source)
    gd._prepare_build_directory()
    gd._copy_assets()
    gd._copy_user_guide_to_docs(gd._discover_user_guide())
    gd._process_sections()
    gd._process_custom_pages()
    build = gd.build_dir
    assert build == (root / "great-docs" if root == source else source / "_quarto/default")
    assert not hasattr(gd, "project_path")
    assert not hasattr(gd, "docs_dir")
    for name in (
        "_quarto.yml",
        "mermaid-renderer.js",
        "references.bib",
        "citation.csl",
        "style.css",
        "scripts/prepare.py",
        "scripts/post-render.py",
        "assets/logo.svg",
        "recipes/start.qmd",
        "custom/about.qmd",
        "_includes/header.html",
        "_shared/authors/logo.svg",
        "favicon.svg",
    ):
        assert (build / name).is_file(), name
    guide_name = "01-start.qmd" if explicit else "start.qmd"
    assert (build / "user-guide" / guide_name).is_file()
    config = read_yaml(build / "_quarto.yml")
    assert config["project"]["output-dir"] == "_site"
    assert "scripts/prepare.py" in config["project"]["pre-render"]
    assert config["bibliography"] == "references.bib"
    assert {"file": "_includes/header.html"} in config["format"]["html"]["include-in-header"]
    assert gd._find_package_root() == root
    assert gd.layout.cache_dir == (
        root / ".great-docs-cache" if root == source else source / ".cache"
    )
    if source != root:
        assert not (source / "_quarto/_quarto.yml").exists()


def test_landing_precedence_and_shared_references(source_project: tuple[Path, Path]) -> None:
    root, source = source_project
    (root / "assets").mkdir()
    (root / "assets/logo.svg").write_text("shared logo")
    (root / "README.md").write_text("# Package\n![Logo](assets/logo.svg?raw=1#logo)")
    gd = make_docs(root, source)
    gd.build_dir.mkdir(parents=True)
    assert gd._find_index_source_file()[0] == root / "README.md"
    if source != root:
        (source / "index.md").write_text(
            '![Logo](../assets/logo.svg) <img src="../assets/logo.svg#mark"> [Download](../assets/logo.svg)'
        )
        assert gd._find_index_source_file()[0] == source / "index.md"
    page = gd._find_index_source_file()[0]
    assert page is not None
    content = gd._rebase_source_references(page.read_text(), page, gd.build_dir / "index.qmd")
    assert "../assets" not in content
    assert "logo.svg" in content
    assert list(gd.build_dir.rglob("*.svg"))
    assert not (source / "_quarto/assets").exists()


def test_duplicate_hook_names_fail_before_copy(source_project: tuple[Path, Path]) -> None:
    root, source = source_project
    for directory in ("a", "b"):
        (source / directory).mkdir()
        (source / directory / "prepare.py").write_text(directory)
    write_yaml(
        {"module": "sample", "pre_render": ["a/prepare.py", "b/prepare.py"]},
        source / "great-docs.yml",
    )
    gd = make_docs(root, source)
    with pytest.raises(ValueError, match="hook|script"):
        gd._prepare_build_directory()


def test_nested_sources_and_shared_assets(source_project: tuple[Path, Path]) -> None:
    root, source = source_project
    (root / "shared").mkdir()
    (root / "shared/plot.svg").write_text("plot")
    (source / "user_guide/deep").mkdir(parents=True)
    prefix = "../" if source == root else "../../"
    page = source / "user_guide/deep/example.qmd"
    page.write_text(f"---\ntitle: Example\n---\n![Plot]({prefix}../shared/plot.svg#panel)")
    gd = make_docs(root, source)
    gd.build_dir.mkdir(parents=True)
    gd._copy_user_guide_to_docs(gd._discover_user_guide())
    generated = gd.build_dir / "user-guide/deep/example.qmd"
    content = generated.read_text()
    asset = "shared/plot.svg" if source == root else "_shared/shared/plot.svg"
    assert f"{asset}#panel" in content
    assert (gd.build_dir / asset).read_text() == "plot"


def test_asset_collision_is_rejected(source_project: tuple[Path, Path]) -> None:
    root, source = source_project
    (source / "image.png").write_text("source")
    gd = make_docs(root, source)
    gd.build_dir.mkdir(parents=True)
    (gd.build_dir / "image.png").write_text("generated")
    with pytest.raises(ValueError, match="conflict"):
        gd._rebase_source_references(
            "![Image](image.png)", source / "README.md", gd.build_dir / "index.qmd"
        )
    assert (gd.build_dir / "image.png").read_text() == "generated"


def test_shared_section_keeps_slug_and_custom_output_is_contained(
    source_project: tuple[Path, Path],
) -> None:
    root, source = source_project
    gd = make_docs(root, source)
    configured = "recipes" if root == source else "../recipes"
    assert gd._section_build_dir({"dir": configured}) == gd.build_dir / "recipes"
    nested = "guides/recipes" if root == source else "../guides/recipes"
    assert gd._section_build_dir({"dir": nested}) == gd.build_dir / "guides/recipes"
    for output in ("../escape", str(root / "escape")):
        with pytest.raises(ValueError, match="inside"):
            gd._output_directory(output)


def test_notebooks_use_documentation_root(source_project: tuple[Path, Path]) -> None:
    root, source = source_project
    (source / "notebooks").mkdir()
    (source / "notebooks/data.json").write_text("{}")
    write_yaml({"module": "sample", "marimo": True}, source / "great-docs.yml")
    gd = make_docs(root, source)
    marimo = MagicMock()
    marimo.get_islands_head_html.return_value = ""
    with (
        patch("importlib.util.find_spec", return_value=object()),
        patch.dict("sys.modules", {"great_docs._marimo": marimo}),
    ):
        gd._prepare_build_directory()
    assert (gd.build_dir / "notebooks/data.json").read_text() == "{}"


def test_api_reference_build_uses_selected_cwd(
    source_project: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from great_docs._apiref.api_reference import APIReference

    class ReferenceReached(BaseException):
        pass

    root, source = source_project
    gd = make_docs(root, source)
    original_cwd = Path.cwd()
    prepare = gd._prepare_build_directory

    def prepare_reference() -> None:
        prepare()
        gd._has_api_reference = True

    def check_cwd(ref: APIReference) -> None:
        assert Path.cwd() == gd.build_dir
        raise ReferenceReached

    monkeypatch.setattr("great_docs.core._ensure_quarto_installed", lambda: None)
    monkeypatch.setattr(gd, "_prepare_build_directory", prepare_reference)
    monkeypatch.setattr(APIReference, "__init__", lambda self, path: None)
    monkeypatch.setattr(APIReference, "build", check_cwd)
    with pytest.raises(ReferenceReached):
        gd.build(refresh=False)
    assert Path.cwd() == original_cwd


def test_landing_links_follow_generated_page_paths(source_project: tuple[Path, Path]) -> None:
    root, source = source_project
    (source / "user_guide").mkdir()
    (source / "user_guide/01-start.qmd").write_text("# Start")
    gd = make_docs(root, source)
    content = "[Start](user_guide/01-start.qmd#intro)"
    assert (
        gd._rebase_source_references(content, source / "index.md", gd.build_dir / "index.qmd")
        == "[Start](user-guide/start.qmd#intro)"
    )


def test_rebasing_preserves_code_examples(source_project: tuple[Path, Path]) -> None:
    root, source = source_project
    (source / "logo.svg").write_text("logo")
    gd = make_docs(root, source)
    content = '```markdown\n![Logo](logo.svg)\n```\n`![Logo](logo.svg)`\n    <img src="logo.svg">\n<pre>![Logo](logo.svg)</pre>\n'
    assert (
        gd._rebase_source_references(content, source / "index.md", gd.build_dir / "index.qmd")
        == content
    )
    assert not gd.build_dir.exists()


@pytest.mark.parametrize(
    "markup",
    [
        '![Plot][plot]\n\n[plot]: assets/plot.svg "A plot"\n',
        '<img\n  alt="Plot"\n  src="assets/plot.svg">\n',
        '<div>\n    <img src="assets/plot.svg">\n</div>\n',
        '```{=html}\n    <img src="assets/plot.svg">\n```\n',
        '```{html}\n<img src="assets/plot.svg">\n```\n',
        '<video poster="assets/plot.svg" src="assets/plot.svg"></video>\n',
        '<img alt=\'src="assets/other.svg"\' src="assets/plot.svg">\n',
    ],
)
def test_static_reference_forms_copy_package_readme_assets(
    source_project: tuple[Path, Path], markup: str
) -> None:
    root, source = source_project
    (root / "assets").mkdir()
    (root / "assets/plot.svg").write_text("plot")
    (root / "assets/other.svg").write_text("other")
    (root / "README.md").write_text(markup)
    gd = make_docs(root, source)
    result = gd._rebase_source_references(markup, root / "README.md", gd.build_dir / "index.qmd")
    expected_path = "assets/plot.svg" if source == root else "_shared/assets/plot.svg"
    assert result == markup.replace("assets/plot.svg", expected_path)
    assert (gd.build_dir / expected_path).read_text() == "plot"


@pytest.mark.parametrize(
    "filename", ["plot chart.svg", "plot#chart.svg", "plot?chart.svg", "plot%chart.svg"]
)
def test_asset_references_preserve_url_escaping(
    source_project: tuple[Path, Path], filename: str
) -> None:
    root, source = source_project
    (source / filename).write_text("plot")
    gd = make_docs(root, source)
    reference = quote(filename) + "?raw=1#panel"
    markup = f"![Plot]({reference})"
    result = gd._rebase_source_references(markup, source / "README.md", gd.build_dir / "index.qmd")
    assert result == markup
    assert (gd.build_dir / filename).is_file()


def test_page_references_preserve_url_escaping(source_project: tuple[Path, Path]) -> None:
    root, source = source_project
    (source / "user_guide").mkdir()
    (source / "user_guide/01-start #?.qmd").write_text("# Start")
    gd = make_docs(root, source)
    result = gd._rebase_source_references(
        "[Start](user_guide/01-start%20%23%3F.qmd#intro)",
        source / "index.md",
        gd.build_dir / "index.qmd",
    )
    assert result == "[Start](user-guide/start%20%23%3F.qmd#intro)"


def test_blended_homepage_references_use_final_destination(
    source_project: tuple[Path, Path],
) -> None:
    root, source = source_project
    (root / "assets").mkdir()
    (root / "assets/plot.svg").write_text("plot")
    guide = source / "user_guide"
    guide.mkdir()
    prefix = "../" if root == source else "../../"
    (guide / "01-start.qmd").write_text(
        f"---\ntitle: Start\n---\n![Plot]({prefix}assets/plot.svg)\n[Next](02-next.qmd)"
    )
    (guide / "02-next.qmd").write_text("---\ntitle: Next\n---\n[Start](01-start.qmd#top)")
    write_yaml(
        {"module": "sample", "homepage": "user_guide", "hero": False}, source / "great-docs.yml"
    )
    gd = make_docs(root, source)
    gd._prepare_build_directory()
    info = gd._discover_user_guide()
    copied = gd._copy_user_guide_to_docs(info)
    gd._create_blended_index(info, copied)
    result = (gd.build_dir / "index.qmd").read_text()
    path = result.split("![Plot](", 1)[1].split(")", 1)[0]
    assert (gd.build_dir / unquote(urlsplit(path).path)).resolve().is_relative_to(gd.build_dir)
    assert (gd.build_dir / unquote(urlsplit(path).path)).read_text() == "plot"
    assert "[Next](user-guide/next.qmd)" in result
    assert "[Start](../index.qmd#top)" in (gd.build_dir / "user-guide/next.qmd").read_text()


def test_custom_html_rebases_local_assets(source_project: tuple[Path, Path]) -> None:
    root, source = source_project
    (root / "assets").mkdir()
    (root / "assets/plot.svg").write_text("plot")
    (source / "custom").mkdir()
    prefix = "../" if root == source else "../../"
    (source / "custom/about.html").write_text(
        f'---\nlayout: raw\n---\n<div>\n    <img\n      src="{prefix}assets/plot.svg">\n</div>'
    )
    gd = make_docs(root, source)
    gd._prepare_build_directory()
    gd._process_custom_pages()
    result = (gd.build_dir / "custom/about.html").read_text()
    path = result.split('src="', 1)[1].split('"', 1)[0]
    assert (gd.build_dir / "custom" / unquote(urlsplit(path).path)).read_text() == "plot"
