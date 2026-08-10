from pathlib import Path

import requests
import tidalapi


def create_tidal_session(session_path: Path) -> tidalapi.Session:
    """Create an authenticated TIDAL session from a profile-scoped session file."""
    session = tidalapi.Session()
    try:
        authenticated = session.login_session_file(session_path)
    except requests.HTTPError as error:
        status = getattr(error.response, "status_code", None)
        if status != 401:
            raise
        session_path.unlink(missing_ok=True)
        session = tidalapi.Session()
        authenticated = session.login_session_file(session_path)

    if not authenticated:
        raise RuntimeError("TIDAL authentication failed")
    return session
