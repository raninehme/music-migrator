# music-migrator

Move or combine your Spotify and TIDAL libraries while keeping playlist order, liked tracks, favorites, and a clear report of anything that could not be matched.

## Features

- Spotify to TIDAL and TIDAL to Spotify
- One-way replacement or safe two-way combination
- Playlists, Spotify Liked Songs, and TIDAL favorites
- ISRC-first matching with title, artist, album, and duration fallback
- Concurrent searches with visible track progress
- Explicit dry runs before anything is changed
- Separate authentication, caches, logs, and reports for every profile

## Choose a mode

| Mode | What happens |
| --- | --- |
| `replace` | The destination playlist becomes identical to the source. Destination-only tracks can be removed. |
| `combine` | Matched tracks from both services are kept and added to both. No playlist tracks are removed. |

With `replace`, `--from` and `--to` define the copy direction. With `combine`, both services receive all matched tracks; `--from` chooses the preferred playlist order and the service used by any `--playlist` IDs.

## Installation

Requires Python 3.11 or newer, a TIDAL account, and a Spotify account with a [Spotify Developer application](https://developer.spotify.com/dashboard).

Install directly:

```bash
python -m pip install git+https://github.com/raninehme/music-migrator.git
```

Or use a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install git+https://github.com/raninehme/music-migrator.git
```

On Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1`.

## Quick start

### 1. Configure Spotify

In the Spotify Developer Dashboard, create an application, enable the Web API, and add this exact redirect URI:

```text
http://127.0.0.1:8888/callback
```

### 2. Create a profile

```bash
music-migrator --setup YOUR_PROFILE
```

Enter the Spotify client ID and secret when prompted. The first migration opens Spotify and TIDAL login in your browser.

### 3. Preview the migration

Replace TIDAL playlists with the Spotify versions:

```bash
music-migrator --profile YOUR_PROFILE \
  --from spotify \
  --to tidal \
  --mode replace \
  --dry-run
```

Or safely combine both libraries:

```bash
music-migrator --profile YOUR_PROFILE \
  --from spotify \
  --to tidal \
  --mode combine \
  --dry-run
```

Review both directional reports when using `combine`.

### 4. Apply it

Run the same command with `--apply` instead of `--dry-run`:

```bash
music-migrator --profile YOUR_PROFILE \
  --from spotify \
  --to tidal \
  --mode combine \
  --apply
```

## Configuration

Each profile has its own `.music-migrator/profiles/NAME/config.yml`:

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

`max_concurrency` controls simultaneous searches. `rate_limit` limits how many searches may start per second. Lower them if a service begins throttling requests. Profile data is ignored by Git; never commit credentials or saved sessions.

## Useful commands

Move in the other direction:

```bash
music-migrator --profile YOUR_PROFILE \
  --from tidal \
  --to spotify \
  --mode replace \
  --dry-run
```

Select individual source playlists and skip liked tracks or favorites:

```bash
music-migrator --profile YOUR_PROFILE \
  --from spotify \
  --to tidal \
  --mode combine \
  --playlist SPOTIFY_PLAYLIST_ID \
  --no-saved-tracks \
  --dry-run
```

Reset saved logins without deleting configuration, caches, or reports:

```bash
music-migrator --profile YOUR_PROFILE --reset-auth
```

Use `--quiet` for the final report only, `--debug` for tracebacks, and `--help` for every option.

## Matching, logs, and reports

The matcher uses ISRC when available, then scores title, artists, album, and duration. Confirmed matches are cached separately for each direction so reruns are faster and consistent.

Tracks without a reliable match are skipped and written to:

```text
.music-migrator/profiles/NAME/reports/SOURCE-to-DESTINATION/unmatched.csv
```

Runtime details are written to `.music-migrator/profiles/NAME/logs/music-migrator.log`.

## Safety and limitations

- `--dry-run` never creates or updates playlists.
- `--apply` is always required for changes.
- `combine` never removes playlist tracks.
- Liked Songs and favorites are add-only in both modes.
- Playlist names identify matching playlists; duplicate names stop the run.
- Local Spotify files and podcasts are skipped.
- Regional catalog differences can leave tracks unmatched.
- The tool moves catalog references, not audio files.

## Troubleshooting

- **Login does not finish:** Confirm the redirect URI is exact and port `8888` is free.
- **Wrong account opens:** Run `music-migrator --profile YOUR_PROFILE --reset-auth`.
- **Requests are throttled:** Lower `max_concurrency` and `rate_limit` in `config.yml`.
- **Tracks are missing:** Review the route's `unmatched.csv` report.

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
