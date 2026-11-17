import textwrap

import griffe as gf
import pytest

from great_docs._apiref._settings import Settings
from great_docs._apiref._tools import _render
from great_docs._builtin.normalization._doctest import (
    _fence_doctest_blocks,
    normalize_doctests,
)


def _function(text: str, parser: str) -> gf.Function:
    """Build a function with a docstring parsed in the selected style"""
    obj = gf.Function("process")
    obj.docstring = gf.Docstring(text, parent=obj, parser=parser)
    return obj


@pytest.mark.parametrize("parser", ["numpy", "google", "sphinx"])
def test_doctests_are_fenced_for_every_parser(parser: str):
    obj = _function("Example.\n\n>>> for i in range(2):\n...     print(i)\n0\n1", parser)

    result = normalize_doctests(obj)

    assert result is obj
    assert obj.docstring.value == (
        "Example.\n\n```python\n>>> for i in range(2):\n...     print(i)\n0\n1\n```"
    )


def test_separate_doctest_groups_get_separate_fences():
    obj = _function(">>> first()\n\nText.\n\n>>> second()", "numpy")

    normalize_doctests(obj)

    assert obj.docstring.value.count("```python") == 2
    assert obj.docstring.value.count("```") == 4


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "- A bullet:\n\n  >>> f()\n  1\n",
            "- A bullet:\n\n  ```python\n  >>> f()\n  1\n  ```\n",
            id="list-item",
        ),
        pytest.param(
            "Example:\n    >>> f()\n    3\n",
            "Example:\n    ```python\n    >>> f()\n    3\n    ```\n",
            id="section-body",
        ),
        pytest.param(
            "Indented:\n\n    >>> f()\n    1\n",
            "Indented:\n\n    ```python\n    >>> f()\n    1\n    ```\n",
            id="indented-block",
        ),
    ],
)
def test_fence_markers_match_prompt_indentation(source: str, expected: str):
    """
    Fence markers match the indentation of their prompts

    A column-zero fence closes its containing list item or indented block. Test
    the transform directly because Griffe dedents each `Docstring` value and
    would remove the indentation under test.
    """
    assert _fence_doctest_blocks(source) == expected


def test_fence_contains_expected_output():
    """
    Expected output remains inside the example's fence

    Quarto parses unfenced output such as `<Widget>` as raw HTML and omits it
    from the page.
    """
    obj = _function(">>> Widget()\n<Widget>", "numpy")

    normalize_doctests(obj)

    assert obj.docstring.value == "```python\n>>> Widget()\n<Widget>\n```"


def test_unseparated_examples_share_one_fence():
    """Examples without a separating blank line form one block"""
    obj = _function(">>> first()\n1\n>>> second()\n2", "numpy")

    normalize_doctests(obj)

    assert obj.docstring.value == "```python\n>>> first()\n1\n>>> second()\n2\n```"


def test_blank_line_ends_example():
    """A blank line ends the example, matching `doctest` parsing"""
    obj = _function(">>> f()\n1\n\nProse about the result.", "numpy")

    normalize_doctests(obj)

    assert obj.docstring.value == "```python\n>>> f()\n1\n```\n\nProse about the result."


def test_dedent_ends_expected_output():
    """
    A dedent ends the expected output

    A subsequent list item belongs to neither the output nor the example's
    block. Including it would consume the rest of the list.
    """
    obj = _function("- First:\n\n  >>> f()\n  1\n- Second:", "numpy")

    normalize_doctests(obj)

    assert obj.docstring.value == "- First:\n\n  ```python\n  >>> f()\n  1\n  ```\n- Second:"


@pytest.mark.parametrize(
    "source",
    [
        "Ordinary prose.",
        "```python\n>>> already_fenced()\n```",
        "```{python}\n>>> executable_cell()\n```",
    ],
)
def test_doctest_normalization_preserves_non_targets(source: str):
    obj = _function(source, "numpy")

    normalize_doctests(obj)

    assert obj.docstring.value == source


def test_doctest_normalization_registers_on_import():
    from great_docs.hooks import _object_resolved

    assert normalize_doctests in _object_resolved.REGISTRY


def _render_with_hooks(source: str, name: str, parser: str = "numpy") -> str:
    """Render the named object of a source snippet to qmd, with the hooks applied"""
    with gf.temporary_visited_package(
        "package", {"__init__.py": textwrap.dedent(source)}, docstring_parser=parser
    ) as package:
        return _render(package[name], Settings(parser=parser))


