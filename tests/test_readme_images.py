from pathlib import Path

import pytest

from great_docs import GreatDocs


@pytest.fixture(params=[".", "docs"])
def docs(tmp_path: Path, request: pytest.FixtureRequest) -> GreatDocs:
    source = tmp_path / request.param
    source.mkdir(parents=True, exist_ok=True)
    (source / "great-docs.yml").write_text("display_name: Sample\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "sample"\nversion = "1"\n')
    result = GreatDocs(str(tmp_path))
    result.build_dir.mkdir(parents=True)
    return result


def stage(docs: GreatDocs, content: str | None) -> str:
    if content is not None:
        (docs.project_root / "README.md").write_text(content)
    docs._create_index_from_readme()
    return (docs.build_dir / "index.qmd").read_text()


def destination(docs: GreatDocs, relative: str) -> Path:
    prefix = "_shared" if docs.layout.source_dir != docs.project_root else "."
    return docs.build_dir / prefix / relative


def test_copy_readme_images_basic(docs: GreatDocs) -> None:
    source = docs.project_root / "images/screenshot.png"
    source.parent.mkdir()
    source.write_bytes(b"fake png data")

    page = stage(docs, "# Sample\n\n![Screenshot](images/screenshot.png)\n")

    copied = destination(docs, "images/screenshot.png")
    assert copied.read_bytes() == source.read_bytes()
    assert copied.relative_to(docs.build_dir).as_posix() in page


def test_copy_readme_images_html_tags(docs: GreatDocs) -> None:
    source = docs.project_root / "diagrams/architecture.svg"
    source.parent.mkdir()
    source.write_bytes(b"<svg></svg>")

    page = stage(docs, '<img src="diagrams/architecture.svg" alt="Architecture">\n')

    copied = destination(docs, "diagrams/architecture.svg")
    assert copied.read_bytes() == source.read_bytes()
    assert f'src="{copied.relative_to(docs.build_dir).as_posix()}"' in page


def test_copy_readme_images_skips_urls(docs: GreatDocs) -> None:
    urls = [
        "https://example.com/img.png",
        "http://example.com/img.png",
        "//example.com/img.png",
        "data:image/png;base64,abc123",
    ]

    page = stage(docs, "\n".join(f"![External]({url})" for url in urls))

    assert all(url in page for url in urls)
    assert not list(docs.build_dir.rglob("*.png"))
    assert not (docs.build_dir / "_shared").exists()


def test_copy_readme_images_reuses_assets(docs: GreatDocs) -> None:
    source = docs.project_root / "assets/logo.svg"
    source.parent.mkdir()
    source.write_bytes(b"<svg></svg>")
    docs._copy_assets()

    page = stage(docs, "![Logo](assets/logo.svg)\n")

    copied = destination(docs, "assets/logo.svg")
    assert copied.read_bytes() == source.read_bytes()
    assert copied.relative_to(docs.build_dir).as_posix() in page
    assert list(docs.build_dir.rglob("logo.svg")) == [copied]


def test_copy_readme_images_none_source(docs: GreatDocs) -> None:
    page = stage(docs, None)

    assert "sample" in page
    assert not list(docs.build_dir.rglob("*.png"))
    assert not (docs.build_dir / "_shared").exists()


def test_copy_readme_images_missing_file(docs: GreatDocs) -> None:
    page = stage(docs, "![Missing](images/nonexistent.png)\n")

    assert "images/nonexistent.png" in page
    assert not destination(docs, "images/nonexistent.png").exists()
