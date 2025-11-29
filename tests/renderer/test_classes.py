from great_docs.renderer._tools import render_code_variable


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

        c: float = 3
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
    assert "## Init Parameters {.doc-init-parameters}" in qmd
    assert "<code>a: [int](`int`) =  1</code>" in qmd
    assert "## Parameter Attributes {.doc-parameter-attributes}" in qmd
    assert "<code>b: [float](`float`) = 2</code>" in qmd
    assert "<code>c: [float](`float`) = 3</code>" in qmd


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
    assert "[meth](#package.Base.meth)" in qmd
