import os

from tempfile import gettempdir
from xdg import xdg_config_home

# General
PACKAGE_NAME = "isubrip"
PYPI_RSS_URL = "https://pypi.org/rss/project/isubrip/releases.xml"  # Used for checking updates

# Paths
DEFAULT_CONFIG_PATH = os.path.join("resources", "default_config.toml")
APPDATA_PATH_WINDOWS = f"{os.getenv('appdata')}"
APPDATA_PATH_LINUX = f"{xdg_config_home().resolve()}"
APPDATA_PATH_MACOS = r"~/Library/Application Support"
APPDATA_FOLDER_NAME = 'iSubRip'
CONFIG_FILE_NAME = "config.toml"
TEMP_FOLDER_PATH = os.path.join(gettempdir(), 'iSubRip')

# Lists
VALID_ARCHIVE_FORMATS = ["zip", "tar", "gztar"]

# RegEx
ITUNES_URL_REGEX = r"^(https?://itunes\.apple\.com/[a-z]{2}/movie/)(?:[\w\-%]+/)?(id\d{9,10})(?:$|\?.*)"
APPLETV_URL_REGEX = r"^(https?://tv.apple.com/[a-z]{2}/movie/)[\w\-]+/(umc\.cmc\.[a-z\d]{24,25})(?:$|\?.*)"

TIMESTAMP_REGEX = r"((?:[0-5][0-9]:)?[0-5][0-9]:[0-5][0-9][\.,]\d{3} --> (?:[0-5][0-9]:)?[0-5][0-9]:[0-5][0-9][\.,]\d{3}).*"  # Match group matches timestamp
SUBTITLES_LINE_SPLIT_REGEX = rf"^(?:\d+\n)?{TIMESTAMP_REGEX}\n"

# Unicode
RTL_CONTROL_CHARS = ('\u200e', '\u200f', '\u202a', '\u202b', '\u202c', '\u202d', '\u202e')
RTL_CHAR = '\u202b'
