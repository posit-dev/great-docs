from __future__ import annotations

import glob
import os
import re
import sys


def _configure_stdio_for_unicode() -> None:
    """Use UTF-8 for console output when the platform default is narrow (e.g. cp1252)."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


_configure_stdio_for_unicode()

# Skip post-render processing during freeze-only renders
if os.environ.get("GD_FREEZE_ONLY"):
    print("Skipping post-render (freeze-only mode)")
    raise SystemExit(0)

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

# Pygments class to Quarto class mapping
# Quarto uses different class names than Pygments default
PYGMENTS_TO_QUARTO_CLASS = {
    "n": "va",  # Name -> variable (generic names)
    "nc": "fu",  # Name.Class -> function (we want class names highlighted)
    "nf": "fu",  # Name.Function -> function
    "fm": "fu",  # Name.Function.Magic -> function
    "nb": "bu",  # Name.Builtin -> builtin
    "bp": "bu",  # Name.Builtin.Pseudo -> builtin
    "k": "kw",  # Keyword -> keyword
    "kc": "cn",  # Keyword.Constant -> constant (None, True, False) - will be split further
    "kd": "kw",  # Keyword.Declaration -> keyword
    "kn": "kw",  # Keyword.Namespace -> keyword
    "kr": "kw",  # Keyword.Reserved -> keyword
    "o": "op",  # Operator -> operator
    "ow": "op",  # Operator.Word -> operator
    "p": "",  # Punctuation -> no special class
    "s": "st",  # String -> string
    "s1": "st",  # String.Single -> string
    "s2": "st",  # String.Double -> string
    "mi": "dv",  # Number.Integer -> decimal value
    "mf": "fl",  # Number.Float -> float
    "c": "co",  # Comment -> comment
    "c1": "co",  # Comment.Single -> comment
}


def highlight_signature_with_pygments(html_content):
    """
    Re-highlight the main signature block (cb1) with Pygments for better syntax coloring.

    This extracts the signature code, highlights it with Pygments, then maps the Pygments CSS
    classes to Quarto's highlighting classes for consistency.
    """
    # Find the main signature code block: the first code block on the page
    # (id="cb1") *and* the one the renderer wrapped in a doc-signature div.
    # The enclosing div is what makes this a signature; without it the first
    # code block on a page is whatever ordinary block comes first, which on a
    # page whose signature is inline markup is usually an Examples doctest.
    cb1_pattern = re.compile(
        r'(<div class="doc-signature[^"]*">\s*'
        r'<div class="sourceCode" id="cb1">.*?<code class="sourceCode python">)'
        r"(.*?)"
        r"(</code>.*?</div>)",
        re.DOTALL,
    )

    def replace_signature(match):
        prefix = match.group(1)
        code_content = match.group(2)
        suffix = match.group(3)

        # Extract plain text from the HTML spans
        # Remove HTML tags but preserve the text content
        plain_code = re.sub(r"<[^>]+>", "", code_content)
        # Clean up the text (unescape HTML entities)
        plain_code = plain_code.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

        # Highlight with Pygments
        lexer = PythonLexer()
        # Use a custom formatter that generates short class names
        formatter = HtmlFormatter(nowrap=True, classprefix="")

        highlighted = highlight(plain_code, lexer, formatter)

        # Map Pygments classes to Quarto classes
        for pg_class, quarto_class in PYGMENTS_TO_QUARTO_CLASS.items():
            if quarto_class:
                highlighted = highlighted.replace(f'class="{pg_class}"', f'class="{quarto_class}"')
            else:
                # Remove empty class attributes
                highlighted = re.sub(
                    rf'<span class="{pg_class}">([^<]*)</span>', r"\1", highlighted
                )

        # Special handling: make method/function name stand out on every signature line
        # Pattern: ClassName.method_name( or function_name( — or, for a TypedDict/Enum
        # page, just Name with nothing after it, since those never show call brackets.
        # The trailing group matches either the opening "(" of a call or the end of the
        # line, so a bare name is still caught without also matching a name that is
        # followed by anything else (which never happens: this block only ever holds a
        # signature line, and a signature line's leading name is always either called,
        # in which case "(" comes right after it, or not, in which case nothing does).
        # Uses re.MULTILINE so ^ matches each line (important for @overload signatures)
        sig_name_pattern = re.compile(
            r'^(<span class="va">)(\w+)(</span>)(<span class="op">\.</span>)?'
            r'(<span class="va">)?(\w+)?(</span>)?(\(|$)',
            re.MULTILINE,
        )

        def enhance_sig_name(m):
            # The final group is "(" for a call, or "" at the end of a bracket-less
            # TypedDict/Enum line; either way it belongs straight after the name.
            trailing = m.group(8)
            # If there's a dot, it's ClassName.method_name
            if m.group(4):  # Has dot
                class_name = m.group(2)
                method_name = m.group(6) or ""
                return (
                    f'<span class="sig-class">{class_name}</span>'
                    f'<span class="op">.</span>'
                    f'<span class="sig-name">{method_name}</span>{trailing}'
                )
            else:
                # Just function_name( or, bracket-less, just Name
                func_name = m.group(2)
                return f'<span class="sig-name">{func_name}</span>{trailing}'

        highlighted = sig_name_pattern.sub(enhance_sig_name, highlighted)

        # Differentiate None from True/False
        # None gets 'cn-none' class, True/False get 'cn-bool' class
        highlighted = highlighted.replace(
            '<span class="cn">None</span>', '<span class="cn-none">None</span>'
        )
        highlighted = highlighted.replace(
            '<span class="cn">True</span>', '<span class="cn-bool">True</span>'
        )
        highlighted = highlighted.replace(
            '<span class="cn">False</span>', '<span class="cn-bool">False</span>'
        )

        # Convert single quotes to double quotes in string literals
        # Pygments outputs HTML entities: &#39; for single quote
        # Match both s1 (string single) and st (after class mapping) classes
        highlighted = re.sub(
            r'<span class="(st|s1)">&#39;([^&]*)&#39;</span>',
            r'<span class="\1">&quot;\2&quot;</span>',
            highlighted,
        )

        # Wrap each line in a span with proper id for line linking
        # For overloaded functions (multiple signature lines), insert a blank spacer
        # span between each signature for visual separation.
        lines = highlighted.split("\n")
        # Filter out empty trailing lines
        while lines and not lines[-1].strip():
            lines.pop()
        is_overloaded = len(lines) > 1 and all(line.strip() == "" or "(" in line for line in lines)
        wrapped_lines = []
        line_num = 1
        for idx, line in enumerate(lines):
            if not line and not is_overloaded:
                continue  # Skip empty lines for non-overloaded functions
            if not line:
                continue  # Skip blank lines; we insert spacers ourselves
            wrapped_lines.append(
                f'<span id="cb1-{line_num}"><a href="#cb1-{line_num}" aria-hidden="true" tabindex="-1"></a>{line}</span>'
            )
            line_num += 1
            # Add a blank spacer line between overload signatures (not after the last)
            if is_overloaded and idx < len(lines) - 1:
                wrapped_lines.append(f'<span id="cb1-{line_num}" class="overload-spacer"> </span>')
                line_num += 1

        new_code = "\n".join(wrapped_lines)

        return f"{prefix}{new_code}{suffix}"

    return cb1_pattern.sub(replace_signature, html_content)


# Process all HTML files in the `_site/reference/` directory (except `index.html`)
# and apply the specified transformations
html_files = [f for f in glob.glob("_site/reference/*.html") if os.path.basename(f) != "index.html"]

print(f"Found {len(html_files)} HTML files to process")

for html_file in html_files:
    print(f"Processing: {html_file}")

    with open(html_file, "r", encoding="utf-8") as file:
        content = file.read()

    # Re-highlight the signature with Pygments for better syntax coloring
    content = highlight_signature_with_pygments(content)

    # Convert back to lines for line-by-line processing
    content = content.splitlines(keepends=True)

    # Add separator lines between class details and individual members,
    # and between individual member sections.
    # - Thin solid line after the Methods/Attributes summary table (before first member section)
    # - Dotted line between each individual member section
    for i, line in enumerate(content):
        # Individual members render as `level3` sections.
        if "<section id=" in line and 'class="level3"' in line:
            # Check if the previous non-blank line ends a table (</table> in </section>)
            # or closes another member section
            for j in range(i - 1, max(0, i - 5), -1):
                prev = content[j].strip()
                if not prev:
                    continue
                if "</table>" in prev:
                    # First member section after a summary table — solid line
                    content[i] = (
                        '<hr style="border: none; border-top: 2px solid #c5c8cd; margin: 1.5rem 0 1rem 0;">\n'
                        + content[i]
                    )
                elif "</section>" in prev:
                    # Between member sections — dotted line
                    content[i] = (
                        '<hr style="border: none; border-top: 2px dotted #b0b4ba; margin: 1.5rem 0 1rem 0;">\n'
                        + content[i]
                    )
                break

    with open(html_file, "w", encoding="utf-8") as file:
        file.writelines(content)


print("Finished processing all files")
print("##GD:PASS:Reference pages processed", flush=True)

all_html_files = glob.glob("_site/**/*.html", recursive=True)
