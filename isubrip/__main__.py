import atexit
import shutil
import sys
import os
import zipfile
from xml.etree import ElementTree

import m3u8
import requests

from isubrip.config import Config
from isubrip.constants import DEFAULT_CONFIG_PATH, PACKAGE_NAME, PYPI_RSS_URL, TEMP_FOLDER_PATH
from isubrip.exceptions import ConfigError, DefaultConfigNotFound, FFmpegNotFound
from isubrip.namedtuples import MovieData
from isubrip.playlist_downloader import PlaylistDownloader
from isubrip.scraper import Scraper
from isubrip.utils import find_config_file, format_file_name, format_title


def main() -> None:
    # Check if at least one argument was passed
    if len(sys.argv) < 2:
        print_usage()
        exit(1)

    # Assure default config file exists
    default_config_path = ''
    try:
        default_config_path = os.path.join(os.path.dirname(sys.modules[PACKAGE_NAME].__file__), DEFAULT_CONFIG_PATH)
        with open(default_config_path, 'r') as default_config_file:
            default_config_data = default_config_file.read()

    except (KeyError, FileNotFoundError):
        raise DefaultConfigNotFound(f"Default config file could not be found on \"{default_config_path}\".")

    config = Config()

    # Load default and user (if it exists) config files
    try:
        config.loads(default_config_data)

        user_config_path = find_config_file()
        if user_config_path is not None:
            with open(user_config_path, 'r') as user_config_data:
                config.loads(user_config_data.read())

    except ConfigError as e:
        print(f"Error: {e}")
        exit(1)

    download_path: str
    download_to_temp: bool

    # Set download path to temp folder "zip" setting is used
    if config.downloads["zip"]:
        download_path = TEMP_FOLDER_PATH
        download_to_temp = True

    else:
        download_path = config.downloads["folder"]
        download_to_temp = False

    try:
        playlist_downloader = PlaylistDownloader(config.ffmpeg["path"], config.ffmpeg["args"])

    except FFmpegNotFound as e:
        print(f"Error: {e}")
        exit(1)

    if config.general["check-for-updates"]:
        check_for_updates()

    for url in sys.argv[1:]:
        print(f"\nScraping {url}...")
        
        try:
            movie_data: MovieData = Scraper.find_movie_data(url, config.scraping["user-agent"])
        
        except Exception as e:
            print(f"Error: {e}")
            continue

        print(f"Found movie: {movie_data.name}")

        if movie_data.playlist is None:
            print(f"Error: No valid playlist could be found.")
            continue

        m3u8_playlist: m3u8.M3U8 = m3u8.load(movie_data.playlist)

        # Create temp folder
        if download_to_temp:
            current_download_path = os.path.join(download_path, f"{format_title(movie_data.name)}.iT.WEB")
            os.makedirs(current_download_path, exist_ok=True)
            atexit.register(shutil.rmtree, current_download_path)

        else:
            current_download_path = download_path

        downloaded_subtitles_list = []
        subtitles_count = 0

        for subtitles in Scraper.find_subtitles(m3u8_playlist, config.downloads["languages"]):
            subtitles_count += 1
            print(f"Downloading \"{subtitles.language_name}\" ({subtitles.language_code}) subtitles...")
            file_name = format_file_name(movie_data.name, movie_data.release_year, subtitles.language_code, subtitles.subtitles_type)

            # Download subtitles
            downloaded_subtitles = playlist_downloader.download_subtitles(subtitles.playlist_url, current_download_path, file_name, config.downloads["format"])

            # Assure subtitles downloaded successfully
            if os.path.isfile(downloaded_subtitles):
                downloaded_subtitles_list.append(playlist_downloader.download_subtitles(subtitles.playlist_url, current_download_path, file_name, config.downloads["format"]))

        if download_to_temp:
            if len(downloaded_subtitles_list) == 1:
                shutil.copy(downloaded_subtitles_list[0], config.downloads["folder"])

            elif len(downloaded_subtitles_list) > 1:
                # Create zip archive
                print(f"Creating zip archive...")
                archive_name = f"{format_title(movie_data.name)}.iT.WEB.zip"
                archive_path = os.path.join(current_download_path, archive_name)

                zf = zipfile.ZipFile(archive_path, compression=zipfile.ZIP_DEFLATED, mode='w')

                for file in downloaded_subtitles_list:
                    zf.write(file, os.path.basename(file))

                zf.close()
                shutil.copy(archive_path, config.downloads["folder"])

            # Remove current temp dir
            shutil.rmtree(current_download_path)
            atexit.unregister(shutil.rmtree)

        print(f"{len(downloaded_subtitles_list)}/{subtitles_count} matching subtitles for \"{movie_data.name}\" successfully downloaded to \"{os.path.abspath(config.downloads['folder'])}\".")


def check_for_updates() -> None:
    """Check and print if a newer version of the package is available."""
    # If anything breaks, just skip update check
    try:
        current_version = sys.modules[PACKAGE_NAME].__version__

        response = requests.get(PYPI_RSS_URL).text
        xml_data = ElementTree.fromstring(response)
        latest_version = xml_data.find("channel/item/title").text

        # If the latest PyPI release is different from current one, print a message
        if latest_version != current_version:
            print(f"Note: You are currently using version {current_version} of {PACKAGE_NAME}, however version {latest_version} is available.",
                  f"\nConsider upgrading by running \"pip install --upgrade {PACKAGE_NAME}\".")

    except Exception:
        return


def print_usage() -> None:
    """Print usage information."""
    print(f"Usage: {PACKAGE_NAME} <iTunes movie URL> [iTunes movie URL...]")


if __name__ == "__main__":
    main()
