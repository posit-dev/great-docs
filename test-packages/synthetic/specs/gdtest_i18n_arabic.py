"""
gdtest_i18n_arabic — Tests i18n with Arabic (RTL script).

Dimensions: K52
Focus: site.language: ar — all UI widgets render Arabic translations and the
page layout is mirrored for right-to-left reading.
All docstrings, user guide, and metadata are in Arabic.
"""

SPEC = {
    "name": "gdtest_i18n_arabic",
    "description": (
        "i18n test with Arabic (RTL script). Docstrings, user guide, and "
        "metadata are written in Arabic for full native-language experience."
    ),
    "dimensions": ["K52"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-i18n-arabic",
            "version": "0.1.0",
            "description": "\u0623\u062f\u0648\u0627\u062a \u062a\u0646\u0633\u064a\u0642 \u0627\u0644\u0646\u0635\u0648\u0635 \u0648\u0627\u0644\u0642\u0648\u0627\u0644\u0628",
            "license": "MIT",
            "authors": [
                {
                    "name": "\u0623\u062d\u0645\u062f \u0645\u062d\u0645\u062f",
                    "email": "ahmed@example.sa",
                },
            ],
            "urls": {
                "Documentation": "https://gdtest-i18n-arabic.example.com",
                "Repository": "https://github.com/test-org/gdtest-i18n-arabic",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "site": {
            "language": "ar",
        },
        "announcement": "\u0645\u0631\u062d\u0628\u0627\u064b! \u0627\u0637\u0644\u0639 \u0639\u0644\u0649 \u062f\u0644\u064a\u0644 \u0627\u0644\u0628\u062f\u0621 \u0627\u0644\u0633\u0631\u064a\u0639 \u0627\u0644\u062c\u062f\u064a\u062f.",
        "github_url": "https://github.com/test-org/gdtest-i18n-arabic",
        "dark_mode_toggle": True,
        "back_to_top": True,
        "copy_code": True,
        "page_metadata": True,
        "funding": {
            "name": "\u0645\u0624\u0633\u0633\u0629 \u0627\u0644\u0628\u062d\u062b \u0627\u0644\u0639\u0644\u0645\u064a"
        },
    },
    "files": {
        "gdtest_i18n_arabic/__init__.py": '''\
            """\u0623\u062f\u0648\u0627\u062a \u062a\u0646\u0633\u064a\u0642 \u0627\u0644\u0646\u0635\u0648\u0635 \u0648\u0627\u0644\u0642\u0648\u0627\u0644\u0628."""

            __version__ = "0.1.0"
            __all__ = [
                "Formatter",
                "format_text",
                "parse_template",
                "escape_html",
            ]


            class Formatter:
                """
                \u062a\u0646\u0633\u064a\u0642 \u0627\u0644\u0646\u0635\u0648\u0635 \u0628\u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0627\u0644\u0642\u0648\u0627\u0644\u0628.

                \u064a\u062f\u0639\u0645 \u0627\u0633\u062a\u0628\u062f\u0627\u0644 \u0627\u0644\u0639\u0646\u0627\u0635\u0631 \u0627\u0644\u0646\u0627\u0626\u0628\u0629\u060c \u0648\u062a\u0631\u0645\u064a\u0632 HTML\u060c
                \u0648\u0641\u0648\u0627\u0635\u0644 \u0642\u0627\u0628\u0644\u0629 \u0644\u0644\u062a\u062e\u0635\u064a\u0635.

                Parameters
                ----------
                left_delim : str
                    \u0627\u0644\u0641\u0627\u0635\u0644 \u0627\u0644\u0623\u064a\u0633\u0631 \u0644\u0644\u0639\u0646\u0627\u0635\u0631 \u0627\u0644\u0646\u0627\u0626\u0628\u0629.
                right_delim : str
                    \u0627\u0644\u0641\u0627\u0635\u0644 \u0627\u0644\u0623\u064a\u0645\u0646 \u0644\u0644\u0639\u0646\u0627\u0635\u0631 \u0627\u0644\u0646\u0627\u0626\u0628\u0629.
                auto_escape : bool
                    \u062a\u0631\u0645\u064a\u0632 HTML \u062a\u0644\u0642\u0627\u0626\u064a\u0627\u064b \u0644\u0644\u0642\u064a\u0645 \u0627\u0644\u0645\u0633\u062a\u0628\u062f\u0644\u0629.

                See Also
                --------
                format_text
                    \u062a\u063a\u0644\u064a\u0641 \u0627\u0644\u0646\u0635 \u0628\u0639\u0631\u0636 \u0633\u0637\u0631 \u0645\u062d\u062f\u062f.
                escape_html
                    \u062a\u0631\u0645\u064a\u0632 \u0627\u0644\u0623\u062d\u0631\u0641 \u0627\u0644\u062e\u0627\u0635\u0629 \u0641\u064a HTML.

                Examples
                --------
                >>> fmt = Formatter(left_delim="{{", right_delim="}}")
                >>> fmt.render("\u0645\u0631\u062d\u0628\u0627\u064b {{name}}!", name="World")
                '\u0645\u0631\u062d\u0628\u0627\u064b World!'

                .. versionadded:: 0.1.0
                """

                def __init__(
                    self,
                    left_delim: str = "{{",
                    right_delim: str = "}}",
                    auto_escape: bool = True,
                ):
                    self.left_delim = left_delim
                    self.right_delim = right_delim
                    self.auto_escape = auto_escape

                def render(self, template: str, **kwargs: str) -> str:
                    """
                    \u0639\u0631\u0636 \u0627\u0644\u0642\u0627\u0644\u0628 \u0628\u0627\u0644\u0642\u064a\u0645 \u0627\u0644\u0645\u0639\u0637\u0627\u0629.

                    Parameters
                    ----------
                    template : str
                        \u0646\u0635 \u0627\u0644\u0642\u0627\u0644\u0628.
                    **kwargs : str
                        \u0627\u0644\u0642\u064a\u0645 \u0627\u0644\u0645\u0633\u0645\u0627\u0629 \u0644\u0644\u0627\u0633\u062a\u0628\u062f\u0627\u0644.

                    Returns
                    -------
                    str
                        \u0627\u0644\u0646\u0635 \u0627\u0644\u0645\u0639\u0631\u0648\u0636.
                    """
                    result = template
                    for key, value in kwargs.items():
                        placeholder = f"{self.left_delim}{key}{self.right_delim}"
                        result = result.replace(placeholder, str(value))
                    return result

                def list_placeholders(self, template: str) -> list[str]:
                    """
                    \u0627\u0633\u062a\u062e\u0631\u0627\u062c \u0623\u0633\u0645\u0627\u0621 \u0627\u0644\u0639\u0646\u0627\u0635\u0631 \u0627\u0644\u0646\u0627\u0626\u0628\u0629 \u0645\u0646 \u0627\u0644\u0642\u0627\u0644\u0628.

                    Parameters
                    ----------
                    template : str
                        \u0627\u0644\u0642\u0627\u0644\u0628 \u0627\u0644\u0645\u0631\u0627\u062f \u0641\u062d\u0635\u0647.

                    Returns
                    -------
                    list[str]
                        \u0642\u0627\u0626\u0645\u0629 \u0628\u0623\u0633\u0645\u0627\u0621 \u0627\u0644\u0639\u0646\u0627\u0635\u0631 \u0627\u0644\u0646\u0627\u0626\u0628\u0629 \u0627\u0644\u0645\u0648\u062c\u0648\u062f\u0629.
                    """
                    return []


            def format_text(text: str, width: int = 80) -> str:
                """
                \u062a\u063a\u0644\u064a\u0641 \u0627\u0644\u0646\u0635 \u0628\u0639\u0631\u0636 \u0633\u0637\u0631 \u0645\u062d\u062f\u062f.

                Parameters
                ----------
                text : str
                    \u0627\u0644\u0646\u0635 \u0627\u0644\u0645\u0631\u0627\u062f \u062a\u063a\u0644\u064a\u0641\u0647.
                width : int
                    \u0623\u0642\u0635\u0649 \u0639\u0631\u0636 \u0644\u0644\u0633\u0637\u0631.

                Returns
                -------
                str
                    \u0627\u0644\u0646\u0635 \u0627\u0644\u0645\u064f\u063a\u0644\u064e\u0651\u0641.

                See Also
                --------
                Formatter
                    \u062a\u0646\u0633\u064a\u0642 \u0627\u0644\u0646\u0635\u0648\u0635 \u0628\u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0627\u0644\u0642\u0648\u0627\u0644\u0628.
                parse_template
                    \u062a\u062d\u0644\u064a\u0644 \u0646\u0635 \u0627\u0644\u0642\u0627\u0644\u0628 \u0625\u0644\u0649 \u0645\u0643\u0648\u0646\u0627\u062a\u0647.

                .. versionchanged:: 0.1.0 \u0623\u0635\u0628\u062d \u0627\u0644\u0639\u0631\u0636 \u0627\u0644\u0627\u0641\u062a\u0631\u0627\u0636\u064a 80 \u062d\u0631\u0641\u0627\u064b.
                """
                return text


            def parse_template(source: str) -> dict:
                """
                \u062a\u062d\u0644\u064a\u0644 \u0646\u0635 \u0627\u0644\u0642\u0627\u0644\u0628 \u0625\u0644\u0649 \u0645\u0643\u0648\u0646\u0627\u062a\u0647.

                Parameters
                ----------
                source : str
                    \u0646\u0635 \u0627\u0644\u0642\u0627\u0644\u0628 \u0627\u0644\u062e\u0627\u0645.

                Returns
                -------
                dict
                    \u0627\u0644\u0642\u0627\u0644\u0628 \u0627\u0644\u0645\u062d\u0644\u0644 \u0645\u0639 \u0645\u0641\u0627\u062a\u064a\u062d 'text' \u0648 'placeholders'.
                """
                return {"text": source, "placeholders": []}


            def escape_html(value: str) -> str:
                """
                \u062a\u0631\u0645\u064a\u0632 \u0627\u0644\u0623\u062d\u0631\u0641 \u0627\u0644\u062e\u0627\u0635\u0629 \u0641\u064a HTML.

                Parameters
                ----------
                value : str
                    \u0627\u0644\u0646\u0635 \u0627\u0644\u0645\u0631\u0627\u062f \u062a\u0631\u0645\u064a\u0632\u0647.

                Returns
                -------
                str
                    \u0646\u0635 \u0622\u0645\u0646 \u0644\u0627\u0633\u062a\u062e\u062f\u0627\u0645\u0647 \u0641\u064a HTML.

                See Also
                --------
                Formatter
                    \u062a\u0646\u0633\u064a\u0642 \u0627\u0644\u0646\u0635\u0648\u0635 \u0628\u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0627\u0644\u0642\u0648\u0627\u0644\u0628.
                format_text
                    \u062a\u063a\u0644\u064a\u0641 \u0627\u0644\u0646\u0635 \u0628\u0639\u0631\u0636 \u0633\u0637\u0631 \u0645\u062d\u062f\u062f.

                .. deprecated:: 0.1.0
                    \u0627\u0633\u062a\u062e\u062f\u0645 Formatter(auto_escape=True) \u0628\u062f\u0644\u0627\u064b \u0645\u0646 \u0630\u0644\u0643.
                """
                return (
                    value
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
        ''',
        "user_guide/01-overview.qmd": """\
            ---
            title: "\u0646\u0638\u0631\u0629 \u0639\u0627\u0645\u0629"
            guide-section: "\u0627\u0644\u0623\u0633\u0627\u0633\u064a\u0627\u062a"
            ---

            # \u0646\u0638\u0631\u0629 \u0639\u0627\u0645\u0629

            \u064a\u0648\u0641\u0631 \u0647\u0630\u0627 \u0627\u0644\u062d\u0632\u0645\u0629 \u0623\u062f\u0648\u0627\u062a \u0644\u062a\u0646\u0633\u064a\u0642 \u0627\u0644\u0646\u0635\u0648\u0635 \u0645\u0639 \u062f\u0639\u0645
            \u0627\u0644\u0642\u0648\u0627\u0644\u0628 \u0648\u062a\u0631\u0645\u064a\u0632 HTML.

            ## \u0627\u0644\u062a\u062b\u0628\u064a\u062a

            ```bash
            pip install gdtest-i18n-arabic
            ```

            ## \u0645\u062b\u0627\u0644 \u0633\u0631\u064a\u0639

            ```python
            from gdtest_i18n_arabic import Formatter

            fmt = Formatter()
            result = fmt.render("\u0645\u0631\u062d\u0628\u0627\u064b {{name}}!", name="World")
            print(result)
            ```
        """,
        "user_guide/02-templates.qmd": """\
            ---
            title: "\u0627\u0644\u0642\u0648\u0627\u0644\u0628"
            guide-section: "\u0627\u0644\u0623\u0633\u0627\u0633\u064a\u0627\u062a"
            ---

            # \u0627\u0644\u0642\u0648\u0627\u0644\u0628

            \u062a\u0639\u0644\u0645 \u0643\u064a\u0641\u064a\u0629 \u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0646\u0635\u0648\u0635 \u0627\u0644\u0642\u0648\u0627\u0644\u0628 \u0645\u0639 \u0627\u0644\u0639\u0646\u0627\u0635\u0631 \u0627\u0644\u0646\u0627\u0626\u0628\u0629.

            ## \u0635\u064a\u063a\u0629 \u0627\u0644\u0639\u0646\u0627\u0635\u0631 \u0627\u0644\u0646\u0627\u0626\u0628\u0629

            ```python
            from gdtest_i18n_arabic import parse_template

            result = parse_template("\u0645\u0631\u062d\u0628\u0627\u064b {{name}}\u060c \u0623\u0647\u0644\u0627\u064b \u0628\u0643 \u0641\u064a {{place}}!")
            print(result["placeholders"])
            ```

            ## \u062a\u0631\u0645\u064a\u0632 HTML

            ```python
            from gdtest_i18n_arabic import escape_html

            safe = escape_html("<script>alert('test')</script>")
            print(safe)
            ```
        """,
        "user_guide/03-table-explorer.qmd": """\
            ---
            title: "\u0645\u0633\u062a\u0643\u0634\u0641 \u0627\u0644\u062c\u062f\u0648\u0644"
            guide-section: "\u0627\u0644\u0623\u0633\u0627\u0633\u064a\u0627\u062a"
            ---

            # \u0645\u0633\u062a\u0643\u0634\u0641 \u0627\u0644\u062c\u062f\u0648\u0644

            \u0627\u0633\u062a\u062e\u062f\u0645 `tbl_explorer()` \u0644\u0627\u0633\u062a\u0643\u0634\u0627\u0641 \u0628\u064a\u0627\u0646\u0627\u062a\u0643 \u0628\u0634\u0643\u0644 \u062a\u0641\u0627\u0639\u0644\u064a.

            ```{python}
            #| echo: false
            import tempfile
            from great_docs import tbl_explorer
            rows = "\u0627\u0644\u0627\u0633\u0645,\u0627\u0644\u0639\u0645\u0631,\u0627\u0644\u0645\u062f\u064a\u0646\u0629,\u0627\u0644\u062f\u0631\u062c\u0629\\n\u0623\u062d\u0645\u062f,28,\u0627\u0644\u0642\u0627\u0647\u0631\u0629,92.5\\n\u0641\u0627\u0637\u0645\u0629,35,\u0627\u0644\u0631\u064a\u0627\u0636,87.3\\n\u062e\u0627\u0644\u062f,22,\u062f\u0628\u064a,95.1\\n\u0646\u0648\u0631,41,\u0628\u064a\u0631\u0648\u062a,78.6\\n\u0633\u0627\u0631\u0629,30,\u0627\u0644\u062f\u0627\u0631 \u0627\u0644\u0628\u064a\u0636\u0627\u0621,88.9\\n\u0639\u0645\u0631,27,\u062a\u0648\u0646\u0633,91.2\\n\u0644\u064a\u0644\u0649,33,\u0639\u0645\u0627\u0646,84.7"
            tf = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
            tf.write(rows)
            tf.close()
            tbl_explorer(tf.name)
            ```
        """,
        "README.md": """\
            # gdtest-i18n-arabic

            \u0623\u062f\u0648\u0627\u062a \u062a\u0646\u0633\u064a\u0642 \u0627\u0644\u0646\u0635\u0648\u0635 \u0648\u0627\u0644\u0642\u0648\u0627\u0644\u0628.

            ## \u0627\u0644\u0645\u064a\u0632\u0627\u062a

            - \u0627\u0633\u062a\u0628\u062f\u0627\u0644 \u0627\u0644\u0639\u0646\u0627\u0635\u0631 \u0627\u0644\u0646\u0627\u0626\u0628\u0629 \u0641\u064a \u0627\u0644\u0642\u0648\u0627\u0644\u0628
            - \u062a\u0631\u0645\u064a\u0632 \u0623\u062d\u0631\u0641 HTML \u0627\u0644\u062e\u0627\u0635\u0629
            - \u0641\u0648\u0627\u0635\u0644 \u0642\u0627\u0628\u0644\u0629 \u0644\u0644\u062a\u062e\u0635\u064a\u0635

            ## \u0627\u0644\u062a\u0631\u062e\u064a\u0635

            MIT
        """,
    },
    "expected": {
        "detected_name": "gdtest-i18n-arabic",
        "detected_module": "gdtest_i18n_arabic",
        "detected_parser": "numpy",
        "export_names": [
            "Formatter",
            "escape_html",
            "format_text",
            "parse_template",
        ],
        "num_exports": 4,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": True,
        "user_guide_files": [
            "01-overview.qmd",
            "02-templates.qmd",
            "03-table-explorer.qmd",
        ],
    },
}
