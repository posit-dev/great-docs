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
# ("class", "namedtuple", "typeddict", "protocol", "abc", "exception", "function", "method", "constant", "enum", "type_alias", "other")
object_types = {}
object_types_path = "_object_types.json"
if os.path.exists(object_types_path):
    print(f"Loading object types from {object_types_path}")
    with open(object_types_path, "r") as f:
        object_types = json.load(f)
    print(f"Loaded {len(object_types)} object type entries")
else:
    print("No object types file found, falling back to heuristic classification")

# Load constant value metadata for displaying values on constant reference pages.
# Keys are constant names, values are dicts with optional "value" and "annotation".
constant_values: dict[str, dict[str, str]] = {}
constant_values_path = "_constant_values.json"
if os.path.exists(constant_values_path):
    with open(constant_values_path, "r") as f:
        constant_values = json.load(f)
    print(f"Loaded {len(constant_values)} constant value entries")

# Load dataclass attributes metadata for fixing incomplete Attributes tables.
# Written by great-docs core during build step 1.7.
# Keys are fully qualified object paths (e.g., "pkg.Config"), values are
# dicts mapping field name -> description.
dataclass_attrs_metadata: dict[str, dict[str, str]] = {}
dataclass_attrs_path = "_dataclass_attrs.json"
if os.path.exists(dataclass_attrs_path):
    with open(dataclass_attrs_path, "r") as f:
        dataclass_attrs_metadata = json.load(f)
    if dataclass_attrs_metadata:
        print(f"Loaded dataclass attribute metadata for {len(dataclass_attrs_metadata)} class(es)")


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

        # Special handling: make method/function name stand out on every signature line
        # Pattern: ClassName.method_name( or function_name(
        # Replace the name before ( with a function class for better highlighting
        # Uses re.MULTILINE so ^ matches each line (important for @overload signatures)
        sig_name_pattern = re.compile(
            r'^(<span class="va">)(\w+)(</span>)(<span class="op">\.</span>)?'
            r'(<span class="va">)?(\w+)?(</span>)?(\()',
            re.MULTILINE,
        )

        def enhance_sig_name(m):
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

    Directives like %seealso and %nodoc are used for organizing documentation but
    they should not appear in the final rendered output. This function removes them after rendering.
    """
    # Match directives wrapped in <p> tags
    # e.g., <p>%seealso func_a, func_b</p>
    p_directive_pattern = re.compile(
        r"<p>\s*%(?:seealso|nodoc)(?:\s+[^<]*)?\s*</p>\s*\n?",
        re.IGNORECASE,
    )

    # Match standalone directive lines (plain text)
    # e.g., %seealso func_a
    standalone_directive_pattern = re.compile(
        r"^\s*%(?:seealso|nodoc)(?:\s+.*)?\s*$\n?",
        re.MULTILINE | re.IGNORECASE,
    )

    # Match directives that might be inline within text
    inline_directive_pattern = re.compile(
        r"%(?:seealso|nodoc)(?:\s+[^\n<]*)?",
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

    After rendering, Sphinx-style docstrings with `:param:`,
    `:type:`, `:returns:`, `:rtype:`, and `:raises:` fields end up
    mashed into a single `<p>` tag:

    ```html
    <p>:param x: Desc. :type x: int :returns: Desc. :rtype: str :raises ValueError: Desc.</p>
    ```

    This function parses those fields and emits the same `<section>` /
    `<dl>` / `<dt>` / `<dd>` structure that the renderer produces for
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


def translate_google_fields(html_content):
    """
    Convert Google-style docstring sections into structured doc sections.

    After rendering, Google-style docstrings with sections like
    ``Args:``, ``Returns:``, ``Raises:``, ``Note:``, ``Example:``,
    ``Warning:``, ``References:``, and ``See Also:`` end up as flat
    ``<p>`` tags::

        <p>Args: items: desc. strict: desc.</p>
        <p>Returns: A dict...</p><pre><code>details</code></pre>
        <p>Raises: ValueError: desc. TypeError: desc.</p>
        <p>Note: text</p>

    Indented continuation text renders as ``<pre><code>`` blocks adjacent
    to the section ``<p>``.  This function detects both patterns and emits
    the same ``<section>``/``<h1>``/``<dl>``/``<dt>``/``<dd>`` markup that
    the renderer produces for NumPy-style sections.
    """

    _PARAM_SECTIONS = {"Args", "Arguments", "Parameters", "Params"}
    _RETURN_SECTIONS = {"Returns", "Return"}
    _RAISE_SECTIONS = {"Raises", "Raise"}
    _SECTION_MAP = {
        "Note": "notes",
        "Notes": "notes",
        "Example": "examples",
        "Examples": "examples",
        "Warning": "warnings",
        "Warnings": "warnings",
        "References": "references",
        "See Also": "see-also",
    }

    ALL_SECTIONS = _PARAM_SECTIONS | _RETURN_SECTIONS | _RAISE_SECTIONS | set(_SECTION_MAP)
    # Sort longest-first so "See Also" matches before "See"
    section_names = "|".join(re.escape(s) for s in sorted(ALL_SECTIONS, key=len, reverse=True))

    # Match <p>SectionName: body</p>, optionally followed by <pre><code>…</code></pre>
    _GOOGLE_P = re.compile(
        rf"<p>(?P<section>{section_names}):\s*(?P<body>(?:(?!</p>).)*)</p>"
        r"(?:\s*<pre><code>(?P<pre_body>.*?)</code></pre>)?",
        re.DOTALL,
    )

    # ── helpers ──────────────────────────────────────────────────────────

    def _dbl_bt(text):
        """Convert ``word`` → <code>word</code>."""
        return re.sub(r"``(.*?)``", r"<code>\1</code>", text)

    def _pre_to_html(pre_text):
        """Convert <pre> block text (bullet lists + backticks) to HTML."""
        lines = pre_text.split("\n")
        out, in_list = [], False
        for line in lines:
            line = _dbl_bt(line)
            stripped = line.strip()
            if stripped.startswith("- "):
                if not in_list:
                    out.append("<ul>")
                    in_list = True
                out.append(f"<li>{stripped[2:]}</li>")
            else:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                if stripped:
                    out.append(f"<p>{stripped}</p>")
        if in_list:
            out.append("</ul>")
        return "\n".join(out)

    def _parse_params(body):
        """Parse 'name: desc. name2: desc2.' into [(name, desc), …]."""
        hits = list(re.finditer(r"(?:^|(?<=\.\s))([a-z_]\w*)\s*:\s*", body))
        if not hits:
            return []
        params = []
        for i, hit in enumerate(hits):
            name = hit.group(1)
            start = hit.end()
            end = hits[i + 1].start() if i + 1 < len(hits) else len(body)
            desc = body[start:end].strip()
            params.append((name, desc))
        return params

    def _parse_raises(body):
        """Parse 'ExcType: desc. ExcType2: desc2.' into [(exc, desc), …]."""
        hits = list(re.finditer(r"(?:^|(?<=\.\s))([A-Z][a-zA-Z]+)\s*:\s*", body))
        if not hits:
            return []
        raises = []
        for i, hit in enumerate(hits):
            exc = hit.group(1)
            start = hit.end()
            end = hits[i + 1].start() if i + 1 < len(hits) else len(body)
            desc = body[start:end].strip()
            raises.append((exc, desc))
        return raises

    # ── main replacer ────────────────────────────────────────────────────

    def _replace(m):
        section = m.group("section")
        body = (m.group("body") or "").strip()
        pre_body = m.group("pre_body").strip() if m.group("pre_body") else None

        # ── Args / Parameters ─────────────────────────────────────────
        if section in _PARAM_SECTIONS:
            full = f"{body} {pre_body}" if pre_body and body else (body or pre_body or "")
            params = _parse_params(full)
            if not params:
                return m.group(0)
            items = []
            for pname, pdesc in params:
                pdesc = _dbl_bt(pdesc)
                dt = (
                    f'<dt><code><span class="parameter-name">'
                    f"<strong>{pname}</strong></span></code></dt>"
                )
                dd = f"<dd>\n<p>{pdesc}</p>\n</dd>" if pdesc else "<dd></dd>"
                items.append(f"{dt}\n{dd}")
            return (
                '<section id="parameters" class="level1 doc-section doc-section-parameters">\n'
                '<h1 class="doc-section doc-section-parameters">Parameters</h1>\n'
                "<dl>\n" + "\n".join(items) + "\n</dl>\n</section>"
            )

        # ── Returns ───────────────────────────────────────────────────
        if section in _RETURN_SECTIONS:
            parts = []
            if body:
                parts.append(f"<p>{_dbl_bt(body)}</p>")
            if pre_body:
                parts.append(_pre_to_html(pre_body))
            content = "\n".join(parts)
            return (
                '<section id="returns" class="level1 doc-section doc-section-returns">\n'
                '<h1 class="doc-section doc-section-returns">Returns</h1>\n'
                f"{content}\n</section>"
            )

        # ── Raises ────────────────────────────────────────────────────
        if section in _RAISE_SECTIONS:
            full = f"{body} {pre_body}" if pre_body and body else (body or pre_body or "")
            raises = _parse_raises(full)
            if not raises:
                return m.group(0)
            items = []
            for exc, desc in raises:
                desc = _dbl_bt(desc)
                dt = f'<dt><code><span class="parameter-annotation">{exc}</span></code></dt>'
                dd = f"<dd>\n<p>{desc}</p>\n</dd>" if desc else "<dd></dd>"
                items.append(f"{dt}\n{dd}")
            return (
                '<section id="raises" class="level1 doc-section doc-section-raises">\n'
                '<h1 class="doc-section doc-section-raises">Raises</h1>\n'
                "<dl>\n" + "\n".join(items) + "\n</dl>\n</section>"
            )

        # ── Example / Examples (code blocks) ──────────────────────────
        if section in {"Example", "Examples"}:
            code_parts = []
            if body:
                code_parts.append(body)
            if pre_body:
                code_parts.append(pre_body)
            code = "\n".join(code_parts)
            return (
                '<section id="examples" class="level1 doc-section doc-section-examples">\n'
                '<h1 class="doc-section doc-section-examples">Examples</h1>\n'
                f"<pre><code>{code}</code></pre>\n</section>"
            )

        # ── Other sections (Note, Warning, References, See Also) ─────
        slug = _SECTION_MAP.get(section, section.lower().replace(" ", "-"))
        full = body
        if pre_body:
            full = f"{body}\n{pre_body}" if body else pre_body
        full = _dbl_bt(full)
        content = f"<p>{full}</p>" if full else ""
        return (
            f'<section id="{slug}" class="level1 doc-section doc-section-{slug}">\n'
            f'<h1 class="doc-section doc-section-{slug}">{section}</h1>\n'
            f"{content}\n</section>"
        )

    html_content = _GOOGLE_P.sub(_replace, html_content)
    return html_content


def translate_sphinx_roles(html_content):
    """
    Convert Sphinx cross-reference roles into clean HTML.

    The renderer sometimes passes through Sphinx-style roles verbatim.  The most
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
    rendering, for example:

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
        content_html = f'<p style="margin: 0; color: #1f2937;">{content}</p>' if content else ""
        return (
            f'<div style="margin: 1rem 0; padding: 0.75rem 1rem; '
            f"background-color: {bg}; "
            f"border-left: 4px solid {border}; "
            f'border-radius: 4px; color: #1f2937;">'
            f'<p style="margin: 0 0 0.25rem 0; font-weight: 600; '
            f'font-size: 0.875rem; color: #1f2937;">{icon} {title}</p>'
            f"{content_html}"
            f"</div>"
        )

    # Pattern 1 – directive <p> followed by a <pre><code> block body.
    # RST block directives like ``.. note::`` with indented body text
    # become: <p>.. note::</p>\n<pre><code>body text</code></pre>
    def _replace_block_directive(m):
        directive = m.group("directive")
        pre_body = m.group("pre_body").strip()
        style = _DIRECTIVE_STYLES[directive]
        icon, bg, border, label = style

        if directive in _VERSION_DIRECTIVES:
            parts = pre_body.split(None, 1) if pre_body else []
            version = parts[0] if parts else ""
            desc = parts[1] if len(parts) > 1 else ""
            title = f"{label} {version}" if version else label
            content = desc
        else:
            title = label
            content = pre_body

        content_html = f'<p style="margin: 0; color: #1f2937;">{content}</p>' if content else ""
        return (
            f'<div style="margin: 1rem 0; padding: 0.75rem 1rem; '
            f"background-color: {bg}; "
            f"border-left: 4px solid {border}; "
            f'border-radius: 4px; color: #1f2937;">'
            f'<p style="margin: 0 0 0.25rem 0; font-weight: 600; '
            f'font-size: 0.875rem; color: #1f2937;">{icon} {title}</p>'
            f"{content_html}"
            f"</div>"
        )

    html_content = re.sub(
        rf"<p>\s*\.\.\s+(?P<directive>{directive_names})::\s*</p>"
        r"\s*<pre><code>(?P<pre_body>.*?)</code></pre>",
        _replace_block_directive,
        html_content,
        flags=re.DOTALL,
    )

    # Pattern 2 – directive with inline body text in the same <p> tag.
    # e.g. <p>.. versionadded:: 2.8.1</p>
    # The body may contain inline HTML tags (e.g. <code>...</code>) produced
    # by the Sphinx-role translation step that runs before this function.
    html_content = re.sub(
        rf"<p>\s*\.\.\s+(?P<directive>{directive_names})::\s*(?P<body>.*?)\s*</p>",
        _replace_directive,
        html_content,
    )

    # Pattern 3 – directive misinterpreted as a return-type annotation in a
    # <dt>/<dd> pair.  the renderer's numpy parser sometimes treats directives
    # like ``.. versionadded:: 2.0`` at the end of a docstring as an extra
    # return entry, producing:
    #   <dt><code>...<span class="parameter-annotation">.. versionadded:: 2.0
    #   </span></code></dt>
    #   <dd><p>Optional description.</p></dd>
    def _replace_dt_directive(m):
        directive = m.group("directive")
        body = (m.group("body") or "").strip()
        dd_body = (m.group("dd_body") or "").strip()
        style = _DIRECTIVE_STYLES[directive]
        icon, bg, border, label = style

        if directive in _VERSION_DIRECTIVES:
            parts = body.split(None, 1) if body else []
            version = parts[0] if parts else ""
            desc = parts[1] if len(parts) > 1 else ""
            if dd_body and not desc:
                desc = dd_body
            elif dd_body:
                desc = f"{desc} {dd_body}"
            title = f"{label} {version}" if version else label
            content = desc
        else:
            title = label
            content = dd_body if dd_body else body

        content_html = f'<p style="margin: 0; color: #1f2937;">{content}</p>' if content else ""
        return (
            f'<div style="margin: 1rem 0; padding: 0.75rem 1rem; '
            f"background-color: {bg}; "
            f"border-left: 4px solid {border}; "
            f'border-radius: 4px; color: #1f2937;">'
            f'<p style="margin: 0 0 0.25rem 0; font-weight: 600; '
            f'font-size: 0.875rem; color: #1f2937;">{icon} {title}</p>'
            f"{content_html}"
            f"</div>"
        )

    _dt_pattern = re.compile(
        rf'<dt><code><span class="parameter-name">[^<]*</span>\s*'
        rf'<span class="parameter-annotation-sep"[^>]*>[^<]*</span>\s*'
        rf'<span class="parameter-annotation">'
        rf"\.\.\s+(?P<directive>{directive_names})::\s*(?P<body>[^<]*?)"
        rf"</span></code></dt>"
        rf"\s*<dd>\s*(?:<p>(?P<dd_body>.*?)</p>\s*)?</dd>",
        re.DOTALL,
    )
    _dt_count = len(_dt_pattern.findall(html_content))
    html_content = _dt_pattern.sub(_replace_dt_directive, html_content)

    return html_content


