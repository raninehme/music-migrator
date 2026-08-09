import logging

from music_migrator.logging_config import configure_logging


def test_debug_logging_enables_debug_and_writes_file(tmp_path):
    log_path = tmp_path / "logs" / "music-migrator.log"
    configure_logging(log_path, debug=True)
    logging.getLogger("test").debug("diagnostic")
    logging.shutdown()

    assert logging.getLogger().level == logging.DEBUG
    assert "diagnostic" in log_path.read_text(encoding="utf-8")


def test_quiet_only_changes_console_while_file_keeps_info(tmp_path):
    log_path = tmp_path / "music-migrator.log"
    configure_logging(log_path, quiet=True)
    root = logging.getLogger()

    assert root.level == logging.INFO
    assert root.handlers[0].level == logging.WARNING
    assert root.handlers[1].level == logging.INFO
