import glob
import json
import os
import re

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

# Print the working directory
print("Current working directory:", os.getcwd())

# Get a list of all files in the working directory
files = os.listdir(".")
print("Files in working directory:", files)

site_files = os.listdir("_site")
print("Files in '_site' directory:", site_files)

# Load source links if available
source_links = {}
source_links_path = "_source_links.json"
if os.path.exists(source_links_path):
    print(f"Loading source links from {source_links_path}")
    with open(source_links_path, "r") as f:
        source_links = json.load(f)
    print(f"Loaded {len(source_links)} source links")
else:
    print("No source links file found, skipping source link injection")

# Load object type metadata for accurate classification
# Keys are object names (e.g., "parser.ParserError"), values are type strings
# ("class", "exception", "function", "method", "constant", "enum", "type_alias", "other")
object_types = {}
object_types_path = "_object_types.json"
if os.path.exists(object_types_path):
    print(f"Loading object types from {object_types_path}")
    with open(object_types_path, "r") as f:
        object_types = json.load(f)
    print(f"Loaded {len(object_types)} object type entries")
else:
    print("No object types file found, falling back to heuristic classification")


def get_source_link_html(item_name):
    """Generate HTML for a source link given an item name."""
    if item_name in source_links:
        url = source_links[item_name]["url"]
        return f'<a href="{url}" class="source-link" target="_blank" rel="noopener">SOURCE</a>'
    return ""


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
    # Find the main signature code block (id="cb1")
    cb1_pattern = re.compile(
        r'(<div class="sourceCode" id="cb1">.*?<code class="sourceCode python">)'
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

        # Special handling for the first line: make method/function name stand out
        # Pattern: ClassName.method_name( or function_name(
        # Replace the name before ( with a function class for better highlighting
        first_line_pattern = re.compile(
            r'^(<span class="va">)(\w+)(</span>)(<span class="op">\.</span>)?'
            r'(<span class="va">)?(\w+)?(</span>)?(\()'
        )

        def enhance_first_line(m):
            # If there's a dot, it's ClassName.method_name
            if m.group(4):  # Has dot
                class_name = m.group(2)
                method_name = m.group(6) or ""
                return (
                    f'<span class="sig-class">{class_name}</span>'
                    f'<span class="op">.</span>'
                    f'<span class="sig-name">{method_name}</span>('
                )
            else:
                # Just function_name(
                func_name = m.group(2)
                return f'<span class="sig-name">{func_name}</span>('

        highlighted = first_line_pattern.sub(enhance_first_line, highlighted, count=1)

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
        lines = highlighted.split("\n")
        wrapped_lines = []
        for i, line in enumerate(lines, 1):
            if line:  # Skip empty lines at the end
                wrapped_lines.append(
                    f'<span id="cb1-{i}"><a href="#cb1-{i}" aria-hidden="true" tabindex="-1"></a>{line}</span>'
                )

        new_code = "\n".join(wrapped_lines)

        return f"{prefix}{new_code}{suffix}"

    return cb1_pattern.sub(replace_signature, html_content)


def format_signature_multiline(html_content):
    """
    Format function/method signatures with multiple arguments onto separate lines.

    If a signature has more than one argument, format it as:
        FunctionName(
            arg1=default1,
            arg2=default2,
        )

    Signatures that are already multiline are skipped.
    """
    # Pattern to match the content inside signature spans
    # The signature is inside <span id="cbN-1">...(args)</span>
    # We need to handle HTML tags within the arguments

    def reformat_signature(match):
        full_match = match.group(0)
        span_start = match.group(1)
        anchor = match.group(2) or ""
        content = match.group(3)
        span_end = match.group(4)

        # Skip if signature is already multiline; this is detected by checking if content ends with
        # just "(" or has a newline
        if content.strip().endswith("(") or "\n" in content:
            return full_match

        # Find the opening paren position
        paren_pos = content.find("(")
        if paren_pos == -1:
            return full_match

        func_name = content[: paren_pos + 1]  # Include the (

        # Find the closing paren - it's the last ) in the content
        close_paren_pos = content.rfind(")")
        if close_paren_pos == -1:
            return full_match

        args_content = content[paren_pos + 1 : close_paren_pos]

        # Count arguments by looking for commas not inside HTML tags or nested parens
        # We need to track both HTML tag depth and paren depth
        arg_count = 1 if args_content.strip() else 0
        html_depth = 0
        paren_depth = 0
        i = 0
        while i < len(args_content):
            if args_content[i : i + 1] == "<":
                html_depth += 1
            elif args_content[i : i + 1] == ">":
                html_depth -= 1
            elif html_depth == 0:
                if args_content[i] in "([{":
                    paren_depth += 1
                elif args_content[i] in ")]}":
                    paren_depth -= 1
                elif args_content[i] == "," and paren_depth == 0:
                    arg_count += 1
            i += 1

        # Only reformat if more than 1 argument
        if arg_count <= 1:
            return full_match

        # Split arguments while preserving HTML
        args = []
        current_arg = ""
        html_depth = 0
        paren_depth = 0
        i = 0
        while i < len(args_content):
            char = args_content[i]
            if char == "<":
                html_depth += 1
                current_arg += char
            elif char == ">":
                html_depth -= 1
                current_arg += char
            elif html_depth == 0:
                if char in "([{":
                    paren_depth += 1
                    current_arg += char
                elif char in ")]}":
                    paren_depth -= 1
                    current_arg += char
                elif char == "," and paren_depth == 0:
                    args.append(current_arg.strip())
                    current_arg = ""
                else:
                    current_arg += char
            else:
                current_arg += char
            i += 1
        if current_arg.strip():
            args.append(current_arg.strip())

        # Build multi-line signature
        formatted_args = ",\n    ".join(args)
        new_content = f"{func_name}\n    {formatted_args},\n)"

        return f"{span_start}{anchor}{new_content}{span_end}"

    # Only match the FIRST code block (cb1) which is always the main signature
    # Other code blocks (cb2, cb3, etc.) are method signatures or examples
    signature_pattern = re.compile(
        r'(<span id="cb1-1"[^>]*>)'
        r"(<a[^>]*></a>)?"
        r"(.*?\))"
        r"(</span>)",
        re.DOTALL,
    )

    return signature_pattern.sub(reformat_signature, html_content)


def strip_directives_from_html(html_content):
    """
    Remove Great Docs %directive lines from rendered HTML.

    Directives like %family, %order, %seealso, and %nodoc are used for organizing documentation but
    they should not appear in the final rendered output. This function removes them after rendering.
    """
    # Match directives wrapped in <p> tags
    # e.g., <p>%family Something</p>
    p_directive_pattern = re.compile(
        r"<p>\s*%(?:family|order|seealso|nodoc)(?:\s+[^<]*)?\s*</p>\s*\n?",
        re.IGNORECASE,
    )

    # Match standalone directive lines (plain text)
    # e.g., %family Something
    standalone_directive_pattern = re.compile(
        r"^\s*%(?:family|order|seealso|nodoc)(?:\s+.*)?\s*$\n?",
        re.MULTILINE | re.IGNORECASE,
    )

    # Match directives that might be inline within text
    inline_directive_pattern = re.compile(
        r"%(?:family|order|seealso|nodoc)(?:\s+[^\n<]*)?",
        re.IGNORECASE,
    )

    # Apply patterns in order of specificity
    cleaned = p_directive_pattern.sub("", html_content)
    cleaned = standalone_directive_pattern.sub("", cleaned)
    cleaned = inline_directive_pattern.sub("", cleaned)

    # Clean up any resulting empty paragraphs
    cleaned = re.sub(r"<p>\s*</p>\s*\n?", "", cleaned)

    return cleaned


def translate_sphinx_fields(html_content):
    """
    Convert Sphinx field-list directives into structured doc sections.

    After quartodoc rendering, Sphinx-style docstrings with ``:param:``,
    ``:type:``, ``:returns:``, ``:rtype:``, and ``:raises:`` fields end up
    mashed into a single ``<p>`` tag::

        <p>:param x: Desc. :type x: int :returns: Desc. :rtype: str :raises ValueError: Desc.</p>

    This function parses those fields and emits the same ``<section>`` /
    ``<dl>`` / ``<dt>`` / ``<dd>`` structure that quartodoc produces for
    NumPy-style Parameters / Returns / Raises sections.
    """

    # Regex for a <p> tag whose text contains Sphinx field markers.
    # Allow inline HTML (e.g. <code>...</code>) inside the field text, but
    # prevent matching across paragraph boundaries by refusing </p> in the body.
    _FIELD_P = re.compile(
        r"<p>((?:(?!</p>).)*?:(?:param|type|returns?|rtype|raises?)(?:(?!</p>).)*)</p>",
        re.DOTALL,
    )

    # Individual field markers within the text.
    # The body captures everything up to the next field marker or end of string,
    # including inline HTML tags like <code>.
    _FIELD_TOKEN = re.compile(
        r":(?P<directive>param|type|returns?|rtype|raises?)"
        r"(?:\s+(?P<name>[^:]*?))?:\s*(?P<body>(?:(?!:(?:param|type|returns?|rtype|raises?)\b).)*)",
        re.DOTALL,
    )

    def _build_sections(m):
        text = m.group(1)
        fields = list(_FIELD_TOKEN.finditer(text))

        if not fields:
            return m.group(0)

        # Collect structured data
        params = {}  # name -> {"desc": ..., "type": ...}
        returns = {}  # key -> {"desc": ..., "type": ...}
        raises = []  # [(exception, desc), ...]

        ret_idx = 0
        for field in fields:
            directive = field.group("directive")
            name = (field.group("name") or "").strip()
            body = (field.group("body") or "").strip()

            if directive == "param":
                params.setdefault(name, {"desc": "", "type": ""})
                params[name]["desc"] = body
            elif directive == "type":
                params.setdefault(name, {"desc": "", "type": ""})
                params[name]["type"] = body
            elif directive in ("returns", "return"):
                key = f"_ret_{ret_idx}"
                returns[key] = {"desc": body, "type": ""}
                ret_idx += 1
            elif directive == "rtype":
                # Assign to the last return entry, or create one
                if returns:
                    last_key = list(returns.keys())[-1]
                    returns[last_key]["type"] = body
                else:
                    returns["_ret_0"] = {"desc": "", "type": body}
            elif directive in ("raises", "raise"):
                raises.append((name, body))

        parts = []

        # ── Parameters section ───────────────────────────────────────────
        if params:
            items = []
            for pname, pinfo in params.items():
                ptype = pinfo["type"]
                pdesc = pinfo["desc"]
                if ptype:
                    dt = (
                        f'<dt><code><span class="parameter-name">'
                        f"<strong>{pname}</strong></span> "
                        f'<span class="parameter-annotation-sep">:</span> '
                        f'<span class="parameter-annotation">{ptype}</span>'
                        f"</code></dt>"
                    )
                else:
                    dt = (
                        f'<dt><code><span class="parameter-name">'
                        f"<strong>{pname}</strong></span></code></dt>"
                    )
                dd = f"<dd>\n<p>{pdesc}</p>\n</dd>" if pdesc else "<dd></dd>"
                items.append(dt + "\n" + dd)
            parts.append(
                '<section id="parameters" class="level1 doc-section doc-section-parameters">\n'
                '<h1 class="doc-section doc-section-parameters">Parameters</h1>\n'
                "<dl>\n" + "\n".join(items) + "\n</dl>\n</section>"
            )

        # ── Returns section ──────────────────────────────────────────────
        if returns:
            items = []
            for _key, rinfo in returns.items():
                rtype = rinfo["type"]
                rdesc = rinfo["desc"]
                if rtype:
                    dt = (
                        f'<dt><code><span class="parameter-name"></span> '
                        f'<span class="parameter-annotation-sep" '
                        f'style="margin-left: -8px;"></span> '
                        f'<span class="parameter-annotation">{rtype}</span>'
                        f"</code></dt>"
                    )
                else:
                    dt = "<dt></dt>"
                dd = f"<dd>\n<p>{rdesc}</p>\n</dd>" if rdesc else "<dd></dd>"
                items.append(dt + "\n" + dd)
            parts.append(
                '<section id="returns" class="level1 doc-section doc-section-returns">\n'
                '<h1 class="doc-section doc-section-returns">Returns</h1>\n'
                "<dl>\n" + "\n".join(items) + "\n</dl>\n</section>"
            )

        # ── Raises section ───────────────────────────────────────────────
        if raises:
            items = []
            for exc, desc in raises:
                dt = f'<dt><code><span class="parameter-annotation">{exc}</span></code></dt>'
                dd = f"<dd>\n<p>{desc}</p>\n</dd>" if desc else "<dd></dd>"
                items.append(dt + "\n" + dd)
            parts.append(
                '<section id="raises" class="level1 doc-section doc-section-raises">\n'
                '<h1 class="doc-section doc-section-raises">Raises</h1>\n'
                "<dl>\n" + "\n".join(items) + "\n</dl>\n</section>"
            )

        return "\n".join(parts)

    html_content = _FIELD_P.sub(_build_sections, html_content)
    return html_content


def translate_sphinx_roles(html_content):
    """
    Convert Sphinx cross-reference roles into clean HTML.

    Quartodoc sometimes passes through Sphinx-style roles verbatim.  The most
    common rendered patterns are:

    * ``:py:exc:<code>ValueError</code>``  →  ``<code>ValueError</code>``
    * ``:class:<code>Foo</code>``          →  ``<code>Foo</code>``
    * ``:func:<code>bar</code>``           →  ``<code>bar()</code>``
    * ``:func:`bar```  (inside ``<pre>``)  →  ``bar()``

    For *function* and *method* roles the name gets trailing ``()`` so the reader
    can tell it is callable.
    """

    _CALLABLE_ROLES = {"func", "meth"}

    # Pattern 1 – role prefix followed by <code>…</code>
    # e.g.  :py:class:<code>datetime.datetime</code>
    #       :func:<code>get_object</code>
    def _replace_code_role(m):
        role = m.group("role")
        inner = m.group("inner")
        if role in _CALLABLE_ROLES and not inner.endswith("()"):
            inner += "()"
        return f"<code>{inner}</code>"

    html_content = re.sub(
        r":(?:py:)?(?P<role>exc|class|func|meth|attr|const|mod|obj|data|type):"
        r"<code>(?P<inner>[^<]+)</code>",
        _replace_code_role,
        html_content,
    )

    # Pattern 2 – role with backtick-delimited text (inside <pre><code> blocks
    # or other contexts where markdown didn't convert backticks to <code>)
    # e.g.  :func:`get_zonefile_instance`
    def _replace_backtick_role(m):
        role = m.group("role")
        inner = m.group("inner")
        if role in _CALLABLE_ROLES and not inner.endswith("()"):
            inner += "()"
        return f"<code>{inner}</code>"

    html_content = re.sub(
        r":(?:py:)?(?P<role>exc|class|func|meth|attr|const|mod|obj|data|type):"
        r"`(?P<inner>[^`]+)`",
        _replace_backtick_role,
        html_content,
    )

    return html_content


def translate_rst_directives(html_content):
    """
    Convert RST admonition / version directives into styled HTML callouts.

    Handles directives that appear as literal text in ``<p>`` tags after
    quartodoc rendering, for example:

    * ``<p>.. versionadded:: 2.8.1</p>``
    * ``<p>.. deprecated:: 2.6 Use X instead.</p>``
    * ``<p>.. note:: Some important note.</p>``
    * ``<p>.. warning:: Be careful.</p>``

    Each directive type gets a distinct icon, colour and label.
    """

    _DIRECTIVE_STYLES = {
        # (icon, bg_color, border_color, label)
        "versionadded": ("🆕", "#ECFDF5", "#059669", "Added in version"),
        "versionchanged": ("🔄", "#EFF6FF", "#3B82F6", "Changed in version"),
        "deprecated": ("⚠️", "#FEF2F2", "#DC2626", "Deprecated since version"),
        "note": ("ℹ️", "#EFF6FF", "#3B82F6", "Note"),
        "warning": ("⚠️", "#FFFBEB", "#D97706", "Warning"),
        "caution": ("⚠️", "#FFFBEB", "#D97706", "Caution"),
        "danger": ("🚨", "#FEF2F2", "#DC2626", "Danger"),
        "important": ("❗", "#FFF7ED", "#EA580C", "Important"),
        "tip": ("💡", "#ECFDF5", "#059669", "Tip"),
        "hint": ("💡", "#ECFDF5", "#059669", "Hint"),
    }

    # Version directives have the version number right after ::
    # e.g.  .. versionadded:: 2.8.1
    #       .. deprecated:: 2.6 Use X instead.
    _VERSION_DIRECTIVES = {"versionadded", "versionchanged", "deprecated"}

    directive_names = "|".join(_DIRECTIVE_STYLES.keys())

    def _replace_directive(m):
        directive = m.group("directive")
        body = (m.group("body") or "").strip()
        style = _DIRECTIVE_STYLES[directive]
        icon, bg, border, label = style

        if directive in _VERSION_DIRECTIVES:
            # Split version number from optional description
            parts = body.split(None, 1) if body else []
            version = parts[0] if parts else ""
            desc = parts[1] if len(parts) > 1 else ""
            title = f"{label} {version}" if version else label
            content = desc
        else:
            title = label
            content = body

        # Build the callout HTML
        content_html = f'<p style="margin: 0;">{content}</p>' if content else ""
        return (
            f'<div style="margin: 1rem 0; padding: 0.75rem 1rem; '
            f"background-color: {bg}; "
            f"border-left: 4px solid {border}; "
            f'border-radius: 4px;">'
            f'<p style="margin: 0 0 0.25rem 0; font-weight: 600; '
            f'font-size: 0.875rem;">{icon} {title}</p>'
            f"{content_html}"
            f"</div>"
        )

    # Match <p>.. directive:: body</p>  (the entire <p> is the directive)
    # The body may contain inline HTML tags (e.g. <code>...</code>) produced
    # by the Sphinx-role translation step that runs before this function.
    html_content = re.sub(
        rf"<p>\s*\.\.\s+(?P<directive>{directive_names})::\s*(?P<body>.*?)\s*</p>",
        _replace_directive,
        html_content,
    )

    return html_content


def translate_rst_math(html_content):
    """
    Convert RST ``.. math::`` directives into display-math blocks.

    After quartodoc rendering, a ``.. math::`` block in a docstring becomes
    literal HTML of the form::

        <p>.. math::</p>
        <pre><code>LATEX EXPRESSION</code></pre>

    This function converts that pattern into a proper KaTeX display math
    block and injects the KaTeX CSS/JS from a CDN so the browser can
    render the equations.
    """
    _KATEX_VERSION = "0.16.11"
    _KATEX_CDN = f"https://cdn.jsdelivr.net/npm/katex@{_KATEX_VERSION}/dist"

    _KATEX_HEAD = (
        f'<link rel="stylesheet" href="{_KATEX_CDN}/katex.min.css"'
        ' crossorigin="anonymous">\n'
        f'<script defer src="{_KATEX_CDN}/katex.min.js"'
        ' crossorigin="anonymous"></script>\n'
        f'<script defer src="{_KATEX_CDN}/contrib/auto-render.min.js"'
        ' crossorigin="anonymous"'
        ' onload="renderMathInElement(document.body, {'
        "delimiters: ["
        "{left: '\\\\[', right: '\\\\]', display: true},"
        "{left: '\\\\(', right: '\\\\)', display: false}"
        "]"
        '});"></script>\n'
    )

    # Replace <p>.. math::</p><pre><code>...</code></pre>  →  display math
    new_content, count = re.subn(
        r"<p>\s*\.\.\s*math::\s*</p>\s*<pre><code>(.*?)</code></pre>",
        lambda m: ('<p><span class="math display">\\[' + m.group(1).strip() + "\\]</span></p>"),
        html_content,
        flags=re.DOTALL,
    )

    # Only inject KaTeX CDN if we actually converted any math blocks
    if count > 0 and _KATEX_CDN not in new_content:
        new_content = new_content.replace("</head>", _KATEX_HEAD + "</head>", 1)

    return new_content


def translate_rst_references(html_content):
    """
    Convert RST citation references into a styled numbered list.

    After quartodoc rendering, RST citations like::

        .. [1] Author (Year). "Title."
        .. [2] https://example.com

    end up as a single ``<p>`` tag with the markers run together::

        <p>.. [1] First ref. .. [2] Second ref.</p>

    This function splits them apart and renders each as a styled list item
    with the citation number as a label.
    """

    def _format_refs(m):
        text = m.group(1)
        # Split on citation markers: .. [N]
        parts = re.split(r"\.\.\s*\[(\d+)\]", text)
        # parts = ['', '1', ' First ref. ', '2', ' Second ref.', ...]
        if len(parts) < 3:
            return m.group(0)  # No valid citations found

        items = []
        # parts[0] is text before first marker (usually empty), then pairs of (number, text)
        for i in range(1, len(parts), 2):
            num = parts[i]
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if not body:
                continue
            # Auto-link bare URLs in the body
            body = re.sub(
                r"(https?://\S+)",
                r'<a href="\1" target="_blank" rel="noopener">\1</a>',
                body,
            )
            items.append(
                f'<li style="margin-bottom: 0.25rem;">'
                f'<span style="font-weight: 600; color: #6c757d;">[{num}]</span> '
                f"{body}</li>"
            )

        if not items:
            return m.group(0)

        return (
            '<ol style="list-style: none; padding-left: 0; margin: 0;">'
            + "\n".join(items)
            + "</ol>"
        )

    # Match <p> tags containing at least one .. [N] citation marker.
    # Use [^<]* instead of .*? to prevent matching across HTML tag boundaries,
    # and omit re.DOTALL so the match stays within a single line.
    html_content = re.sub(
        r"<p>((?:[^<]*\.\.\s*\[\d+\][^<]*)+)</p>",
        _format_refs,
        html_content,
    )
    return html_content


def extract_seealso_from_html(html_content):
    """
    Extract %seealso values from HTML content before stripping.

    Returns a list of referenced item names, or empty list if none found.
    """
    # Match %seealso in <p> tags (most common after markdown rendering)
    # This handles both standalone %seealso and when it follows other directives
    p_pattern = re.compile(
        r"<p>[^<]*%seealso\s+([^<%]+?)(?:%|</p>)",
        re.IGNORECASE,
    )

    # Match standalone %seealso lines (not in HTML tags)
    standalone_pattern = re.compile(
        r"%seealso\s+([^\n%<]+)",
        re.IGNORECASE,
    )

    # Try <p> pattern first
    match = p_pattern.search(html_content)
    if not match:
        match = standalone_pattern.search(html_content)

    if match:
        # Parse comma-separated list
        items_str = match.group(1).strip()
        items = [item.strip() for item in items_str.split(",")]
        return [item for item in items if item]

    return []


def generate_seealso_html(seealso_items):
    """
    Generate HTML for a "See Also" section with links to other reference pages.
    """
    if not seealso_items:
        return ""

    links = []
    for item in seealso_items:
        # Generate link to the reference page
        # Item could be "Graph.add_edge" or just "add_edge"
        html_filename = f"{item}.html"
        links.append(f'<a href="{html_filename}">{item}</a>')

    links_html = ", ".join(links)

    return f"""
<div class="see-also" style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid #dee2e6;">
<h3 style="font-size: 0.9rem; font-weight: 600; color: #6c757d; margin-bottom: 0.5rem;">See Also</h3>
<p style="margin: 0;">{links_html}</p>
</div>
"""


# Process all HTML files in the `_site/reference/` directory (except `index.html`)
# and apply the specified transformations
html_files = [f for f in glob.glob("_site/reference/*.html") if not f.endswith("index.html")]

print(f"Found {len(html_files)} HTML files to process")

for html_file in html_files:
    print(f"Processing: {html_file}")

    # Extract the item name from the filename (e.g., "GreatDocs.html" -> "GreatDocs")
    item_name_from_file = os.path.basename(html_file).replace(".html", "")

    with open(html_file, "r") as file:
        content = file.read()

    # Extract %seealso before stripping directives
    seealso_items = extract_seealso_from_html(content)

    # Strip %directive lines from rendered HTML (safety net for docstring directives)
    content = strip_directives_from_html(content)

    # Translate Sphinx field lists (:param, :type, :returns, :rtype, :raises)
    content = translate_sphinx_fields(content)

    # Translate Sphinx cross-reference roles (e.g. :py:exc:`ValueError`)
    content = translate_sphinx_roles(content)

    # Translate RST directives (e.g. .. versionadded:: 2.8.1)
    content = translate_rst_directives(content)

    # Translate RST .. math:: blocks into display math
    content = translate_rst_math(content)

    # Translate RST citation references (.. [1] ...)
    content = translate_rst_references(content)

    # Re-highlight the signature with Pygments for better syntax coloring
    content = highlight_signature_with_pygments(content)

    # Format signatures with multiple arguments onto separate lines
    content = format_signature_multiline(content)

    # Convert back to lines for line-by-line processing
    content = content.splitlines(keepends=True)

    # Determine the classification of each h1 tag based on its content
    # Use object_types metadata from introspection when available,
    # falling back to heuristics only when the metadata is missing
    _TYPE_BADGE_STYLES = {
        "class": ("class", "#6366f1", "#EEF2FF"),
        "exception": ("exception", "#dc2626", "#FEF2F2"),
        "enum": ("enum", "#6366f1", "#EEF2FF"),
        "function": ("function", "#7c3aed", "#F5F3FF"),
        "method": ("method", "#0891b2", "#ECFEFF"),
        "constant": ("constant", "#d97706", "#FFFBEB"),
        "type_alias": ("type alias", "#059669", "#ECFDF5"),
        "other": ("other", "#6b7280", "#F9FAFB"),
    }

    classification_info = {}
    for i, line in enumerate(content):
        # Look for both class="title" and styled h1 tags
        h1_match = re.search(r'<h1\s+class="title">(.*?)</h1>', line)
        if not h1_match:
            # Also check for h1 tags with style attribute (for level1 section titles)
            h1_match = re.search(r'<h1\s+style="[^"]*">(.*?)</h1>', line)

        if h1_match:
            original_h1_content = h1_match.group(1).strip()

            # Try metadata lookup first (use item_name_from_file as key)
            obj_type = object_types.get(item_name_from_file)

            if obj_type and obj_type in _TYPE_BADGE_STYLES:
                classification_info[i] = _TYPE_BADGE_STYLES[obj_type]
            else:
                # Fallback heuristic (only when metadata is unavailable)
                if original_h1_content and original_h1_content[0].isupper():
                    if "." in original_h1_content:
                        classification_info[i] = _TYPE_BADGE_STYLES["method"]
                    else:
                        classification_info[i] = _TYPE_BADGE_STYLES["class"]
                else:
                    classification_info[i] = _TYPE_BADGE_STYLES["function"]

    # Remove the literal text `Validate.` from the h1 tag
    # TODO: Add line below stating the class name for the method
    content = [
        line.replace(
            '<h1 class="title">Validate.',
            '<h1 class="title">',
        )
        for line in content
    ]

    # Add `()` only to functions and methods in the h1 title
    # Uses object_types metadata when available, otherwise falls back to heuristics
    _CALLABLE_TYPES = {"function", "method"}

    for i, line in enumerate(content):
        # Use regex to find h1 tags (both class="title" and styled versions)
        h1_match = re.search(r'<h1\s+class="title">', line)

        if not h1_match:
            h1_match = re.search(r'<h1\s+style="[^"]*">', line)

        if h1_match:
            # Extract the content of the h1 tag
            start = h1_match.end()
            end = line.find("</h1>", start)
            h1_content = line[start:end].strip()

            # Determine whether this item should get ()
            obj_type = object_types.get(item_name_from_file)

            if obj_type:
                # Metadata available — only add () for functions/methods
                should_add_parens = obj_type in _CALLABLE_TYPES
            else:
                # Fallback heuristic (original behaviour)
                should_add_parens = "." in h1_content or (
                    h1_content and not h1_content[0].isupper()
                )

            if should_add_parens:
                h1_content += "()"

            # Replace the h1 tag with the modified content
            content[i] = line[:start] + h1_content + line[end:]

    # Add classification labels using stored info
    for i, line in enumerate(content):
        if i in classification_info:
            h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", line)
            if h1_match:
                h1_content = h1_match.group(1)
                label_type, label_color, background_color = classification_info[i]

                label_span = f'<span style="font-size: 1rem; border-style: solid; border-width: 1px; border-color: {label_color}; background-color: {background_color}; margin-left: 12px; vertical-align: 0.1rem;"><code style="background-color: transparent; color: {label_color};">{label_type}</code></span>'

                new_h1_content = h1_content + label_span
                new_line = line.replace(h1_content, new_h1_content)
                content[i] = new_line

    # Wrap bare h1 tags (those with style attribute but no quarto-title wrapper) in proper structure
    for i, line in enumerate(content):
        # Look for h1 tags with style attribute that aren't already wrapped
        if "<h1 style=" in line and "SFMono-Regular" in line:
            # Check if this h1 is already wrapped in quarto-title div
            # Look at previous lines to see if there's a quarto-title div
            is_wrapped = False
            for j in range(max(0, i - 5), i):
                if 'class="quarto-title"' in content[j]:
                    is_wrapped = True
                    break

            # If not wrapped, wrap it
            if not is_wrapped:
                # Extract the h1 content
                h1_content = line.strip()

                # Replace the line with the wrapped version
                wrapped_h1 = f'<div class="quarto-title">\n{h1_content}\n</div>\n'
                content[i] = wrapped_h1

    # Add a style attribute to the h1 tag to use a monospace font for code-like appearance
    content = [
        line.replace(
            '<h1 class="title">',
            "<h1 class=\"title\" style=\"font-family: SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size: 1.25rem;\">",
        )
        for line in content
    ]

    # Some h1 tags may not have a class attribute, so we handle that case too
    content = [
        line.replace(
            "<h1>",
            "<h1 style=\"font-family: SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size: 1.25rem;\">",
        )
        for line in content
    ]

    # Move the first <p> tag (description) to immediately after the title header
    header_end_line = None
    first_p_line = None
    first_p_content = None
    found_sourcecode = False
    title_line = None
    sourcecode_line = None

    # First pass: find the header end, title, sourcecode, and the first <p> tag after sourceCode
    for i, line in enumerate(content):
        # Find where the header ends
        if "</header>" in line:
            header_end_line = i

        # Find the title line (either in header or in level1 section)
        if '<h1 class="title"' in line or ("<h1 style=" in line and "SFMono-Regular" in line):
            title_line = i

        # Look for the sourceCode div
        if '<div class="sourceCode" id="cb1">' in line:
            found_sourcecode = True
            sourcecode_line = i

        # Find the first <p> tag after we've seen the sourceCode div
        if found_sourcecode and first_p_line is None and line.strip().startswith("<p"):
            first_p_line = i
            first_p_content = line
            break

    # Determine where to insert the description paragraph
    # If title is after header, insert after title; otherwise insert after header
    if (
        header_end_line is not None
        and first_p_line is not None
        and title_line is not None
        and sourcecode_line is not None
    ):
        if title_line > header_end_line:
            # Title is in a separate section, insert after title
            insert_after_line = title_line
        else:
            # Title is in header, insert after header
            insert_after_line = header_end_line

        # Apply italic styling to the description
        if "style=" not in first_p_content:
            styled_p = first_p_content.replace(
                "<p>",
                '<p class="doc-description" style="font-size: 1rem; font-style: italic; margin-top: 0.25rem; line-height: 1.3;">',
            )
        else:
            styled_p = first_p_content

        # Remove the original <p> line
        content.pop(first_p_line)

        # Adjust sourcecode_line since we removed a line before it
        if first_p_line < sourcecode_line:
            sourcecode_line -= 1

        # Insert the styled <p> line after the determined position (accounting for the removed line)
        insert_position = (
            insert_after_line + 1 if first_p_line > insert_after_line else insert_after_line
        )
        content.insert(insert_position, "\n")  # Add spacing
        content.insert(insert_position + 1, styled_p)
        content.insert(insert_position + 2, "\n")  # Add spacing

        # Adjust sourcecode_line since we added lines before it
        sourcecode_line += 3

        # Add "USAGE" label and "SOURCE" link before the sourceCode div
        # The SOURCE link will be on the right side, USAGE on the left
        source_link = get_source_link_html(item_name_from_file)
        if source_link:
            usage_row = f'<div class="usage-source-row" style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: -14px;"><span style="font-size: 12px; color: rgb(170, 170, 170);">USAGE</span>{source_link}</div>\n'
        else:
            usage_row = '<p style="font-size: 12px; color: rgb(170, 170, 170); margin-bottom: -14px;">USAGE</p>\n'
        content.insert(sourcecode_line, usage_row)

    # Fix return value formatting in individual function pages, removing the `:` before the
    # return value and adjusting the style of the parameter annotation separator
    content_str = "".join(content)
    return_value_pattern = (
        r'<span class="parameter-name"></span> <span class="parameter-annotation-sep">:</span>'
    )
    return_value_replacement = r'<span class="parameter-name"></span> <span class="parameter-annotation-sep" style="margin-left: -8px;"></span>'
    content_str = re.sub(return_value_pattern, return_value_replacement, content_str)

    # Fix double asterisks in **kwargs and **attributes style parameters
    # Pattern: ****name** -> **name (with proper styling)
    content_str = re.sub(r"\*\*\*\*(\w+)\*\*", r"**<strong>\1</strong>", content_str)

    # Fix leading colon in Raises/Returns sections (e.g., ": ValueError" -> "ValueError")
    # This handles cases like: <dt><code><span class="parameter-annotation-sep">:</span> <span class="parameter-annotation">ValueError</span></code></dt>
    content_str = re.sub(
        r'<dt><code><span class="parameter-annotation-sep">:</span>\s*<span class="parameter-annotation">([^<]+)</span></code></dt>',
        r'<dt><code><span class="parameter-annotation">\1</span></code></dt>',
        content_str,
    )

    content = content_str.splitlines(keepends=True)

    # Turn all h3 tags into h4 tags
    content = [line.replace("<h3", "<h4").replace("</h3>", "</h4>") for line in content]

    # Turn all h2 tags into h3 tags
    content = [line.replace("<h2", "<h3").replace("</h2>", "</h3>") for line in content]

    # Inject "See Also" section if %seealso was found
    content_str = "".join(content)
    if seealso_items:
        seealso_html = generate_seealso_html(seealso_items)
        # Insert before </main>
        content_str = content_str.replace("</main>", f"{seealso_html}</main>")

    # Place a horizontal rule at the end of each reference page
    main_end_pattern = r"</main>"
    main_end_replacement = '</main>\n<hr style="padding: 0; margin: 0;">\n'
    content_str = re.sub(main_end_pattern, main_end_replacement, content_str)

    # Remove breadcrumb navigation (redundant with sidebar)
    breadcrumb_pattern = r'<nav class="quarto-page-breadcrumbs[^"]*"[^>]*>.*?</nav>'
    content_str = re.sub(breadcrumb_pattern, "", content_str, flags=re.DOTALL)

    content = content_str.splitlines(keepends=True)

    with open(html_file, "w") as file:
        file.writelines(content)


# Modify the `index.html` file in the `_site/reference/` directory
index_file = "_site/reference/index.html"

if os.path.exists(index_file):
    print(f"Processing index file: {index_file}")

    with open(index_file, "r") as file:
        content = file.read()

    # Convert tables to dl/dt/dd format
    def convert_table_to_dl(match):
        table_content = match.group(1)

        # Extract all table rows
        row_pattern = r"<tr[^>]*>(.*?)</tr>"
        rows = re.findall(row_pattern, table_content, re.DOTALL)

        dl_items = []
        for row in rows:
            # Extract the two td elements
            td_pattern = r"<td[^>]*>(.*?)</td>"
            tds = re.findall(td_pattern, row, re.DOTALL)

            if len(tds) == 2:
                link_content = tds[0].strip()
                description = tds[1].strip()

                dt = f"<dt>{link_content}</dt>"
                dd = f'<dd style="margin-top: -3px;">{description}</dd>'
                dl_items.append(f"{dt}\n{dd}")

        dl_content = "\n\n".join(dl_items)
        return f'<div class="caption-top table" style="border-top-style: dashed; border-bottom-style: dashed;">\n<dl style="margin-top: 10px;">\n\n{dl_content}\n\n</dl>\n</div>'

    # Replace all table structures with dl/dt/dd
    table_pattern = r'<table class="caption-top table">\s*<tbody>(.*?)</tbody>\s*</table>'
    content = re.sub(table_pattern, convert_table_to_dl, content, flags=re.DOTALL)

    # Add () only to functions and methods in <a> tags within <dt> elements
    def add_parens_to_functions(match):
        full_tag = match.group(0)
        link_text = match.group(1)

        # Use object_types metadata when available
        obj_type = object_types.get(link_text)
        if obj_type:
            if obj_type in ("function", "method"):
                return full_tag.replace(f">{link_text}</a>", f">{link_text}()</a>")
            return full_tag

        # Fallback heuristic (only when metadata is unavailable)
        if "." in link_text or (link_text and not link_text[0].isupper()):
            return full_tag.replace(f">{link_text}</a>", f">{link_text}()</a>")

        return full_tag

    # Find all <a> tags within <dt> elements and apply the function
    dt_link_pattern = r"<dt><a[^>]*>([^<]+)</a></dt>"
    content = re.sub(dt_link_pattern, add_parens_to_functions, content)

    # Remove redundant "API Reference" top-level nav item
    # Find the nav structure and flatten it by removing the top-level wrapper
    nav_pattern = r'(<nav[^>]*>.*?<h2[^>]*>.*?</h2>\s*<ul>\s*)<li><a[^>]*href="[^"]*#api-reference"[^>]*>API Reference</a>\s*<ul[^>]*>(.*?)</ul></li>\s*(</ul>\s*</nav>)'
    nav_replacement = r"\1\2\3"
    content = re.sub(nav_pattern, nav_replacement, content, flags=re.DOTALL)

    with open(index_file, "w") as file:
        file.write(content)

    print("Index file processing complete")
else:
    print(f"Index file not found: {index_file}")


# Update quarto-secondary-nav-title to display "User Guide" text
# This improves the mobile navigation by making it clear what the sidebar toggle reveals
all_html_files = glob.glob("_site/**/*.html", recursive=True)
print(f"Found {len(all_html_files)} HTML files to check for secondary nav title")

for html_file in all_html_files:
    with open(html_file, "r") as file:
        content = file.read()

    # Replace empty h1.quarto-secondary-nav-title with h5 containing "User Guide"
    original_pattern = r'<h1 class="quarto-secondary-nav-title"></h1>'
    replacement = '<h5 class="quarto-secondary-nav-title">User Guide</h5>'

    if original_pattern in content:
        print(f"Updating secondary nav title in: {html_file}")
        content = content.replace(original_pattern, replacement)

        with open(html_file, "w") as file:
            file.write(content)

print("Finished processing all files")


# ============================================================================
# GitHub Widget Injection
# ============================================================================
# Replace escaped GitHub widget placeholder with actual HTML
# This handles cases where Quarto escapes the HTML in navbar text items


def inject_github_widget():
    """
    Find and replace escaped GitHub widget placeholders with actual widget HTML.

    Quarto escapes HTML in navbar text items, so we need to post-process to inject the actual widget
    div.
    """
    print("Checking for GitHub widget placeholders...")

    widget_escaped_pattern = re.compile(
        r'<span class="menu-text">&lt;div id="github-widget" '
        r'data-owner="([^"]*)" data-repo="([^"]*)"&gt;&lt;/div&gt;</span>'
    )

    widget_count = 0

    for html_file in all_html_files:
        with open(html_file, "r") as file:
            content = file.read()

        # Check if this file has an escaped widget placeholder
        match = widget_escaped_pattern.search(content)
        if match:
            owner = match.group(1)
            repo = match.group(2)

            # Replace with actual widget HTML
            replacement = f'<div id="github-widget" data-owner="{owner}" data-repo="{repo}"></div>'
            content = widget_escaped_pattern.sub(replacement, content)

            with open(html_file, "w") as file:
                file.write(content)

            widget_count += 1

    if widget_count > 0:
        print(f"Injected GitHub widget into {widget_count} HTML files")
    else:
        print("No GitHub widget placeholders found")


inject_github_widget()


# ============================================================================
# Version Badge Injection
# ============================================================================
# Insert a version badge into the navbar title from _package_meta.json


def inject_version_badge():
    """
    Inject a version badge next to the package name in the navbar.

    Reads package version (and optional release date) from
    ``_package_meta.json`` (written by the build) and inserts a small badge
    span inside each ``<span class="navbar-title">`` element across all
    rendered HTML files.  When a ``published_at`` date is present the badge
    receives a ``title`` attribute so the release date appears as a native
    browser tooltip on hover.
    """
    meta_path = "_package_meta.json"
    if not os.path.exists(meta_path):
        print("No _package_meta.json found, skipping version badge injection")
        return

    with open(meta_path, "r") as f:
        meta = json.load(f)

    version = meta.get("version", "")
    if not version:
        print("No version in _package_meta.json, skipping version badge injection")
        return

    # Build an optional title attribute with the release date
    published_at = meta.get("published_at", "")
    title_attr = ""
    if published_at:
        # published_at is ISO-8601 e.g. "2025-06-15T12:00:00Z"
        date_str = published_at[:10]  # "2025-06-15"
        title_attr = f' title="Released {date_str}"'

    print(f"Injecting version badge v{version} into navbar...")

    # Match <span class="navbar-title">PackageName</span>
    navbar_title_pattern = re.compile(r'(<span class="navbar-title">)(.*?)(</span>)')

    badge_html = f'<span class="version-badge"{title_attr}>v{version}</span>'

    badge_count = 0

    for html_file in all_html_files:
        with open(html_file, "r") as file:
            content = file.read()

        match = navbar_title_pattern.search(content)
        if match:
            # Only inject if badge not already present
            if "version-badge" not in content:
                replacement = f"{match.group(1)}{match.group(2)} {badge_html}{match.group(3)}"
                content = navbar_title_pattern.sub(replacement, content)

                with open(html_file, "w") as file:
                    file.write(content)

                badge_count += 1

    if badge_count > 0:
        print(f"Injected version badge into {badge_count} HTML files")
    else:
        print("No navbar titles found for version badge injection")


inject_version_badge()


# ============================================================================
# Process CLI reference pages to style titles like API reference pages


def process_cli_reference_pages():
    """
    Process CLI reference pages to add consistent styling.

    This adds the 'cli-title' class to h1 elements in CLI reference pages
    so they match the monospaced font style of API reference pages.
    """
    cli_html_files = glob.glob("_site/reference/cli/*.html")

    if not cli_html_files:
        return

    print(f"Processing {len(cli_html_files)} CLI reference pages...")

    for html_file in cli_html_files:
        with open(html_file, "r") as file:
            content = file.read()

        # Add 'cli-title' class to h1.title elements
        # This matches the pattern: <h1 class="title">
        content = content.replace('<h1 class="title">', '<h1 class="title cli-title">')

        with open(html_file, "w") as file:
            file.write(content)

    print(f"Styled {len(cli_html_files)} CLI reference page titles")


process_cli_reference_pages()


def fix_script_paths():
    """
    Fix relative script paths for HTML files in subdirectories.

    Quarto's include-after-body with text doesn't resolve paths relative to the output file's
    location. This function finds script tags with relative paths and adjusts them based on the
    file's depth in the directory structure.
    """
    print("Fixing script paths for subdirectory pages...")

    fixed_count = 0

    for html_file in all_html_files:
        # Calculate depth relative to _site directory
        rel_path = os.path.relpath(html_file, "_site")
        depth = rel_path.count(os.sep)

        # Skip files at root level (depth 0)
        if depth == 0:
            continue

        with open(html_file, "r") as file:
            content = file.read()

        # Build the relative path prefix (e.g., "../" for depth 1, "../../" for depth 2)
        prefix = "../" * depth

        modified = False

        # Fix github-widget.js path
        old_gh_script = '<script src="github-widget.js"></script>'
        new_gh_script = f'<script src="{prefix}github-widget.js"></script>'

        if old_gh_script in content:
            content = content.replace(old_gh_script, new_gh_script)
            modified = True

        # Fix sidebar-filter.js path
        old_filter_script = '<script src="sidebar-filter.js"></script>'
        new_filter_script = f'<script src="{prefix}sidebar-filter.js"></script>'

        if old_filter_script in content:
            content = content.replace(old_filter_script, new_filter_script)
            modified = True

        # Fix reference-switcher.js path
        old_ref_switcher = '<script src="reference-switcher.js"></script>'
        new_ref_switcher = f'<script src="{prefix}reference-switcher.js"></script>'

        if old_ref_switcher in content:
            content = content.replace(old_ref_switcher, new_ref_switcher)
            modified = True

        # Fix dark-mode-toggle.js path
        old_dark_mode = '<script src="dark-mode-toggle.js"></script>'
        new_dark_mode = f'<script src="{prefix}dark-mode-toggle.js"></script>'

        if old_dark_mode in content:
            content = content.replace(old_dark_mode, new_dark_mode)
            modified = True

        # Fix theme-init.js path
        old_theme_init = '<script src="theme-init.js"></script>'
        new_theme_init = f'<script src="{prefix}theme-init.js"></script>'

        if old_theme_init in content:
            content = content.replace(old_theme_init, new_theme_init)
            modified = True

        if modified:
            with open(html_file, "w") as file:
                file.write(content)
            fixed_count += 1

    if fixed_count > 0:
        print(f"Fixed script paths in {fixed_count} HTML files in subdirectories")
    else:
        print("No script path fixes needed")


fix_script_paths()
