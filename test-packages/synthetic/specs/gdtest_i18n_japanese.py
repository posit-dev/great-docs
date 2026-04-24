"""
gdtest_i18n_japanese — Tests i18n with Japanese (CJK script).

Dimensions: K51
Focus: site.language: ja — all UI widgets render Japanese translations.
All docstrings, user guide, and metadata are in Japanese.
"""

SPEC = {
    "name": "gdtest_i18n_japanese",
    "description": (
        "i18n test with Japanese (CJK script). Docstrings, user guide, and "
        "metadata are written in Japanese for full native-language experience."
    ),
    "dimensions": ["K51"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-i18n-japanese",
            "version": "0.1.0",
            "description": "\u79d1\u5b66\u8a08\u7b97\u306e\u305f\u3081\u306e\u96fb\u5353\u30e6\u30fc\u30c6\u30a3\u30ea\u30c6\u30a3",
            "license": "MIT",
            "authors": [
                {"name": "\u7530\u4e2d\u592a\u90ce", "email": "tanaka@example.jp"},
            ],
            "urls": {
                "Documentation": "https://gdtest-i18n-japanese.example.com",
                "Repository": "https://github.com/test-org/gdtest-i18n-japanese",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "site": {
            "language": "ja",
        },
        "announcement": "\u3088\u3046\u3053\u305d\uff01\u65b0\u3057\u3044\u30af\u30a4\u30c3\u30af\u30b9\u30bf\u30fc\u30c8\u30ac\u30a4\u30c9\u3092\u3054\u89a7\u304f\u3060\u3055\u3044\u3002",
        "github_url": "https://github.com/test-org/gdtest-i18n-japanese",
        "dark_mode_toggle": True,
        "back_to_top": True,
        "copy_code": True,
        "page_metadata": True,
        "funding": {"name": "\u79d1\u5b66\u6280\u8853\u632f\u8208\u8ca1\u56e3"},
    },
    "files": {
        "gdtest_i18n_japanese/__init__.py": '''\
            """\u79d1\u5b66\u8a08\u7b97\u306e\u305f\u3081\u306e\u96fb\u5353\u30e6\u30fc\u30c6\u30a3\u30ea\u30c6\u30a3\u3002"""

            __version__ = "0.1.0"
            __all__ = [
                "Calculator",
                "add",
                "multiply",
                "divide",
            ]


            class Calculator:
                """
                \u30e1\u30e2\u30ea\u6a5f\u80fd\u4ed8\u304d\u306e\u96fb\u5353\u3002

                \u57fa\u672c\u7684\u306a\u56db\u5247\u6f14\u7b97\u3092\u30b5\u30dd\u30fc\u30c8\u3057\u3001\u7d2f\u8a08\u5024\u3092
                \u4fdd\u6301\u3057\u307e\u3059\u3002\u30ea\u30bb\u30c3\u30c8\u3082\u53ef\u80fd\u3067\u3059\u3002

                Parameters
                ----------
                precision : int
                    \u7d50\u679c\u306e\u5c0f\u6570\u70b9\u4ee5\u4e0b\u306e\u6841\u6570\u3002

                See Also
                --------
                add
                    \u4e8c\u3064\u306e\u6570\u5024\u3092\u52a0\u7b97\u3059\u308b\u3002
                multiply
                    \u4e8c\u3064\u306e\u6570\u5024\u3092\u4e57\u7b97\u3059\u308b\u3002

                Examples
                --------
                >>> calc = Calculator(precision=2)
                >>> calc.add_to_total(3.14159)
                3.14

                .. versionadded:: 0.1.0
                """

                def __init__(self, precision: int = 2):
                    self.precision = precision
                    self._total = 0.0

                def add_to_total(self, value: float) -> float:
                    """
                    \u7d2f\u8a08\u306b\u5024\u3092\u52a0\u7b97\u3059\u308b\u3002

                    Parameters
                    ----------
                    value : float
                        \u52a0\u7b97\u3059\u308b\u5024\u3002

                    Returns
                    -------
                    float
                        \u8a2d\u5b9a\u3055\u308c\u305f\u7cbe\u5ea6\u3067\u4e38\u3081\u3089\u308c\u305f\u66f4\u65b0\u5f8c\u306e\u7d2f\u8a08\u3002
                    """
                    self._total += value
                    return round(self._total, self.precision)

                def reset(self) -> None:
                    """
                    \u7d2f\u8a08\u3092\u30bc\u30ed\u306b\u30ea\u30bb\u30c3\u30c8\u3059\u308b\u3002
                    """
                    self._total = 0.0

                def get_total(self) -> float:
                    """
                    \u73fe\u5728\u306e\u7d2f\u8a08\u3092\u8fd4\u3059\u3002

                    Returns
                    -------
                    float
                        \u73fe\u5728\u306e\u7d2f\u8a08\u5024\u3002
                    """
                    return round(self._total, self.precision)


            def add(a: float, b: float) -> float:
                """
                \u4e8c\u3064\u306e\u6570\u5024\u3092\u52a0\u7b97\u3059\u308b\u3002

                Parameters
                ----------
                a : float
                    \u7b2c\u4e00\u30aa\u30da\u30e9\u30f3\u30c9\u3002
                b : float
                    \u7b2c\u4e8c\u30aa\u30da\u30e9\u30f3\u30c9\u3002

                Returns
                -------
                float
                    a \u3068 b \u306e\u548c\u3002

                See Also
                --------
                multiply
                    \u4e8c\u3064\u306e\u6570\u5024\u3092\u4e57\u7b97\u3059\u308b\u3002
                divide
                    \u4e8c\u3064\u306e\u6570\u5024\u3092\u9664\u7b97\u3059\u308b\u3002
                Calculator
                    \u30e1\u30e2\u30ea\u6a5f\u80fd\u4ed8\u304d\u306e\u96fb\u5353\u3002

                .. versionchanged:: 0.1.0 \u623b\u308a\u5024\u306e\u578b\u304c int \u304b\u3089 float \u306b\u5909\u66f4\u3055\u308c\u307e\u3057\u305f\u3002
                """
                return a + b


            def multiply(a: float, b: float) -> float:
                """
                \u4e8c\u3064\u306e\u6570\u5024\u3092\u4e57\u7b97\u3059\u308b\u3002

                Parameters
                ----------
                a : float
                    \u7b2c\u4e00\u30aa\u30da\u30e9\u30f3\u30c9\u3002
                b : float
                    \u7b2c\u4e8c\u30aa\u30da\u30e9\u30f3\u30c9\u3002

                Returns
                -------
                float
                    a \u3068 b \u306e\u7a4d\u3002

                See Also
                --------
                add
                    \u4e8c\u3064\u306e\u6570\u5024\u3092\u52a0\u7b97\u3059\u308b\u3002
                divide
                    \u4e8c\u3064\u306e\u6570\u5024\u3092\u9664\u7b97\u3059\u308b\u3002
                """
                return a * b


            def divide(a: float, b: float) -> float:
                """
                \u4e8c\u3064\u306e\u6570\u5024\u3092\u9664\u7b97\u3059\u308b\u3002

                Parameters
                ----------
                a : float
                    \u88ab\u9664\u6570\u3002
                b : float
                    \u9664\u6570\u3002\u30bc\u30ed\u306f\u4e0d\u53ef\u3002

                Returns
                -------
                float
                    a \u3092 b \u3067\u5272\u3063\u305f\u5546\u3002

                Raises
                ------
                ZeroDivisionError
                    b \u304c\u30bc\u30ed\u306e\u5834\u5408\u3002

                .. deprecated:: 0.1.0
                    Calculator.divide() \u30e1\u30bd\u30c3\u30c9\u3092\u4f7f\u7528\u3057\u3066\u304f\u3060\u3055\u3044\u3002
                """
                return a / b
        ''',
        "user_guide/01-quickstart.qmd": """\
            ---
            title: "\u30af\u30a4\u30c3\u30af\u30b9\u30bf\u30fc\u30c8"
            guide-section: "\u306f\u3058\u3081\u306b"
            ---

            # \u30af\u30a4\u30c3\u30af\u30b9\u30bf\u30fc\u30c8

            \u96fb\u5353\u30d1\u30c3\u30b1\u30fc\u30b8\u306e\u57fa\u672c\u7684\u306a\u4f7f\u3044\u65b9\u3092\u7d39\u4ecb\u3057\u307e\u3059\u3002

            ## \u30a4\u30f3\u30b9\u30c8\u30fc\u30eb

            pip \u3067\u30a4\u30f3\u30b9\u30c8\u30fc\u30eb\u3057\u307e\u3059\uff1a

            ```bash
            pip install gdtest-i18n-japanese
            ```

            ## \u57fa\u672c\u7684\u306a\u4f7f\u3044\u65b9

            ```python
            from gdtest_i18n_japanese import Calculator

            calc = Calculator(precision=3)
            calc.add_to_total(10.5)
            calc.add_to_total(20.3)
            print(calc.get_total())  # 30.8
            ```
        """,
        "user_guide/02-functions.qmd": """\
            ---
            title: "\u95a2\u6570\u30ea\u30d5\u30a1\u30ec\u30f3\u30b9"
            guide-section: "\u306f\u3058\u3081\u306b"
            ---

            # \u95a2\u6570\u30ea\u30d5\u30a1\u30ec\u30f3\u30b9

            \u500b\u5225\u306e\u7b97\u8853\u95a2\u6570\u3092\u4f7f\u3063\u305f\u7c21\u5358\u306a\u8a08\u7b97\u65b9\u6cd5\u3092\u7d39\u4ecb\u3057\u307e\u3059\u3002

            ```python
            from gdtest_i18n_japanese import add, multiply, divide

            result = add(10, 20)
            product = multiply(3, 7)
            quotient = divide(100, 4)
            ```

            ## \u5229\u7528\u53ef\u80fd\u306a\u95a2\u6570

            | \u95a2\u6570       | \u8aac\u660e               |
            |------------|------------------------|
            | `add`      | \u4e8c\u3064\u306e\u6570\u5024\u3092\u52a0\u7b97   |
            | `multiply` | \u4e8c\u3064\u306e\u6570\u5024\u3092\u4e57\u7b97   |
            | `divide`   | \u4e8c\u3064\u306e\u6570\u5024\u3092\u9664\u7b97   |
        """,
        "user_guide/03-table-explorer.qmd": """\
            ---
            title: "\u30c6\u30fc\u30d6\u30eb\u30a8\u30af\u30b9\u30d7\u30ed\u30fc\u30e9\u30fc"
            guide-section: "\u306f\u3058\u3081\u306b"
            ---

            # \u30c6\u30fc\u30d6\u30eb\u30a8\u30af\u30b9\u30d7\u30ed\u30fc\u30e9\u30fc

            `tbl_explorer()` \u3092\u4f7f\u3063\u3066\u30c7\u30fc\u30bf\u3092\u30a4\u30f3\u30bf\u30e9\u30af\u30c6\u30a3\u30d6\u306b\u63a2\u7d22\u3067\u304d\u307e\u3059\u3002

            ```{python}
            #| echo: false
            import tempfile
            from great_docs import tbl_explorer
            rows = "\u540d\u524d,\u5e74\u9f62,\u90fd\u5e02,\u5f97\u70b9\\n\u592a\u90ce,28,\u6771\u4eac,92.5\\n\u82b1\u5b50,35,\u5927\u962a,87.3\\n\u6b21\u90ce,22,\u4eac\u90fd,95.1\\n\u7f8e\u6708,41,\u6a2a\u6d5c,78.6\\n\u5065,30,\u798f\u5ca1,88.9\\n\u3055\u304f\u3089,27,\u540d\u53e4\u5c4b,91.2\\n\u8aa0,33,\u672d\u5e4c,84.7"
            tf = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
            tf.write(rows)
            tf.close()
            tbl_explorer(tf.name)
            ```
        """,
        "README.md": """\
            # gdtest-i18n-japanese

            \u79d1\u5b66\u8a08\u7b97\u306e\u305f\u3081\u306e\u96fb\u5353\u30e6\u30fc\u30c6\u30a3\u30ea\u30c6\u30a3\u3002

            ## \u6a5f\u80fd

            - \u30e1\u30e2\u30ea\u6a5f\u80fd\u4ed8\u304d\u96fb\u5353\u30af\u30e9\u30b9
            - \u57fa\u672c\u7684\u306a\u56db\u5247\u6f14\u7b97\u95a2\u6570
            - \u7cbe\u5ea6\u8a2d\u5b9a\u304c\u53ef\u80fd

            ## \u30e9\u30a4\u30bb\u30f3\u30b9

            MIT
        """,
    },
    "expected": {
        "detected_name": "gdtest-i18n-japanese",
        "detected_module": "gdtest_i18n_japanese",
        "detected_parser": "numpy",
        "export_names": ["Calculator", "add", "divide", "multiply"],
        "num_exports": 4,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": True,
        "user_guide_files": [
            "01-quickstart.qmd",
            "02-functions.qmd",
            "03-table-explorer.qmd",
        ],
    },
}
