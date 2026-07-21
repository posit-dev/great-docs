"""
gdtest_skill_complex — Tests sophisticated skill compositions with subdirectories.

Dimensions: S7
Focus: Curated SKILL.md accompanied by the full Agent Skills directory structure:
       references/ (API cheatsheet, migration guide), scripts/ (setup helper,
       test runner), and assets/ (config template). The SKILL.md body references
       these companion files. Tests that the raw rendering faithfully displays
       the full skill directory structure and that the build pipeline handles
       a complex skills/ tree without errors.
"""

SPEC = {
    "name": "gdtest_skill_complex",
    "description": "Tests skill with subdirectories: references/, scripts/, assets/",
    "dimensions": ["S7"],
    "pyproject_toml": {
        "project": {
            "name": "gdtest-skill-complex",
            "version": "3.1.0",
            "description": (
                "A task-orchestration framework with comprehensive agent skill "
                "documentation including reference cheatsheets, setup scripts, "
                "and configuration templates"
            ),
            "license": "MIT",
            "requires-python": ">=3.10",
            "urls": {
                "Homepage": "https://example.com/gdtest-skill-complex",
                "Repository": "https://github.com/test-org/gdtest-skill-complex",
            },
        },
        "build-system": {
            "requires": ["setuptools"],
            "build-backend": "setuptools.build_meta",
        },
    },
    "config": {
        "site_url": "https://example.com/gdtest-skill-complex",
        "skill": {
            "gotchas": [
                "`Scheduler.tick()` is not re-entrant — never call it from inside a task callback.",
                "Task names must be unique within a `Scheduler` instance; "
                "duplicates raise `DuplicateTaskError`.",
                "The `CronExpr` parser does not support second-level "
                "granularity — minimum resolution is one minute.",
            ],
            "best_practices": [
                "Use `Scheduler(workers=N)` to match your CPU core count for CPU-bound tasks.",
                "Always set `task.timeout` to avoid runaway tasks — the default is no timeout.",
                "Prefer `Scheduler.submit()` over `Scheduler.run()` for fire-and-forget patterns.",
            ],
            "decision_table": [
                {
                    "if": "Running tasks on a fixed interval",
                    "then": "scheduler.every(seconds=30, fn=task)",
                },
                {
                    "if": "Running tasks on a cron schedule",
                    "then": "scheduler.cron('*/5 * * * *', fn=task)",
                },
                {
                    "if": "Running a one-shot delayed task",
                    "then": "scheduler.once(delay=60, fn=task)",
                },
                {
                    "if": "Running tasks concurrently",
                    "then": "scheduler = Scheduler(workers=4)",
                },
                {
                    "if": "Need task dependency chains",
                    "then": "scheduler.chain(task_a, task_b, task_c)",
                },
            ],
        },
    },
    "files": {
        "gdtest_skill_complex/__init__.py": '''\
            """A task-orchestration framework."""

            __version__ = "3.1.0"
            __all__ = [
                "Scheduler",
                "Task",
                "CronExpr",
                "TaskResult",
                "every",
                "cron",
                "once",
                "chain",
            ]


            class Scheduler:
                """
                Central task scheduler with worker pool.

                Parameters
                ----------
                workers
                    Number of concurrent worker threads.
                name
                    Scheduler instance identifier.
                """

                def __init__(self, workers: int = 1, name: str = "default"):
                    self.workers = workers
                    self.name = name
                    self._tasks: list = []

                def every(self, seconds: int, fn=None, name: str = "") -> "Task":
                    """
                    Schedule a recurring task at a fixed interval.

                    Parameters
                    ----------
                    seconds
                        Interval in seconds between executions.
                    fn
                        Callable to execute.
                    name
                        Task identifier.

                    Returns
                    -------
                    Task
                        The registered task.
                    """
                    t = Task(name=name or "interval", fn=fn)
                    self._tasks.append(t)
                    return t

                def cron(self, expr: str, fn=None, name: str = "") -> "Task":
                    """
                    Schedule a task using a cron expression.

                    Parameters
                    ----------
                    expr
                        Cron expression (e.g., ``*/5 * * * *``).
                    fn
                        Callable to execute.
                    name
                        Task identifier.

                    Returns
                    -------
                    Task
                        The registered task.
                    """
                    CronExpr(expr)  # validate
                    t = Task(name=name or "cron", fn=fn)
                    self._tasks.append(t)
                    return t

                def once(self, delay: int, fn=None, name: str = "") -> "Task":
                    """
                    Schedule a one-shot task after a delay.

                    Parameters
                    ----------
                    delay
                        Delay in seconds before execution.
                    fn
                        Callable to execute.
                    name
                        Task identifier.

                    Returns
                    -------
                    Task
                        The registered task.
                    """
                    t = Task(name=name or "once", fn=fn)
                    self._tasks.append(t)
                    return t

                def chain(self, *tasks: "Task") -> list["TaskResult"]:
                    """
                    Execute tasks sequentially, passing each result to the next.

                    Parameters
                    ----------
                    *tasks
                        Tasks to chain in order.

                    Returns
                    -------
                    list[TaskResult]
                        Results from each task in the chain.
                    """
                    return [TaskResult(task=t, status="pending") for t in tasks]

                def submit(self, fn=None, name: str = "") -> "Task":
                    """
                    Submit a fire-and-forget task.

                    Parameters
                    ----------
                    fn
                        Callable to execute.
                    name
                        Task identifier.

                    Returns
                    -------
                    Task
                        The submitted task.
                    """
                    t = Task(name=name or "submitted", fn=fn)
                    self._tasks.append(t)
                    return t

                def run(self) -> list["TaskResult"]:
                    """
                    Start the scheduler and block until stopped.

                    Returns
                    -------
                    list[TaskResult]
                        Results of all completed tasks.
                    """
                    return []

                def stop(self) -> None:
                    """Stop the scheduler gracefully."""
                    pass


            class Task:
                """
                A unit of work managed by a Scheduler.

                Parameters
                ----------
                name
                    Task identifier (must be unique within a scheduler).
                fn
                    Callable to execute.
                timeout
                    Maximum execution time in seconds (None = no limit).
                """

                def __init__(self, name: str, fn=None, timeout: int | None = None):
                    self.name = name
                    self.fn = fn
                    self.timeout = timeout


            class CronExpr:
                """
                A parsed cron expression.

                Parameters
                ----------
                expr
                    Cron expression string (5 fields: min hour dom month dow).

                Raises
                ------
                ValueError
                    If the expression is malformed.
                """

                def __init__(self, expr: str):
                    parts = expr.strip().split()
                    if len(parts) != 5:
                        raise ValueError(
                            f"Cron expression must have 5 fields, got {len(parts)}: {expr!r}"
                        )
                    self.expr = expr

                def matches(self, dt) -> bool:
                    """
                    Check if a datetime matches this cron expression.

                    Parameters
                    ----------
                    dt
                        A datetime to test.

                    Returns
                    -------
                    bool
                        True if the datetime matches.
                    """
                    return True


            class TaskResult:
                """
                The result of a completed task.

                Parameters
                ----------
                task
                    The task that produced this result.
                status
                    Execution status (pending, success, failed, timeout).
                value
                    Return value from the task callable.
                error
                    Exception if the task failed.
                """

                def __init__(
                    self,
                    task: Task,
                    status: str = "pending",
                    value=None,
                    error: Exception | None = None,
                ):
                    self.task = task
                    self.status = status
                    self.value = value
                    self.error = error


            def every(seconds: int, fn=None) -> Task:
                """
                Module-level shortcut: schedule a recurring task.

                Parameters
                ----------
                seconds
                    Interval between executions.
                fn
                    Callable to execute.

                Returns
                -------
                Task
                    The registered task.
                """
                return Scheduler().every(seconds, fn)


            def cron(expr: str, fn=None) -> Task:
                """
                Module-level shortcut: schedule a cron task.

                Parameters
                ----------
                expr
                    Cron expression.
                fn
                    Callable to execute.

                Returns
                -------
                Task
                    The registered task.
                """
                return Scheduler().cron(expr, fn)


            def once(delay: int, fn=None) -> Task:
                """
                Module-level shortcut: schedule a one-shot task.

                Parameters
                ----------
                delay
                    Seconds before execution.
                fn
                    Callable to execute.

                Returns
                -------
                Task
                    The registered task.
                """
                return Scheduler().once(delay, fn)


            def chain(*tasks: Task) -> list[TaskResult]:
                """
                Module-level shortcut: chain tasks sequentially.

                Parameters
                ----------
                *tasks
                    Tasks to chain.

                Returns
                -------
                list[TaskResult]
                    Results from each task.
                """
                return Scheduler().chain(*tasks)
        ''',
        # ── Curated skill: SKILL.md with companion directory references ──
        "skills/gdtest-skill-complex/SKILL.md": """\
            ---
            name: gdtest-skill-complex
            description: >
              Orchestrate recurring, cron-scheduled, and one-shot tasks with
              gdtest-skill-complex. Supports worker pools, task chaining,
              cron expressions, timeouts, and fire-and-forget patterns.
            license: MIT
            compatibility: Requires Python >=3.10.
            metadata:
              author: gdg-test-suite
              version: "3.1"
              tags:
                - task-scheduling
                - cron
                - orchestration
                - worker-pool
            ---

            # gdtest-skill-complex

            A task-orchestration framework for scheduling, chaining, and
            monitoring background work.

            ## Quick start

            ```python
            from gdtest_skill_complex import Scheduler

            sched = Scheduler(workers=4)
            sched.every(seconds=60, fn=check_health, name="healthcheck")
            sched.cron("0 2 * * *", fn=nightly_backup, name="backup")
            sched.run()
            ```

            ## Skill directory structure

            This skill ships with companion files for agent consumption:

            ```
            skills/gdtest-skill-complex/
            ├── SKILL.md              ← This file
            ├── references/
            │   ├── api-cheatsheet.md ← Quick-reference for all public APIs
            │   └── migration-v2-v3.md ← Migration guide from v2 to v3
            ├── scripts/
            │   ├── setup-env.sh      ← Environment bootstrap script
            │   └── run-tests.sh      ← Test runner with coverage
            └── assets/
                └── config-template.yaml ← Starter configuration file
            ```

            ## When to use what

            | Need | Use |
            |------|-----|
            | Fixed-interval polling | `scheduler.every(seconds=30, fn=poll)` |
            | Cron-scheduled jobs | `scheduler.cron('*/5 * * * *', fn=job)` |
            | One-shot delayed task | `scheduler.once(delay=120, fn=migrate)` |
            | Sequential pipeline | `scheduler.chain(extract, transform, load)` |
            | Fire-and-forget | `scheduler.submit(fn=send_email)` |
            | Concurrent workers | `Scheduler(workers=cpu_count())` |

            ## Core concepts

            ### Scheduler

            The `Scheduler` manages a pool of workers and a task registry.
            Tasks are added via `.every()`, `.cron()`, `.once()`, or `.submit()`.
            Call `.run()` to start blocking execution, or `.stop()` to shut down
            gracefully.

            ### Task

            A `Task` wraps a callable with a unique name and optional timeout.
            Task names **must be unique** within a scheduler — duplicates raise
            `DuplicateTaskError`.

            ### CronExpr

            Parses and evaluates standard 5-field cron expressions
            (minute, hour, day-of-month, month, day-of-week). Does **not**
            support second-level granularity.

            ```python
            from gdtest_skill_complex import CronExpr

            expr = CronExpr("*/5 * * * *")   # every 5 minutes
            expr.matches(datetime.now())       # True/False
            ```

            ### TaskResult

            Returned by `.run()` and `.chain()`. Contains the execution status
            (`pending`, `success`, `failed`, `timeout`), the return value, and
            any exception.

            ## Task chaining

            Chain tasks to build sequential pipelines where each task's output
            feeds the next:

            ```python
            extract = Task("extract", fn=extract_data)
            transform = Task("transform", fn=clean_and_normalize)
            load = Task("load", fn=write_to_db)

            results = scheduler.chain(extract, transform, load)
            for r in results:
                print(f"{r.task.name}: {r.status}")
            ```

            ## Reference files

            ### API cheatsheet (`references/api-cheatsheet.md`)

            A condensed reference of every public class and function:

            | Symbol | Signature | Purpose |
            |--------|-----------|---------|
            | `Scheduler` | `(workers=1, name='default')` | Central orchestrator |
            | `Task` | `(name, fn=None, timeout=None)` | Unit of work |
            | `CronExpr` | `(expr)` | Cron parser |
            | `TaskResult` | `(task, status, value, error)` | Execution result |
            | `every()` | `(seconds, fn)` | Module-level interval shortcut |
            | `cron()` | `(expr, fn)` | Module-level cron shortcut |
            | `once()` | `(delay, fn)` | Module-level one-shot shortcut |
            | `chain()` | `(*tasks)` | Module-level chain shortcut |

            ### Migration guide (`references/migration-v2-v3.md`)

            Key changes from v2 to v3:

            1. `Scheduler.interval()` renamed to `Scheduler.every()`.
            2. `Task.callback` renamed to `Task.fn`.
            3. `CronExpr` now validates on construction (was lazy).
            4. Worker count defaults to 1 (was `os.cpu_count()`).

            ## Scripts

            ### `scripts/setup-env.sh`

            Bootstrap a development environment:

            ```bash
            #!/usr/bin/env bash
            set -euo pipefail
            python -m venv .venv
            source .venv/bin/activate
            pip install -e ".[dev,test]"
            echo "Environment ready."
            ```

            ### `scripts/run-tests.sh`

            Run the test suite with coverage:

            ```bash
            #!/usr/bin/env bash
            set -euo pipefail
            pytest tests/ --cov=gdtest_skill_complex --cov-report=term-missing
            ```

            ## Configuration template

            The `assets/config-template.yaml` provides a starter configuration:

            ```yaml
            # gdtest-skill-complex configuration
            scheduler:
              workers: 4
              name: production

            tasks:
              - name: healthcheck
                type: every
                seconds: 30
                fn: app.health.check

              - name: nightly-backup
                type: cron
                expr: "0 2 * * *"
                fn: app.backup.run
                timeout: 3600

              - name: weekly-report
                type: cron
                expr: "0 9 * * 1"
                fn: app.reports.weekly
            ```

            ## Error handling

            ```python
            results = scheduler.run()
            for r in results:
                if r.status == "failed":
                    print(f"Task {r.task.name} failed: {r.error}")
                elif r.status == "timeout":
                    print(f"Task {r.task.name} timed out after {r.task.timeout}s")
            ```

            ## Capabilities and boundaries

            **What agents can configure:**

            - Create schedulers with worker pools
            - Register interval, cron, one-shot, and fire-and-forget tasks
            - Chain tasks into sequential pipelines
            - Set per-task timeouts
            - Parse and validate cron expressions
            - Use reference files for quick API lookups
            - Run setup and test scripts

            **Requires human setup:**

            - Deploying as a system service (systemd, Docker, etc.)
            - Configuring monitoring and alerting
            - Setting up log aggregation
            - Database and credential provisioning

            ## Resources

            - [llms.txt](llms.txt) — Indexed API reference for LLMs
            - [llms-full.txt](llms-full.txt) — Comprehensive documentation for LLMs
        """,
        # ── Companion subdirectories ──
        # references/
        "skills/gdtest-skill-complex/references/api-cheatsheet.md": """\
            # API Cheatsheet — gdtest-skill-complex

            ## Classes

            | Class | Constructor | Key Methods |
            |-------|------------|-------------|
            | `Scheduler` | `(workers=1, name='default')` | `.every()`, `.cron()`, `.once()`, `.submit()`, `.chain()`, `.run()`, `.stop()` |
            | `Task` | `(name, fn=None, timeout=None)` | — |
            | `CronExpr` | `(expr)` | `.matches(dt)` |
            | `TaskResult` | `(task, status, value, error)` | — |

            ## Module-level functions

            | Function | Signature | Equivalent to |
            |----------|-----------|---------------|
            | `every()` | `(seconds, fn)` | `Scheduler().every(...)` |
            | `cron()` | `(expr, fn)` | `Scheduler().cron(...)` |
            | `once()` | `(delay, fn)` | `Scheduler().once(...)` |
            | `chain()` | `(*tasks)` | `Scheduler().chain(...)` |

            ## Cron expression format

            ```
            ┌───────────── minute (0–59)
            │ ┌─────────── hour (0–23)
            │ │ ┌───────── day of month (1–31)
            │ │ │ ┌─────── month (1–12)
            │ │ │ │ ┌───── day of week (0–6, Sun=0)
            * * * * *
            ```

            ## Common patterns

            ```python
            # Every 30 seconds
            scheduler.every(seconds=30, fn=poll)

            # Every 5 minutes (cron)
            scheduler.cron("*/5 * * * *", fn=check)

            # Weekdays at 9 AM
            scheduler.cron("0 9 * * 1-5", fn=report)

            # One-shot in 2 minutes
            scheduler.once(delay=120, fn=migrate)

            # Sequential pipeline
            scheduler.chain(task_a, task_b, task_c)
            ```
        """,
        "skills/gdtest-skill-complex/references/migration-v2-v3.md": """\
            # Migration Guide: v2 → v3

            ## Breaking changes

            ### 1. `Scheduler.interval()` → `Scheduler.every()`

            ```python
            # v2 (removed)
            scheduler.interval(30, fn=poll)

            # v3
            scheduler.every(seconds=30, fn=poll)
            ```

            ### 2. `Task.callback` → `Task.fn`

            ```python
            # v2
            task = Task("name", callback=my_func)

            # v3
            task = Task("name", fn=my_func)
            ```

            ### 3. CronExpr validates eagerly

            ```python
            # v2: no error until .matches() called
            expr = CronExpr("bad")
            expr.matches(now)  # ValueError here

            # v3: error on construction
            expr = CronExpr("bad")  # ValueError here
            ```

            ### 4. Worker default changed

            | Setting | v2 | v3 |
            |---------|----|----|
            | `Scheduler(workers=...)` | `os.cpu_count()` | `1` |

            Set `workers` explicitly to preserve v2 behavior:

            ```python
            import os
            scheduler = Scheduler(workers=os.cpu_count())
            ```

            ## Non-breaking additions

            - `scheduler.submit()` — fire-and-forget tasks
            - `scheduler.chain()` — sequential task pipelines
            - `TaskResult.error` — exception capture on failure
            - `Task.timeout` — per-task execution time limit
        """,
        # scripts/
        "skills/gdtest-skill-complex/scripts/setup-env.sh": """\
            #!/usr/bin/env bash
            # Setup development environment for gdtest-skill-complex
            set -euo pipefail

            echo "Creating virtual environment..."
            python -m venv .venv
            source .venv/bin/activate

            echo "Installing package with dev extras..."
            pip install -e ".[dev,test]"

            echo "Running initial validation..."
            python -c "from gdtest_skill_complex import Scheduler; print('Import OK')"

            echo "Environment ready."
        """,
        "skills/gdtest-skill-complex/scripts/run-tests.sh": """\
            #!/usr/bin/env bash
            # Run test suite with coverage for gdtest-skill-complex
            set -euo pipefail

            echo "Running tests with coverage..."
            pytest tests/ \\
                --cov=gdtest_skill_complex \\
                --cov-report=term-missing \\
                --cov-fail-under=80

            echo "Tests complete."
        """,
        # assets/
        "skills/gdtest-skill-complex/assets/config-template.yaml": """\
            # gdtest-skill-complex starter configuration
            # Copy this to your project root as scheduler-config.yaml

            scheduler:
              workers: 4
              name: production

            tasks:
              - name: healthcheck
                type: every
                seconds: 30
                fn: app.health.check

              - name: nightly-backup
                type: cron
                expr: "0 2 * * *"
                fn: app.backup.run
                timeout: 3600

              - name: weekly-report
                type: cron
                expr: "0 9 * * 1"
                fn: app.reports.weekly

              - name: data-cleanup
                type: cron
                expr: "0 3 * * 0"
                fn: app.maintenance.cleanup
                timeout: 7200
        """,
        "README.md": """\
            # gdtest-skill-complex

            A task-orchestration framework with comprehensive agent skill
            documentation including reference cheatsheets, setup scripts,
            and configuration templates.

            ## Installation

            ```bash
            pip install gdtest-skill-complex
            ```
        """,
    },
    "expected": {
        "detected_name": "gdtest-skill-complex",
        "detected_module": "gdtest_skill_complex",
        "detected_parser": "numpy",
        "export_names": [
            "Scheduler",
            "Task",
            "CronExpr",
            "TaskResult",
            "every",
            "cron",
            "once",
            "chain",
        ],
        "num_exports": 8,
        "section_titles": ["Classes", "Functions"],
        "has_user_guide": False,
        "has_skill_md": True,
        "has_skills_page": True,
        "skill_is_curated": True,
        "skill_has_gotchas": True,
        "skill_has_best_practices": True,
        "skill_has_decision_table": True,
        "has_github_url": True,
        "coverage_exclude": ["nodoc", "bigcl", "ug", "supp", "hdg"],
    },
}
