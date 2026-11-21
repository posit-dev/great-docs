"""Pydantic model field descriptions"""

SPEC = {
    "name": "gdtest_pydantic_fields",
    "description": "Pydantic model field descriptions",
    "dimensions": ["A1", "B1", "C2", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-pydantic-fields",
            "version": "0.1.0",
            "description": "Field documentation for a Pydantic model",
            "dependencies": ["pydantic>=2"],
        },
        "build-system": {"requires": ["setuptools"], "build-backend": "setuptools.build_meta"},
    },
    "files": {
        "gdtest_pydantic_fields/__init__.py": '''\
            """An RGBA colour model"""

            from typing import Annotated

            from pydantic import BaseModel, Field

            __all__ = ["Colour"]


            class Colour(BaseModel):
                """An RGB colour with an alpha channel"""

                red: int = Field(description="Intensity of the red channel.")
                green: Annotated[int, "Intensity of the green channel."]
                blue: Annotated[int, Field(description="Intensity of the blue channel.")]
                alpha: int = 255
                """Opacity of the colour"""
        ''',
        "README.md": "# Pydantic field descriptions\n",
    },
    "expected": {
        "detected_name": "gdtest-pydantic-fields",
        "detected_module": "gdtest_pydantic_fields",
        "detected_parser": "numpy",
        "export_names": ["Colour"],
        "num_exports": 1,
        "section_titles": ["Classes"],
        "has_user_guide": False,
    },
}
