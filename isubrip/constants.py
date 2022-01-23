import os
from xdg import xdg_config_home


DEFAULT_CONFIG_PATH = "resources/default_config.toml"
USER_CONFIG_PATH_WINDOWS = f"{os.getenv('appdata')}\\iSubRip\\config.toml"
USER_CONFIG_PATH_LINUX = f"{xdg_config_home().resolve()}/iSubRip/config.toml"
USER_CONFIG_PATH_MACOS = r"~/Library/Application Support/isubrip/config.toml"

VALID_ARCHIVE_FORMATS = ["zip", "tar", "gztar"]

ITUNES_STORE_REGEX = r"https?://itunes.apple.com/[a-z]{2}/movie/[a-zA-Z0-9\-%]+/id[0-9]+($|(\?.*))"