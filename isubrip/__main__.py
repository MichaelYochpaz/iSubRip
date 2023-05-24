from __future__ import annotations

import atexit
import shutil
import sys
from pathlib import Path

import requests
from requests.utils import default_user_agent

from isubrip.config import Config, ConfigException
from isubrip.constants import ARCHIVE_FORMAT, DATA_FOLDER_PATH, DEFAULT_CONFIG_PATH, DEFAULT_CONFIG_SETTINGS, \
    PACKAGE_NAME, TEMP_FOLDER_PATH, USER_CONFIG_FILE
from isubrip.data_structures import EpisodeData,  MediaData, MovieData, SubtitlesDownloadResults, SubtitlesData
from isubrip.scrapers.scraper import Scraper, ScraperFactory
from isubrip.utils import download_subtitles_to_file, generate_non_conflicting_path, generate_release_name, \
    single_to_list


def main():
    scraper_factory = None

    try:
        # Assure at least one argument was passed
        if len(sys.argv) < 2:
            print_usage()
            exit(1)

        config = generate_config()
        update_settings(config)

        if config.general.get("check-for-updates", True):
            check_for_updates()

        scraper_factory = ScraperFactory()

        multiple_urls = len(sys.argv) > 2

        for idx, url in enumerate(sys.argv[1:]):
            if idx > 0:
                print("\n--------------------------------------------------\n")  # Print between different movies

            print(f"Scraping {url}")

            try:
                scraper = scraper_factory.get_scraper_instance(url=url, config_data=config.data.get("scrapers"))
                atexit.register(scraper.close)
                scraper.config.check()

                media_data: MovieData = scraper.get_data(url=url)
                media_items: list[MovieData] = single_to_list(media_data)

                print(f"Found movie: {media_items[0].name} ({media_items[0].release_date.year})")

                if not media_data:
                    print(f"Error: No supported media data was found for {url}.")
                    continue

                download_media_subtitles_args = {
                    "download_path": Path(config.downloads["folder"]),
                    "language_filter": config.downloads.get("languages"),
                    "convert_to_srt": config.subtitles.get("convert-to-srt", False),
                    "overwrite_existing": config.downloads.get("overwrite-existing", False),
                    "zip_files": config.downloads.get("zip", False),
                }

                multiple_media_items = len(media_items) > 1
                if multiple_media_items:
                    print(f"{len(media_items)} media items were found.")

                for media_item in media_items:
                    media_id = media_item.id or media_item.alt_id or media_item.name

                    try:
                        if multiple_media_items:
                            print(f"{media_id}:")

                        if not media_item.playlist:
                            if media_data.preorder_availability_date:
                                message = f"{media_item.name} is currently unavailable on " \
                                          f"{media_item.scraper.name}.\n" \
                                          f"Release date ({media_item.scraper.name}): " \
                                          f"{media_data.preorder_availability_date}."
                            else:
                                message = f"No valid playlist was found for {media_item.name} on {scraper.name}."

                            print(message)
                            continue

                        results = download_subtitles(media_data=media_item,
                                                     **download_media_subtitles_args)

                        success_count = len(results.successful_subtitles)

                        if not success_count:
                            print("No matching subtitles were found.")
                            continue

                        else:
                            failed_count = len(results.failed_subtitles)
                            print(f"\n{success_count}/{success_count + failed_count} matching subtitles "
                                  f"have been successfully downloaded.", sep='')

                    except Exception as e:
                        if multiple_media_items:
                            print(f"Error: Encountered an error while scraping playlist for "
                                  f"{media_id}: {e}")
                            continue

                        else:
                            raise e

            except Exception as e:
                if multiple_urls:
                    print(f"Error: Encountered an error while scraping {url}: {e}")
                    continue

                else:
                    raise e

    except Exception as e:
        print(f"Error: {e}")
        exit(1)

    finally:
        # Note: This will only close scrapers that were initialized using the ScraperFactory.
        if scraper_factory:
            for scraper in scraper_factory.get_initialized_scrapers():
                scraper.close()


