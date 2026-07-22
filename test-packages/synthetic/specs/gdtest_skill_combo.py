"""
gdtest_skill_combo — Tests skill + user guide + hero + GitHub URL + extras.

Dimensions: S6
Focus: Cross-feature integration. Curated skill combined with a user guide,
       hero section, GitHub repo URL, and a site_url. Verifies Skills page
       renders install tabs correctly (GitHub tab uses repo URL), sidebar
       ordering (Skills above llms.txt), and coexistence with other features.
"""

SPEC = {
    "name": "gdtest_skill_combo",
    "description": "Tests skill + user guide + hero + GitHub URL + extras",
    "dimensions": ["S6"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-skill-combo",
            "version": "2.0.0",
            "description": "A full-featured package combining skills with user guides and hero sections",
            "license": "MIT",
            "requires-python": ">=3.10",
            "urls": {
                "Homepage": "https://example.com/gdtest-skill-combo",
                "Repository": "https://github.com/test-org/gdtest-skill-combo",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "site_url": "https://example.com/gdtest-skill-combo",
        "hero": {
            "title": "gdtest-skill-combo",
            "description": "The everything-included test package",
            "install_command": "pip install gdtest-skill-combo",
        },
        "skill": {
            "gotchas": [
                "The `Router` is not thread-safe — create one per thread or use `AsyncRouter`.",
                "Middleware runs in LIFO order (last added runs first).",
            ],
            "best_practices": [
                "Use dependency injection via `Router(deps={...})` for testability.",
                "Keep middleware functions pure — avoid side effects.",
            ],
            "decision_table": [
                {
                    "if": "Building a simple API",
                    "then": "router = Router(); router.get('/path', handler)",
                },
                {
                    "if": "Need async handlers",
                    "then": "router = AsyncRouter()",
                },
                {
                    "if": "Adding auth",
                    "then": "router.use(auth_middleware)",
                },
                {
                    "if": "Serving static files",
                    "then": "router.static('/public', './static')",
                },
            ],
        },
    },
    "files": {
        "gdtest_skill_combo/__init__.py": '''\
            """A lightweight API router toolkit."""

            __version__ = "2.0.0"
            __all__ = [
                "Router",
                "AsyncRouter",
                "Request",
                "Response",
                "Middleware",
                "route",
            ]


            class Router:
                """
                A synchronous HTTP router.

                Parameters
                ----------
                prefix
                    URL prefix for all routes.
                deps
                    Dependency injection mapping.
                """

                def __init__(self, prefix: str = "", deps: dict | None = None):
                    self.prefix = prefix
                    self.deps = deps or {}
                    self._routes: list = []
                    self._middleware: list = []

                def get(self, path: str, handler=None):
                    """
                    Register a GET route.

                    Parameters
                    ----------
                    path
                        URL path pattern.
                    handler
                        Request handler callable.
                    """
                    self._routes.append(("GET", path, handler))

                def post(self, path: str, handler=None):
                    """
                    Register a POST route.

                    Parameters
                    ----------
                    path
                        URL path pattern.
                    handler
                        Request handler callable.
                    """
                    self._routes.append(("POST", path, handler))

                def use(self, middleware) -> None:
                    """
                    Add middleware to the router.

                    Parameters
                    ----------
                    middleware
                        Middleware callable.
                    """
                    self._middleware.append(middleware)

                def static(self, url_path: str, dir_path: str) -> None:
                    """
                    Serve static files.

                    Parameters
                    ----------
                    url_path
                        URL prefix for static files.
                    dir_path
                        Local directory path.
                    """
                    pass


            class AsyncRouter(Router):
                """
                An asynchronous HTTP router.

                Inherits from :class:`Router` but supports async handlers.

                Parameters
                ----------
                prefix
                    URL prefix for all routes.
                deps
                    Dependency injection mapping.
                """

                pass


            class Request:
                """
                An incoming HTTP request.

                Parameters
                ----------
                method
                    HTTP method (GET, POST, etc.).
                path
                    Request path.
                headers
                    Request headers.
                body
                    Request body.
                """

                def __init__(
                    self,
                    method: str = "GET",
                    path: str = "/",
                    headers: dict | None = None,
                    body: str = "",
                ):
                    self.method = method
                    self.path = path
                    self.headers = headers or {}
                    self.body = body


            class Response:
                """
                An HTTP response.

                Parameters
                ----------
                status
                    HTTP status code.
                body
                    Response body.
                headers
                    Response headers.
                """

                def __init__(
                    self,
                    status: int = 200,
                    body: str = "",
                    headers: dict | None = None,
                ):
                    self.status = status
                    self.body = body
                    self.headers = headers or {}


            class Middleware:
                """
                Base class for middleware.

                Parameters
                ----------
                name
                    Middleware identifier.
                """

                def __init__(self, name: str = ""):
                    self.name = name

                def __call__(self, request: Request, next_handler=None) -> Response:
                    """
                    Process a request.

                    Parameters
                    ----------
                    request
                        Incoming request.
                    next_handler
                        Next handler in the chain.

                    Returns
                    -------
                    Response
                        The response.
                    """
                    if next_handler:
                        return next_handler(request)
                    return Response()


            def route(method: str, path: str):
                """
                Decorator to register a route handler.

                Parameters
                ----------
                method
                    HTTP method.
                path
                    URL path pattern.

                Returns
                -------
                callable
                    Decorated handler function.
                """
                def decorator(fn):
                    fn._route = (method, path)
                    return fn
                return decorator
        ''',
        # Curated skill
        "skills/gdtest-skill-combo/SKILL.md": """\
            ---
            name: gdtest-skill-combo
            description: >
              Build and serve HTTP APIs with gdtest-skill-combo. Supports
              sync and async routing, middleware, dependency injection,
              and static file serving.
            license: MIT
            compatibility: Requires Python >=3.10.
            metadata:
              author: gdg-test-suite
              version: "2.0"
            ---

            # gdtest-skill-combo

            A lightweight, composable API router toolkit.

            ## Quick start

            ```python
            from gdtest_skill_combo import Router, route

            app = Router(prefix="/api/v1")

            @route("GET", "/users")
            def list_users(req):
                return Response(body='[{"name": "Alice"}]')

            app.get("/users", list_users)
            ```

            ## When to use what

            | Need | Use |
            |------|-----|
            | Simple sync API | `Router()` |
            | Async handlers | `AsyncRouter()` |
            | Add middleware | `router.use(fn)` |
            | Serve static files | `router.static(url, dir)` |
            | Decorate handlers | `@route("GET", "/path")` |
            | Inject dependencies | `Router(deps={"db": db})` |

            ## Middleware

            Middleware functions wrap request processing. They run in
            **LIFO order** (last added runs first):

            ```python
            def logging_middleware(req, next_handler):
                print(f"{req.method} {req.path}")
                return next_handler(req)

            router.use(logging_middleware)
            ```

            ## Capabilities and boundaries

            **What agents can configure:**

            - Create routers with route registration
            - Add middleware and dependency injection
            - Serve static files
            - Use async handlers for concurrent processing

            **Requires human setup:**

            - Deploying behind a production ASGI/WSGI server
            - TLS certificate configuration
            - Database connection setup

            ## Resources

            - [llms.txt](llms.txt) — Indexed API reference for LLMs
            - [llms-full.txt](llms-full.txt) — Full documentation for LLMs
        """,
        # User guide
        "user_guide/01-getting-started.qmd": """\
            ---
            title: Getting Started
            ---

            ## Installation

            Install gdtest-skill-combo from PyPI:

            ```bash
            pip install gdtest-skill-combo
            ```

            ## Your first router

            Create a router and register a handler:

            ```python
            from gdtest_skill_combo import Router

            app = Router()
            app.get("/hello", lambda req: Response(body="Hello!"))
            ```

            ## Adding middleware

            Middleware wraps every request:

            ```python
            def timer(req, next_handler):
                import time
                start = time.time()
                resp = next_handler(req)
                print(f"Took {time.time() - start:.3f}s")
                return resp

            app.use(timer)
            ```
        """,
        "README.md": """\
            # gdtest-skill-combo

            A full-featured package combining skills with user guides and hero.

            ## Installation

            ```bash
            pip install gdtest-skill-combo
            ```
        """,
    },
    "expected": {
        "detected_name": "gdtest-skill-combo",
        "detected_module": "gdtest_skill_combo",
        "detected_parser": "numpy",
        "export_names": [
            "Router",
            "AsyncRouter",
            "Request",
            "Response",
            "Middleware",
            "route",
        ],
        "num_exports": 6,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": True,
        "has_skill_md": True,
        "has_skills_page": True,
        "skill_is_curated": True,
        "skill_has_gotchas": True,
        "skill_has_best_practices": True,
        "skill_has_decision_table": True,
        "has_hero": True,
        "has_github_url": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
