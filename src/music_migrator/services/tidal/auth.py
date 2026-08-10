from pathlib import Path

import tidalapi


def create_tidal_session(session_path: Path) -> tidalapi.Session:
    """Create an authenticated TIDAL session from a profile-scoped session file."""
    session = tidalapi.Session()
    if not session.login_session_file(session_path):
        raise RuntimeError("TIDAL authentication failed")
    return session