def check_for_updates() -> None:
    """Check and print if a newer version of the package is available."""
    api_url = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"

    try:
        current_version = sys.modules[PACKAGE_NAME].__version__

        response = requests.get(
            url=api_url,
            headers={"Accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        response_data = response.json()

        if latest_version := response_data["info"]["version"]:
            if latest_version != current_version:
                print(f"Note: You are currently using version {current_version} of {PACKAGE_NAME}, "
                      f"however version {latest_version} is available.",
                      f"\nConsider upgrading by running \"python3 -m pip install --upgrade {PACKAGE_NAME}\"\n")

    except Exception:
        return


def download_subtitles(media_data: MovieData | EpisodeData, download_path: Path,
                       language_filter: list[str] | None = None, convert_to_srt: bool = False,
                       overwrite_existing: bool = True, zip_files: bool = False) -> SubtitlesDownloadResults:
    """
    Download subtitles for the given media data.

    Args:
        media_data (MovieData | EpisodeData): A MovieData or an EpisodeData object of the media.
        download_path (Path): Path to a folder where the subtitles will be downloaded to.
        language_filter (list[str] | None): List of specific languages to download subtitles for.
            None for all languages (no filter). Defaults to None.
        convert_to_srt (bool, optional): Whether to convert the subtitles to SRT format. Defaults to False.
        overwrite_existing (bool, optional): Whether to overwrite existing subtitles. Defaults to True.
        zip_files (bool, optional): Whether to unite the subtitles into a single zip file
            (only if there are multiple subtitles).

    Returns:
        Path: Path to the parent folder of the downloaded subtitles files / zip file.
    """
    temp_download_path = generate_media_path(base_path=TEMP_FOLDER_PATH, media_data=media_data)
    atexit.register(shutil.rmtree, TEMP_FOLDER_PATH, ignore_errors=False, onerror=None)

    if not media_data.playlist:
        raise ValueError("No playlist data was found for the given media data.")

    successful_downloads: list[SubtitlesData] = []
    failed_downloads: list[SubtitlesData] = []
    temp_downloads: list[Path] = []

    playlist = single_to_list(media_data.playlist)[0]

    for subtitles_data in media_data.scraper.get_subtitles(main_playlist=playlist.data,
                                                           language_filter=language_filter,
                                                           subrip_conversion=convert_to_srt):
        try:
            temp_downloads.append(download_subtitles_to_file(
                media_data=media_data,
                subtitles_data=subtitles_data,
                output_path=temp_download_path,
                overwrite=overwrite_existing,
            ))

            successful_downloads.append(subtitles_data)
            language_data = f"{subtitles_data.language_name} ({subtitles_data.language_code})"

            print(f"{language_data} subtitles were successfully downloaded.")

        except Exception:
            failed_downloads.append(subtitles_data)
            continue

    if not zip_files or len(temp_downloads) == 1:
        for file_path in temp_downloads:
            if overwrite_existing:
                file_path.replace(download_path / file_path.name)

            else:
                file_path.replace(generate_non_conflicting_path(download_path / file_path.name))

    else:
        archive_path = Path(shutil.make_archive(
            base_name=str(temp_download_path.parent / temp_download_path.name),
            format=ARCHIVE_FORMAT,
            root_dir=temp_download_path,
        ))

        file_name = generate_media_folder_name(media_data=media_data) + f".{ARCHIVE_FORMAT}"

        if overwrite_existing:
            destination_path = download_path / file_name

        else:
            destination_path = generate_non_conflicting_path(download_path / file_name)

        archive_path.replace(destination_path)

    shutil.rmtree(temp_download_path)
    atexit.unregister(shutil.rmtree)

    return SubtitlesDownloadResults(
        media_data=media_data,
        successful_subtitles=successful_downloads,
        failed_subtitles=failed_downloads,
        is_zip=zip_files,
    )


def generate_config() -> Config:
    """
    Generate a config object using config files, and validate it.

    Returns:
        Config: A config object.

    Raises:
        ConfigException: If there is a general config error.
        MissingConfigValue: If a required config value is missing.
        InvalidConfigValue: If a config value is invalid.
    """
    config_files = [DEFAULT_CONFIG_PATH]

    if not DEFAULT_CONFIG_PATH.is_file():
        raise ConfigException("Default config file could not be found.")

    # If data folder doesn't exist, create it
    if not DATA_FOLDER_PATH.is_dir():
        DATA_FOLDER_PATH.mkdir(parents=True, exist_ok=True)

    else:
        # If a user config file exists, add it to config_files
        if USER_CONFIG_FILE.is_file():
            config_files.append(USER_CONFIG_FILE)

    config = Config(config_settings=DEFAULT_CONFIG_SETTINGS)

    for file_path in config_files:
        with open(file_path, 'r') as data:
            config.loads(config_data=data.read(), check_config=True)

    config.check()
    return config


def generate_media_folder_name(media_data: MediaData) -> str:
    """
    Generate a folder name for media data.

    Args:
        media_data (MediaData): A media data object.

    Returns:
        str: A folder name for the media data.
    """
    return generate_release_name(
        title=media_data.name,
        release_year=media_data.release_date.year,
        media_source=media_data.scraper.abbreviation,
    )


def generate_media_path(base_path: Path, media_data: MediaData) -> Path:
    """
    Generate a temporary folder for downloading media data.

    Args:
        base_path (Path): A base path to generate the folder in.
        media_data (MediaData): A media data object.

    Returns:
        Path: A path to the temporary folder.
    """
    temp_folder_name = generate_media_folder_name(media_data=media_data)
    path = generate_non_conflicting_path(base_path / temp_folder_name, has_extension=False)
    path.mkdir(parents=True, exist_ok=True)

    return path


def update_settings(config: Config) -> None:
    """
    Update settings according to config.

    Args:
        config (Config): An instance of a config to set settings according to.
    """
    Scraper.subtitles_fix_rtl = config.subtitles["fix-rtl"]
    Scraper.subtitles_fix_rtl_languages = config.subtitles.get("rtl-languages")
    Scraper.subtitles_remove_duplicates = config.subtitles["remove-duplicates"]
    Scraper.default_user_agent = config.scrapers.get("user-agent", default_user_agent())


def print_usage() -> None:
    """Print usage information."""
    print(f"Usage: {PACKAGE_NAME} <iTunes movie URL> [iTunes movie URL...]")


if __name__ == "__main__":
    main()
