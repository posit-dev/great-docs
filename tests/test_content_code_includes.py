from pathlib import Path

import pytest

from great_docs._content import code_includes
from great_docs._layout import Layout


@pytest.fixture
def layout(tmp_path: Path) -> Layout:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    return Layout.make(tmp_path)


def test_includes_a_code_file_as_a_fenced_block(tmp_path: Path, layout: Layout):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "demo.py").write_text('print("hello")\nx = 42\n')
    content = "Some text\n\n{{< include examples/demo.py >}}\n\nMore text"

    result = code_includes.expand(content, tmp_path, layout)

    assert result == 'Some text\n\n```python\nprint("hello")\nx = 42\n```\n\nMore text'


def test_includes_each_shortcode_in_a_page(tmp_path: Path, layout: Layout):
    (tmp_path / "a.py").write_text("alpha\n")
    (tmp_path / "b.yaml").write_text("key: value\n")
    content = "{{< include a.py >}}\n\n{{< include b.yaml >}}\n"

    result = code_includes.expand(content, tmp_path, layout)

    assert result == "```python\nalpha\n```\n\n```yaml\nkey: value\n```\n"


def test_lang_overrides_the_language_of_the_suffix(tmp_path: Path, layout: Layout):
    (tmp_path / "script.py").write_text("x = 1\n")

    result = code_includes.expand('{{< include script.py lang="text" >}}', tmp_path, layout)

    assert result == "```text\nx = 1\n```"


def test_unknown_suffix_gives_a_block_without_language(tmp_path: Path, layout: Layout):
    (tmp_path / "data.xyz").write_text("some data\n")

    result = code_includes.expand("{{< include data.xyz >}}", tmp_path, layout)

    assert result == "```\nsome data\n```"


@pytest.mark.parametrize(
    ("lines", "expected"),
    [("2-4", "line2\nline3\nline4"), ("2", "line2"), ("4-100", "line4\nline5")],
)
def test_lines_selects_an_inclusive_range(
    tmp_path: Path, layout: Layout, lines: str, expected: str
):
    (tmp_path / "code.py").write_text("line1\nline2\nline3\nline4\nline5\n")

    result = code_includes.expand(f'{{{{< include code.py lines="{lines}" >}}}}', tmp_path, layout)

    assert result == f"```python\n{expected}\n```"


def test_lang_and_lines_combine_in_any_order(tmp_path: Path, layout: Layout):
    (tmp_path / "code.py").write_text("# header\nimport os\nprint(os.getcwd())\n")
    content = '{{< include "code.py" lines="2-3" lang="text" >}}'

    result = code_includes.expand(content, tmp_path, layout)

    assert result == "```text\nimport os\nprint(os.getcwd())\n```"


def test_fence_is_longer_than_any_backtick_run(tmp_path: Path, layout: Layout):
    (tmp_path / "example.txt").write_text("Some text\n```python\nx = 1\n```\n")

    result = code_includes.expand("{{< include example.txt >}}", tmp_path, layout)

    assert result == "````\nSome text\n```python\nx = 1\n```\n````"


def test_page_directory_is_searched_before_the_package_root(tmp_path: Path, layout: Layout):
    guide = tmp_path / "user_guide"
    (guide / "snippets").mkdir(parents=True)
    (guide / "snippets" / "example.py").write_text("local = True\n")
    (tmp_path / "snippets").mkdir()
    (tmp_path / "snippets" / "example.py").write_text("root = True\n")

    result = code_includes.expand("{{< include snippets/example.py >}}", guide, layout)

    assert "local = True" in result


def test_package_root_is_searched_last(tmp_path: Path, layout: Layout):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.js").write_text('console.log("hello");\n')
    guide = tmp_path / "user_guide"
    guide.mkdir()

    result = code_includes.expand("{{< include src/app.js >}}", guide, layout)

    assert result == '```javascript\nconsole.log("hello");\n```'


def test_missing_file_becomes_a_comment(tmp_path: Path, layout: Layout):
    result = code_includes.expand("{{< include does/not/exist.py >}}", tmp_path, layout)

    assert result == "<!-- include error: file not found: does/not/exist.py -->"


def test_unreadable_file_becomes_a_comment(tmp_path: Path, layout: Layout):
    (tmp_path / "data.bin").write_bytes(b"\xff\xfe\x00")

    result = code_includes.expand("{{< include data.bin >}}", tmp_path, layout)

    assert result.startswith("<!-- include error: ")


@pytest.mark.parametrize(
    "content",
    [
        "# Hello\n\n{{< icon heart >}}\n",
        "Before\n\n{{< include _shared.qmd >}}\n\nAfter",
        '{{< include lang="python" >}}',
        "{{{< include examples/usage.py >}}}",
    ],
    ids=["other-shortcode", "page-include", "no-path", "escaped"],
)
def test_leaves_other_shortcodes_for_quarto(tmp_path: Path, layout: Layout, content: str):
    (tmp_path / "_shared.qmd").write_text("# Shared\n")

    assert code_includes.expand(content, tmp_path, layout) == content


@pytest.mark.parametrize("keyword", ['lang="markdown"', 'lines="1-2"'])
def test_page_include_with_lang_or_lines_becomes_code(tmp_path: Path, layout: Layout, keyword: str):
    (tmp_path / "snippet.qmd").write_text("---\ntitle: Example\n---\n")

    result = code_includes.expand(f"{{{{< include snippet.qmd {keyword} >}}}}", tmp_path, layout)

    assert "{{< include" not in result
    assert "title: Example" in result
