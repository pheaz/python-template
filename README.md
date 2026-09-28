# Python Project Template

Personal Copier template for modern Python projects.

## Baseline

Generated projects use:

- Python 3.14
- uv
- uv_build
- Typer
- Ruff
- BasedPyright (`recommended`)
- pytest + pytest-cov
- Nox
- pre-commit
- GitHub Actions
- normative `spec/`
- ADRs, architecture documentation and plans
- exploratory `project-memory/`
- `main` as the initial branch

Public repositories additionally receive:

- MIT license
- PyPI-ready package metadata
- PyPI Trusted Publishing release workflow
- installation instructions for uv / pipx / pip

## Create a project

```bash
uvx copier copy --trust \
  https://github.com/philippwallrafen/python-template.git \
  my-project
```

Copier initializes Git on `main`, creates `uv.lock`, synchronizes the environment,
installs the pre-commit hooks and executes the complete initial quality suite.

Then:

```bash
cd my-project
git add .
git commit -m "Initial project scaffold"

gh repo create philippwallrafen/my-project \
  --private \
  --source=. \
  --remote=origin \
  --push
```

Use `--public` instead for a public/PyPI-oriented project.

## Update an existing generated project

```bash
cd my-project
uvx copier update --trust
```

Template releases are versioned using Git tags.
