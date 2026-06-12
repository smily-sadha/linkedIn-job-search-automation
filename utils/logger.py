"""Colored console + daily-rotating file logger."""
import logging
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from config.config import LOG_DIR

_COLORS = {
    "DEBUG": "\033[37m",     # grey
    "INFO": "\033[36m",      # cyan
    "WARNING": "\033[33m",   # yellow
    "ERROR": "\033[31m",     # red
    "CRITICAL": "\033[41m",  # red bg
}
_RESET = "\033[0m"


class _ColorFormatter(logging.Formatter):
    def format(self, record):
        msg = super().format(record)
        color = _COLORS.get(record.levelname, "")
        return f"{color}{msg}{_RESET}" if color and sys.stdout.isatty() else msg


_configured = set()


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if name in _configured:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_ColorFormatter(fmt, datefmt))
    logger.addHandler(console)

    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    log_file = Path(LOG_DIR) / f"run_{datetime.now():%Y%m%d}.log"
    fileh = TimedRotatingFileHandler(log_file, when="midnight", backupCount=14, encoding="utf-8")
    fileh.setFormatter(logging.Formatter(fmt, datefmt))
    logger.addHandler(fileh)

    _configured.add(name)
    return logger
