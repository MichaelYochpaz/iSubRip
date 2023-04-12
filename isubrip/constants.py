from __future__ import annotations

from pathlib import Path
from tempfile import gettempdir
from typing import List

from isubrip.config import ConfigSetting, SpecialConfigType

# General
PACKAGE_NAME = "isubrip"

# Downloads
ARCHIVE_FORMAT = "zip"

# Paths
DEFAULT_CONFIG_PATH = Path(__file__).parent / "resources" / "default_config.toml"
DATA_FOLDER_PATH = Path.home() / f".{PACKAGE_NAME}"
SCRAPER_MODULES_SUFFIX = "_scraper"
USER_CONFIG_FILE_NAME = "config.toml"
USER_CONFIG_FILE = DATA_FOLDER_PATH / USER_CONFIG_FILE_NAME
TEMP_FOLDER_PATH = Path(gettempdir()) / PACKAGE_NAME

# Config
DEFAULT_CONFIG_SETTINGS = [
    ConfigSetting(
        key="check-for-updates",
        type=bool,
        category="general",
        required=False,
    ),
    ConfigSetting(
        key="add-release-year-to-series",
        type=bool,
        category="downloads",
        required=False,
    ),
    ConfigSetting(
        key="folder",
        type=str,
        category="downloads",
        required=True,
        special_type=SpecialConfigType.EXISTING_FOLDER_PATH,
    ),
    ConfigSetting(
        key="languages",
        type=List[str],
        category="downloads",
        required=False,
    ),
    ConfigSetting(
        key="overwrite-existing",
        type=bool,
        category="downloads",
        required=True,
    ),
    ConfigSetting(
        key="zip",
        type=bool,
        category="downloads",
        required=False,
    ),
    ConfigSetting(
        key="fix-rtl",
        type=bool,
        category="subtitles",
        required=True,
    ),
    ConfigSetting(
        key="rtl-languages",
        type=List[str],
        category="subtitles",
        required=False,
    ),
    ConfigSetting(
        key="remove-duplicates",
        type=bool,
        category="subtitles",
        required=True,
    ),
    ConfigSetting(
        key="convert-to-srt",
        type=bool,
        category="subtitles",
        required=False,
    ),
    ConfigSetting(
        key="user-agent",
        type=str,
        category="scrapers",
        required=True,
    ),
]
