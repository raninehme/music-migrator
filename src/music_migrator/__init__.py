"""Service-independent music library migration."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("music-migrator")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = ["__version__"]
