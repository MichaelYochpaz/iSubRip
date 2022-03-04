import atexit
import json
import os
import pkgutil
import shutil
import sys
import zipfile
from typing import Union, Any

import m3u8
import tomli
from m3u8 import M3U8
from mergedeep import merge

from isubrip.scraper import Scraper
from isubrip.playlist_downloader import PlaylistDownloader
from isubrip.exceptions import *
from isubrip.constants import *
from isubrip.enums import *
from isubrip.namedtuples import *


def main() -> None:
    # Check if at least one argument was passed
    if len(sys.argv) < 2:
        print_usage()
        exit(1)

    try:
        config: dict[str, Any] = parse_config(find_config_file())

    except ConfigError as e:
        print(f"Error: {e}")
        exit(1)

    # Remove last char from downloads folder if it's '/'
    if config["downloads"]["folder"][-1:] == '/':
        config["downloads"]["folder"] = config["downloads"]["folder"][:-1]

    download_path: str
    download_to_temp: bool

    # Set download path to temp folder "zip" setting is used
    if config["downloads"]["zip"]:
        download_path = TEMP_FOLDER_PATH
        download_to_temp = True

    else:
        download_path = config["downloads"]["folder"]
        download_to_temp = False

    try:
        playlist_downloader = PlaylistDownloader(config["ffmpeg"]["path"], config["ffmpeg"]["args"])

    except FFmpegNotFound as e:
        print(f"Error: {e}")
        exit(1)

    for url in sys.argv[1:]:
        print(f"\nScraping {url}...")
        
        try:
            movie_data: MovieData = Scraper.find_movie_data(url, config["scraping"]["user-agent"])
        
        except Exception as e:
            print(f"Error: {e}")
            continue

        print(f"Found movie: {movie_data.name}\n")

        if movie_data.playlist is None:
            print(f"Error: No valid playlist could be found.")
            continue

        m3u8_playlist: M3U8 = m3u8.load(movie_data.playlist)
        current_download_path: str

        # Create temp folder
        if download_to_temp:
            current_download_path = os.path.join(download_path, f"{format_title(movie_data.name)}.iT.WEB")
            os.makedirs(current_download_path, exist_ok=True)
            atexit.register(shutil.rmtree, current_download_path)

        else:
            current_download_path = download_path

        downloaded_subtitles: list = []

        for subtitles in Scraper.find_matching_subtitles(m3u8_playlist, config["downloads"]["languages"]):
            print(f"Downloading \"{subtitles.language_name}\" ({subtitles.language_code}) subtitles...")
            file_name = format_file_name(movie_data.name, movie_data.release_year, subtitles.language_code, subtitles.subtitles_type)

            # Download subtitles
            downloaded_subtitles.append(playlist_downloader.download_subtitles(subtitles.playlist_url, current_download_path, file_name, config["downloads"]["format"]))

            if download_to_temp:
                if len(downloaded_subtitles) == 1:
                    shutil.move(downloaded_subtitles[0], config["downloads"]["folder"])

                elif len(downloaded_subtitles) > 1:
                    # Create zip archive
                    print(f"Creating zip archive...")
                    archive_name = f"{format_title(movie_data.name)}.iT.WEB.zip"
                    archive_path = os.path.join(current_download_path, archive_name)

                    zf = zipfile.ZipFile(archive_path, compression=zipfile.ZIP_DEFLATED, mode='w')

                    for file in downloaded_subtitles:
                        zf.write(file, os.path.basename(file))

                    zf.close()
                    shutil.move(archive_path, config["downloads"]["folder"])

                # Remove current temp dir
                shutil.rmtree(current_download_path)
                atexit.unregister(shutil.rmtree)

            print(f"\n{len(downloaded_subtitles)} matching subtitles for \"{movie_data.name}\" were found and downloaded to \"{os.path.abspath(config['downloads']['folder'])}\".")


def parse_config(user_config_path: Union[str, None] = None) -> dict[str, Any]:
    """Parse default config file, with an option of an added user config, and return a dictionary with all settings.

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
    try:
        default_config_data: Union[bytes, None] = pkgutil.get_data(PACKAGE_NAME, DEFAULT_CONFIG_PATH)

        if default_config_data is None:
            raise FileNotFoundError

    except FileNotFoundError:
        raise DefaultConfigNotFound("Default config file could not be found.")

    else:
        default_config_str: str = str(default_config_data, 'utf-8')

    # Load settings from default config file
    config: Union[dict[str, Any], None] = tomli.loads(default_config_str)

    config["user-config"] = False

    # If a user config file exists, load it and update the dictionary with its values
    if user_config_path is not None:
        # Assure user config file exists
        if not os.path.isfile(user_config_path):
            raise UserConfigNotFound(f"User config file could not be found at \"{user_config_path}\".")

        with open(user_config_path, "r") as config_file:
            user_config: Union[dict[str, Any], None] = tomli.loads(config_file.read())

        # Merge user_config with the default config, and override existing config values with values from user_config
        merge(config, user_config)
        config["user-config"] = True

    # Check if subtitles format is valid, and convert it to enum
    subtitle_formats: set = set(item.name for item in SubtitlesFormat)

    if config["downloads"]["format"].upper() in subtitle_formats:
        config["downloads"]["format"] = SubtitlesFormat[config["downloads"]["format"].upper()]

    else:
        raise InvalidConfigValue(f"{config['downloads']['format']} is an invalid format.")

    # If languages = [], change it to None
    if not config["downloads"]["languages"]:
        config["downloads"]["languages"] = None

    # Change config["ffmpeg"]["args"] value to None if empty
    if config["ffmpeg"]["args"] == "":
        config["ffmpeg"]["args"] = None

    return config


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


def format_file_name(movie_title: str, movie_release_year: int, language_code: str, subtitles_type: SubtitlesType) -> str:
    """Generate file name for a subtitles file.

    Args:
        movie_title (str): Movie title.
        movie_release_year(int): Movie release year.
        language_code (str): Subtitles language code.
        subtitles_type (SubtitlesType): Subtitles type.

    Returns:
        str: A formatted file name (does not include a file extension).
    """
    # Add release year only if it's not already included in the title
    movie_release_year_str = '.' + str(movie_release_year) if str(movie_release_year) not in movie_title else ''
    file_name = f"{format_title(movie_title)}{movie_release_year_str}.iT.WEB.{language_code}"

    if subtitles_type is not SubtitlesType.NORMAL:
        file_name += f".{subtitles_type.name.lower()}"

    return file_name


def print_usage() -> None:
    """Print usage information."""
    print(f"Usage: {PACKAGE_NAME} <iTunes movie URL> [iTunes movie URL...]")


if __name__ == "__main__":
    main()