def translate_bold_section_headers(html_content):
    """
    Convert bold-text section headings into proper doc-section markup.

    Sphinx-format docstrings sometimes use ``**Examples**::`` to introduce
    a section.  After rendering this becomes::

        <p><strong>Examples</strong>::</p>

    This function converts those into the same ``<section>``/``<h1>``
    structure that the renderer uses for NumPy-style sections so the page
    has a consistent look.
    """

    # Map of recognized section names → CSS id / class suffix
    _SECTION_NAMES = {
        "Examples": "examples",
        "Example": "examples",
        "Notes": "notes",
        "Note": "notes",
        "References": "references",
        "Warnings": "warnings",
        "Warning": "warnings",
        "See Also": "see-also",
    }

    section_pattern = "|".join(re.escape(n) for n in _SECTION_NAMES)

    def _replace_header(m):
        name = m.group("name")
        slug = _SECTION_NAMES.get(name, name.lower().replace(" ", "-"))
        return (
            f'<section id="{slug}" class="level1 doc-section doc-section-{slug}">\n'
            f'<h1 class="doc-section doc-section-{slug}">{name}</h1>'
        )

    html_content = re.sub(
        rf"<p><strong>(?P<name>{section_pattern})</strong>::</p>",
        _replace_header,
        html_content,
    )

    return html_content


