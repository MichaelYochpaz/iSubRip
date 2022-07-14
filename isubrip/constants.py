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

# Scraping
APPLETV_API_PARAMS = {
    "utscf": "OjAAAAAAAAA~",
    "utsk": "6e3013c6d6fae3c2::::::235656c069bb0efb",
    "caller": "web",
    "sf": "143441",
    "v": "58",
    "pfm": "web",
    "locale": "en-US"
}

# RegEx
# - Urls (Match groups result in a URL without movie's title, which is a valid URL)
ITUNES_URL_REGEX = r"^(https?://itunes\.apple\.com/[a-z]{2}/movie/)(?:[\w\-%]+/)?(id\d{9,10})(?:$|\?.*)"
APPLETV_URL_REGEX = r"^(https?://tv.apple.com/[a-z]{2}/movie/)[\w\-]+/(umc\.cmc\.[a-z\d]{24,25})(?:$|\?.*)"

# - WEBVTT
WEBVTT_PERCENTAGE_REGEX = r"\d{1,3}(?:.\d+)?%"
WEBVTT_CAPTION_TIMINGS_REGEX = r"(?:[0-5]\d:)?[0-5]\d:[0-5]\d[\.,]\d{3}[ \t]+-->[ \t]+(?:[0-5]\d:)?[0-5]\d:[0-5]\d[\.,]\d{3}"

WEBVTT_CAPTION_SETTING_ALIGNMENT_REGEX = r"align:(?:start|center|middle|end|left|right)"
WEBVTT_CAPTION_SETTING_LINE_REGEX = rf"line:(?:{WEBVTT_PERCENTAGE_REGEX}|-?\d+%)(?:,(?:start|center|middle|end))?"
WEBVTT_CAPTION_SETTING_POSITION_REGEX = rf"position:{WEBVTT_PERCENTAGE_REGEX}(?:,(?:start|center|middle|end))?"
WEBVTT_CAPTION_SETTING_REGION_REGEX = r"region:(?:(?!(?:-->)|\t)\S)+"
WEBVTT_CAPTION_SETTING_SIZE_REGEX = rf"size:{WEBVTT_PERCENTAGE_REGEX}"
WEBVTT_CAPTION_SETTING_VERTICAL_REGEX = r"vertical:(?:lr|rl)"

WEBVTT_CAPTION_SETTINGS_REGEX = f"(?:(?:{WEBVTT_CAPTION_SETTING_ALIGNMENT_REGEX})|" \
                                f"(?:{WEBVTT_CAPTION_SETTING_LINE_REGEX})|" \
                                f"(?:{WEBVTT_CAPTION_SETTING_POSITION_REGEX})|" \
                                f"(?:{WEBVTT_CAPTION_SETTING_REGION_REGEX})|" \
                                f"(?:{WEBVTT_CAPTION_SETTING_SIZE_REGEX})|" \
                                f"(?:{WEBVTT_CAPTION_SETTING_VERTICAL_REGEX})|" \
                                f"(?:[ \t]+))*"

WEBVTT_CAPTION_BLOCK_REGEX = rf"^({WEBVTT_CAPTION_TIMINGS_REGEX})[ \t]*({WEBVTT_CAPTION_SETTINGS_REGEX})?"

# Can't use isubrip.webvtt.Comment.header instead of literal "NOTE" string because of circualr import
WEBVTT_COMMENT_HEADER_REGEX = rf"^NOTE(?:$|[ \t])(.+)?"

# Unicode
RTL_CONTROL_CHARS = ('\u200e', '\u200f', '\u202a', '\u202b', '\u202c', '\u202d', '\u202e')
RTL_CHAR = '\u202b'
