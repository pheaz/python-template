from __future__ import annotations

import shutil
from pathlib import Path

import nox

QUALITY_TARGETS = (
    "src",
    "tests",
    "scripts",
    "noxfile.py",
)

FULL_CHECK_SESSIONS = (
    "format",
    "lint",
    "typecheck",
    "spec",
    "tests",
    "lock",
    "build",
)

nox.options.default_venv_backend = "none"
nox.options.sessions = ["full"]
nox.options.stop_on_first_error = False
nox.options.error_on_external_run = True


def _run_module(
    session: nox.Session,
    module: str,
    *arguments: str,
) -> None:
    _ = session.run(
        "python",
        "-m",
        module,
        *arguments,
        external=True,
    )


@nox.session
def fix(session: nox.Session) -> None:
    """Apply safe automatic fixes."""
    _run_module(
        session,
        "ruff",
        "check",
        "--fix",
        "--exit-zero",
        *QUALITY_TARGETS,
    )
    _run_module(
        session,
        "ruff",
        "format",
        *QUALITY_TARGETS,
    )


@nox.session(name="format")
def format_check(session: nox.Session) -> None:
    """Verify formatting."""
    _run_module(
        session,
        "ruff",
        "format",
        "--check",
        *QUALITY_TARGETS,
    )


@nox.session
def lint(session: nox.Session) -> None:
    """Run Ruff."""
    _run_module(
        session,
        "ruff",
        "check",
        *QUALITY_TARGETS,
    )


@nox.session
def typecheck(session: nox.Session) -> None:
    """Run BasedPyright."""
    _run_module(session, "basedpyright")


@nox.session
def spec(session: nox.Session) -> None:
    """Validate the normative specification."""
    _run_module(session, "scripts.check_spec")


@nox.session
def tests(session: nox.Session) -> None:
    """Run tests."""
    _run_module(
        session,
        "pytest",
        *session.posargs,
    )


@nox.session
def lock(session: nox.Session) -> None:
    """Verify the uv lockfile."""
    _ = session.run(
        "uv",
        "lock",
        "--check",
        external=True,
    )


@nox.session
def build(session: nox.Session) -> None:
    """Build and smoke-test the distribution."""
    dist = Path("dist")

    if dist.exists():
        shutil.rmtree(dist)

    _ = session.run(
        "uv",
        "build",
        "--no-sources",
        external=True,
    )

    _run_module(
        session,
        "scripts.smoke_distribution",
    )


@nox.session
def full(session: nox.Session) -> None:
    """Run all non-mutating quality checks."""
    for session_name in FULL_CHECK_SESSIONS:
        _ = session.notify(session_name)
