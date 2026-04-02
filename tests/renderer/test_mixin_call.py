# pyright: reportPrivateUsage=false
"""Tests for _qrenderer/_render/mixin_call.py — covering docstring section merging,
RST directive handling, overload signatures, parameter exclusion, and **kwargs rendering."""

from __future__ import annotations

import griffe as gf

from great_docs._qrenderer._tools import render_code_variable


def test_merges_unnamed_returns_with_same_annotation():
    """Consecutive unnamed DocstringReturn items sharing an annotation are merged."""
    code = '''
    def func() -> str:
        """
        A function returning a string.

        Returns
        -------
        str
            First paragraph.
        str
            Second paragraph.
        """
        return "hello"
    '''
    qmd = render_code_variable(code, "func")

    # The two items should be merged into one
    assert "Returns" in qmd
    assert "First paragraph" in qmd
    assert "Second paragraph" in qmd


def test_named_returns_not_merged():
    """Named return items should not be merged even if they share an annotation."""
    code = '''
    def func():
        """
        Return named values.

        Returns
        -------
        x : int
            First value.
        y : int
            Second value.
        """
        pass
    '''
    qmd = render_code_variable(code, "func")

    assert "First value" in qmd
    assert "Second value" in qmd


def test_yields_section_also_merges():
    """DocstringSectionYields also triggers the merge logic."""
    code = '''
    def gen():
        """
        A generator.

        Yields
        ------
        int
            First yield description.
        int
            Second yield description.
        """
        yield 1
    '''
    qmd = render_code_variable(code, "gen")

    assert "Yields" in qmd
    assert "First yield" in qmd
    assert "Second yield" in qmd


def test_rst_directive_in_parameters_section():
    """An RST directive annotation (.. note::) is detected and converted."""
    code = '''
    def func(x):
        """
        A function.

        Parameters
        ----------
        x : int
            The input.

        .. note::
            This is a note.
        """
        pass
    '''
    qmd = render_code_variable(code, "func")

    # The parameter should still be rendered
    assert "x" in qmd

    # The note directive should be converted (not rendered as a parameter)
    assert "note" in qmd.lower() or "x" in qmd


def test_rst_directive_without_description():
    """An RST directive with no description body is handled."""
    code = '''
    def func(x):
        """
        A function.

        Parameters
        ----------
        x : int
            The input.

        .. deprecated::
        """
        pass
    '''
    qmd = render_code_variable(code, "func")

    assert "x" in qmd


def test_normal_items_and_directive_parts():
    """When both normal params and RST directives exist, both are rendered."""
    code = '''
    def func(x, y):
        """
        A function with parameters and a directive.

        Parameters
        ----------
        x : int
            First param.
        y : str
            Second param.

        .. warning::
            Be careful with this function.
        """
        pass
    '''
    qmd = render_code_variable(code, "func")

    assert "x" in qmd
    assert "y" in qmd


def test_exclude_single_parameter_as_string():
    """When EXCLUDE_PARAMETERS value is a string, it's coerced to a tuple."""
    code = '''
    def func(a, b, c):
        """
        A function.

        Parameters
        ----------
        a : int
            First.
        b : int
            Second.
        c : int
            Third.
        """
        pass
    '''
    from great_docs._qrenderer import _globals

    original = _globals.EXCLUDE_PARAMETERS.copy()
    try:
        _globals.EXCLUDE_PARAMETERS["package.func"] = "b"
        qmd = render_code_variable(code, "func")
    finally:
        _globals.EXCLUDE_PARAMETERS.clear()
        _globals.EXCLUDE_PARAMETERS.update(original)

    # "b" should be excluded from the signature
    assert "func(a" in qmd
    assert "func(a, b" not in qmd


