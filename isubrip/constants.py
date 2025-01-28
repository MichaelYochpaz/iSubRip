from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path
from tempfile import gettempdir

# General
PACKAGE_NAME = "isubrip"
PACKAGE_VERSION = "2.6.0"

# Async
EVENT_LOOP = asyncio.get_event_loop()

# Paths
DEFAULT_CONFIG_PATH = Path(__file__).parent / "resources" / "default_config.toml"
DATA_FOLDER_PATH = Path.home() / f".{PACKAGE_NAME}"
SCRAPER_MODULES_SUFFIX = "_scraper"
TEMP_FOLDER_PATH = Path(gettempdir()) / PACKAGE_NAME

# Config Paths
USER_CONFIG_FILE_NAME = "config.toml"
USER_CONFIG_FILE_PATH = DATA_FOLDER_PATH / USER_CONFIG_FILE_NAME

# Logging Paths
LOG_FILES_PATH = DATA_FOLDER_PATH / "logs"
LOG_FILE_NAME = f"{PACKAGE_NAME}_{dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"


# Other
TITLE_REPLACEMENT_STRINGS = {  # Replacements will be done by the order of the keys.
    ": ": ".", ":": ".", " - ": "-", ", ": ".", ". ": ".", " ": ".", "|": ".", "/": ".", "…": ".",
    "<": "", ">": "", "(": "", ")": "", '"': "", "?": "", "*": "",
}
WINDOWS_RESERVED_FILE_NAMES = ("CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7",
                               "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9")
