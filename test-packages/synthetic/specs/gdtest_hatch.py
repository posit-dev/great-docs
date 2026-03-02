"""
gdtest_hatch — Hatch build system with explicit wheel packages.

Dimensions: A5, B1, C4, D1, E6, F6, G1, H7
Focus: Uses [tool.hatch.build.targets.wheel.packages] to specify the
       package directory. Module name differs from project name.
       Tests _detect_module_name hatch code path.
"""

SPEC = {
    "name": "gdtest_hatch",
    "description": "Hatch build system with explicit wheel packages; clean is %nodoc and should not appear",
    "dimensions": ["A5", "B1", "C4", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-hatch",
            "version": "0.1.0",
            "description": "A synthetic test package using Hatch build system",
        },
        "build-system": {
            "requires": ["hatchling"],
            "build-backend": "hatchling.build",
        },
        "tool": {
            "hatch": {
                "build": {
                    "targets": {
                        "wheel": {
                            "packages": ["gdtest_hatch_pkg"],
                        },
                    },
                },
            },
        },
    },
    "files": {
        "gdtest_hatch_pkg/__init__.py": '''\
            """A test package using Hatch build system."""

            __version__ = "0.1.0"
            __all__ = ["Builder", "build", "clean"]


            class Builder:
                """
                A build manager.

                Parameters
                ----------
                output_dir
                    Directory for build output.
                """

                def __init__(self, output_dir: str = "dist"):
                    self.output_dir = output_dir

                def run(self) -> bool:
                    """
                    Execute the build.

                    Returns
                    -------
                    bool
                        True if build succeeded.
                    """
                    return True

                def clean(self) -> None:
                    """
                    Remove build artifacts.
                    """
                    pass


            def build(target: str = "wheel") -> str:
                """
                Build the project.

                Parameters
                ----------
                target
                    Build target (wheel, sdist).

                Returns
                -------
                str
                    Path to the built artifact.
                """
                return f"dist/pkg.{target}"


            def clean() -> None:
                """
                Clean all build artifacts.

                %nodoc
                """
                pass
        ''',
        "README.md": """\
            # gdtest-hatch

            A synthetic test package using the Hatch build system.
        """,
    },
    "expected": {
        "detected_name": "gdtest-hatch",
        "detected_module": "gdtest_hatch_pkg",
        "detected_parser": "numpy",
        "export_names": ["Builder", "build", "clean"],
        "num_exports": 3,
        "nodoc_items": ["clean"],
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
    },
}
