# Contributing

Bug reports, documentation improvements, focused fixes, and new service adapters are welcome.

Open an issue before starting a large behavioral change or new integration. Keep pull requests focused and include tests for new behavior and bug fixes.

## Development setup

Use Python 3.11 or newer and install the development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run the same checks used by CI:

```bash
ruff format --check src tests
ruff check .
pytest
python -m build
```

## Project boundaries

- Put service-independent models, matching, retries, caching, and migration behavior in `core/`.
- Put authentication and API-specific workarounds in the relevant `services/` adapter.
- Put multi-route execution in `application.py`.
- Keep argument parsing, console presentation, and command error handling in `cli.py`.
- Extend the service registry instead of adding service-name conditionals to the core migration flow.

Preserve backward compatibility unless the pull request explicitly explains a breaking change. Avoid unrelated refactors and new dependencies.

Do not include credentials, OAuth tokens, session files, caches, logs, playlist exports, or other personal music data.
