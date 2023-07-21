from __future__ import annotations

import atexit
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import List

import requests
from requests.utils import default_user_agent

from isubrip.config import Config, ConfigException, ConfigSetting, SpecialConfigType
from isubrip.constants import ARCHIVE_FORMAT, DATA_FOLDER_PATH, DEFAULT_CONFIG_PATH, PACKAGE_NAME, TEMP_FOLDER_PATH, \
    USER_CONFIG_FILE, LOG_FILES_PATH, LOG_FILE_NAME
from isubrip.data_structures import Movie, ScrapedMediaResponse, SubtitlesDownloadResults, SubtitlesData
from isubrip.logger import CustomLogFileFormatter, CustomStdoutFormatter, logger
from isubrip.scrapers.scraper import Scraper, ScraperFactory
from isubrip.utils import download_subtitles_to_file, generate_non_conflicting_path, generate_release_name, \
    raise_for_status, single_to_list

LOG_ROTATION_SIZE: int | None = None

BASE_CONFIG_SETTINGS = [
    ConfigSetting(
        key="check-for-updates",
        type=bool,
        category="general",
        required=False,
    ),
    ConfigSetting(
        key="log_rotation_size",
        type=str,
        category="general",
        required=False,
    ),
    ConfigSetting(
        key="add-release-year-to-series",
        type=bool,
        category="downloads",
        required=False,
    ),
    ConfigSetting(
        key="folder",
        type=str,
        category="downloads",
        required=True,
        special_type=SpecialConfigType.EXISTING_FOLDER_PATH,
    ),
    ConfigSetting(
        key="languages",
        type=List[str],
        category="downloads",
        required=False,
    ),
    ConfigSetting(
        key="overwrite-existing",
        type=bool,
        category="downloads",
        required=True,
    ),
    ConfigSetting(
        key="zip",
        type=bool,
        category="downloads",
        required=False,
    ),
    ConfigSetting(
        key="fix-rtl",
        type=bool,
        category="subtitles",
        required=True,
    ),
    ConfigSetting(
        key="rtl-languages",
        type=List[str],
        category="subtitles",
        required=False,
    ),
    ConfigSetting(
        key="remove-duplicates",
        type=bool,
        category="subtitles",
        required=True,
    ),
    ConfigSetting(
        key="convert-to-srt",
        type=bool,
        category="subtitles",
        required=False,
    ),
    ConfigSetting(
        key="user-agent",
        type=str,
        category="scrapers",
        required=True,
    ),
]


def main():
    # Assure at least one argument was passed
    if len(sys.argv) < 2:
        print_usage()
        exit(0)

    create_required_folders()
    setup_loggers(stdout_loglevel=logging.INFO, file_loglevel=logging.DEBUG)

    cli_args = " ".join(sys.argv[1:])

    if sys.modules.get(PACKAGE_NAME):
        package_version = sys.modules[PACKAGE_NAME].__version__

    else:
        package_version = "Unknown"
        logger.debug("Could not find pack's version.")

    logger.debug(f'Used CLI Command: {PACKAGE_NAME} {cli_args}')
    logger.debug(f'Python version: {sys.version}')
    logger.debug(f'Package version: {package_version}')
    logger.debug(f'OS: {sys.platform}')

    config = generate_config()
    update_settings(config)

    if config.general.get("check-for-updates", True):
        check_for_updates()

    scraper_factory = ScraperFactory()

    for idx, url in enumerate(sys.argv[1:]):
        logger.info(f"Scraping '{url}'...")

        scraper = scraper_factory.get_scraper_instance(url=url, config_data=config.data.get("scrapers"))
        atexit.register(scraper.close)
        scraper.config.check()  # Recheck config after scraper settings were loaded

        scraper_response: ScrapedMediaResponse[Movie] = scraper.get_data(url=url)
        movie_data: list[Movie] = single_to_list(scraper_response.media_data)

        if not movie_data:
            logger.error(f"Error: No supported media was found for {url}.")
            continue

        download_media_subtitles_args = {
            "download_path": Path(config.downloads["folder"]),
            "language_filter": config.downloads.get("languages"),
            "convert_to_srt": config.subtitles.get("convert-to-srt", False),
            "overwrite_existing": config.downloads.get("overwrite-existing", False),
            "zip_files": config.downloads.get("zip", False),
        }

        for movie_item in movie_data:
            id_str = f" (ID: {movie_item.id})" if movie_item.id else ''
            logger.info(f"Found movie: {movie_item.name} [{movie_item.release_date.year}]" + id_str)

            if not movie_item.playlist:
                if movie_item.preorder_availability_date:
                    logger.info(f"'{movie_item.name}' is currently unavailable on '{scraper.name}'.\n"
                                f"Release date ({scraper.name}): {movie_item.preorder_availability_date}.")
                else:
                    logger.info(f"No valid playlist was found for '{movie_item.name}' on '{scraper.name}'.")

                continue

            try:
                results = download_subtitles(movie_data=movie_item,
                                             scraper=scraper,
                                             **download_media_subtitles_args)

                success_count = len(results.successful_subtitles)
                failed_count = len(results.failed_subtitles)

                if success_count:
                    logger.info(f"{success_count}/{success_count + failed_count} matching subtitles "
                                f"have been successfully downloaded.")

                elif failed_count:
                    logger.info(f"{failed_count} subtitles were matched, but failed to download.")

                else:
                    logger.info("No matching subtitles were found.")

            except Exception as e:
                logger.error(f"Error: Encountered an error while scraping '{url}'{id_str}: {e}")
                logger.debug(f"Error details: {e}", exc_info=True)
                continue


