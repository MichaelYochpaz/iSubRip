import os
import sys
from typing import Union

from isubrip.constants import CONFIG_FILE_NAME, APPDATA_FOLDER_NAME, APPDATA_PATH_LINUX, APPDATA_PATH_MACOS, APPDATA_PATH_WINDOWS
from isubrip.namedtuples import SubtitlesType


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
        ('(', ''),
        (')', '')
    ]

    for pair in replacement_pairs:
        title = title.replace(pair[0], pair[1])

    return title


def format_file_name(movie_title: str, release_year: int, language_code: str, subtitles_type: SubtitlesType) -> str:
    """Generate file name for a subtitles file.

    Args:
        movie_title (str): Movie title.
        release_year(int): Movie release year.
        language_code (str): Subtitles language code.
        subtitles_type (SubtitlesType): Subtitles type.

    Returns:
        str: A formatted file name (does not include a file extension).
    """
    # Add release year only if it's not already included in the title
    movie_release_year_str = '.' + str(release_year) if str(release_year) not in movie_title else ''
    file_name = f"{format_title(movie_title)}{movie_release_year_str}.iT.WEB.{language_code}"

    if subtitles_type is not SubtitlesType.NORMAL:
        file_name += f".{subtitles_type.name.lower()}"

    return file_name
