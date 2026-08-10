# music-migrator

music-migrator moves or combines playlists and saved tracks between Spotify and TIDAL. It matches recordings across both catalogs and only writes changes when `--apply` is explicit.

It migrates catalog references, not audio files. Use a dry run first to review match counts and tracks that could not be found.

## Features

- Supports Spotify to TIDAL and TIDAL to Spotify
- Offers one-way replacement and safe two-way combination
- Migrates playlists, Spotify Liked Songs, and TIDAL favorites
- Matches by ISRC first, then title, artists, album, and duration
- Searches concurrently with configurable worker and request limits
- Provides explicit `--dry-run` and `--apply` modes
- Isolates accounts, caches, logs, and reports by profile and direction

## Requirements

- Python 3.11 or newer
- A Spotify account and [Spotify Developer application](https://developer.spotify.com/dashboard)
- A TIDAL account

## Installation

Install directly with pip:

```bash
python -m pip install git+https://github.com/raninehme/music-migrator.git
```

Or use a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # Linux, macOS, or WSL
python -m pip install git+https://github.com/raninehme/music-migrator.git
```

On Windows PowerShell, activate it with `.venv\Scripts\Activate.ps1`.

For an editable development install:

```bash
git clone https://github.com/raninehme/music-migrator.git
cd music-migrator
python -m pip install -e .
```

## Quick start

Run commands from the directory where you want the local `.music-migrator` profile data stored.

Create a Spotify application in the Spotify Developer Dashboard, select the Web API, and register this exact redirect URI:

```text
http://127.0.0.1:8888/callback
```

Create a profile and enter the Spotify client ID and secret when prompted:

```bash
music-migrator --setup YOUR_PROFILE
```

Preview the default Spotify to TIDAL replacement:

```bash
music-migrator --profile YOUR_PROFILE --dry-run
```

Review the summary and unmatched report before applying it:

```bash
music-migrator --profile YOUR_PROFILE --apply
```

To migrate in the other direction:

```bash
music-migrator --profile YOUR_PROFILE --from tidal --to spotify --dry-run
music-migrator --profile YOUR_PROFILE --from tidal --to spotify --apply
```

The first run opens Spotify and TIDAL authentication in your configured browser.

## Configuration

Each profile contains its own `config.yml`:

```yaml
spotify:
  client_id: your_client_id
  client_secret: your_client_secret
  redirect_uri: http://127.0.0.1:8888/callback
  open_browser: true

include_saved_tracks: true

max_concurrency: 10
rate_limit: 10
```

`max_concurrency` controls simultaneous destination searches. `rate_limit` limits how many search requests may start per second. The defaults are a practical starting point; lower them if the destination begins rejecting requests.

Profile data is ignored by Git. Never commit Spotify credentials or saved sessions.

## Profiles

Create each profile once with `--setup NAME`. Use `--profile NAME` for migrations and authentication resets. Profiles prevent one migration from silently reusing another account's login or match cache.

```bash
music-migrator --setup girlfriend
music-migrator --profile girlfriend --dry-run
```

Profile names may contain letters, numbers, underscores, and hyphens. Local state is stored as:

```text
.music-migrator/
+-- profiles/
    +-- YOUR_PROFILE/
        +-- config.yml
        +-- spotify-session.json
        +-- tidal-session.json
        +-- cache/
        |   +-- spotify-to-tidal.sqlite3
        |   +-- tidal-to-spotify.sqlite3
        +-- logs/
        |   +-- music-migrator.log
        +-- reports/
            +-- spotify-to-tidal/
            |   +-- unmatched.csv
            +-- tidal-to-spotify/
                +-- unmatched.csv
```

To remove only a profile's saved logins:

```bash
music-migrator --profile YOUR_PROFILE --reset-auth
```

The profile configuration, match cache, logs, and reports remain available.

## Modes

`replace` is the default. It makes the destination playlist match the source exactly, including its order. Destination-only playlist tracks can be removed.

```bash
music-migrator --profile YOUR_PROFILE --mode replace --dry-run
```

`combine` runs in both directions. It keeps tracks found on either service, adds the missing tracks to both, and removes no playlist tracks. The service selected by `--from` supplies the primary playlist order; tracks found only on the other service are appended.

```bash
music-migrator --profile YOUR_PROFILE \
  --from tidal \
  --to spotify \
  --mode combine \
  --dry-run
```

After reviewing both directional reports, replace `--dry-run` with `--apply`. Spotify Liked Songs and TIDAL favorites are add-only in either mode.

To replace Spotify playlists from TIDAL instead:

```bash
music-migrator --profile YOUR_PROFILE --from tidal --to spotify --dry-run
```

Select source playlists by ID and skip saved tracks or favorites:

```bash
music-migrator --profile YOUR_PROFILE \
  --from tidal \
  --to spotify \
  --dry-run \
  --playlist TIDAL_PLAYLIST_ID \
  --playlist ANOTHER_PLAYLIST_ID \
  --no-saved-tracks
```

`--playlist` may be repeated and expects an ID from the selected source service. Use `--quiet` for errors and the final report only. Use `--debug` for detailed diagnostics and tracebacks. Run `music-migrator --help` for the complete CLI reference.

## Matching and safety

The matcher first tries the recording's ISRC. When an exact identifier is unavailable, it searches the destination service and compares title, artists, album, and duration. Confirmed matches are cached separately for each direction.

Migration mode must be explicit. `--dry-run` authenticates, loads the source library, searches the destination, and reports planned changes without modifying it. `--apply` is required to create or update playlists and saved tracks.

Tracks without a sufficiently reliable match are omitted instead of inserting a questionable result. They are written to each route's `reports/<source>-to-<destination>/unmatched.csv`.

## Logs and reports

Console output shows migration stages and track progress. Each profile also receives a persistent log at `logs/music-migrator.log`. Logs rotate at 5 MiB and retain three backups.

The unmatched CSV contains source ID, title, artists, album, and ISRC. A successful run with no unmatched tracks removes that route's previous report so stale results are not mistaken for current ones.

## Behavior and limitations

- Playlist names identify corresponding playlists across services.
- `replace` may reorder playlists and remove destination-only playlist tracks.
- `combine` preserves tracks from both services and uses the selected source's order first.
- Liked Songs and favorites are add-only; neither mode removes them.
- Duplicate playlist names stop the run rather than risk updating the wrong playlist.
- Local Spotify files and podcasts are skipped.
- Music files are not copied; the tool maps catalog entries between services.
- Catalog and regional availability differ, so some tracks cannot be migrated automatically.
- Review the dry-run summary and unmatched report before using `--apply`.

## Troubleshooting

- **Authentication does not finish:** Confirm the Spotify redirect URI is exactly `http://127.0.0.1:8888/callback` and that port 8888 is available.
- **Wrong account opens:** Reset the profile sessions and sign in again:

  ```bash
  music-migrator --profile YOUR_PROFILE --reset-auth
  ```

- **Searches are throttled:** Lower `max_concurrency` and `rate_limit` in the profile's `config.yml`.
- **Tracks remain unmatched:** Check `reports/<source>-to-<destination>/unmatched.csv`. Editions, regional availability, and catalog differences can prevent a reliable match.

## Development

```bash
git clone https://github.com/raninehme/music-migrator.git
cd music-migrator
python -m pip install -e ".[dev]"
ruff format --check src tests
ruff check .
pytest
python -m build
```

Bug reports and focused contributions are welcome. See the [contribution guide](.github/CONTRIBUTING.md), [security policy](.github/SECURITY.md), and [code of conduct](.github/CODE_OF_CONDUCT.md).

## License

[PolyForm Noncommercial License 1.0.0](LICENSE). Commercial use is not permitted.
