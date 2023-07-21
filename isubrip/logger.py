from functools import lru_cache
import logging

from isubrip.constants import ANSI_COLORS, LOGGING_DATE_FORMAT, LOGGING_FILE_METADATA, PACKAGE_NAME, RESET_COLOR

logger = logging.getLogger(PACKAGE_NAME)


def set_logger(_logger: logging.Logger) -> None:
    """
    Set an external logger to be used by the package.

    Args:
        _logger (logging.Logger): A logger instance to be used by the package.
    """
    global logger
    logger = _logger


@lru_cache
def get_formatter(fmt: str, datefmt=LOGGING_DATE_FORMAT) -> logging.Formatter:
    """
    Get a formatter instance, and utilize caching.

    Args:
        fmt (str): The format of the formatter.
        datefmt (str, optional): The date format of the formatter. Defaults to LOGGING_DATE_FORMAT.

    Returns:
        logging.Formatter: A formatter instance.
    """
    return logging.Formatter(fmt=fmt, datefmt=datefmt)


class CustomStdoutFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if record.levelno in ANSI_COLORS:
            log_format = ANSI_COLORS[record.levelno] + "%(message)s" + RESET_COLOR

        else:
            log_format = "%(message)s"

        formatter = get_formatter(fmt=log_format, datefmt=LOGGING_DATE_FORMAT)
        return formatter.format(record)


class CustomLogFileFormatter(logging.Formatter):
    _log_format = LOGGING_FILE_METADATA + "%(message)s"
    _formatter = get_formatter(fmt=_log_format, datefmt=LOGGING_DATE_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        return self._formatter.format(record)
