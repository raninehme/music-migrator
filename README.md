# music-migrator

Move playlists and saved tracks between Spotify and TIDAL in either direction with safe previews, concurrent matching, isolated profiles, and useful migration reports.

## Features

- Migrates Spotify to TIDAL and TIDAL to Spotify
- Migrates playlists plus Spotify Liked Songs or TIDAL favorites
- Finds reliable matches while preserving playlist order
- Supports fast concurrent searches with progress tracking
- Provides explicit preview and apply modes
- Keeps accounts, route-specific caches, logs, and reports isolated by profile

## Requirements

- Python 3.11 or newer
- A Spotify account and [Spotify Developer application](https://developer.spotify.com/dashboard)
- A TIDAL account

Check your Python version with:

```bash
python --version
```

## Installation

### Install directly with pip

```bash
python -m pip install git+https://github.com/raninehme/music-migrator.git
```

### Install in a virtual environment

A virtual environment is recommended because it keeps music-migrator and its dependencies isolated.

```bash
python -m venv .venv
```

Activate it on Linux, macOS, or WSL:

```bash
source .venv/bin/activate
```

Or activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Then install music-migrator:

```bash
python -m pip install git+https://github.com/raninehme/music-migrator.git
```

To install an editable checkout for development:

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

Preview Spotify to TIDAL. This is the default route, so the service flags are optional:

```bash
music-migrator --profile YOUR_PROFILE --from spotify --to tidal --dry-run
```

Review the summary and unmatched report, then apply the migration:

```bash
music-migrator --profile YOUR_PROFILE --from spotify --to tidal --apply
```

To migrate in the other direction:

```bash
music-migrator --profile YOUR_PROFILE --from tidal --to spotify --dry-run
music-migrator --profile YOUR_PROFILE --from tidal --to spotify --apply
```

The first run for a route opens Spotify and TIDAL authentication in your configured browser. Always review a dry run before applying changes.

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

## Migration commands

Spotify to TIDAL remains the default route:

```bash
music-migrator --profile YOUR_PROFILE --dry-run
music-migrator --profile YOUR_PROFILE --apply
```

The equivalent explicit commands are:

```bash
music-migrator --profile YOUR_PROFILE --from spotify --to tidal --dry-run
music-migrator --profile YOUR_PROFILE --from spotify --to tidal --apply
```

For TIDAL to Spotify:

```bash
music-migrator --profile YOUR_PROFILE --from tidal --to spotify --dry-run
music-migrator --profile YOUR_PROFILE --from tidal --to spotify --apply
```

Preview selected source playlists and skip saved tracks:

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

Tracks without a sufficiently reliable match are omitted instead of inserting a questionable result. They are written to the selected route's `reports/<source>-to-<destination>/unmatched.csv`.

## Logs and reports

Console output shows migration stages and track progress. Each profile also receives a persistent log at `logs/music-migrator.log`. Logs rotate at 5 MiB and retain three backups.

The unmatched CSV contains source ID, title, artists, album, and ISRC. A successful run with no unmatched tracks removes that route's previous report so stale results are not mistaken for current ones.

## Behavior and limitations

- Playlist names identify corresponding playlists on the destination service.
- Duplicate destination playlist names stop the run rather than risk updating the wrong playlist.
- Existing destination playlists are reordered to match the source.
- Local Spotify files and podcasts are skipped.
- Music files are not copied; the tool maps catalog entries between services.
- Catalog and regional availability differ, so some tracks cannot be migrated automatically.
- Review the dry-run summary and unmatched report before using `--apply`.

## Troubleshooting

### The browser opens but authentication does not finish

Confirm the Spotify application uses `http://127.0.0.1:8888/callback` exactly. If port 8888 is already occupied, identify the process before stopping it.

Linux or WSL:

```bash
ss -ltnp 'sport = :8888'
```

macOS:

```bash
lsof -nP -iTCP:8888 -sTCP:LISTEN
```

Windows PowerShell:

```powershell
Get-NetTCPConnection -LocalPort 8888 -State Listen
```

Once you have confirmed the process is stale, stop it using the appropriate system tool and retry the migration.

### The wrong account opens

Reset the selected profile, then run it again and sign in with the intended Spotify and TIDAL accounts:

```bash
music-migrator --profile YOUR_PROFILE --reset-auth
music-migrator --profile YOUR_PROFILE --dry-run
```

### Searches are throttled or unstable

Reduce `max_concurrency` and `rate_limit` in the profile's `config.yml`, then rerun. Confirmed cached matches will be reused.

### Some tracks remain unmatched

Check the selected route's `reports/<source>-to-<destination>/unmatched.csv`. Editions, remasters, regional catalog differences, and unavailable releases can prevent a reliable automatic match.

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
