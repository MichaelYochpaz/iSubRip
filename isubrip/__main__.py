import atexit
import shutil
import sys
import os
import zipfile
from xml.etree import ElementTree

import m3u8
import requests

from isubrip.constants import DEFAULT_CONFIG_PATH, PACKAGE_NAME, PYPI_RSS_URL, TEMP_FOLDER_PATH
from isubrip.exceptions import ConfigError, DefaultConfigNotFound
from isubrip.namedtuples import MovieData
from isubrip.playlist_downloader import PlaylistDownloader
from isubrip.scraper import Scraper
from isubrip.subtitles import Subtitles
from isubrip.utils import find_config_file, format_title, parse_config


def main() -> None:
    # Check if at least one argument was passed
    if len(sys.argv) < 2:
        print_usage()
        exit(1)

    # Assure default config file exists
    try:
        default_config_path = os.path.join(os.path.dirname(sys.modules[PACKAGE_NAME].__file__), DEFAULT_CONFIG_PATH)

    except KeyError:
        raise DefaultConfigNotFound(f"Default config file could not be found.")

    # Load default and user (if it exists) config files
    config_files = [default_config_path]
    user_config_path = find_config_file()

    if user_config_path is not None:
        config_files.append(find_config_file())

    try:
        config = parse_config(*config_files)

    except (ConfigError, FileNotFoundError) as e:
        raise ConfigError(e)

    # Set `Subtitles` settings from config
    Subtitles.remove_duplicates = config.subtitles["remove-duplicates"]
    Subtitles.fix_rtl = config.subtitles["fix-rtl"]
    Subtitles.rtl_languages = config.subtitles["rtl-languages"]

    download_path: str
    download_to_temp: bool

    # Set download path to temp folder "zip" setting is used
    if config.downloads["zip"]:
        download_path = TEMP_FOLDER_PATH
        download_to_temp = True

    else:
        download_path = config.downloads["folder"]
        download_to_temp = False

    if config.general["check-for-updates"]:
        check_for_updates()

    for idx, url in enumerate(sys.argv[1:]):
        if idx > 0:
            print()  # Print newline between different movies

        print(f"Scraping {url}...")

        try:
            movie_data: MovieData = Scraper.find_movie_data(url, config.scraping["user-agent"])

        except Exception as e:
            print(f"Error: {e}")
            continue

        print(f"Found movie: {movie_data.name}")

        if movie_data.playlist is None:
            print(f"Error: No valid playlist could be found.")
            print("\n--------------------------------------------------")
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

        with PlaylistDownloader(config.downloads["user-agent"]) as playlist_downloader:
            for subtitles in Scraper.find_subtitles(m3u8_playlist, config.downloads["languages"]):
                subtitles_count += 1
                print(f"Downloading \"{subtitles.language_name}\" ({subtitles.language_code}) subtitles...")
                downloaded_subtitles = playlist_downloader.download_subtitles_file(movie_data, subtitles, current_download_path, config.downloads["format"])

                # Assure subtitles downloaded successfully
                if os.path.isfile(downloaded_subtitles):
                    downloaded_subtitles_list.append(downloaded_subtitles)

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

        print(f"\n{len(downloaded_subtitles_list)}/{subtitles_count} matching subtitles for \"{movie_data.name}\" were downloaded to \"{os.path.abspath(config.downloads['folder'])}\".")

        if idx < (len(sys.argv) - 2):
            print("\n--------------------------------------------------")


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
                  f"\nConsider upgrading by running \"python3 -m pip install --upgrade {PACKAGE_NAME}\"\n")

    except Exception:
        return


def print_usage() -> None:
    """Print usage information."""
    print(f"Usage: {PACKAGE_NAME} <iTunes movie URL> [iTunes movie URL...]")


if __name__ == "__main__":
    main()
