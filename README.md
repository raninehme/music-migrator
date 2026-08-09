# music-migrator

Move all of your Spotify playlists and liked songs to TIDAL.

## What it does

- Migrates every playlist you own, plus collaborative playlists
- Optionally migrates only selected Spotify playlist IDs
- Migrates Spotify Liked Songs to TIDAL favorites
- Matches by ISRC first, then title, artist, album, and duration
- Reuses matching TIDAL playlists and preserves track order
- Caches confirmed matches for safe, faster reruns
- Retries TIDAL playlist precondition conflicts
- Runs read-only by default and writes unmatched tracks to `unmatched.csv`

## Requirements

- Python 3.11 or newer
- A Spotify Developer application
- A TIDAL account

## Setup

Create a Spotify application at <https://developer.spotify.com/dashboard>. Add this exact redirect
URI to the application:

```text
http://127.0.0.1:8888/callback
```

Install the project:

```bash
git clone https://github.com/raninehme/music-migrator.git
cd music-migrator
pyenv virtualenv 3.12.8 music-migrator
pyenv local music-migrator
python -m pip install -e .
cp example_config.yml config.yml
```

Put the Spotify client ID and secret in `config.yml`. The file is ignored by Git. Never commit it.
`max_concurrency` controls simultaneous track searches; `rate_limit` caps search requests per second.

## Run

Preview all changes without writing to TIDAL:

```bash
music-migrator
```

Apply the migration after checking the preview:

```bash
music-migrator --apply
```

Migrate one or more playlists only:

```bash
music-migrator --playlist SPOTIFY_PLAYLIST_ID --no-saved-tracks
```

Use `--quiet` for only errors and the final report, or `--debug` for dependency logs and tracebacks.

The first run opens Spotify and TIDAL authentication in your configured browser. Session files,
the match cache, configuration, and unmatched report remain local and are ignored by Git.

## Multiple accounts

Use a named profile to keep another person's Spotify login, TIDAL login, match cache, and unmatched
report separate:

```bash
music-migrator --profile girlfriend
music-migrator --profile girlfriend --apply
```

To remove the saved logins for a profile without deleting its match cache:

```bash
music-migrator --profile girlfriend --reset-auth
```
## Behavior and limits

Playlist names identify corresponding TIDAL playlists. The command stops if TIDAL has duplicate
playlist names, avoiding an ambiguous write. Existing playlists are updated to the Spotify order;
tracks that cannot be matched are omitted and reported. Local files and podcasts are skipped.

No music files are copied. Availability can differ by country and service catalog, so review
`unmatched.csv` after migration.

## Development

```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
python -m build
```

## License

[PolyForm Noncommercial License 1.0.0](LICENSE). Commercial use is not permitted.
