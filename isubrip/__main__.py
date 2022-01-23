import os
import sys
import tomli
from typing import Union, Any
from mergedeep import merge

import isubrip.utils as utils
from isubrip.scraper import iSubRip
from isubrip.constants import *
from isubrip.playlist_downloader import PlaylistDownloader
from isubrip.enums import SubtitlesType, SubtitlesFormat
from isubrip.exceptions import DefaultConfigNotFound, UserConfigNotFound, InvalidConfigValue


def main() -> None:
    # Check if at least one argument was passed
    if len(sys.argv) < 2:
        print_usage()
        exit(0)

    config: dict[str, Any] = parse_config(find_config_file())

    # Remove last char from downloads folder if it's '/'
    if config["downloads"]["folder"][-1:] == '/':
        config["downloads"]["folder"] = config["downloads"]["folder"][:-1]

    # Check and print and exit if an error is raised during object creation
    try:
        playlist_downloader = PlaylistDownloader(config["ffmpeg"]["path"], config["ffmpeg"]["args"])

    except Exception as e:
        print(f"Error: {e}")
        exit(1)

    for url in sys.argv[1:]:
        try:
            print(f"\nScraping {url}...")
            movie_data = iSubRip.find_m3u8_playlist(url, config["downloads"]["user-agent"])
            print(f"Found movie \"{movie_data.name}\".")

            if movie_data.playlist is None:
                print(f"Error: Main m3u8 playlist could not be found / downloaded.")
                continue
            
            downloaded_subtitles = 0

            for subtitles in iSubRip.find_matching_subtitles(movie_data.playlist, config["downloads"]["filter"]):
                subtitles_type_str = (' [' + subtitles.subtitles_type.name.lower() + ']') if (subtitles.subtitles_type != SubtitlesType.NORMAL) else ''

                print(f"Found \"{subtitles.language_name}\" ({subtitles.language_code})" + subtitles_type_str + f" subtitles. Downloading...")
                file_name = format_file_name(movie_data.name, subtitles.language_code, subtitles.subtitles_type)

                # Download subtitles
                playlist_downloader.download_subtitles(subtitles.playlist_url, file_name, SubtitlesFormat.VTT)
                downloaded_subtitles += 1

            print(f"{downloaded_subtitles} matching subtitles for \"{movie_data.name}\" were found and downloaded.")

        except Exception as e:
            print(f"Error: {e}\nSkipping...")
            continue


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
    with open(DEFAULT_CONFIG_PATH, "r") as config_file:
        config: Union[dict[str, Any], None] = tomli.loads(config_file.read())

    config["user-config"] = False

    # If filter = [], change it to None
    if not config["downloads"]["filter"]:
        config["downloads"]["filter"] = None

    # If a user config file exists, load it and update default config with its values
    if user_config_path is not None:
        # Assure config file exists
        if not os.path.isfile(user_config_path):
            raise UserConfigNotFound(f"User config file could not be found at \"{user_config_path}\".")

        with open(user_config_path, "r") as config_file:
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

    if (config_path is not None) and (os.path.exists(config_path)):
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


def format_file_name(title: str, language_code: str, subtitles_type: SubtitlesType) -> str:
    """Generate file name for subtitles.

    Args:
        title (str): A movie title
        language_code (str): Subtitles language code
        subtitles_type (SubtitlesType): Subtitles type

    Returns:
        str: A formatted file name (without a file extension).
    """
    file_name = f"{format_title(title)}.iT.WEB.{language_code}"

    if type is not SubtitlesType.NORMAL:
        file_name += '.' + subtitles_type.name

    return file_name


def print_usage() -> None:
    """Print usage information."""
    print(f"Usage: {sys.argv[0]} <iTunes movie URL>")


if __name__ == "__main__":
    main()
