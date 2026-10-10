# Contributing

Bug reports, documentation improvements, focused fixes, and new service adapters are welcome.

Open an issue before starting a large behavioral change or new integration. Keep pull requests focused and include tests for new behavior and bug fixes.

## Branch workflow

The default `main` branch contains the latest stable release. Feature, fix, test, and documentation pull requests must target `release`, not `main`.

Create a branch from the latest `release` branch:

```bash
git fetch origin
git switch release
git pull --ff-only
git switch -c fix/short-description
```

- Open feature and fix pull requests against `release`.
- `release` collects and validates changes for the next version.
- Before the final `release` → `main` pull request, update the version in `pyproject.toml`.
- The release-source check requires the pull request into `main` to come from `release` and have a newer version than `main`.
- Merging the release pull request triggers the release workflow, which tests, builds, tags, and creates the GitHub Release.
- After a successful release, `main` is merged back into `release` with a merge commit. Do not squash or rebase that sync.

Merged feature branches from this repository are deleted automatically. The protected `release` branch remains available for the next contribution.

## Development

Clone the repository, then install the development dependencies:

```bash
python -m pip install -e ".[dev]"
```

Run the checks before opening a pull request:

```bash
ruff format --check src tests
ruff check .
pytest
python -m build
```

## Project boundaries

- Put provider-neutral music and collection state in `domain/`.
- Put matching, normalization, scoring, and match-cache behavior in `matching/`.
- Put single-route migration orchestration in `migration/`.
- Put desired-state and operation planning in `reconciliation/`.
- Put resumable migration state in `persistence/`.
- Put authentication and API-specific workarounds in the relevant `services/` adapter.
- Put shared request/retry behavior in `transport/`.
- Put multi-route execution and provider wiring in `application.py`.
- Keep argument parsing and command dispatch in `cli.py`.
- Keep progress, report presentation, and unmatched CSV output in `cli_output.py`.
- Extend the service registry instead of adding service-name conditionals to provider-neutral migration code.

For deliberate breaking changes:

- Remove obsolete compatibility shims instead of carrying multiple formats indefinitely.
- Document changes to public CLI, configuration, or on-disk contracts.
- Use an appropriate major version for incompatible changes.
- Keep persisted-data schema migrations when they safely upgrade existing state in place.

Avoid unrelated refactors and new dependencies.

Do not include credentials, OAuth tokens, session files, caches, logs, playlist exports, or other personal music data.
