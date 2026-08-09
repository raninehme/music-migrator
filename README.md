# music-migrator

Move Spotify playlists and Liked Songs to TIDAL with safe previews, concurrent matching, isolated account profiles, and useful migration reports.

## Features

- Migrates every owned or collaborative Spotify playlist
- Migrates Spotify Liked Songs to TIDAL favorites
- Supports selecting individual playlists by Spotify ID
- Matches by ISRC first, then searches and scores title, artists, album, and duration
- Preserves playlist order and reuses corresponding TIDAL playlists
- Searches concurrently with configurable worker and request limits
- Caches confirmed matches for faster, consistent reruns
- Runs as a read-only dry run unless `--apply` is supplied
- Keeps authentication, caches, logs, and reports isolated by profile
- Shows track-level progress and writes rotating logs
- Produces a CSV containing tracks that could not be matched

## Requirements

- Python 3.11 or newer
- A Spotify account and [Spotify Developer application](https://developer.spotify.com/dashboard)
- A TIDAL account

## Quick start

Clone and install the project:

```bash
git clone https://github.com/raninehme/music-migrator.git
cd music-migrator
pyenv virtualenv 3.12.8 music-migrator
pyenv local music-migrator
python -m pip install -e .
cp example_config.yml config.yml
```

Create an application in the Spotify Developer Dashboard, select the Web API, and register this exact redirect URI:

```text
http://127.0.0.1:8888/callback
```

Add the application's client ID and client secret to `config.yml`, then preview the migration:

```bash
music-migrator --profile rani
```

Review the summary and unmatched report. When ready, apply the same migration:

```bash
music-migrator --profile rani --apply
```

The first run opens Spotify and TIDAL authentication in your configured browser.

## Configuration

`config.yml` contains shared application and migration settings:

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

`max_concurrency` controls simultaneous TIDAL searches. `rate_limit` limits how many search requests may start per second. The defaults are a practical starting point; lower them if the service begins rejecting requests.

`config.yml` is ignored by Git. Never commit Spotify credentials or profile data.

## Profiles

`--profile` is required for every command. Each name represents one Spotify-to-TIDAL account pairing, preventing a later migration from silently reusing another person's login or match cache.

```bash
music-migrator --profile rani
music-migrator --profile girlfriend
```

Profile names may contain letters, numbers, underscores, and hyphens. Local state is stored as:

```text
.music-migrator/
└── profiles/
    └── rani/
        ├── spotify-session.json
        ├── tidal-session.json
        ├── matches.sqlite3
        ├── logs/
        │   └── music-migrator.log
        └── reports/
            └── unmatched.csv
```

To authenticate a profile with different accounts, remove only its saved login sessions:

```bash
music-migrator --profile rani --reset-auth
```

The match cache and previous reports remain available.

## Migration commands

Preview all playlists and Liked Songs:

```bash
music-migrator --profile rani
```

Apply all changes:

```bash
music-migrator --profile rani --apply
```

Migrate selected playlists and skip Liked Songs:

```bash
music-migrator --profile rani \
  --playlist SPOTIFY_PLAYLIST_ID \
  --playlist ANOTHER_PLAYLIST_ID \
  --no-saved-tracks
```

Use a different config file:

```bash
music-migrator --profile rani --config path/to/config.yml
```

Use `--quiet` for errors and the final report only. Use `--debug` for detailed diagnostics and tracebacks. Run `music-migrator --help` for the complete CLI reference.

## Matching and safety

The matcher first tries the recording's ISRC. When an exact identifier is unavailable, it searches TIDAL using normalized title and primary-artist queries, then compares title, artists, album, and duration. Confirmed matches are cached per profile.

Dry-run mode is always the default. It authenticates, loads the source library, searches TIDAL, and reports planned changes without modifying the destination. `--apply` is required to create or update playlists and favorites.

Tracks without a sufficiently reliable match are omitted instead of inserting a questionable result. They are written to the profile's `reports/unmatched.csv` for review.

## Logs and reports

Console output shows migration stages and track progress. Each profile also receives a persistent log at `logs/music-migrator.log`. Logs rotate at 5 MiB and retain three backups.

The unmatched CSV contains Spotify ID, title, artists, album, and ISRC. A successful run with no unmatched tracks removes the previous unmatched report so stale results are not mistaken for current ones.

## Behavior and limitations

- Playlist names identify corresponding TIDAL playlists.
- Duplicate TIDAL playlist names stop the run rather than risk updating the wrong playlist.
- Existing destination playlists are reordered to match Spotify.
- Local Spotify files and podcasts are skipped.
- Music files are not copied; the tool maps catalog entries between services.
- Catalog and regional availability differ, so some tracks cannot be migrated automatically.
- Review the dry-run summary and unmatched report before using `--apply`.

## Troubleshooting

### The browser opens but authentication does not finish

Confirm the Spotify application uses `http://127.0.0.1:8888/callback` exactly. If port 8888 is occupied in WSL, identify the process with `fuser 8888/tcp` and stop only the stale process before retrying.

### The wrong account opens

Reset the selected profile, then run it again and sign in with the intended Spotify and TIDAL accounts:

```bash
music-migrator --profile rani --reset-auth
music-migrator --profile rani
```

### Searches are throttled or unstable

Reduce `max_concurrency` and `rate_limit` in `config.yml`, then rerun. Confirmed cached matches will be reused.

### Some tracks remain unmatched

Check the profile's `reports/unmatched.csv`. Editions, remasters, regional catalog differences, and unavailable releases can prevent a reliable automatic match.

## Development

Install development dependencies and run all checks:

```bash
python -m pip install -e ".[dev]"
ruff format --check src tests
ruff check .
pytest
python -m build
```

Bug reports and focused contributions are welcome. See the [contribution guide](.github/CONTRIBUTING.md), [security policy](.github/SECURITY.md), and [code of conduct](.github/CODE_OF_CONDUCT.md).

## License

[PolyForm Noncommercial License 1.0.0](LICENSE). Commercial use is not permitted.
