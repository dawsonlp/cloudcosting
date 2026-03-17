# Python CLI Tool: Repository, CI/CD, and PyPI Release Setup Guide

Precise instructions based on the docsmith project. Follow exactly to avoid known pitfalls.

---

## Prerequisites

- `uv`, `gh`, `git` installed
- GitHub account with access to your org/user
- PyPI account at https://pypi.org

---

## 1. Project Structure

Create this exact structure. Replace `<package>` with your package name throughout.

```
<project>/
├── .github/
│   └── workflows/
│       ├── ci.yaml
│       └── publish_to_pypi.yaml
├── .gitignore
├── .pre-commit-config.yaml
├── LICENSE
├── README.md
├── pyproject.toml
├── src/
│   └── <package>/
│       ├── __init__.py
│       ├── __main__.py
│       └── cli.py          # or main.py, whatever your entry point is
└── tests/
    ├── __init__.py          # REQUIRED -- must exist with content, not empty
    └── test_<something>.py  # At least one test file with at least one test
```

### Pitfall: tests/ directory

Git does not track empty directories. If `tests/` has no files, CI will fail in two ways:

1. `ruff check tests/` fails with "No such file or directory"
2. `pytest tests/` exits with code 5 (no tests collected)

**Fix:** Always include `tests/__init__.py` with at least a comment, AND at least one test file.

`tests/__init__.py`:

```python
# tests package
```

`tests/test_smoke.py` (minimal example):

```python
"""Smoke test."""


def test_import():
    """Package is importable."""
    import <package>
    assert <package>.__version__
```

### Pitfall: Trailing newlines

ruff enforces W292 (no newline at end of file). Every file must end with a newline character. Run `ruff format` on all files before committing.

---

## 2. pyproject.toml

```toml
[project]
name = "<package>"
version = "0.1.0"
description = "Your description"
authors = [{name = "Development Team"}]
readme = "README.md"
requires-python = ">=3.13"
license = "GPL-3.0-or-later"
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.13",
]

dependencies = [
    # your runtime deps here
]

[project.optional-dependencies]
dev = [
    "pre-commit",
    "pytest",
    "ruff",
]

[project.scripts]
<command-name> = "<package>.cli:main"

[project.urls]
Homepage = "https://github.com/dawsonlp/<project>"
Repository = "https://github.com/dawsonlp/<project>"
Issues = "https://github.com/dawsonlp/<project>/issues"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/<package>"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
src = ["src"]
target-version = "py313"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["<package>"]
```

Key points:

- `pre-commit` is in dev deps, not installed globally
- `[project.scripts]` is what makes `pipx install` give you a CLI command
- `[tool.hatch.build.targets.wheel] packages = ["src/<package>"]` must match your actual package directory

---

## 3. src/\<package\>/\_\_init\_\_.py

```python
"""Package description."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("<package>")
except PackageNotFoundError:
    __version__ = "dev"
```

---

## 4. .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.2
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

---

## 5. .github/workflows/ci.yaml

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

jobs:
  lint:
    name: Lint & Format
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Set up Python
        run: uv python install 3.13

      - name: Install dependencies
        run: |
          uv venv .venv
          uv pip install -e ".[dev]"

      - name: Ruff lint
        run: uv run ruff check src/ tests/

      - name: Ruff format check
        run: uv run ruff format --check src/ tests/

  test:
    name: Test
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Set up Python
        run: uv python install 3.13

      - name: Install dependencies
        run: |
          uv venv .venv
          uv pip install -e ".[dev]"

      - name: Run tests
        run: uv run pytest tests/ -v
```

### Pitfall: GitHub Actions Node.js version

- Use `astral-sh/setup-uv@v5` (NOT v4 -- v4 uses Node.js 20 which is deprecated)
- Set `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` at workflow level
- Use `actions/checkout@v4` (works with the Node.js 24 flag)

---

## 6. .github/workflows/publish_to_pypi.yaml

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

jobs:
  publish:
    name: Build & Publish
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Set up Python
        run: uv python install 3.13

      - name: Build package
        run: uv build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

---

## 7. .gitignore

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
*.egg
dist/
build/
*.whl

# Virtual environments
.venv/
venv/

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Environment
.env
```

---

## 8. Setup Commands (in order)

```bash
# 1. Create local dev environment
cd <project>
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# 2. Format and lint BEFORE first commit
uv run ruff format src/ tests/
uv run ruff check src/ tests/ --fix

# 3. Run tests locally to confirm they pass
uv run pytest tests/ -v

# 4. Initialize git and install pre-commit hook
git init
uv run pre-commit install

# 5. First commit
git add -A
git commit -m "feat: initial release"

# 6. Create GitHub repo and push
gh repo create dawsonlp/<project> --public --source=. \
  --description "Your description" --push

# 7. Verify CI passes on GitHub before proceeding
gh run list --limit 1
```

---

## 9. First Publish to PyPI (Bootstrap)

There is a chicken-and-egg problem: you cannot register a trusted publisher for a project that does not yet exist on PyPI, and the trusted publisher workflow only works for projects that exist.

**Solution: Use a temporary account-scoped API token for the first publish only.**

```bash
# 1. Create an account-scoped API token at https://pypi.org/manage/account/token/
# 2. Store it (e.g., in ~/.env as PYPI_TEMP_KEY)

# 3. Build
uv build

# 4. Publish with the temp token
source ~/.env
uv publish --token "$PYPI_TEMP_KEY"

# 5. Verify
curl -s https://pypi.org/pypi/<package>/json | jq '.info.version'
```

---

## 10. Register Trusted Publisher (After First Publish)

1. Go to `https://pypi.org/manage/project/<package>/settings/publishing/`
2. Add a new publisher:
   - **Repository owner**: `dawsonlp`
   - **Repository name**: `<project>`
   - **Workflow name**: `publish_to_pypi.yaml`
   - **Environment name**: `pypi`
3. Revoke the temporary account-scoped API token

---

## 11. Subsequent Releases (Fully Automated)

```bash
# 1. Bump version in pyproject.toml
# 2. Commit and push
git add -A
git commit -m "feat: v1.1.0 -- description"
git tag v1.1.0
git push && git push origin v1.1.0

# 3. Create GitHub release (triggers publish workflow)
gh release create v1.1.0 --title "v1.1.0" --generate-notes --latest

# 4. Verify
gh run list --limit 1
pipx upgrade <package>
```

---

## Summary of Pitfalls to Avoid

| Pitfall | Cause | Prevention |
|---------|-------|------------|
| tests/ not found in CI | Git ignores empty dirs | Always include `tests/__init__.py` + at least one test file |
| pytest exit code 5 | No tests collected | Include at least one `test_*.py` with a real test function |
| W292 no newline at end of file | Missing trailing newline | Run `ruff format` before every commit (pre-commit hook handles this) |
| Node.js 20 deprecation warnings | Old action versions | Use `setup-uv@v5`, set `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` |
| pip install pre-commit | Installing outside project | Add to `[project.optional-dependencies] dev`, install via `uv pip install -e ".[dev]"` |
| First PyPI publish fails with trusted publisher | Project must exist first | Use temp API token for first publish, then register trusted publisher |
| F401 unused import in tests | Leftover imports | Run `ruff check --fix` before committing |