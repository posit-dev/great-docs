from great_docs._directives import (
    DocDirectives,
    extract_directives,
    has_directives,
    strip_directives,
)


class TestExtractDirectives:
    """Tests for extract_directives function."""

    def test_extract_seealso(self):
        """Test extracting %seealso directive."""
        docstring = """
        Short description.

        %seealso func_a, func_b, ClassC

        Parameters
        ----------
        x : int
        """
        directives = extract_directives(docstring)
        assert directives.seealso == ["func_a", "func_b", "ClassC"]

    def test_extract_nodoc(self):
        """Test extracting %nodoc directive."""
        docstring = """
        Short description.

        %nodoc true
        """
        directives = extract_directives(docstring)
        assert directives.nodoc is True

    def test_extract_nodoc_without_value(self):
        """Test extracting %nodoc directive without explicit value."""
        docstring = """
        Short description.

        %nodoc
        """
        directives = extract_directives(docstring)
        assert directives.nodoc is True

    def test_extract_multiple_directives(self):
        """Test extracting multiple directives from one docstring."""
        docstring = """
        Validate column values are greater than a threshold.

        %seealso func_1, func_2

        Parameters
        ----------
        columns : str
            Target columns.
        """
        directives = extract_directives(docstring)
        assert directives.seealso == ["func_1", "func_2"]
        assert directives.nodoc is False

    def test_extract_from_none(self):
        """Test extracting from None returns empty directives."""
        directives = extract_directives(None)
        assert directives.seealso == []
        assert directives.nodoc is False

    def test_extract_from_empty_string(self):
        """Test extracting from empty string returns empty directives."""
        directives = extract_directives("")
        assert directives.seealso == []
        assert directives.nodoc is False

    def test_extract_no_directives(self):
        """Test docstring without directives."""
        docstring = """
        Short description.

        Parameters
        ----------
        x : int
            The input value.
        """
        directives = extract_directives(docstring)
        assert directives.seealso == []
        assert directives.nodoc is False

    def test_directive_with_indentation(self):
        """Test that indented directives are extracted."""
        docstring = """
        Short description.

            %seealso func_a, func_b
        """
        directives = extract_directives(docstring)
        assert directives.seealso == ["func_a", "func_b"]


class TestStripDirectives:
    """Tests for strip_directives function."""

    def test_strip_single_directive(self):
        """Test stripping a single directive."""
        docstring = """Short description.

%seealso func_a, func_b

Parameters
----------
x : int"""
        result = strip_directives(docstring)
        assert "%seealso" not in result
        assert "Short description." in result
        assert "Parameters" in result

    def test_strip_multiple_directives(self):
        """Test stripping multiple directives."""
        docstring = """Short description.

%seealso func_a, func_b
%nodoc true

Parameters
----------
x : int"""
        result = strip_directives(docstring)
        assert "%seealso" not in result
        assert "%nodoc" not in result
        assert "Short description." in result
        assert "Parameters" in result

    def test_strip_preserves_content(self):
        """Test that stripping preserves non-directive content."""
        docstring = """Short description.

This is a longer explanation of what the function does.
It spans multiple lines.

%seealso func_a

Parameters
----------
x : int
    The input value.

Returns
-------
str
    The output value."""
        result = strip_directives(docstring)
        assert "Short description." in result
        assert "longer explanation" in result
        assert "Parameters" in result
        assert "Returns" in result
        assert "%seealso" not in result

    def test_strip_cleans_blank_lines(self):
        """Test that stripping removes extra blank lines."""
        docstring = """Short description.

%nodoc true

Parameters
----------"""
        result = strip_directives(docstring)
        # Should not have more than 2 consecutive newlines
        assert "\n\n\n" not in result

    def test_strip_from_none(self):
        """Test stripping from None returns empty string."""
        result = strip_directives(None)
        assert result == ""

    def test_strip_from_empty(self):
        """Test stripping from empty string returns empty string."""
        result = strip_directives("")
        assert result == ""

    def test_strip_indented_directives(self):
        """Test that indented directives are stripped."""
        docstring = """Short description.

    %seealso func_a
    %nodoc true

Parameters
----------"""
        result = strip_directives(docstring)
        assert "%seealso" not in result
        assert "%nodoc" not in result


class TestHasDirectives:
    """Tests for has_directives function."""

    def test_has_order(self):
        """Test detecting %seealso directive."""
        assert has_directives("%seealso func_a")

    def test_has_nodoc(self):
        """Test detecting %nodoc directive."""
        assert has_directives("%nodoc true")

    def test_no_directives(self):
        """Test docstring without directives."""
        assert not has_directives("Just a regular docstring.")

    def test_none_input(self):
        """Test None input returns False."""
        assert not has_directives(None)

    def test_empty_input(self):
        """Test empty string returns False."""
        assert not has_directives("")


class TestDocDirectives:
    """Tests for DocDirectives dataclass."""

    def test_bool_false_when_empty(self):
        """Test that empty DocDirectives is falsy."""
        directives = DocDirectives()
        assert not directives

    def test_bool_true_with_seealso(self):
        """Test that DocDirectives with seealso is truthy."""
        directives = DocDirectives(seealso=["func_a"])
        assert directives

    def test_bool_true_with_nodoc(self):
        """Test that DocDirectives with nodoc is truthy."""
        directives = DocDirectives(nodoc=True)
        assert directives


class TestIntegration:
    """Integration tests combining extract and strip."""

    def test_roundtrip(self):
        """Test extracting directives then stripping produces clean docstring."""
        original = """
        Validate column values are greater than a threshold.

        This validation step checks values against a threshold.

        %seealso func_1, func_2

        Parameters
        ----------
        columns : str
            Target columns.
        value : numeric
            The threshold.

        Returns
        -------
        Validate
            Self for chaining.
        """

        # Extract directives
        directives = extract_directives(original)
        assert directives.seealso == ["func_1", "func_2"]

        # Strip directives
        cleaned = strip_directives(original)
        assert "%seealso" not in cleaned
        assert "Validate column values" in cleaned
        assert "Parameters" in cleaned
        assert "Returns" in cleaned
