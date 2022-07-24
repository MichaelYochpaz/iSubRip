import atexit
import os
import shutil
import sys

from pathlib import Path
from xml.etree import ElementTree

import m3u8
import requests

from isubrip.constants import DATA_FOLDER_PATH, DEFAULT_CONFIG_PATH, PACKAGE_NAME, PYPI_RSS_URL, TEMP_FOLDER_PATH, USER_CONFIG_FILE
from isubrip.enums import DataSource
from isubrip.exceptions import ConfigError
from isubrip.namedtuples import MovieData
from isubrip.playlist_downloader import PlaylistDownloader
from isubrip.scraper import Scraper
from isubrip.subtitles import Subtitles
from isubrip.utils import format_title, parse_config


def main() -> None:
    # Load default and user (if it exists) config files
    config_files = [DEFAULT_CONFIG_PATH]

    ### DEPRECATED ###
    deprecated_config_file = None

    # Windows
    if sys.platform == "win32":
        deprecated_config_file = Path(os.environ['APPDATA']) / "iSubRip" / "config.toml"

    # Linux
    elif sys.platform == "linux":
        deprecated_config_file = Path.home() / ".config" / "iSubRip" / "config.toml"

    if deprecated_config_file and deprecated_config_file.is_file():
        config_files.append(deprecated_config_file)
        print("Warning: A config file was found in a deprecated location that will be unsupported in future versions.\n"
              f"Please move the config file to \"{USER_CONFIG_FILE}\" to avoid future issues.\n")
    ### END DEPRECATED ###

    # If data folder doesn't exist, create it
    if not DATA_FOLDER_PATH.is_dir():
        DATA_FOLDER_PATH.mkdir(parents=True, exist_ok=True)

    else:
        # If a user config file exists, add it
        if USER_CONFIG_FILE.is_file():
            config_files.append(USER_CONFIG_FILE)

    # Check if at least one argument was passed, exit if not
    if len(sys.argv) < 2:
        print_usage()
        exit(1)

    # Exit if default config file is missing for some reason
    if not DEFAULT_CONFIG_PATH.is_file():
        print("Error: Default config file could not be found.")
        exit(1)

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
        TEMP_FOLDER_PATH.mkdir(exist_ok=True)
        atexit.register(shutil.rmtree, TEMP_FOLDER_PATH)

    else:
        download_path = config.downloads["folder"]
        download_to_temp = False

    if config.general["check-for-updates"]:
        check_for_updates()

    for idx, url in enumerate(sys.argv[1:]):
        if idx > 0:
            print("\n--------------------------------------------------\n")  # Print between different movies

        print(f"Scraping {url}...")

        try:
            movie_data: MovieData = Scraper.get_movie_data(url, {"User-Agent": config.scraping["user-agent"]})

            # AppleTV link used, but no iTunes playlist found on page
            if movie_data.data_source == DataSource.APPLETV and not movie_data.playlists:
                print("An iTunes offer could not be found. Skipping...")
                continue

        except Exception as e:
            print(f"Error: {e}")
            continue

        print(f"Found movie: {movie_data.name}")

        if not movie_data.playlists:
            print(f"Error: No valid playlist could be found.")
            continue

        multiple_playlists = len(movie_data.playlists) > 1
        downloaded_subtitles_langs = set()
        downloaded_subtitles_paths = []
        subtitles_count = 0

        # Create temp folder if needed
        if download_to_temp:
            movie_download_path = os.path.join(download_path, f"{format_title(movie_data.name)}.iT.WEB")
            os.makedirs(movie_download_path, exist_ok=True)

        else:
            movie_download_path = download_path

        with PlaylistDownloader(config.downloads["user-agent"]) as playlist_downloader:
            for idy, playlist in enumerate(movie_data.playlists):
                # Print empty line between different playlists
                if idy > 0:
                    print()

                if multiple_playlists:
                    print(f"id{playlist.itunes_id}:")

                m3u8_playlist: m3u8.M3U8 = m3u8.load(playlist.url)
                separate_playlist_folder: bool = multiple_playlists and not config.downloads["merge-playlists"]
                playlist_subtitles_count = 0

                # Create folder for playlist if needed
                if separate_playlist_folder:
                    playlist_download_path = os.path.join(movie_download_path, f"id{playlist.itunes_id}")
                    os.makedirs(playlist_download_path, exist_ok=True)

                else:
                    playlist_download_path = movie_download_path

                for subtitles in Scraper.find_subtitles(m3u8_playlist, config.downloads["languages"]):
                    if not config.downloads["merge-playlists"] or \
                            (config.downloads["merge-playlists"] and subtitles.language_code not in downloaded_subtitles_langs):
                        playlist_subtitles_count += 1
                        print(f"Downloading \"{subtitles.language_name}\" ({subtitles.language_code}) subtitles...")
                        downloaded_subtitles = playlist_downloader.download_subtitles(movie_data, subtitles, playlist_download_path, config.downloads["format"])

                        # Assure subtitles downloaded successfully
                        if os.path.isfile(downloaded_subtitles):
                            downloaded_subtitles_paths.append(downloaded_subtitles)

                if separate_playlist_folder:
                    print(f"{playlist_subtitles_count} subtitles were downloaded.")

                    # Remove playlist folder if it's empty
                    if playlist_subtitles_count == 0:
                        os.rmdir(playlist_download_path)

                subtitles_count += playlist_subtitles_count

        # If files were downloaded to a temp folder ("zip" option was used)
        if download_to_temp:
            if len(downloaded_subtitles_paths) == 1:
                shutil.copy(downloaded_subtitles_paths[0], config.downloads["folder"])

            elif len(downloaded_subtitles_paths) > 1:
                # Create zip archive
                print(f"\nCreating zip archive...")
                archive_inital_path = os.path.join(download_path, os.path.basename(movie_download_path))
                archive_dest_path = shutil.make_archive(base_name=archive_inital_path, format="zip", root_dir=movie_download_path)
                shutil.copy(archive_dest_path, config.downloads["folder"])

            # Remove temp dir
            shutil.rmtree(movie_download_path)
            atexit.unregister(shutil.rmtree)

        # Add playlists count only if it's more than 1
        playlists_messgae = f"from {len(movie_data.playlists)} playlists " if len(movie_data.playlists) > 0 else ""

        print(f"\n{len(downloaded_subtitles_paths)}/{subtitles_count} matching subtitles ",
              f"for \"{movie_data.name}\" were downloaded {playlists_messgae}",
              f"to {os.path.abspath(config.downloads['folder'])}\".", sep="")


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
