# Contributing

Thank you for considering a contribution to **approck-services**.

## Getting started

1. Clone the repository and create a virtual environment (Poetry is what this repo uses today).

   ```bash
   git clone https://github.com/approck-pro/approck-services.git
   cd approck-services
   poetry install --all-extras
   ```

2. Run the test suite. Integration tests expect **PostgreSQL** with async access (same URL shape as in `tests/conftest.py`: user `postgres`, password `postgres`, database `postgres`, port `5432`).

   ```bash
   poetry run pytest
   ```

3. Run linters and the type checker before opening a pull request:

   ```bash
   poetry run ruff check .
   poetry run ruff format --check .
   poetry run mypy approck_services
   ```

## Pull requests

- Keep changes focused and describe the motivation in the PR text.
- Add or update tests when behavior changes.
- Ensure CI passes (GitHub Actions runs tests against PostgreSQL when configured in the workflow).

## Security

Please report security issues privately as described in [SECURITY.md](SECURITY.md).
