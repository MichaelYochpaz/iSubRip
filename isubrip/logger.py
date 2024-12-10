from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from rich.highlighter import NullHighlighter
from rich.logging import RichHandler

from isubrip.constants import (
    LOG_FILE_NAME,
    LOG_FILES_PATH,
    PACKAGE_NAME,
)

if TYPE_CHECKING:
    from rich.console import Console

BBCOE_REGEX = re.compile(
    r"(?i)(?P<opening_tag>\[(?P<tag_name>[a-z#@][^[]*?)])(?P<content>.*)(?P<closing_tag>\[/(?P=tag_name)])")
LOG_FILE_METADATA = "[%(asctime)s | %(levelname)s | %(threadName)s | %(filename)s::%(funcName)s::%(lineno)d] "

logger = logging.getLogger(PACKAGE_NAME)


def set_logger(_logger: logging.Logger) -> None:
    """
    Set an external logger to be used by the package.

    Args:
        _logger (logging.Logger): A logger instance to be used by the package.
    """
    global logger
    logger = _logger


class CustomStdoutFormatter(RichHandler):
    def __init__(self, console: Console | None = None, debug_mode: bool = False) -> None:
        super().__init__(
            console=console,
            show_time=debug_mode,
            show_level=debug_mode,
            show_path=debug_mode,
            highlighter=NullHighlighter(),
            markup=True,
            log_time_format="%H:%M:%S",
            rich_tracebacks=debug_mode,
            tracebacks_extra_lines=0,
        )

    def format(self, record: logging.LogRecord) -> str:
        if record.levelno == logging.ERROR:
            record.msg = f"[red]{record.getMessage()}[/red]"
        elif record.levelno == logging.WARNING:
            record.msg = f"[dark_orange]{record.getMessage()}[/dark_orange]"
        elif record.levelno == logging.DEBUG:
            record.msg = f"[grey54]{record.getMessage()}[/grey54]"
        return super().format(record)


class CustomLogFileFormatter(logging.Formatter):
    _log_format = LOG_FILE_METADATA + "%(message)s"

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()

        # Remove Rich markup tags
        while match := BBCOE_REGEX.search(message):
            message = message[:match.start()] + match.group('content') + message[match.end():]
        
        return logging.Formatter(fmt=LOG_FILE_METADATA + message, datefmt=r"%Y-%m-%d %H:%M:%S").format(record)


def setup_loggers(stdout_output: bool = True, stdout_console: Console | None = None,
                  stdout_loglevel: int = logging.INFO, logfile_output: bool = True,
                  logfile_loglevel: int = logging.DEBUG) -> None:
    """
    Configure loggers.

    Args:
        stdout_output (bool, optional): Whether to output logs to STDOUT. Defaults to True.
        stdout_console (Console | None, optional): A Rich console instance to be used for STDOUT logging.
            Relevant only if `stdout_output` is True. Defaults to None.
        stdout_loglevel (int, optional): Log level for STDOUT logger. Relevant only if `stdout_output` is True.
            Defaults to logging.INFO.
        logfile_output (bool, optional): Whether to output logs to a logfile. Defaults to True.
        logfile_loglevel (int, optional): Log level for logfile logger. Relevant only if `logfile_output` is True.
            Defaults to logging.DEBUG.
    """
    logger.setLevel(logging.DEBUG)

    if stdout_output:
        debug_mode = (stdout_loglevel == logging.DEBUG)
        stdout_handler = CustomStdoutFormatter(
            debug_mode=debug_mode,
            console=stdout_console,
        )
        stdout_handler.setLevel(stdout_loglevel)
        logger.addHandler(stdout_handler)

    if logfile_output:
        if not LOG_FILES_PATH.is_dir():
            logger.debug("Logs directory could not be found and will be created.")
            LOG_FILES_PATH.mkdir()

        logfile_path = LOG_FILES_PATH / LOG_FILE_NAME
        logfile_handler = logging.FileHandler(filename=logfile_path, encoding="utf-8")
        logfile_handler.setLevel(logfile_loglevel)
        logfile_handler.setFormatter(CustomLogFileFormatter())
        logger.debug(f"Log file location: '{logfile_path}'")
        logger.addHandler(logfile_handler)
