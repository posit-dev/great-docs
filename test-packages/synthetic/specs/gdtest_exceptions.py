"""
gdtest_exceptions — Custom exception hierarchy.

Dimensions: A1, B1, C23, D1, E6, F6, G1, H7
Focus: Exception classes inheriting from Exception to verify they
       render like normal classes in the documentation.
"""

SPEC = {
    "name": "gdtest_exceptions",
    "description": "Custom exception class hierarchy",
    "dimensions": ["A1", "B1", "C23", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-exceptions",
            "version": "0.1.0",
            "description": "Test exception class documentation",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_exceptions/__init__.py": '''\
            """Package with a custom exception hierarchy."""

            __version__ = "0.1.0"
            __all__ = [
                "AppError",
                "ValidationError",
                "NotFoundError",
                "PermissionError_",
                "TimeoutError_",
            ]


            class AppError(Exception):
                """
                Base exception for the application.

                Parameters
                ----------
                message
                    Human-readable error message.
                code
                    Machine-readable error code.
                """

                def __init__(self, message: str, code: int = 0):
                    super().__init__(message)
                    self.code = code


            class ValidationError(AppError):
                """
                Raised when input validation fails.

                Parameters
                ----------
                field
                    The field that failed validation.
                message
                    Description of the validation failure.
                """

                def __init__(self, field: str, message: str):
                    super().__init__(f"{field}: {message}", code=400)
                    self.field = field


            class NotFoundError(AppError):
                """
                Raised when a requested resource is not found.

                Parameters
                ----------
                resource
                    Name or ID of the missing resource.
                """

                def __init__(self, resource: str):
                    super().__init__(f"Not found: {resource}", code=404)
                    self.resource = resource


            class PermissionError_(AppError):
                """
                Raised when the user lacks permission.

                Parameters
                ----------
                action
                    The action that was denied.
                """

                def __init__(self, action: str):
                    super().__init__(f"Permission denied: {action}", code=403)
                    self.action = action


            class TimeoutError_(AppError):
                """
                Raised when an operation times out.

                Parameters
                ----------
                operation
                    The operation that timed out.
                seconds
                    Number of seconds before timeout.
                """

                def __init__(self, operation: str, seconds: float):
                    super().__init__(f"Timeout: {operation} after {seconds}s", code=408)
                    self.operation = operation
                    self.seconds = seconds
        ''',
        "README.md": """\
            # gdtest-exceptions

            Tests custom exception hierarchy documentation.
        """,
    },
    "expected": {
        "detected_name": "gdtest-exceptions",
        "detected_module": "gdtest_exceptions",
        "detected_parser": "numpy",
        "export_names": [
            "AppError",
            "ValidationError",
            "NotFoundError",
            "PermissionError_",
            "TimeoutError_",
        ],
        "num_exports": 5,
        "section_titles": ["Classes"],
        "has_user_guide": False,
        "coverage_exclude": ['nodoc', 'bigcl', 'ug', 'supp', 'hdg'],
},
}