def fix_doctest_blockquotes(html_content):
    """
    Convert nested blockquotes from doctest `>>>` lines into code blocks.

    When the renderer produces an Example section with raw `>>>` lines in the
    `.qmd` file, Quarto/Pandoc interprets the leading `>` characters as
    Markdown blockquote markers.  A `>>>` line becomes triple-nested
    `<blockquote>` elements:

    ```html
    <blockquote class="blockquote">
    <blockquote class="blockquote">
    <blockquote class="blockquote">
    <p>func(x) 'result'</p>
    </blockquote>
    </blockquote>
    </blockquote>
    ```

    This function detects that pattern inside Example/Examples doc-sections
    and replaces it with a proper `<pre><code>` block so the content
    renders in monospace as code.
    """
    # Match one or more triple-nested blockquote clusters inside an
    # Example or Examples doc-section.
    _SECTION_RE = re.compile(
        r'(<section\s[^>]*class="[^"]*doc-section-examples?[^"]*"[^>]*>\s*'
        r"<h1[^>]*>.*?</h1>\s*)"
        r"((?:\s*<blockquote\s[^>]*>\s*<blockquote\s[^>]*>\s*<blockquote\s[^>]*>"
        r"\s*<p>.*?</p>\s*</blockquote>\s*</blockquote>\s*</blockquote>\s*)+)",
        re.DOTALL,
    )

    # Extract individual <p> content from triple-nested blockquotes
    _BQ_TEXT_RE = re.compile(
        r"<blockquote\s[^>]*>\s*<blockquote\s[^>]*>\s*<blockquote\s[^>]*>"
        r"\s*<p>(.*?)</p>\s*</blockquote>\s*</blockquote>\s*</blockquote>",
        re.DOTALL,
    )

    def _replace_section(m):
        header = m.group(1)
        bq_block = m.group(2)
        lines = []
        for bq in _BQ_TEXT_RE.finditer(bq_block):
            text = bq.group(1).strip()
            # Reconstruct the doctest line with >>> prefix
            lines.append(f"&gt;&gt;&gt; {text}")
        code = "\n".join(lines)
        return f"{header}<pre><code>{code}</code></pre>\n"

    return _SECTION_RE.sub(_replace_section, html_content)