def _unfenced_prompts(qmd: str) -> list[str]:
    """Return the doctest prompt lines of `qmd` that fall outside a code fence"""
    outside: list[str] = []
    in_fence = False
    for line in qmd.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
        elif stripped.startswith(">>>") and not in_fence:
            outside.append(line)
    return outside


@pytest.mark.parametrize(
    ("name", "source"),
    [
        (
            "prose_then_code",
            '''
            def prose_then_code():
                """
                Do a thing.

                Examples
                --------
                Some explanatory prose.

                >>> prose_then_code()
                3
                """
            ''',
        ),
        (
            "two_groups",
            '''
            def two_groups():
                """
                Do two things.

                Examples
                --------
                >>> two_groups()
                1

                >>> two_groups()
                2
                """
            ''',
        ),
        (
            "no_section",
            '''
            def no_section():
                """
                Do an unsectioned thing.

                >>> no_section()
                3
                """
            ''',
        ),
        (
            "google_header",
            '''
            def google_header():
                """
                Do a thing.

                Example:
                    >>> google_header()
                    3
                """
            ''',
        ),
        (
            "rst_literal",
            '''
            def rst_literal():
                """
                Do a thing.

                Examples
                --------
                ::

                    >>> rst_literal()
                    3
                """
            ''',
        ),
        (
            "indented_groups",
            '''
            def indented_groups():
                """
                Do two things.

                Examples
                --------
                Indented block:

                    >>> indented_groups()
                    1

                    >>> indented_groups()
                    2
                """
            ''',
        ),
        (
            "nested_in_list",
            '''
            def nested_in_list():
                """
                Do a listed thing.

                Examples
                --------
                - First bullet:

                  >>> nested_in_list()
                  1
                """
            ''',
        ),
        (
            "Widget",
            '''
            class Widget:
                """
                A widget.

                Examples
                --------
                >>> Widget()
                <Widget>
                """

                def resize(self):
                    """
                    Resize the widget.

                    Examples
                    --------
                    >>> for i in range(2):
                    ...     print(i)
                    0
                    1
                    """
            ''',
        ),
    ],
)
def test_every_doctest_prompt_reaches_the_qmd_fenced(name: str, source: str):
    """
    No doctest prompt survives into the qmd outside a code fence

    An unfenced prompt reaches Quarto as markdown, where a leading `>` is a
    blockquote marker and the block is left unhighlighted. The prompts must be
    fenced whatever their shape: inside an `Examples` section or loose in the
    subject, one group or several, indented under a literal block, a paragraph
    or a list item, and on a class or on its members.
    """
    qmd = _render_with_hooks(source, name)

    assert ">>>" in qmd, "the sample rendered without its doctest at all"
    assert _unfenced_prompts(qmd) == []


@pytest.mark.parametrize(
    ("parser", "docstring"),
    [
        (
            "google",
            """
            Do a thing.

            Args:
                value: The value.

            Examples:
                >>> convert(1)
                1

                >>> convert(2)
                2
            """,
        ),
        (
            "sphinx",
            """
            Do a thing.

            :param value: The value.

            .. rubric:: Examples

            >>> convert(1)
            1

            >>> convert(2)
            2
            """,
        ),
    ],
)
def test_native_dialect_doctests_reach_the_qmd_fenced(parser: str, docstring: str):
    """
    A docstring written in its configured dialect keeps its prompts fenced

    The dialect decides how griffe splits the sections, so each one reaches the
    fencing hook differently.
    """
    source = f'''
    def convert(value):
        """
        {textwrap.indent(textwrap.dedent(docstring), " " * 8).strip()}
        """
    '''

    qmd = _render_with_hooks(source, "convert", parser=parser)

    assert ">>>" in qmd, "the sample rendered without its doctest at all"
    assert _unfenced_prompts(qmd) == []


def test_indented_example_remains_inside_list_item():
    """
    An indented example remains intact inside its rendered list item

    The fence markers must stay inside the bullet, and the expected output must
    stay inside the fence.
    """
    source = '''
    def listed():
        """
        Return a listed value.

        Examples
        --------
        - First bullet:

          >>> listed()
          <Listed>
        """
    '''

    qmd = _render_with_hooks(source, "listed")

    assert "  ```python\n  >>> listed()\n  <Listed>\n  ```" in qmd
    assert _unfenced_prompts(qmd) == []
