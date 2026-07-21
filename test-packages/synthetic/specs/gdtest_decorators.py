"""
gdtest_decorators — Module of decorator functions.

Dimensions: A1, B1, C22, D1, E6, F6, G1, H7
Focus: Functions that return decorators (higher-order functions).
       Tests that decorator signatures render correctly.
"""

SPEC = {
    "name": "gdtest_decorators",
    "description": "Decorator functions",
    "dimensions": ["A1", "B1", "C22", "D1", "E6", "F6", "G1", "H7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-decorators",
            "version": "0.1.0",
            "description": "Test decorator function documentation",
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "files": {
        "gdtest_decorators/__init__.py": '''\
            """Package with decorator functions."""

            import functools
            from typing import Callable, Any

            __version__ = "0.1.0"
            __all__ = ["retry", "cache", "validate_args", "log_calls"]


            def retry(max_retries: int = 3, delay: float = 1.0) -> Callable:
                """
                Decorator that retries a function on failure.

                Parameters
                ----------
                max_retries
                    Maximum number of retries.
                delay
                    Delay between retries in seconds.

                Returns
                -------
                Callable
                    Decorator function.
                """
                def decorator(func):
                    @functools.wraps(func)
                    def wrapper(*args, **kwargs):
                        for i in range(max_retries):
                            try:
                                return func(*args, **kwargs)
                            except Exception:
                                if i == max_retries - 1:
                                    raise
                    return wrapper
                return decorator


            def cache(ttl: int = 300) -> Callable:
                """
                Decorator that caches function results.

                Parameters
                ----------
                ttl
                    Time-to-live in seconds.

                Returns
                -------
                Callable
                    Decorator function.
                """
                def decorator(func):
                    _cache: dict = {}

                    @functools.wraps(func)
                    def wrapper(*args, **kwargs):
                        key = (args, tuple(sorted(kwargs.items())))
                        if key in _cache:
                            return _cache[key]
                        result = func(*args, **kwargs)
                        _cache[key] = result
                        return result
                    return wrapper
                return decorator


            def validate_args(*types) -> Callable:
                """
                Decorator that validates argument types.

                Parameters
                ----------
                *types
                    Expected types for each positional argument.

                Returns
                -------
                Callable
                    Decorator function.
                """
                def decorator(func):
                    @functools.wraps(func)
                    def wrapper(*args, **kwargs):
                        for arg, expected in zip(args, types):
                            if not isinstance(arg, expected):
                                raise TypeError(
                                    f"Expected {expected.__name__}, got {type(arg).__name__}"
                                )
                        return func(*args, **kwargs)
                    return wrapper
                return decorator


            def log_calls(func: Callable) -> Callable:
                """
                Decorator that logs function calls.

                Parameters
                ----------
                func
                    The function to wrap.

                Returns
                -------
                Callable
                    Wrapped function with logging.
                """
                @functools.wraps(func)
                def wrapper(*args, **kwargs):
                    print(f"Calling {func.__name__}")
                    result = func(*args, **kwargs)
                    print(f"{func.__name__} returned {result}")
                    return result
                return wrapper
        ''',
        "README.md": """\
            # gdtest-decorators

            Tests documentation of decorator functions.
        """,
    },
    "expected": {
        "detected_name": "gdtest-decorators",
        "detected_module": "gdtest_decorators",
        "detected_parser": "numpy",
        "export_names": ["retry", "cache", "validate_args", "log_calls"],
        "num_exports": 4,
        "section_titles": ["Functions"],
        "has_user_guide": False,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
