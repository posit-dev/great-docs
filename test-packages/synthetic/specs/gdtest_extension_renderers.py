"""Report reference with a custom class renderer"""

SPEC = {
    "name": "gdtest_extension_renderers",
    "description": "Guide readers to a factory function from a customised class page.",
    "dimensions": ["D1"],
    "pyproject_toml": {"project": {"name": "gdtest-extension-renderers", "version": "0.1.0"}},
    "config": {
        "api_reference_extension": "_api_reference_extension.py",
        "dynamic": False,
        "reference": [{"title": "Reports", "contents": ["Report", "read_report"]}],
    },
    "files": {
        "gdtest_extension_renderers/__init__.py": '''\
            """Reports containing whole-number amounts"""

            __all__ = ["Report", "read_report"]


            class Report:
                """
                A collection of whole-number amounts

                Parameters
                ----------
                amounts
                    The amounts recorded in the report.

                Notes
                -----
                Amounts can include negative adjustments.
                """

                def __init__(self, amounts: list[int]) -> None:
                    self._amounts = amounts.copy()

                def total(self) -> int:
                    """Sum the amounts in the report"""
                    return sum(self._amounts)


            def read_report(text: str) -> Report:
                """
                Read a report with one amount per line

                Parameters
                ----------
                text
                    Lines of text containing integer amounts.

                Returns
                -------
                The report containing the parsed amounts.
                """
                return Report([int(line) for line in text.splitlines()])
        ''',
        "docs/_api_reference_extension.py": """\
            from great_docs.extensions import Extension
            from great_docs.pandoc.blocks import BlockContent, Blocks, Para
            from great_docs.rendering import ClassRenderer, Renderers


            class ReportRenderer(ClassRenderer):
                def render_signature(self) -> BlockContent:
                    if self.context.authored_name == "Report":
                        return None
                    return super().render_signature()

                def render_docstring_body(self) -> BlockContent:
                    body = super().render_docstring_body()
                    if self.context.authored_name == "Report":
                        return Blocks([body, Para("Use read_report to open a report from text.")])
                    return body


            def setup(extension: Extension) -> None:
                extension.set_renderers(Renderers(classes=ReportRenderer))
        """,
        "README.md": (
            "# Report reader\n\n"
            "Open a report with [`read_report`](reference/read_report.html). "
            "See the [`Report` reference](reference/Report.html) for the methods you can call "
            "on the result.\n"
        ),
    },
    "expected": {
        "detected_name": "gdtest-extension-renderers",
        "detected_module": "gdtest_extension_renderers",
        "export_names": ["Report", "read_report"],
        "num_exports": 2,
        "hidden_signatures": ["Report"],
        "explicit_reference": True,
        "init_section_titles": ["Classes", "Functions"],
    },
}
