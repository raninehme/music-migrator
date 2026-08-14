# Contributing

Bug reports, documentation improvements, focused fixes, and new service adapters are welcome.

Open an issue before starting a large behavioral change or new integration. Keep pull requests focused and include tests for new behavior and bug fixes.

## Branch workflow

The default `main` branch contains the latest stable release. Feature, fix, test, and
documentation pull requests must target `release`, not `main`.

Create a branch from the latest `release` branch:

```bash
git fetch origin
git switch release
git pull --ff-only
git switch -c fix/short-description
```

Open the pull request with `release` as its base branch. Merged branches from this repository
are deleted automatically, while the protected `release` branch remains available for the next
contribution.

The `release` branch collects and validates the next release. Only the final release pull request
targets `main`. Before opening that pull request, the maintainer updates the package version in
`pyproject.toml` on `release`. The release-source check requires that version to be newer than the
version on `main` and requires the pull request to come from this repository's `release` branch.
After the release pull request is merged, the push to `main` runs the release workflow. That
workflow validates and builds the package, creates the matching `v<version>` tag, and publishes
the GitHub Release with the built wheel and source archive.

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
