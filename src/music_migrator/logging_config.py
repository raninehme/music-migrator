import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    log_path: Path,
    *,
    quiet: bool = False,
    debug: bool = False,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if debug else logging.WARNING if quiet else logging.INFO)
    console.setFormatter(formatter)

    log_file = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    log_file.setLevel(logging.DEBUG if debug else logging.INFO)
    log_file.setFormatter(formatter)

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        handlers=[console, log_file],
        force=True,
    )

    dependency_level = logging.DEBUG if debug else logging.WARNING
    for name in ("requests", "urllib3", "spotipy", "tidalapi"):
        logging.getLogger(name).setLevel(dependency_level)