def fix_plain_doctest_code_blocks(html_content):
    """
    Convert plain ``<pre><code>`` blocks containing doctest ``>>>`` lines
    into properly highlighted Python code blocks.

    When the renderer renders consecutive doctest examples separated by blank
    lines, only the first block gets a proper ```` ```python ```` fence.
    Subsequent blocks become 4-space-indented text in the ``.qmd``, which
    Quarto renders as plain ``<pre><code>`` without syntax highlighting.

    This function finds those plain code blocks, re-highlights them with
    Pygments, and wraps them in the same ``sourceCode python`` structure
    that Quarto uses for fenced code blocks.
    """
    # Match <pre><code> blocks that contain &gt;&gt;&gt; (i.e. >>>) but
    # are NOT already inside a sourceCode div.  We look for <pre><code>
    # (no class) immediately, which distinguishes them from Quarto's
    # <pre class="sourceCode ..."><code class="sourceCode ..."> blocks.
    _PLAIN_DOCTEST_RE = re.compile(
        r"<pre><code>(.*?)</code></pre>",
        re.DOTALL,
    )

    # Track a counter for generating unique cb IDs
    _cb_counter = [0]

    def _find_max_cb_id(html):
        """Find the highest existing cb ID to avoid collisions."""
        ids = re.findall(r'id="cb(\d+)"', html)
        return max(int(i) for i in ids) if ids else 0

    _cb_counter[0] = _find_max_cb_id(html_content)

    def _replace_plain_doctest(m):
        code_html = m.group(1)

        # Only process blocks that contain doctest >>> markers
        if "&gt;&gt;&gt;" not in code_html:
            return m.group(0)

        # Decode HTML entities to get plain text for Pygments
        plain_text = code_html
        plain_text = plain_text.replace("&lt;", "<")
        plain_text = plain_text.replace("&gt;", ">")
        plain_text = plain_text.replace("&amp;", "&")
        plain_text = plain_text.replace("&quot;", '"')
        plain_text = plain_text.replace("&#39;", "'")
        # Strip any existing HTML tags (unlikely but safe)
        plain_text = re.sub(r"<[^>]+>", "", plain_text)

        # Highlight with Pygments
        lexer = PythonLexer()
        formatter = HtmlFormatter(nowrap=True, classprefix="")
        highlighted = highlight(plain_text, lexer, formatter)

        # Map Pygments CSS classes to Quarto CSS classes
        for pg_class, quarto_class in PYGMENTS_TO_QUARTO_CLASS.items():
            if quarto_class:
                highlighted = highlighted.replace(f'class="{pg_class}"', f'class="{quarto_class}"')
            else:
                highlighted = re.sub(
                    rf'<span class="{pg_class}">([^<]*)</span>',
                    r"\1",
                    highlighted,
                )

        # Assign a unique cb ID
        _cb_counter[0] += 1
        cb_id = f"cb{_cb_counter[0]}"

        # Wrap each line in a span with proper id for line linking
        lines = highlighted.rstrip("\n").split("\n")
        wrapped_lines = []
        for j, line in enumerate(lines, 1):
            span_id = f"{cb_id}-{j}"
            wrapped_lines.append(
                f'<span id="{span_id}">'
                f'<a href="#{span_id}" aria-hidden="true" tabindex="-1"></a>'
                f"{line}</span>"
            )
        highlighted = "\n".join(wrapped_lines)

        return (
            f'<div class="code-copy-outer-scaffold">'
            f'<div class="sourceCode" id="{cb_id}">'
            f'<pre class="sourceCode python code-with-copy">'
            f'<code class="sourceCode python">'
            f"{highlighted}"
            f"</code></pre></div>"
            f'<button title="Copy to Clipboard" class="code-copy-button">'
            f'<i class="bi"></i></button></div>'
        )

    return _PLAIN_DOCTEST_RE.sub(_replace_plain_doctest, html_content)


