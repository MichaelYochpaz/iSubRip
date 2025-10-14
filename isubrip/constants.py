from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from tempfile import gettempdir

# General
PACKAGE_NAME = "isubrip"
PACKAGE_VERSION = "2.6.8"

SCRAPER_MODULES_SUFFIX = "_scraper"
USER_CONFIG_FILE_NAME = "config.toml"

@lru_cache(maxsize=1)
def data_folder_path() -> Path:
    return Path.home() / f".{PACKAGE_NAME}"

@lru_cache(maxsize=1)
def temp_folder_path() -> Path:
    return Path(gettempdir()) / PACKAGE_NAME

@lru_cache(maxsize=1)
def user_config_file_path() -> Path:
    return data_folder_path() / USER_CONFIG_FILE_NAME

# Logging Paths
@lru_cache(maxsize=1)
def log_files_path() -> Path:
    return data_folder_path() / "logs"

# Other
WINDOWS_RESERVED_FILE_NAMES = frozenset(
    ["CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1",
     "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"],
     )

RTL_LANGUAGES = frozenset(["ar", "arc", "az", "dv", "he", "ks", "ku", "fa", "ur", "yi"])
