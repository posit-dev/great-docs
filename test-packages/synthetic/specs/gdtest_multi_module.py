"""
gdtest_multi_module — Package with multiple submodules re-exported.

Dimensions: A1, B8, C4, D1, E6, F6, G1, H7
Focus: Package with three submodules (models, views, controllers)
       that re-exports all their symbols via __init__.py.
"""

SPEC = {
    "name": "gdtest_multi_module",
    "description": "Multi-module package with re-exports",
    "dimensions": ["A1", "B8", "C4", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-multi-module",
            "version": "0.1.0",
            "description": "Test multi-module re-export package",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_multi_module/__init__.py": '''\
            """Package with multiple submodules."""

            __version__ = "0.1.0"

            from gdtest_multi_module.models import Model, create_model
            from gdtest_multi_module.views import View, render_view
            from gdtest_multi_module.controllers import Controller, dispatch

            __all__ = [
                "Model", "create_model",
                "View", "render_view",
                "Controller", "dispatch",
            ]
        ''',
        "gdtest_multi_module/models.py": '''\
            """Model definitions."""


            class Model:
                """
                A data model.

                Parameters
                ----------
                name
                    Model name.
                """

                def __init__(self, name: str):
                    self.name = name

                def save(self) -> bool:
                    """
                    Save the model.

                    Returns
                    -------
                    bool
                        True if saved.
                    """
                    return True


            def create_model(name: str) -> Model:
                """
                Create a new model.

                Parameters
                ----------
                name
                    Model name.

                Returns
                -------
                Model
                    New model instance.
                """
                return Model(name)
        ''',
        "gdtest_multi_module/views.py": '''\
            """View definitions."""


            class View:
                """
                A display view.

                Parameters
                ----------
                template
                    View template name.
                """

                def __init__(self, template: str):
                    self.template = template

                def render(self) -> str:
                    """
                    Render the view.

                    Returns
                    -------
                    str
                        Rendered HTML.
                    """
                    return f"<div>{self.template}</div>"


            def render_view(view: View) -> str:
                """
                Render a view and return its content.

                Parameters
                ----------
                view
                    View to render.

                Returns
                -------
                str
                    Rendered content.
                """
                return view.render()
        ''',
        "gdtest_multi_module/controllers.py": '''\
            """Controller definitions."""


            class Controller:
                """
                A request controller.

                Parameters
                ----------
                name
                    Controller name.
                """

                def __init__(self, name: str):
                    self.name = name

                def handle(self, request: dict) -> dict:
                    """
                    Handle a request.

                    Parameters
                    ----------
                    request
                        Request data.

                    Returns
                    -------
                    dict
                        Response data.
                    """
                    return {"status": "ok"}


            def dispatch(path: str) -> Controller:
                """
                Dispatch a request to the appropriate controller.

                Parameters
                ----------
                path
                    Request path.

                Returns
                -------
                Controller
                    Matched controller.
                """
                return Controller(path)
        ''',
        "README.md": """\
            # gdtest-multi-module

            Tests multi-module package with re-exports.
        """,
    },
    "expected": {
        "detected_name": "gdtest-multi-module",
        "detected_module": "gdtest_multi_module",
        "detected_parser": "numpy",
        "export_names": [
            "Model",
            "create_model",
            "View",
            "render_view",
            "Controller",
            "dispatch",
        ],
        "num_exports": 6,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