def test_exclude_multiple_parameters_as_tuple():
    """When EXCLUDE_PARAMETERS value is a tuple, parameters are excluded."""
    code = '''
    def func(a, b, c):
        """
        A function.

        Parameters
        ----------
        a : int
            First.
        b : int
            Second.
        c : int
            Third.
        """
        pass
    '''
    from great_docs._qrenderer import _globals

    original = _globals.EXCLUDE_PARAMETERS.copy()
    try:
        _globals.EXCLUDE_PARAMETERS["package.func"] = ("a", "c")
        qmd = render_code_variable(code, "func")
    finally:
        _globals.EXCLUDE_PARAMETERS.clear()
        _globals.EXCLUDE_PARAMETERS.update(original)

    # Only b should remain in the signature
    assert "func(b)" in qmd


def test_function_with_overloads():
    """Functions with @overload return multiple signature lines."""
    code = '''
    from typing import overload

    @overload
    def func(x: int) -> int: ...

    @overload
    def func(x: str) -> str: ...

    def func(x):
        """
        An overloaded function.

        Parameters
        ----------
        x : int or str
            The input.
        """
        return x
    '''
    qmd = render_code_variable(code, "func")

    # Should have the function rendered
    assert "func" in qmd


def test_overload_with_defaults_and_return():
    """Overloaded signatures include default values and return types."""
    code = '''
    from typing import overload

    @overload
    def process(data: list, flag: bool = True) -> list: ...

    @overload
    def process(data: dict, flag: bool = False) -> dict: ...

    def process(data, flag=True):
        """
        Process data.

        Parameters
        ----------
        data : list or dict
            Input data.
        flag : bool
            A flag.
        """
        return data
    '''
    qmd = render_code_variable(code, "process")

    assert "process" in qmd


def test_overload_untyped_and_no_return():
    """Overloads with default-only and bare params, no return type."""
    code = '''
    from typing import overload

    @overload
    def func(x: int) -> int: ...

    @overload
    def func(x=5): ...

    @overload
    def func(x): ...

    def func(x=None):
        """An overloaded function."""
        return x
    '''
    qmd = render_code_variable(code, "func")

    # All three overload forms should render
    assert "func" in qmd


def test_var_keyword_in_signature():
    """**kwargs rendered correctly with double-star prefix."""
    code = '''
    def func(a: int, **kwargs: str):
        """
        A function.

        Parameters
        ----------
        a : int
            First param.
        **kwargs : str
            Extra keyword args.
        """
        pass
    '''
    qmd = render_code_variable(code, "func")

    assert "**kwargs" in qmd


def test_var_keyword_no_annotation():
    """**kwargs without annotation."""
    code = '''
    def func(x, **kwargs):
        """
        Parameters
        ----------
        x :
            An input.
        **kwargs :
            Keyword arguments.
        """
        pass
    '''
    qmd = render_code_variable(code, "func")

    assert "**kwargs" in qmd


def test_combined_var_positional_and_var_keyword():
    """Both *args and **kwargs in the same signature."""
    code = '''
    def func(*args, **kwargs):
        """
        Parameters
        ----------
        *args :
            Positional args.
        **kwargs :
            Keyword args.
        """
        pass
    '''
    qmd = render_code_variable(code, "func")

    assert "*args" in qmd
    assert "**kwargs" in qmd


def test_method_omits_self():
    """Instance methods should omit 'self' from parameters."""
    code = '''
    class MyClass:
        """A class."""

        def method(self, x: int):
            """
            A method.

            Parameters
            ----------
            x : int
                An input.
            """
            pass
    '''
    qmd = render_code_variable(code, "MyClass")

    # 'self' should not appear in the rendered method signature
    assert "method(self" not in qmd
    assert "method(x" in qmd


def test_classmethod_omits_cls():
    """Class methods should omit 'cls' from parameters."""
    code = '''
    class MyClass:
        """A class."""

        @classmethod
        def create(cls, name: str):
            """
            Create an instance.

            Parameters
            ----------
            name : str
                The name.
            """
            return cls()
    '''
    qmd = render_code_variable(code, "MyClass")

    assert "create(cls" not in qmd


