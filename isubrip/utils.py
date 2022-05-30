import os
import sys
from typing import Union

from isubrip.config import Config
from isubrip.constants import CONFIG_FILE_NAME, APPDATA_FOLDER_NAME, APPDATA_PATH_LINUX, APPDATA_PATH_MACOS, APPDATA_PATH_WINDOWS


def find_appdata_path() -> str:
    """Return the path to appdata folder.

    Returns:
        Union[str, None]: A string with the appdata folder.
    """
    # Windows
    if sys.platform == "win32":
        return APPDATA_PATH_WINDOWS

    # Linux
    elif sys.platform == "linux":
        return APPDATA_PATH_LINUX

    # MacOS
    elif sys.platform == "darwin":
        return APPDATA_PATH_MACOS


def find_config_file() -> Union[str, None]:
    """Return the path to user's config file (if it exists).

    Returns:
        Union[str, None]: A string with the path to user's config file if it's found, and None otherwise.
    """
    config_path = os.path.join(find_appdata_path(), APPDATA_FOLDER_NAME, CONFIG_FILE_NAME)

    if (config_path is not None) and (os.path.exists(config_path)):
        return config_path

    return None


def format_title(title: str) -> str:
    """Format movie title to a standardized title that can be used as a file name.

    Args:
        title (str): An iTunes movie title.

    Returns:
        str: The title, in a file-name-friendly format.
    """
    # Replacements will be done in the same order of this list
    replacement_pairs = [
        (': ', '.'),
        (' - ', '-'),
        (', ', '.'),
        ('. ', '.'),
        (' ', '.'),
        ('|', '.'),
        ('<', ''),
        ('>', ''),
        ('(', ''),
        (')', ''),
        ('"', ''),
        ('?', ''),
        ('*', ''),
    ]

    for pair in replacement_pairs:
        title = title.replace(pair[0], pair[1])

    return title


def parse_config(file_path: str, *file_paths: str) -> Config:
    """
    Parse config files by order and return a Config object.

    Args:
        file_path (str): A config file to parse.
        *file_paths (str, optional): Additional config files to parse (will override previous settings).

    Returns:
        Config: A parsed Config object.
    """
    config = Config()
    file_paths: tuple = (file_path,) + file_paths

    for file_path in file_paths:
        with open(file_path, 'r') as data:
            config.loads(data.read())

    return config
