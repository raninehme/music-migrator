# music-migrator

Move or combine Spotify and TIDAL playlists, liked songs, and favorites while preserving playlist order and reporting tracks that could not be matched.

## Features

- Migrate Spotify to TIDAL or TIDAL to Spotify.
- Replace destination playlists or safely combine both services.
- Include saved tracks, or migrate playlists only.
- Select one or more playlists by source playlist ID.
- Preview every migration with `--dry-run` before applying changes.
- Resume interrupted apply runs from current destination state.
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

Profile authentication sessions are stored under:

```text
.music-migrator/profiles/NAME/sessions/
├── spotify.json
└── tidal.json
```

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
| `--refresh-matches` | Clear cached matches for every route executed by this command after confirmation. |
| `--yes` | Confirm `--refresh-matches` non-interactively. |
| `--reset-auth` | Remove saved Spotify and TIDAL login sessions, then exit. |
| `--quiet` | Show errors and the final report only. |
| `--debug` | Include debug logs and tracebacks. |
| `--version` | Print the installed version. |

Run `music-migrator --help` for the installed command reference.

## Migration modes

### Replace

The destination version of each non-empty source playlist is replaced with the matched source tracks. Destination-only tracks are removed.

Empty source playlists are intentionally skipped. Existing destination playlists are left unchanged and new empty playlists are not created. A non-empty source playlist for which no tracks can be matched is also left untouched and never creates an empty destination playlist. Partial matches still proceed with the tracks that were matched.

### Combine

Both directions run in sequence. Matched tracks from each service are retained and added to the other service without removing playlist tracks. `--from` determines the preferred playlist order and identifies which service owns IDs passed with `--playlist`.

A non-empty playlist with zero matched tracks is a no-op in combine mode as well; an existing destination playlist is left unchanged and a missing one is not created.

Liked Songs and TIDAL favorites are add-only in both modes.

## Configuration

Each profile stores its configuration at `.music-migrator/profiles/NAME/config.yml`:

```yaml
services:
  spotify:
    client_id: your_client_id
    client_secret: your_client_secret
    redirect_uri: http://127.0.0.1:8888/callback
    open_browser: true

    # Optional request limits. Uncomment only to override the safe defaults.
    # requests:
    #   max_concurrency: 3
    #   rate_limit: 3

  # TIDAL authentication starts when a migration first uses TIDAL.
  # tidal:
  #   requests:
  #     max_concurrency: 8
  #     rate_limit: 8

include_saved_tracks: true
```

Each destination adapter provides safe request defaults. Most users should leave the commented settings unchanged. Advanced users can override both `max_concurrency` and `rate_limit` under a service's `requests` section.

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

Confirmed matches are cached per direction. Matcher-version changes automatically invalidate older entries. Destination write failures do not invalidate successful matches, so a retry can reuse matching work and reconcile the destination again. Use `--refresh-matches` only when a complete rebuild is necessary. Replace mode clears the requested route; combine mode clears both directions. The command asks for confirmation because every track must be searched again.

Apply runs also checkpoint migration and reconciliation-operation progress per direction. If an apply run is interrupted, rerunning the same route, mode, playlist selection, and saved-track selection resumes that run automatically. The destination service is always read again first and reconciliation is rebuilt from its current state; stale local checkpoints never override remote state. An operation that is no longer required is marked superseded, while only the operation still required by the live destination is applied.

Dry runs do not create or update resume state.

## Safety and limitations

- Nothing is written unless `--apply` is supplied.
- Empty source playlists are skipped in both modes.
- Non-empty playlists with zero matched tracks are also skipped in both modes.
- `combine` never removes playlist tracks.
- Saved tracks and favorites are always add-only.
- Interrupted playlist replacements attempt to restore the original destination contents before returning an error.
- Interrupted apply runs can resume from the destination state observed on the next run.
- Playlist names identify corresponding playlists; duplicate writable names stop the run.
- Local Spotify files and podcasts are skipped.
- Regional catalog differences can leave tracks unmatched.
- The tool migrates catalog references, not audio files.

## Troubleshooting

- **Login does not finish:** Confirm the redirect URI is exact and port `8888` is available.
- **Wrong account opens:** Run with `--reset-auth` for the affected profile.
- **Requests are throttled:** Lower `max_concurrency` and `rate_limit` under the destination service's `requests` configuration.
- **Tracks are missing:** Review the route-specific `unmatched.csv`. Use `--refresh-matches` only when rebuilding every cached match is necessary because it can consume significant API quota.
- **A playlist write fails:** The tool attempts restoration and exits with an error. Inspect the destination playlist and runtime log before retrying; rerunning the same apply scope resumes from the current destination state.

## Contributing

Bug reports and focused contributions are welcome. See the [contribution guide](.github/CONTRIBUTING.md), [security policy](.github/SECURITY.md), and [code of conduct](.github/CODE_OF_CONDUCT.md).

The codebase keeps provider-neutral state and behavior separate from provider APIs and application wiring:

```text
src/music_migrator/
├── application.py
├── cli.py
├── cli_output.py
├── domain/
├── matching/
├── migration/
├── persistence/
├── reconciliation/
├── services/
└── transport/
```

`domain` defines provider-neutral music and collection state, `matching` resolves source tracks to destination catalog entries, `reconciliation` turns current and desired collection state into provider-neutral operations, `migration` coordinates those components for one route, `persistence` checkpoints resumable progress, `services` contains provider adapters and registration, and `transport` contains shared request retry behavior. `cli.py` handles command parsing and dispatch while `cli_output.py` owns progress and report presentation.

## License

[Apache License 2.0](LICENSE).
