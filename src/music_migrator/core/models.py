"""Compatibility imports for models that now live in domain and matching components."""

from music_migrator.domain.models import Playlist, Track
from music_migrator.matching.models import TrackMatch

__all__ = ["Playlist", "Track", "TrackMatch"]
