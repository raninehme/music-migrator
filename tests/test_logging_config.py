import logging

from music_migrator.logging_config import configure_logging


def test_debug_logging_enables_debug_and_dependency_logs():
    configure_logging(debug=True)
    assert logging.getLogger().level == logging.DEBUG
    assert logging.getLogger("urllib3").level == logging.DEBUG


def test_quiet_logging_only_shows_warnings():
    configure_logging(quiet=True)
    assert logging.getLogger().level == logging.WARNING
