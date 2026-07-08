from great_docs._apiref._tools import render_code_variable


def test_dataclass_parameters():
    code = '''
    from dataclasses import InitVar, dataclass
    from typing import ClassVar

    @dataclass
    class Base:
        """
        Just testing things
        """

        a: InitVar[int] = 1
        "Init Parameter a"
        b: float = 2
        "Parameter b"
        x: ClassVar[str]
        "Base Class variable x"

        def __post_init__(self, a: int):
            pass

        @property
        def base_value(self):
            pass

    @dataclass
    class Derived(Base):
        """
        Docstring of derived class
        """

        c: float = 3.0
        "Parameter c"
        y: ClassVar[str]
        "Derived Class variable y"

        def __post_init__(self, a: int):
            pass

        @property
        def derived_value(self):
            pass
    '''
    qmd = render_code_variable(code, "Derived")

    def assert_in_qmd(name: str, annotation: str, default: str, co: str = ""):
        """
        Ensure that a parameter is rendered
        """
        assert f"<code>[{name}]{{.doc-parameter-name}}" in qmd
        assert f"[{annotation}]{{.doc-parameter-annotation}}" in qmd
        assert f"[[{default}]{{.{co}}}]{{.doc-parameter-default}}</code>" in qmd

    assert "## Init Parameters {.doc-init-parameters}" in qmd

    assert_in_qmd("a", "int", "1", "dv")

    assert "## Parameter Attributes {.doc-parameter-attributes}" in qmd

    assert_in_qmd("b", "float", "2", "dv")
    assert_in_qmd("c", "float", "3.0", "fl")


def test_dataclass_parameter_docstrings():
    code = """
    from dataclasses import dataclass

    @dataclass(kw_only=True)
    class Base:
        a: str = "param a"
        "Parameter a"
    """

    qmd = render_code_variable(code, "Base")

    assert ":   Parameter a" in qmd


def test_contained_docstring_link():
    code = """
    from dataclasses import dataclass

    class Base:
        def meth(self):
            "Interesting method of class Base"
    """

    qmd = render_code_variable(code, "Base")

    # Methods in summary tables use short name anchors (matching Quarto section IDs)
    assert '<a href="#meth"' in qmd and ">meth()</a>" in qmd


def test_dataclass_with_methods_keeps_constructor_signature():
    """A dataclass that also defines methods must still render its constructor
    signature.

    Regression: `Class.overloads` is a `dict` keyed by member name, so any
    class that merely defines a method had a non-empty (truthy) `overloads`
    and was rendered through the overload path, producing an empty `Name()`
    usage signature instead of the dataclass constructor.
    """
    code = '''
    from dataclasses import dataclass

    @dataclass
    class Widget:
        """A widget."""

        name: str
        size: int = 1

        def resize(self, size: int) -> None:
            """Resize the widget."""
            self.size = size
    '''
    qmd = render_code_variable(code, "Widget")

    # The usage signature must include the constructor parameters, not a bare `Widget()`.
    assert "Widget(name, size=1)" in qmd


def test_dataclass_without_methods_keeps_constructor_signature():
    """Control: a dataclass with only fields renders its constructor signature.

    This already worked before the overloads fix and guards against a regression
    in the other direction.
    """
    code = '''
    from dataclasses import dataclass

    @dataclass
    class Widget:
        """A widget."""

        name: str
        size: int = 1
    '''
    qmd = render_code_variable(code, "Widget")

    assert "Widget(name, size=1)" in qmd


def test_dataclass_attributes_section_not_duplicated():
    """A dataclass documented with an `Attributes` section renders that section
    once, without a synthesized "Parameter Attributes" duplicate.

    The author may document a dataclass's fields with either a `Parameters` or
    an `Attributes` section; great-docs must not also auto-generate a
    "Parameter Attributes" section listing the same fields.
    """
    code = '''
    from dataclasses import dataclass

    @dataclass
    class Widget:
        """A widget.

        Attributes
        ----------
        name
            The widget name.
        size
            The widget size.
        """

        name: str
        size: int = 1
    '''
    qmd = render_code_variable(code, "Widget")

    assert "## Attributes {.doc-attributes}" in qmd
    assert "## Parameter Attributes {.doc-parameter-attributes}" not in qmd
    # The author's descriptions must be preserved.
    assert "The widget name." in qmd


def test_dataclass_parameters_section_not_duplicated():
    """A dataclass documented with a `Parameters` section renders that section
    once, without a synthesized "Parameter Attributes" duplicate.
    """
    code = '''
    from dataclasses import dataclass

    @dataclass
    class Widget:
        """A widget.

        Parameters
        ----------
        name
            The widget name.
        size
            The widget size.
        """

        name: str
        size: int = 1
    '''
    qmd = render_code_variable(code, "Widget")

    assert "## Parameters {.doc-parameters}" in qmd
    assert "## Parameter Attributes {.doc-parameter-attributes}" not in qmd
    assert "The widget name." in qmd
