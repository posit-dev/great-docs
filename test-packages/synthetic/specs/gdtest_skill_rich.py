"""
gdtest_skill_rich — Tests curated skill with rich content (tables, code, sections).

Dimensions: S5
Focus: Curated SKILL.md with extensive Markdown features: multiple heading
       levels, fenced code blocks in different languages, tables, inline
       formatting (bold, code, links), nested lists, and gotchas/best-practices
       from config layered on top. Exercises the full _render_skill_body_html()
       pipeline and SCSS styling.
"""

SPEC = {
    "name": "gdtest_skill_rich",
    "description": "Tests curated skill with rich content — tables, code, many sections",
    "dimensions": ["S5"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-skill-rich",
            "version": "1.0.0",
            "description": "A data-pipeline toolkit with rich agent skill documentation",
            "license": "Apache-2.0",
            "requires-python": ">=3.10",
            "urls": {
                "Repository": "https://github.com/test-org/gdtest-skill-rich",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "skill": {
            "gotchas": [
                "`Pipeline.run()` blocks until all stages complete — use "
                "`Pipeline.run_async()` for non-blocking execution.",
            ],
            "best_practices": [
                "Pin your pipeline to a schema version with "
                "`Pipeline(schema='v2')` for reproducible results.",
            ],
        },
    },
    "files": {
        "gdtest_skill_rich/__init__.py": '''\
            """A data-pipeline toolkit."""

            __version__ = "1.0.0"
            __all__ = [
                "Pipeline",
                "Stage",
                "Source",
                "Sink",
                "run_pipeline",
                "validate_schema",
            ]


            class Pipeline:
                """
                An ordered chain of processing stages.

                Parameters
                ----------
                name
                    Pipeline identifier.
                schema
                    Schema version string for reproducibility.
                """

                def __init__(self, name: str = "default", schema: str = "v2"):
                    self.name = name
                    self.schema = schema
                    self._stages: list = []

                def add(self, stage: "Stage") -> "Pipeline":
                    """
                    Append a stage to the pipeline.

                    Parameters
                    ----------
                    stage
                        The stage to add.

                    Returns
                    -------
                    Pipeline
                        Self, for chaining.
                    """
                    self._stages.append(stage)
                    return self

                def run(self) -> dict:
                    """
                    Execute the pipeline synchronously.

                    Returns
                    -------
                    dict
                        Pipeline results keyed by stage name.
                    """
                    return {}

                async def run_async(self) -> dict:
                    """
                    Execute the pipeline asynchronously.

                    Returns
                    -------
                    dict
                        Pipeline results keyed by stage name.
                    """
                    return {}


            class Stage:
                """
                A single processing step in a pipeline.

                Parameters
                ----------
                name
                    Stage identifier.
                fn
                    Callable that processes data.
                """

                def __init__(self, name: str, fn=None):
                    self.name = name
                    self.fn = fn


            class Source:
                """
                A data source feeding a pipeline.

                Parameters
                ----------
                uri
                    Connection URI (file path, URL, or database DSN).
                format
                    Data format (csv, json, parquet).
                """

                def __init__(self, uri: str, format: str = "json"):
                    self.uri = uri
                    self.format = format

                def read(self) -> list:
                    """
                    Read all records from the source.

                    Returns
                    -------
                    list
                        Records as dicts.
                    """
                    return []


            class Sink:
                """
                A data destination for pipeline output.

                Parameters
                ----------
                uri
                    Destination URI.
                format
                    Output format.
                """

                def __init__(self, uri: str, format: str = "json"):
                    self.uri = uri
                    self.format = format

                def write(self, records: list) -> int:
                    """
                    Write records to the sink.

                    Parameters
                    ----------
                    records
                        Records to write.

                    Returns
                    -------
                    int
                        Number of records written.
                    """
                    return len(records)


            def run_pipeline(source: Source, *stages: Stage, sink: Sink) -> dict:
                """
                One-shot helper: source -> stages -> sink.

                Parameters
                ----------
                source
                    Data source.
                *stages
                    Processing stages.
                sink
                    Data destination.

                Returns
                -------
                dict
                    Execution summary.
                """
                return {"records": 0}


            def validate_schema(data: dict, schema: str = "v2") -> bool:
                """
                Validate data against a schema version.

                Parameters
                ----------
                data
                    Data to validate.
                schema
                    Schema version string.

                Returns
                -------
                bool
                    True if valid.
                """
                return True
        ''',
        # Rich curated skill with multiple heading levels, code blocks, tables,
        # inline formatting, and nested lists
        "skills/gdtest-skill-rich/SKILL.md": """\
            ---
            name: gdtest-skill-rich
            description: >
              Build, run, and monitor data pipelines with gdtest-skill-rich.
              Supports sync and async execution, schema validation, and
              pluggable stages for ETL workflows.
            license: Apache-2.0
            compatibility: Requires Python >=3.10.
            metadata:
              author: gdg-test-suite
              version: "1.0"
              tags:
                - data-pipeline
                - etl
                - streaming
            ---

            # gdtest-skill-rich

            A full-featured data-pipeline toolkit for ETL workflows.

            ## Quick start

            ```python
            from gdtest_skill_rich import Pipeline, Stage, Source, Sink

            src = Source("data/input.json")
            snk = Sink("data/output.parquet", format="parquet")

            pipe = (
                Pipeline(name="etl-demo", schema="v2")
                .add(Stage("clean", fn=clean_fn))
                .add(Stage("transform", fn=transform_fn))
            )
            pipe.run()
            ```

            ## Core concepts

            ### Pipeline

            A `Pipeline` is an ordered chain of `Stage` objects. Pipelines are
            **immutable once running** — modifications after `.run()` raise
            `RuntimeError`.

            ### Stage

            A stage wraps a callable `fn(data) -> data`. Stages execute in
            insertion order.

            ### Source & Sink

            Sources read data; sinks write it. Both accept a `uri`
            (file path, URL, or database DSN) and a `format` string.

            #### Supported formats

            | Format | Source | Sink | Notes |
            |--------|--------|------|-------|
            | `json` | Yes | Yes | Default format |
            | `csv` | Yes | Yes | Header row required |
            | `parquet` | Yes | Yes | Requires `pyarrow` |
            | `sqlite` | Yes | No | Read-only |
            | `postgres` | Yes | Yes | Requires `psycopg2` |

            ## Decision table

            | If you need to… | Then use |
            |-----------------|----------|
            | Run a simple one-shot ETL | `run_pipeline(source, *stages, sink=sink)` |
            | Build a reusable pipeline | `Pipeline().add(stage).add(stage)` |
            | Run without blocking | `await pipeline.run_async()` |
            | Validate input data | `validate_schema(data, schema="v2")` |
            | Read from a database | `Source("postgres://...", format="postgres")` |
            | Write to Parquet | `Sink("out.parquet", format="parquet")` |

            ## Configuration example

            ```yaml
            # great-docs.yml
            skill:
              gotchas:
                - "Pipeline.run() blocks until all stages complete."
              best_practices:
                - "Pin to a schema version for reproducibility."
            ```

            ## Error handling

            ```python
            try:
                pipe.run()
            except PipelineError as e:
                print(f"Stage {e.stage} failed: {e}")
            ```

            ## Advanced: custom stages

            ```python
            class MyStage(Stage):
                def __init__(self):
                    super().__init__("my-stage", fn=self._process)

                def _process(self, data):
                    return [row for row in data if row["active"]]
            ```

            ## Capabilities and boundaries

            **What agents can configure:**

            - Create and run pipelines
            - Add custom stages
            - Read from files, URLs, and databases
            - Write to files and databases
            - Validate schemas
            - Run async pipelines

            **Requires human setup:**

            - Database credentials and access
            - Installing optional dependencies (`pyarrow`, `psycopg2`)
            - Deploying to production infrastructure

            ## Resources

            - [llms.txt](llms.txt) — Indexed API reference for LLMs
            - [llms-full.txt](llms-full.txt) — Full documentation for LLMs
        """,
        "README.md": """\
            # gdtest-skill-rich

            A data-pipeline toolkit with rich agent skill documentation.

            ## Installation

            ```bash
            pip install gdtest-skill-rich
            ```
        """,
    },
    "expected": {
        "detected_name": "gdtest-skill-rich",
        "detected_module": "gdtest_skill_rich",
        "detected_parser": "numpy",
        "export_names": [
            "Pipeline",
            "Stage",
            "Source",
            "Sink",
            "run_pipeline",
            "validate_schema",
        ],
        "num_exports": 6,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "has_skill_md": True,
        "has_skills_page": True,
        "skill_is_curated": True,
        "skill_has_gotchas": True,
        "skill_has_best_practices": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
