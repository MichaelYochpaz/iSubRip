import sys
import os
import tomli
from typing import Union, Any
from xdg import xdg_config_home
from mergedeep import merge

from isubrip.types import SubtitlesType
from isubrip.exceptions import DefaultConfigNotFound, UserConfigNotFound


DEFAULT_CONFIG_PATH = "resources/default_config.toml"
USER_CONFIG_PATH_WINDOWS = f"{os.getenv('appdata')}\\iSubRip\\config.toml"
USER_CONFIG_PATH_LINUX = f"{xdg_config_home().resolve()}/iSubRip/config.toml"
USER_CONFIG_PATH_MACOS = r"~/Library/Application Support/isubrip/config.toml"

VALID_ARCHIVE_FORMATS = ["zip", "tar", "gztar"]

ITUNES_STORE_REGEX = r"https?://itunes.apple.com/[a-z]{2}/movie/[a-zA-Z0-9\-%]+/id[0-9]+($|(\?.*))"


# -------------------- Functions ------------------- #

def parse_config(user_config_path: Union[str, None] = None) -> dict[str, Any]:
    """Parse and config file and save settings to a dictionary.

    Args:
        user_config_path (str, optional): Path to an additional optional config to use for overwriting default settings.
        Defaults to None.

    Raises:
        DefaultConfigNotFound: Default config file could not be found.
        UserConfigNotFound: User config file could not be found.
        InvalidConfigValue: An invalid value was used in the config file.

    Returns:
        dict: A dictionary containing all settings.
    """
    # Assure default config file exists
    if not os.path.isfile(DEFAULT_CONFIG_PATH):
        raise DefaultConfigNotFound(f"Default config file could not be found at \"{DEFAULT_CONFIG_PATH}\".")

    # Load settings from default config file
    with open (DEFAULT_CONFIG_PATH, "r") as config_file:
        config: Union[dict[str, Any], None] = tomli.loads(config_file.read())

    config["user-config"] = False

    # If a user config file exists, load it and update default config with it's values
    if user_config_path != None:
        # Assure config file exists
        if not os.path.isfile(user_config_path):
            raise UserConfigNotFound(f"User config file could not be found at \"{user_config_path}\".")
            
        with open (user_config_path, "r") as config_file:
            user_config: Union[dict[str, Any], None] = tomli.loads(config_file.read())

        # Change config["ffmpeg"]["args"] value to None if empty
        if config["ffmpeg"]["args"] == "":
            config["ffmpeg"]["args"] = None

        # Merge user_config with the default config, and override existing config values with values from user_config
        merge(config, user_config)
        config["user-config"] = True

    return config


def find_config_file() -> Union[str, None]:
    """Return the path to user's config file.

    Returns:
        Union[str, None]: A string with the path to user's config file if it's found, and None otherwise.
    """
    config_path = None

    # Windows
    if sys.platform == "win32":
        config_path = USER_CONFIG_PATH_WINDOWS

    # Linux
    elif sys.platform == "linux":
        config_path = USER_CONFIG_PATH_LINUX
    
    # MacOS
    elif sys.platform == "darwin":
        config_path = USER_CONFIG_PATH_MACOS

    if (config_path != None) and (os.path.exists(config_path)):
        return config_path
    
    return None


def format_title(title: str) -> str:
    """Format iTunes movie title to a standardized title.

    Args:
        title (str): An iTunes movie title.

    Returns:
        str: A modified standardized title.
    """
    # Replacements will be done in the same order as the list
    replacement_pairs = [
        (': ', '.'),
        (' - ', '-'),
        (', ', '.'),
        ('. ', '.'),
        (' ', '.'),
        ('(', ''),
        (')', '')
    ]

    for pair in replacement_pairs:
        title = title.replace(pair[0], pair[1])

    return title


def format_file_name(title: str, language_code: str, type: SubtitlesType) -> str:
    """Generate file name for subtitles.

    Args:
        title (str): A movie title
        language_code (str): Subtitles language code
        type (SubtitlesType): Subtitles type

    Returns:
        str: A formatted file name (without a file extension).
    """
    file_name = f"{format_title(title)}.iT.WEB.{language_code}"

    if type is not SubtitlesType.NORMAL:
        file_name += '.' + type.name

    return file_name