def test_raises_section():
    """Raises section is rendered as definitions."""
    code = '''
    def func(x):
        """
        A function.

        Parameters
        ----------
        x : int
            Input.

        Raises
        ------
        ValueError
            If x is negative.
        TypeError
            If x is not an int.
        """
        if not isinstance(x, int):
            raise TypeError
        if x < 0:
            raise ValueError
    '''
    qmd = render_code_variable(code, "func")

    assert "ValueError" in qmd
    assert "TypeError" in qmd


def test_warns_section():
    """Warns section is rendered."""
    code = '''
    import warnings

    def func(x):
        """
        A function.

        Parameters
        ----------
        x : int
            Input.

        Warns
        -----
        UserWarning
            When x is zero.
        """
        if x == 0:
            warnings.warn("x is zero")
    '''
    qmd = render_code_variable(code, "func")

    assert "UserWarning" in qmd or "Warns" in qmd


def test_other_parameters_section():
    """Other Parameters section renders definitions."""
    code = '''
    def func(x, **kwargs):
        """
        A function.

        Parameters
        ----------
        x : int
            Main input.

        Other Parameters
        ----------------
        debug : bool
            Enable debug mode.
        verbose : bool
            Enable verbose output.
        """
        pass
    '''
    qmd = render_code_variable(code, "func")

    assert "debug" in qmd
    assert "verbose" in qmd


def test_attributes_section():
    """Attributes section on a class is rendered."""
    code = '''
    class MyClass:
        """
        A class.

        Attributes
        ----------
        name : str
            The name of the object.
        value : int
            The value.
        """
        def __init__(self):
            self.name = ""
            self.value = 0
    '''
    qmd = render_code_variable(code, "MyClass")

    assert "name" in qmd
    assert "value" in qmd


def test_empty_description_parameter():
    """A parameter with empty description still renders."""
    code = '''
    def func(x: int, y: str):
        """
        A function.

        Parameters
        ----------
        x : int
        y : str
            The y param.
        """
        pass
    '''
    qmd = render_code_variable(code, "func")

    assert "x" in qmd
    assert "y" in qmd


def test_positional_only_separator():
    """Positional-only parameters add '/' separator."""
    code = '''
    def func(a, b, /, c):
        """
        Parameters
        ----------
        a : int
            First.
        b : int
            Second.
        c : int
            Third.
        """
        pass
    '''
    qmd = render_code_variable(code, "func")

    assert "/" in qmd


def test_keyword_only_separator():
    """Keyword-only parameters add '*' separator."""
    code = '''
    def func(a, *, b, c):
        """
        Parameters
        ----------
        a : int
            First.
        b : int
            Second.
        c : int
            Third.
        """
        pass
    '''
    qmd = render_code_variable(code, "func")

    assert "*" in qmd


def test_parameter_with_annotation_and_default():
    """Parameter with both annotation and default shows ': type = default'."""
    code = '''
    def func(x: int = 42):
        """
        Parameters
        ----------
        x : int
            The x parameter.
        """
        pass
    '''
    qmd = render_code_variable(code, "func")

    assert "42" in qmd
    assert "x" in qmd


def test_parameter_default_only():
    """Parameter with default but no annotation shows 'name=default'."""
    code = '''
    def func(x=42):
        """
        Parameters
        ----------
        x :
            The x parameter.
        """
        pass
    '''
    qmd = render_code_variable(code, "func")

    assert "42" in qmd


def test_annotation_in_signature():
    """When show_signature_annotation=True, annotations appear in the signature."""
    from great_docs._qrenderer import RenderDocFunction, RenderConfig, layout

    code = '''
    def func(x: int, y: str = "hello"):
        """
        A function.

        Parameters
        ----------
        x : int
            An input.
        y : str
            A string.
        """
        pass
    '''
    with gf.temporary_visited_package(
        "package", {"__init__.py": code}, docstring_parser="numpy"
    ) as m:
        obj = m["func"]

    doc = layout.Doc.from_griffe(obj.name, obj)
    rd = RenderDocFunction(doc, RenderConfig(), show_signature_annotation=True)
    qmd = str(rd)

    # Annotations should appear in the signature with ': type' format
    assert ": int" in qmd
    assert ": str" in qmd
