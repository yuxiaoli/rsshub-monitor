# Migration from Poetry to uv

This project has been migrated from Poetry to [uv](https://github.com/astral-sh/uv).

## Key Changes

1.  **Dependency Management**: `poetry.lock` has been replaced by `uv.lock`.
2.  **Configuration**: `pyproject.toml` has been updated to use standard PEP 621 metadata (`[project]` table) instead of Poetry-specific sections.
3.  **Commands**:
    *   `poetry install` -> `uv sync`
    *   `poetry run <cmd>` -> `uv run <cmd>`
    *   `poetry add <pkg>` -> `uv add <pkg>`
    *   `poetry remove <pkg>` -> `uv remove <pkg>`

## CI/CD Updates

The GitHub Actions workflow `.github/workflows/monthly-scan.yml` has been updated to use `astral-sh/setup-uv` instead of `snok/install-poetry`.

## Docker / Deployment

If you have Dockerfiles, update them to install `uv` and use `uv sync --frozen` for reproducible builds.

## Developer Notes

- `uv` is significantly faster than Poetry.
- The virtual environment is still located in `.venv` by default.
- Use `uv pip install -r requirements.txt` if you need to install from a requirements file, but `uv sync` is preferred for project development.
