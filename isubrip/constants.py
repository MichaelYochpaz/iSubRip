import os
from tempfile import gettempdir
from xdg import xdg_config_home

# General
PACKAGE_NAME = "isubrip"

# Paths
DEFAULT_CONFIG_PATH = "resources/default_config.toml"
USER_CONFIG_PATH_WINDOWS = f"{os.getenv('appdata')}\\iSubRip\\config.toml"
USER_CONFIG_PATH_LINUX = f"{xdg_config_home().resolve()}/iSubRip/config.toml"
USER_CONFIG_PATH_MACOS = r"~/Library/Application Support/isubrip/config.toml"
TEMP_FOLDER_PATH = os.path.join(gettempdir(), 'iSubRip')

# Lists
VALID_ARCHIVE_FORMATS = ["zip", "tar", "gztar"]

# RegEx
ITUNES_STORE_REGEX = r"https?://itunes.apple.com/[a-z]{2}/movie/[a-zA-Z0-9\-%]+/id[0-9]+($|(\?.*))"