def translate_rst_math(html_content):
    """
    Convert RST `.. math::` directives into display-math blocks.

    After rendering, a `.. math::` block in a docstring becomes
    literal HTML of the form:

    ```html
    <p>.. math::</p>
    <pre><code>LATEX EXPRESSION</code></pre>
    ```

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
    # (original two-colon pattern from RST)
    new_content, count = re.subn(
        r"<p>\s*\.\.\s*math::\s*</p>\s*<pre><code>(.*?)</code></pre>",
        lambda m: ('<p><span class="math display">\\[' + m.group(1).strip() + "\\]</span></p>"),
        html_content,
        flags=re.DOTALL,
    )

    # Also handle the single-colon variant produced when Pandoc reduces
    # trailing :: to : (e.g. <p>.. math:</p> followed by a sourceCode block)
    new_content, count2 = re.subn(
        r"<p>\s*\.\.\s*math:\s*</p>\s*"
        r"(?:<div[^>]*>\s*)?"  # optional wrapper div
        r"<pre[^>]*><code[^>]*>(.*?)</code></pre>"
        r"(?:\s*</div>)?",  # optional closing wrapper div
        lambda m: (
            '<p><span class="math display">\\['
            + re.sub(r"</?span[^>]*>", "", m.group(1)).strip()
            + "\\]</span></p>"
        ),
        new_content,
        flags=re.DOTALL,
    )
    count += count2

    # Only inject KaTeX CDN if we actually converted any math blocks
    if count > 0 and _KATEX_CDN not in new_content:
        new_content = new_content.replace("</head>", _KATEX_HEAD + "</head>", 1)

    return new_content


def translate_rst_references(html_content):
    """
    Convert RST citation references into a styled numbered list.

    After rendering, RST citations like::

        .. [1] Author (Year). "Title."
        .. [2] https://example.com

    end up as a single `<p>` tag with the markers run together::

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


def extract_seealso_from_doc_section(html_content):
    """
    Extract See Also items from rendered doc-section ``<section>`` blocks.

    NumPy-style and Google-style docstrings produce sections like::

        <section id="see-also" class="level1 doc-section doc-section-see-also">
        <h1 ...>See Also</h1>
        <p>transform : Transform data before analysis.</p>
        </section>

    This function parses those sections and returns a list of referenced
    item names (e.g., ``["transform"]``).
    """
    # Match <section id="see-also" ...> ... </section> blocks
    section_pat = re.compile(
        r'<section[^>]*\bid=["\']see-also["\'][^>]*>'
        r"(.*?)"
        r"</section>",
        re.DOTALL,
    )
    items = []
    for m in section_pat.finditer(html_content):
        body = m.group(1)
        # Remove the heading tags
        body = re.sub(r"<h[1-6][^>]*>.*?</h[1-6]>", "", body, flags=re.DOTALL)
        # Strip HTML tags to get plain text
        plain = re.sub(r"<[^>]+>", "", body).strip()
        if not plain:
            continue
        # Parse entries: each may be "name : description" or "name: description"
        # or multiple comma-separated or newline-separated entries
        for line in plain.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Handle comma-separated items on a single line
            parts = line.split(",")
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                # Extract the name before any " : " or ":" separator
                # e.g., "transform : Transform data before analysis."
                # e.g., "``validate``: Validate a schema before processing."
                # Strip backticks first
                part = part.replace("``", "").replace("`", "")
                name_match = re.match(r"^([\w.]+)(?:\s*:\s*.*)?$", part)
                if name_match:
                    items.append(name_match.group(1))
    return items


def remove_seealso_doc_section(html_content):
    """
    Remove ``<section id="see-also" ...>`` blocks from the HTML.

    Also removes the corresponding TOC entry.
    """
    # Remove the section block
    html_content = re.sub(
        r'<section[^>]*\bid=["\']see-also["\'][^>]*>'
        r".*?"
        r"</section>",
        "",
        html_content,
        flags=re.DOTALL,
    )
    # Remove the TOC entry for See Also
    html_content = re.sub(
        r'\s*<li><a[^>]*href=["\']#see-also["\'][^>]*>See Also</a></li>',
        "",
        html_content,
    )
    return html_content


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


