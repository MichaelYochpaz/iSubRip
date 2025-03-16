from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import ClassVar, Dict, Optional, TYPE_CHECKING

from rich.highlighter import NullHighlighter
from rich.logging import RichHandler

from isubrip.cli import console
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


def set_logger(_logger: logging.Logger) -> None:
    """
    Set an external logger to be used by the package.

    Args:
        _logger (logging.Logger): A logger instance to be used by the package.
    """
    global logger
    logger = _logger


class CustomStdoutFormatter(RichHandler):
    """
    Custom formatter for stdout logging with Rich integration.
    
    This formatter adds color to log messages based on their level and
    supports hiding messages in interactive mode.
    """
    LEVEL_COLORS: ClassVar[Dict[int, str]] = {
        logging.ERROR: "red",
        logging.WARNING: "dark_orange",
        logging.DEBUG: "grey54"
    }
    
    def __init__(self, console: Console | None = None, debug_mode: bool = False) -> None:
        """
        Initialize the stdout formatter.
        
        Args:
            console (Console | None, optional): Rich console instance to use for output. Defaults to None.
            debug_mode (bool, optional): Whether to show additional debug information. Defaults to False.
        """
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
        self._console = console

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record, respecting the 'hide_when_interactive' flag.
        
        Args:
            record (LogRecord): The log record to emit.
        """
        # Skip emission if record is marked to be hidden in interactive mode
        if getattr(record, 'hide_when_interactive', False) and self._console and self._console.is_interactive:
            return
        super().emit(record)

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with appropriate color based on level.
        
        Args:
            record (LogRecord): The log record to format.
            
        Returns:
            str: Formatted log message with Rich markup.
        """
        # Get the message once
        message = record.getMessage()
        
        # Apply color based on log level using the class variable mapping
        if color := self.LEVEL_COLORS.get(record.levelno):
            record.msg = f"[{color}]{message}[/{color}]"
        
        return super().format(record)


class CustomLogFileFormatter(logging.Formatter):
    """
    Custom formatter for log files that removes Rich markup tags.
    """
    def __init__(self):
        """
        Initialize the formatter with metadata format but without message part.
        We'll append the message manually to avoid issues with special characters.
        """
        super().__init__(
            fmt=LOG_FILE_METADATA,
            datefmt=r"%Y-%m-%d %H:%M:%S",
        )
    
    @staticmethod
    @lru_cache(maxsize=64)
    def _remove_rich_markup(text: str) -> str:
        """
        Remove Rich markup tags from text efficiently with caching.
        
        Args:
            text: Text containing Rich markup tags
            
        Returns:
            Text with Rich markup tags removed
        """
        while match := BBCOE_REGEX.search(text):
            text = text[:match.start()] + match.group('content') + text[match.end():]
        return text
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record for file output, removing Rich markup.
        This implementation uses the standard formatter for the metadata part
        and then appends the message without formatting to avoid issues with
        special characters within the log message.
        
        Args:
            record: The log record to format
            
        Returns:
            Formatted log message suitable for file output
        """
        message = record.getMessage()
        clean_message = self._remove_rich_markup(message)
        
        # Store the original message
        original_msg = record.msg
        original_args = record.args
        
        # Temporarily set an empty message to format just the metadata
        record.msg = ""
        record.args = None
        
        # Format the metadata part using the standard formatter
        metadata = super().format(record)
        
        # Restore the original message and args
        record.msg = original_msg
        record.args = original_args
        
        # Combine metadata and message without formatting the message
        return metadata + clean_message


def setup_loggers(stdout_output: bool = True, stdout_console: Optional[Console] = None,
                  stdout_loglevel: int = logging.INFO, logfile_output: bool = True,
                  logfile_loglevel: int = logging.DEBUG) -> None:
    """
    Configure loggers for both stdout and file output.

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
    logger.handlers.clear()  # Remove and reset existing handlers
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


logger = logging.getLogger(PACKAGE_NAME)

# Temporarily set the logger to INFO level until the config is loaded and the logger is properly set up
logger.setLevel(logging.INFO)
logger.addHandler(CustomStdoutFormatter(console=console))
