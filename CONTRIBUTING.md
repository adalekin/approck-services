# Contributing

Thank you for considering a contribution to **approck-services**.

## Getting started

1. Clone the repository and install dependencies with [uv](https://docs.astral.sh/uv/).

   ```bash
   git clone https://github.com/approck-pro/approck-services.git
   cd approck-services
   uv sync --all-extras --group dev
   ```

2. Run the test suite. Integration tests expect **PostgreSQL** with async access (same URL shape as in `tests/conftest.py`: user `postgres`, password `postgres`, database `postgres`, port `5432`).

   ```bash
   uv run pytest
   ```

3. Run linters and the type checker before opening a pull request:

   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy approck_services
   ```

## Pull requests

- Keep changes focused and describe the motivation in the PR text.
- Add or update tests when behavior changes.
- Ensure CI passes (GitHub Actions runs tests against PostgreSQL when configured in the workflow).

## Security

Please report security issues privately as described in [SECURITY.md](SECURITY.md).
