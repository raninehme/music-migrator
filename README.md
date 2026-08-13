# music-migrator

Move or combine Spotify and TIDAL playlists, liked songs, and favorites while preserving playlist order and reporting tracks that could not be matched.

## Features

- Migrate Spotify to TIDAL or TIDAL to Spotify.
- Replace destination playlists or safely combine both services.
- Include saved tracks, or migrate playlists only.
- Select one or more playlists by source playlist ID.
- Preview every migration with `--dry-run` before applying changes.
- Match tracks by ISRC first, then title, artist, album, and duration.
- Cache confirmed matches independently for each migration direction.
- Control search concurrency and request rate per profile.
- Keep authentication, caches, logs, and reports separate for every profile.
- Refresh cached matches with `--refresh-matches` when catalogs change.
- Reset saved login sessions with `--reset-auth` without deleting profile settings.
- Reduce console output with `--quiet` or include tracebacks with `--debug`.

## Requirements

- Python 3.11 or newer
- Spotify account and a [Spotify Developer application](https://developer.spotify.com/dashboard)
- TIDAL account

## Installation

```bash
python -m pip install git+https://github.com/raninehme/music-migrator.git
```

For development setup, see [Contributing](.github/CONTRIBUTING.md).

## Setup

In the Spotify Developer Dashboard, enable the Web API and add this exact redirect URI:

```text
http://127.0.0.1:8888/callback
```

Create a profile:

```bash
music-migrator --setup YOUR_PROFILE
```

Enter the Spotify client ID and secret when prompted. The first migration starts the Spotify and TIDAL login flows.

## Run a migration

Use one command shape for every migration:

```bash
music-migrator --profile YOUR_PROFILE \
  --from spotify \
  --to tidal \
  --mode replace \
  --dry-run
```

Review the output, then replace `--dry-run` with `--apply` to write changes.

### Options

| Option | Description |
| --- | --- |
| `--profile NAME` | Use an existing profile. |
| `--setup NAME` | Create a profile configuration and exit. |
| `--from {spotify,tidal}` | Select the source service. Defaults to `spotify`. |
| `--to {spotify,tidal}` | Select the destination service. Defaults to `tidal`. |
| `--mode {replace,combine}` | Replace destination playlist contents or combine both services. Defaults to `replace`. |
| `--dry-run` | Preview changes without writing. |
| `--apply` | Apply changes. One of `--dry-run` or `--apply` is required for migration. |
| `--playlist ID` | Migrate one source playlist. Repeat the flag for multiple playlists. |
| `--no-saved-tracks` | Skip Spotify Liked Songs and TIDAL favorites. |
| `--refresh-matches` | Clear route-specific cached matches before migrating. |
| `--reset-auth` | Remove saved Spotify and TIDAL login sessions, then exit. |
| `--quiet` | Show errors and the final report only. |
| `--debug` | Include debug logs and tracebacks. |
| `--version` | Print the installed version. |

Run `music-migrator --help` for the installed command reference.

## Migration modes

### Replace

The destination version of each non-empty source playlist is replaced with the matched source tracks. Destination-only tracks are removed.

Empty source playlists are intentionally skipped. Existing destination playlists are left unchanged and new empty playlists are not created. This prevents an accidentally emptied source playlist from deleting destination contents; empty playlists can be managed manually.

### Combine

Both directions run in sequence. Matched tracks from each service are retained and added to the other service without removing playlist tracks. `--from` determines the preferred playlist order and identifies which service owns IDs passed with `--playlist`.

Liked Songs and TIDAL favorites are add-only in both modes.

## Configuration

Each profile stores its configuration at `.music-migrator/profiles/NAME/config.yml`:

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

`max_concurrency` controls simultaneous catalog searches. `rate_limit` controls how many searches may start per second. Lower either value if a service begins throttling requests.

Boolean values must be YAML booleans such as `true` or `false`, not quoted strings. Concurrency and rate-limit values must be positive integers.

Profile data is ignored by Git. Never commit credentials, OAuth sessions, caches, logs, or exported personal music data.

## Reports and local state

Unmatched tracks are written per migration direction:

```text
.music-migrator/profiles/NAME/reports/SOURCE-to-DESTINATION/unmatched.csv
```

Runtime logs are written to:

```text
.music-migrator/profiles/NAME/logs/music-migrator.log
```

Confirmed matches are cached per direction. Matcher-version changes automatically invalidate older entries. Failed destination writes discard affected entries so the next run searches again. Use `--refresh-matches` to force a complete route refresh.

## Safety and limitations

- Nothing is written unless `--apply` is supplied.
- Empty source playlists are skipped in both modes.
- `combine` never removes playlist tracks.
- Saved tracks and favorites are always add-only.
- Interrupted playlist replacements attempt to restore the original destination contents before returning an error.
- Playlist names identify corresponding playlists; duplicate writable names stop the run.
- Local Spotify files and podcasts are skipped.
- Regional catalog differences can leave tracks unmatched.
- The tool migrates catalog references, not audio files.

## Troubleshooting

- **Login does not finish:** Confirm the redirect URI is exact and port `8888` is available.
- **Wrong account opens:** Run with `--reset-auth` for the affected profile.
- **Requests are throttled:** Lower `max_concurrency` and `rate_limit` in the profile configuration.
- **Tracks are missing:** Review the route-specific `unmatched.csv` and retry with `--refresh-matches`.
- **A playlist write fails:** The tool attempts restoration and exits with an error. Inspect the destination playlist and runtime log before retrying.

## Contributing

Bug reports and focused contributions are welcome. See the [contribution guide](.github/CONTRIBUTING.md), [security policy](.github/SECURITY.md), and [code of conduct](.github/CODE_OF_CONDUCT.md).

The codebase separates reusable migration behavior from service adapters, application orchestration, and CLI presentation:

```text
src/music_migrator/
├── application.py
├── cli.py
├── core/
└── services/
```

## License

[PolyForm Noncommercial License 1.0.0](LICENSE). Commercial use is not permitted.
