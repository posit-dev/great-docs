from great_docs._apiref._tools import render_code_variable


def test_dataclass_with_keyword_only_signature():
    code = """
    from dataclasses import KW_ONLY, dataclass
    from typing import ClassVar

    @dataclass
    class Point:
        x: float
        _: KW_ONLY
        y: float
        z: float
    """
    qmd = render_code_variable(code, "Point")
    assert "Point(\n    x,\n    *,\n    y,\n    z,\n)" in qmd


def test_position_only_and_keyword_only_signatures():
    code = """
    def func(a, b, /, c, d, *, e, f):
        pass
    """
    qmd = render_code_variable(code, "func")
    assert "func(\n    a,\n    b,\n    /,\n    c,\n    d,\n    *,\n    e,\n    f,\n)" in qmd


def test_variable_positional_parameters():
    code = """
    def func(a: int=1, b: int=2, *c: int, z: int=26):
        '''
        Parameters
        ----------
        a :
            Parameter a
        b :
            Parameter b
        *c :
            Variable position parameters.
        z :
            Parameter z
        '''
    """
    qmd = render_code_variable(code, "func")
    assert "func(\n    a=1,\n    b=2,\n    *c,\n    z=26,\n)" in qmd


def test_variable_keyword_parameters():
    code = """
    def func(a: int =1, b: int =2, **kwargs: int):
        '''
        A function

        Parameters
        ----------
        a :
            Parameter a
        b :
            Parameter b
        *kwargs :
            Variable keyword parameters
        '''
        pass
    """
    qmd = render_code_variable(code, "func")
    assert "func(\n    a=1,\n    b=2,\n    **kwargs,\n)" in qmd
    assert "{}" not in qmd
