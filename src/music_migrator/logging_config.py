import logging


def configure_logging(*, quiet: bool = False, debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.WARNING if quiet else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

    dependency_level = logging.DEBUG if debug else logging.WARNING
    for name in ("requests", "urllib3", "spotipy", "tidalapi"):
        logging.getLogger(name).setLevel(dependency_level)