def check_for_updates() -> None:
    """Check and print if a newer version of the package is available."""
    api_url = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
    logger.debug("Checking for package updates on PyPI...")
    try:
        current_version = sys.modules[PACKAGE_NAME].__version__

        response = requests.get(
            url=api_url,
            headers={"Accept": "application/json"},
            timeout=10,
        )
        raise_for_status(response)
        response_data = response.json()

        pypi_latest_version = response_data["info"]["version"]

        if pypi_latest_version != current_version:
            logger.info(f"Found a newer version of {PACKAGE_NAME} - {pypi_latest_version}")

            logger.warning(f"Note: You are currently using version '{current_version}' of '{PACKAGE_NAME}', "
                           f"however version '{pypi_latest_version}' is available.",
                           f"\nConsider upgrading by running \"python3 -m pip install --upgrade {PACKAGE_NAME}\"\n")

        else:
            logger.debug(f"Latest version of {PACKAGE_NAME} ({current_version}) is currently installed.")

    except Exception as e:
        logger.warning(f"Update check failed: {e}")
        logger.debug(f"Stack trace: {e}", exc_info=True)
        return


def create_required_folders():
    if not DATA_FOLDER_PATH.is_dir():
        logger.debug(f"'{DATA_FOLDER_PATH}' directory could not be found and will be created.")
        LOG_FILES_PATH.mkdir(parents=True, exist_ok=True)

    else:
        if not LOG_FILES_PATH.is_dir():
            logger.debug(f"'{LOG_FILES_PATH}' directory could not be found and will be created.")
            LOG_FILES_PATH.mkdir()