def fix_dataclass_attributes(content_str):
    """Rebuild the Attributes table for dataclass pages using *_dataclass_attrs.json* metadata.

    The renderer may only discover a subset of dataclass fields.  This function
    replaces the ``<tbody>`` of the Attributes ``<table>`` with the complete
    set of fields recorded in the metadata file.
    """
    if not dataclass_attrs_metadata:
        return content_str

    # Locate the Attributes <section> (Quarto wraps each ## heading in a section)
    attrs_match = re.search(r'<section[^>]*\bid="attributes"[^>]*>', content_str)
    if not attrs_match:
        return content_str

    # Determine the object path by inspecting existing <a href="#obj.field">
    # anchors inside the Attributes table.
    attrs_section_start = attrs_match.start()
    attrs_section_end = content_str.find("</section>", attrs_section_start)
    if attrs_section_end < 0:
        return content_str

    attrs_section = content_str[attrs_section_start : attrs_section_end + len("</section>")]

    # Extract obj_path from an existing anchor (e.g., href="#pkg.Cls.field" -> "pkg.Cls")
    anchor_re = re.search(r'href="#([^"]+)\.(\w+)"', attrs_section)
    if not anchor_re:
        return content_str

    obj_path = anchor_re.group(1)

    if obj_path not in dataclass_attrs_metadata:
        return content_str

    fields = dataclass_attrs_metadata[obj_path]

    # Build new table rows
    rows = []
    for i, (fname, desc) in enumerate(fields.items()):
        row_class = "odd" if i % 2 == 0 else "even"
        anchor = f"{obj_path}.{fname}"
        rows.append(
            f'<tr class="{row_class}">\n'
            f'<td><a href="#{anchor}">{fname}</a></td>\n'
            f"<td>{desc}</td>\n"
            f"</tr>"
        )

    new_tbody = "<tbody>\n" + "\n".join(rows) + "\n</tbody>"

    # Replace the <tbody> inside the Attributes section
    new_attrs_section = re.sub(r"<tbody>.*?</tbody>", new_tbody, attrs_section, flags=re.DOTALL)

    content_str = (
        content_str[:attrs_section_start]
        + new_attrs_section
        + content_str[attrs_section_end + len("</section>") :]
    )
    return content_str


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

    # Translate Google-style field sections (Args:, Returns:, Raises:, etc.)
    content = translate_google_fields(content)

    # Translate Sphinx cross-reference roles (e.g. :py:exc:`ValueError`)
    content = translate_sphinx_roles(content)

    # Translate RST directives (e.g. .. versionadded:: 2.8.1)
    content = translate_rst_directives(content)

    # Translate bold section headers (e.g. **Examples**::) into doc-sections
    content = translate_bold_section_headers(content)

    # Fix doctest >>> lines that Quarto rendered as nested blockquotes
    content = fix_doctest_blockquotes(content)

    # Fix plain <pre><code> blocks containing >>> doctest lines
    # (consecutive examples where only the first got a proper code fence)
    content = fix_plain_doctest_code_blocks(content)

    # Translate RST .. math:: blocks into display math
    content = translate_rst_math(content)

    # Translate RST citation references (.. [1] ...)
    content = translate_rst_references(content)

    # Re-highlight the signature with Pygments for better syntax coloring
    content = highlight_signature_with_pygments(content)

    # Format signatures with multiple arguments onto separate lines
    content = format_signature_multiline(content)

    # For non-callable types (e.g., TypedDict, Enum), strip empty () from the signature
    # TypedDicts are structural type definitions, not constructors
    # Enums are accessed via members (e.g., Color.RED), not called
    _NON_CALLABLE_SIGNATURE_TYPES = {"typeddict", "enum"}
    obj_type_for_sig = object_types.get(item_name_from_file)
    if obj_type_for_sig and obj_type_for_sig in _NON_CALLABLE_SIGNATURE_TYPES:
        content = re.sub(
            r'(<span class="sig-name">[^<]+</span>)\(\)',
            r"\1",
            content,
        )

    # Convert back to lines for line-by-line processing
    content = content.splitlines(keepends=True)

    # Determine the classification of each h1 tag based on its content
    # Use object_types metadata from introspection when available,
    # falling back to heuristics only when the metadata is missing
    _TYPE_BADGE_STYLES = {
        "class": ("class", "#6366f1", "#EEF2FF"),
        "namedtuple": ("NamedTuple", "#6366f1", "#EEF2FF"),
        "typeddict": ("TypedDict", "#6366f1", "#EEF2FF"),
        "protocol": ("Protocol", "#6366f1", "#EEF2FF"),
        "abc": ("ABC", "#6366f1", "#EEF2FF"),
        "exception": ("exception", "#dc2626", "#FEF2F2"),
        "enum": ("enum", "#6366f1", "#EEF2FF"),
        "function": ("function", "#7c3aed", "#F5F3FF"),
        "method": ("method", "#0891b2", "#ECFEFF"),
        "classmethod": ("classmethod", "#0891b2", "#ECFEFF"),
        "staticmethod": ("staticmethod", "#0891b2", "#ECFEFF"),
        "property": ("property", "#0d9488", "#F0FDFA"),
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
                # Strip HTML tags to check plain text for existing ()
                _plain = re.sub(r"<[^>]+>", "", h1_content).strip()
                if not _plain.endswith("()"):
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
    # But skip "Attributes" and "Methods" section headings — they should look like
    # the Parameters section label (doc-section style), not code font.
    _SECTION_HEADINGS = {"Attributes", "Methods"}
    new_content = []
    for line in content:
        if "<h1>" in line:
            # Check if this is a section heading like Attributes or Methods
            h1_text_match = re.search(r"<h1>(.*?)</h1>", line)
            if h1_text_match and h1_text_match.group(1).strip() in _SECTION_HEADINGS:
                # Style like Parameters: use doc-section class instead of code font
                line = line.replace(
                    "<h1>",
                    '<h1 class="doc-section">',
                )
            else:
                line = line.replace(
                    "<h1>",
                    "<h1 style=\"font-family: SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size: 1.25rem;\">",
                )
        new_content.append(line)
    content = new_content

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

    # Inject constant value/annotation into constant reference pages.
    # Replaces the bare ``<p><code>NAME</code></p>`` that the renderer emits with a
    # styled display showing the type annotation and assigned value.
    obj_type_for_value = object_types.get(item_name_from_file)
    if obj_type_for_value == "constant" and item_name_from_file in constant_values:
        meta = constant_values[item_name_from_file]
        annotation = meta.get("annotation", "")
        value = meta.get("value", "")

        # Build the display string:  NAME: type = value
        parts = [f"<code>{item_name_from_file}</code>"]
        if annotation:
            parts.append(f'<code style="color: #6b7280;">: {annotation}</code>')
        if value:
            parts.append(f'<code style="color: #6b7280;"> = {value}</code>')
        replacement_html = "<p>" + "".join(parts) + "</p>"

        # Replace the original bare name paragraph
        bare_name_html = f"<p><code>{item_name_from_file}</code></p>"
        if bare_name_html in content_str:
            content_str = content_str.replace(bare_name_html, replacement_html, 1)

    return_value_pattern = (
        r'<span class="parameter-name"></span> <span class="parameter-annotation-sep">:</span>'
    )
    return_value_replacement = r'<span class="parameter-name"></span> <span class="parameter-annotation-sep" style="margin-left: -8px;"></span>'
    content_str = re.sub(return_value_pattern, return_value_replacement, content_str)

    # Remove empty annotation separator + annotation (e.g., Attributes with no type)
    # Pattern: ` <span class="parameter-annotation-sep">:</span> <span class="parameter-annotation"></span>`
    # This leaves just the parameter name without a trailing colon and space.
    content_str = re.sub(
        r' <span class="parameter-annotation-sep"[^>]*>:</span>\s*<span class="parameter-annotation"></span>',
        "",
        content_str,
    )

    # Normalize single quotes to double quotes in parameter default values
    content_str = re.sub(
        r'<span class="parameter-default">&#39;([^&]*)&#39;</span>',
        r'<span class="parameter-default">&quot;\1&quot;</span>',
        content_str,
    )
    content_str = re.sub(
        r"""<span class="parameter-default">'([^']*)'</span>""",
        r'<span class="parameter-default">"\1"</span>',
        content_str,
    )

    # Fix incomplete Attributes tables for dataclass pages
    content_str = fix_dataclass_attributes(content_str)

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

    # Inject decorator/descriptor badges into member-level headings (h3 tags)
    # Method headings are originally h2 in the renderer output, converted to h3 above.
    # These headings have data-anchor-id attributes like "pkg.Class.method"
    # We look up the member type in object_types to add classmethod/staticmethod/property badges.
    # Also style member headings in code font and append () for callable members.
    _MONO_FONT = "font-family: SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size: 1.1rem;"
    _CALLABLE_MEMBER_TYPES = {"method", "classmethod", "staticmethod", "function"}
    if object_types:
        _MEMBER_BADGE_TYPES = {"method", "classmethod", "staticmethod", "property"}
        for i, line in enumerate(content):
            anchor_match = re.search(r'<h3[^>]*data-anchor-id="([^"]+)"[^>]*>(.*?)</h3>', line)
            if anchor_match:
                anchor_id = anchor_match.group(1)
                h3_content = anchor_match.group(2)

                # Try to find a matching object_types key
                # The anchor_id is like "pkg.Class.method"; object_types keys are "Class.method"
                member_type = None
                for key, val in object_types.items():
                    if anchor_id.endswith(f".{key}") or anchor_id == key:
                        member_type = val
                        break

                # Build the new heading content: code font + parens + badge
                display_text = h3_content
                # Add () for callable members
                if member_type and member_type in _CALLABLE_MEMBER_TYPES:
                    _plain_member = re.sub(r"<[^>]+>", "", display_text).strip()
                    if not _plain_member.endswith("()"):
                        display_text += "()"

                badge_html = ""
                if member_type and member_type in _MEMBER_BADGE_TYPES:
                    badge_info = _TYPE_BADGE_STYLES.get(member_type)
                    if badge_info:
                        label_text, label_color, bg_color = badge_info
                        badge_html = (
                            f'<span style="font-size: 0.7rem; border-style: solid; '
                            f"border-width: 1px; border-color: {label_color}; "
                            f"background-color: {bg_color}; margin-left: 8px; "
                            f"padding: 1px 6px; vertical-align: 0.1rem; "
                            f'border-radius: 3px;">'
                            f'<code style="background-color: transparent; '
                            f'color: {label_color}; font-size: 0.7rem;">'
                            f"{label_text}</code></span>"
                        )

                new_heading = display_text + badge_html
                # Replace h3 content and add code font style
                content[i] = line.replace(h3_content + "</h3>", new_heading + "</h3>")
                # Add code font styling to the h3 tag
                content[i] = re.sub(
                    r"<h3([^>]*?)(?<!style=)>",
                    f'<h3\\1 style="{_MONO_FONT}">',
                    content[i],
                    count=1,
                )
    else:
        # Even without object_types, style member h3 headings in code font
        for i, line in enumerate(content):
            anchor_match = re.search(r'<h3[^>]*data-anchor-id="[^"]+"[^>]*>(.*?)</h3>', line)
            if anchor_match:
                content[i] = re.sub(
                    r"<h3([^>]*?)(?<!style=)>",
                    f'<h3\\1 style="{_MONO_FONT}">',
                    content[i],
                    count=1,
                )

    # Inject property badges into the Attributes table
    # Attributes table cells: <td><a href="#pkg.Class.attr">attr_name</a></td>
    if object_types:
        property_badge_info = _TYPE_BADGE_STYLES.get("property")
        if property_badge_info:
            p_label, p_color, p_bg = property_badge_info
            p_badge = (
                f'<span style="font-size: 0.65rem; border-style: solid; '
                f"border-width: 1px; border-color: {p_color}; "
                f"background-color: {p_bg}; margin-left: 6px; "
                f"padding: 0px 4px; vertical-align: 0.05rem; "
                f'border-radius: 3px;">'
                f'<code style="background-color: transparent; '
                f'color: {p_color}; font-size: 0.65rem;">'
                f"{p_label}</code></span>"
            )
            for i, line in enumerate(content):
                td_match = re.search(r'<td><a href="#([^"]+)">([^<]+)</a></td>', line)
                if td_match:
                    anchor_ref = td_match.group(1)
                    link_text = td_match.group(2)
                    # Check if this attribute is a property
                    for key, val in object_types.items():
                        if (
                            anchor_ref.endswith(f".{key}") or anchor_ref == key
                        ) and val == "property":
                            new_link = f"{link_text}</a>{p_badge}</td>"
                            content[i] = line.replace(f"{link_text}</a></td>", new_link)
                            break

    # Add separator lines between class details and individual members,
    # and between individual member sections.
    # - Thin solid line after the Methods/Attributes summary table (before first member section)
    # - Dotted line between each individual member section
    for i, line in enumerate(content):
        # Detect <section class="level2"> — these are individual member sections
        if "<section id=" in line and 'class="level2"' in line:
            # Check if the previous non-blank line ends a table (</table> in </section>)
            # or is another level2 section close
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

    # Merge See Also items from %seealso directives and doc-section blocks
    content_str = "".join(content)
    doc_section_seealso = extract_seealso_from_doc_section(content_str)
    if doc_section_seealso:
        content_str = remove_seealso_doc_section(content_str)
        # Merge with %seealso items (deduplicate, preserving order)
        seen = set(seealso_items)
        for item in doc_section_seealso:
            if item not in seen:
                seealso_items.append(item)
                seen.add(item)

    # Inject unified "See Also" section at the bottom
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

    # Shift all heading levels down by 1 within <main> content so that
    # reference page titles use <h2> instead of <h1>, differentiating them
    # from the top-level "Reference" heading on the index page.
    main_start = content_str.find("<main")
    main_end = content_str.find("</main>")
    if main_start != -1 and main_end != -1:
        before = content_str[:main_start]
        main_content = content_str[main_start : main_end + len("</main>")]
        after = content_str[main_end + len("</main>") :]

        # Shift in reverse order (h5→h6, h4→h5, ..., h1→h2) to avoid
        # double-shifting (e.g. h1→h2→h3).
        for level in range(5, 0, -1):
            main_content = main_content.replace(f"<h{level}", f"<h{level + 1}")
            main_content = main_content.replace(f"</h{level}>", f"</h{level + 1}>")
            main_content = re.sub(
                rf'\bclass="level{level}\b',
                f'class="level{level + 1}',
                main_content,
            )

        content_str = before + main_content + after

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

    # Clean up Sphinx cross-reference roles in index descriptions
    content = translate_sphinx_roles(content)

    # Shift section headings down by 1 within <main> so that category headings
    # (Classes, Methods, etc.) render as <h2>, visually subordinate to the
    # <h1> "Reference" page title.  Skip the page title itself (class="title").
    main_start = content.find("<main")
    main_end = content.find("</main>")
    if main_start != -1 and main_end != -1:
        before = content[:main_start]
        main_content = content[main_start : main_end + len("</main>")]
        after = content[main_end + len("</main>") :]

        # Protect the title heading from being shifted by replacing it with a
        # temporary placeholder, then shifting everything else, then restoring.
        title_pattern = re.compile(r'(<h1\s+class="title"[^>]*>.*?</h1>)', re.DOTALL)
        title_placeholder = "<!--TITLE_PLACEHOLDER-->"
        title_match = title_pattern.search(main_content)
        if title_match:
            saved_title = title_match.group(1)
            main_content = main_content.replace(saved_title, title_placeholder, 1)

        for level in range(5, 0, -1):
            main_content = main_content.replace(f"<h{level}", f"<h{level + 1}")
            main_content = main_content.replace(f"</h{level}>", f"</h{level + 1}>")
            main_content = re.sub(
                rf'\bclass="level{level}\b',
                f'class="level{level + 1}',
                main_content,
            )

        # Restore the title heading
        if title_match:
            main_content = main_content.replace(title_placeholder, saved_title, 1)

        content = before + main_content + after

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
    `_package_meta.json` (written by the build) and inserts a small badge
    span inside each `<span class="navbar-title">` element across all
    rendered HTML files.  When a `published_at` date is present the badge
    receives a `title` attribute so the release date appears as a native
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
