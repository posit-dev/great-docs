"""Tests for post-render transformation functions."""

from pathlib import Path

# The script runs file-system side effects at module level, so tests read its source
_SCRIPT = Path(__file__).resolve().parent.parent / "great_docs" / "assets" / "post-render.py"


class TestFixScriptPathsBackToTop:
    """Verify fix_script_paths handles back-to-top.js in subdirectories."""

    def test_back_to_top_listed_in_fix_script_paths(self):
        """back-to-top.js should appear in the fix_script_paths function body."""
        source = _SCRIPT.read_text()
        # Find the fix_script_paths function
        assert "def fix_script_paths():" in source
        # Find the start of the function
        start = source.find("def fix_script_paths():")
        # Find the next top-level definition after it
        rest = source[start:]
        lines = rest.split("\n")
        func_lines = [lines[0]]
        for line in lines[1:]:
            if line and not line[0].isspace() and not line.startswith("#"):
                break
            func_lines.append(line)
        func_body = "\n".join(func_lines)
        assert "back-to-top.js" in func_body

    def test_back_to_top_path_fix_pattern(self):
        """The fix uses the same old/new replacement pattern as other scripts."""
        source = _SCRIPT.read_text()
        # Verify the exact pattern strings exist
        assert "'<script src=\"back-to-top.js\"></script>'" in source
        assert "back-to-top.js" in source


class TestFixScriptPathsKeyboardNav:
    """Verify fix_script_paths handles keyboard-nav.js in subdirectories."""

    def test_keyboard_nav_listed_in_fix_script_paths(self):
        """keyboard-nav.js should appear in the fix_script_paths function body."""
        source = _SCRIPT.read_text()
        assert "def fix_script_paths():" in source
        start = source.find("def fix_script_paths():")
        rest = source[start:]
        lines = rest.split("\n")
        func_lines = [lines[0]]
        for line in lines[1:]:
            if line and not line[0].isspace() and not line.startswith("#"):
                break
            func_lines.append(line)
        func_body = "\n".join(func_lines)
        assert "keyboard-nav.js" in func_body

    def test_keyboard_nav_path_fix_pattern(self):
        """The fix uses the same old/new replacement pattern as other scripts."""
        source = _SCRIPT.read_text()
        assert "'<script src=\"keyboard-nav.js\"></script>'" in source
        assert "keyboard-nav.js" in source