def download_subtitles(movie_data: Movie, scraper: Scraper, download_path: Path,
                       language_filter: list[str] | None = None, convert_to_srt: bool = False,
                       overwrite_existing: bool = True, zip_files: bool = False) -> SubtitlesDownloadResults:
    """
    Download subtitles for the given media data.

    Args:
        movie_data (Movie | Episode): A Movie object.
        scraper (Scraper): A Scraper object to use for downloading subtitles.
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
    temp_download_path = generate_media_path(base_path=TEMP_FOLDER_PATH, movie_data=movie_data)
    atexit.register(shutil.rmtree, TEMP_FOLDER_PATH, ignore_errors=False, onerror=None)

    if not movie_data.playlist:
        raise ValueError("No playlist data was found for the given media data.")

    successful_downloads: list[SubtitlesData] = []
    failed_downloads: list[SubtitlesData] = []
    temp_downloads: list[Path] = []

    for subtitles_data in scraper.get_subtitles(main_playlist=movie_data.playlist,
                                                language_filter=language_filter,
                                                subrip_conversion=convert_to_srt):
        language_data = f"{subtitles_data.language_name} ({subtitles_data.language_code})"

        try:
            temp_downloads.append(download_subtitles_to_file(
                media_data=movie_data,
                subtitles_data=subtitles_data,
                output_path=temp_download_path,
                overwrite=overwrite_existing,
            ))

            logger.info(f"{language_data} subtitles were successfully downloaded.")
            successful_downloads.append(subtitles_data)

        except Exception as e:
            logger.error(f"Error: Failed to download '{language_data}' subtitles: {e}")
            logger.debug("Stack trace:", exc_info=True)
            failed_downloads.append(subtitles_data)
            continue

    if not zip_files or len(temp_downloads) == 1:
        for file_path in temp_downloads:
            if overwrite_existing:
                new_path = download_path / file_path.name

            else:
                new_path = generate_non_conflicting_path(download_path / file_path.name)

            # str conversion needed only for Python <= 3.8 - https://github.com/python/cpython/issues/76870
            shutil.move(src=str(file_path), dst=new_path)

    elif len(temp_downloads) > 0:
        archive_path = Path(shutil.make_archive(
            base_name=str(temp_download_path.parent / temp_download_path.name),
            format=ARCHIVE_FORMAT,
            root_dir=temp_download_path,
        ))

        file_name = generate_media_folder_name(movie_data=movie_data,
                                               source=scraper.abbreviation) + f".{ARCHIVE_FORMAT}"

        if overwrite_existing:
            destination_path = download_path / file_name

        else:
            destination_path = generate_non_conflicting_path(download_path / file_name)

        shutil.move(src=str(archive_path), dst=destination_path)

    shutil.rmtree(temp_download_path)
    atexit.unregister(shutil.rmtree)

    return SubtitlesDownloadResults(
        movie_data=movie_data,
        successful_subtitles=successful_downloads,
        failed_subtitles=failed_downloads,
        is_zip=zip_files,
    )

def handle_log_rotation(log_rotation_size: int):
    """
    Handle log rotation and remove old log files if needed.

    Args:
        log_rotation_size (int): Maximum amount of log files to keep.
    """
    log_files: list[Path] = sorted(LOG_FILES_PATH.glob("*.log"), key=os.path.getctime, reverse=True)

    if len(log_files) > log_rotation_size:
        for log_file in log_files[log_rotation_size:]:
            log_file.unlink()


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
    if not DEFAULT_CONFIG_PATH.is_file():
        raise ConfigException("Default config file could not be found.")

    config = Config(config_settings=BASE_CONFIG_SETTINGS)

    logger.debug(f"Loading default config data...")

    with open(DEFAULT_CONFIG_PATH, 'r') as data:
        config.loads(config_data=data.read(), check_config=True)

    logger.debug(f"Default config data loaded and validated successfully.")

    # If logs folder doesn't exist, create it (also handles data folder)
    if not DATA_FOLDER_PATH.is_dir():
        logger.debug(f"'{DATA_FOLDER_PATH}' directory could not be found and will be created.")
        DATA_FOLDER_PATH.mkdir(parents=True, exist_ok=True)
        LOG_FILES_PATH.mkdir()

    else:
        if not LOG_FILES_PATH.is_dir():
            logger.debug(f"'{LOG_FILES_PATH}' directory could not be found and will be created.")
            LOG_FILES_PATH.mkdir()

        # If a user config file exists, add it to config_files
        if USER_CONFIG_FILE.is_file():
            logger.info(f"User config file detected at '{USER_CONFIG_FILE}' and will be used.")
            with open(USER_CONFIG_FILE, 'r') as data:
                config.loads(config_data=data.read(), check_config=True)
            logger.debug(f"User config file loaded and validated successfully.")

    return config


def generate_media_folder_name(movie_data: Movie, source: str | None = None) -> str:
    """
    Generate a folder name for media data.

    Args:
        movie_data (MediaData): A movie data object.
        source (str | None, optional): Abbreviation of the source to use for file names. Defaults to None.

    Returns:
        str: A folder name for the media data.
    """
    return generate_release_name(
        title=movie_data.name,
        release_date=movie_data.release_date,
        media_source=source,
    )


def generate_media_path(base_path: Path, movie_data: Movie) -> Path:
    """
    Generate a temporary folder for downloading media data.

    Args:
        base_path (Path): A base path to generate the folder in.
        movie_data (MediaData): A movie data object.

    Returns:
        Path: A path to the temporary folder.
    """
    temp_folder_name = generate_media_folder_name(movie_data=movie_data)
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

    if log_rotation := config.general.get("log-rotation-size"):
        global LOG_ROTATION_SIZE
        LOG_ROTATION_SIZE = log_rotation


def print_usage() -> None:
    """Print usage information."""
    logger.info(f"Usage: {PACKAGE_NAME} <iTunes movie URL> [iTunes movie URL...]")


def setup_loggers(stdout_loglevel: int, file_loglevel: int) -> None:
    """
    Configure loggers.

    Args:
        stdout_loglevel (int): Log level for STDOUT logger.
        file_loglevel (int): Log level for logfile logger.
    """
    logger.setLevel(logging.DEBUG)

    # Setup STDOUT logger
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(stdout_loglevel)
    stdout_handler.setFormatter(CustomStdoutFormatter())
    logger.addHandler(stdout_handler)

    # Setup logfile logger
    logfile_path = generate_non_conflicting_path(LOG_FILES_PATH / LOG_FILE_NAME)
    logfile_handler = logging.FileHandler(filename=logfile_path, encoding="utf-8")
    logfile_handler.setLevel(file_loglevel)
    logfile_handler.setFormatter(CustomLogFileFormatter())
    logger.addHandler(logfile_handler)


if __name__ == "__main__":
    try:
        main()

    except Exception as ex:
        logger.error(f"Error: {ex}")
        logger.debug(f"Stack trace: {ex}", exc_info=True)
        exit(1)

    finally:
        if _log_rotation_size := LOG_ROTATION_SIZE:
            handle_log_rotation(log_rotation_size=_log_rotation_size)

        _scraper_factory = ScraperFactory()

        # Note: This will only close scrapers that were initialized using the ScraperFactory.
        for _scraper in _scraper_factory.get_initialized_scrapers():
            _scraper.close()
