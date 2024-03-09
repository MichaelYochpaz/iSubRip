from __future__ import annotations

import logging
from pathlib import Path
import shutil
import sys
from typing import List

import requests
from requests.utils import default_user_agent

from isubrip.config import Config, ConfigError, ConfigSetting, SpecialConfigType
from isubrip.constants import (
    ARCHIVE_FORMAT,
    DATA_FOLDER_PATH,
    DEFAULT_CONFIG_PATH,
    LOG_FILE_NAME,
    LOG_FILES_PATH,
    PACKAGE_NAME,
    PACKAGE_VERSION,
    PREORDER_MESSAGE,
    TEMP_FOLDER_PATH,
    USER_CONFIG_FILE,
)
from isubrip.data_structures import (
    Episode,
    MediaData,
    Movie,
    ScrapedMediaResponse,
    Season,
    Series,
    SubtitlesData,
    SubtitlesDownloadResults,
)
from isubrip.logger import CustomLogFileFormatter, CustomStdoutFormatter, logger
from isubrip.scrapers.scraper import PlaylistLoadError, Scraper, ScraperError, ScraperFactory
from isubrip.subtitle_formats.webvtt import Caption as WebVTTCaption
from isubrip.utils import (
    TempDirGenerator,
    download_subtitles_to_file,
    format_media_description,
    format_release_name,
    format_subtitles_description,
    generate_non_conflicting_path,
    raise_for_status,
    single_to_list,
)

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
        key="subrip-alignment-conversion",
        type=bool,
        category=("subtitles", "webvtt"),
        required=False,
    ),
    ConfigSetting(
        key="user-agent",
        type=str,
        category="scrapers",
        required=True,
    ),
    ConfigSetting(
        key="proxy",
        type=str,
        category="scrapers",
        required=False,
    ),
    ConfigSetting(
        key="verify-ssl",
        type=bool,
        category="scrapers",
        required=False,
    ),
]


def main() -> None:
    try:
        # Assure at least one argument was passed
        if len(sys.argv) < 2:
            print_usage()
            exit(0)

        setup_loggers(stdout_loglevel=logging.INFO,
                      file_loglevel=logging.DEBUG)

        generate_project_folders()

        cli_args = " ".join(sys.argv[1:])
        logger.debug(f"Used CLI Command: {PACKAGE_NAME} {cli_args}")
        logger.debug(f"Python version: {sys.version}")
        logger.debug(f"Package version: {PACKAGE_VERSION}")
        logger.debug(f"OS: {sys.platform}")

        config = generate_config()
        update_settings(config)

        if config.general.get("check-for-updates", True):
            check_for_updates(current_package_version=PACKAGE_VERSION)

        urls = single_to_list(sys.argv[1:])
        download(urls=urls, config=config)

    except Exception as ex:
        logger.error(f"Error: {ex}")
        logger.debug(f"Stack trace: {ex}", exc_info=True)
        exit(1)

    finally:
        if log_rotation_size := LOG_ROTATION_SIZE:
            handle_log_rotation(log_rotation_size=log_rotation_size)

        # NOTE: This will only close scrapers that were initialized using the ScraperFactory.
        for scraper in ScraperFactory.get_initialized_scrapers():
            scraper.close()

        TempDirGenerator.cleanup()


def download(urls: list[str], config: Config) -> None:
    """
    Download subtitles from a given URL.

    Args:
        urls (list[str]): A list of URLs to download subtitles from.
        config (Config): A config to use for downloading subtitles.
    """
    for url in urls:
        try:
            logger.info(f"Scraping '{url}'...")

            scraper = ScraperFactory.get_scraper_instance(url=url,
                                                          kwargs={"config_data": config.data.get("scrapers")},
                                                          extract_scraper_config=True)
            scraper.config.check()  # Recheck config after scraper settings were loaded

            try:
                logger.debug(f"Fetching '{url}'...")
                scraper_response: ScrapedMediaResponse = scraper.get_data(url=url)

            except ScraperError as e:
                logger.error(f"Error: {e}")
                logger.debug("Debug information:", exc_info=True)
                continue

            media_data = scraper_response.media_data
            playlist_scraper = ScraperFactory.get_scraper_instance(scraper_id=scraper_response.playlist_scraper,
                                                                   kwargs={"config_data": config.data.get("scrapers")},
                                                                   extract_scraper_config=True)

            if not media_data:
                logger.error(f"Error: No supported media was found for {url}.")
                continue

            for media_item in media_data:
                try:
                    object_type_str = media_item.__class__.__name__.lower()

                    logger.info(f"Found {object_type_str}: {format_media_description(media_data=media_item)}")
                    download_media(scraper=playlist_scraper, media_item=media_item, config=config)

                except Exception as e:
                    if len(media_data) > 1:
                        logger.warning(f"Error scraping media item "
                                       f"'{format_media_description(media_data=media_item)}': {e}\n"
                                       f"Skipping to next media item...")
                        logger.debug("Debug information:", exc_info=True)
                        continue

                    raise

        except Exception as e:
            logger.error(f"Error while scraping '{url}': {e}")
            logger.debug("Debug information:", exc_info=True)
            continue


def download_media(scraper: Scraper, media_item: MediaData, config: Config) -> None:
    """
    Download a media item.

    Args:
        scraper (Scraper): A Scraper object to use for downloading subtitles.
        media_item (MediaData): A media data item to download subtitles for.
        config (Config): A config to use for downloading subtitles.
    """
    if isinstance(media_item, Series):
        for season in media_item.seasons:
            download_media(scraper=scraper, media_item=season, config=config)
        return

    if isinstance(media_item, Season):
        for episode in media_item.episodes:
            logger.info(f"{format_media_description(media_data=episode, shortened=True)}:")
            download_media(scraper=scraper, media_item=episode, config=config)
        return

    if media_item.playlist:
        download_subtitles_kwargs = {
            "download_path": Path(config.downloads["folder"]),
            "language_filter": config.downloads.get("languages"),
            "convert_to_srt": config.subtitles.get("convert-to-srt", False),
            "overwrite_existing": config.downloads.get("overwrite-existing", False),
            "zip_files": config.downloads.get("zip", False),
        }

        try:
            results = download_subtitles(scraper=scraper,
                                         media_data=media_item,
                                         **download_subtitles_kwargs)

            success_count = len(results.successful_subtitles)
            failed_count = len(results.failed_subtitles)

            if success_count:
                logger.info(f"{success_count}/{success_count + failed_count} matching subtitles "
                            f"have been successfully downloaded.")

            elif failed_count:
                logger.info(f"{failed_count} subtitles were matched, but failed to download.")

            else:
                logger.info("No matching subtitles were found.")

            return  # noqa: TRY300

        except PlaylistLoadError:
            pass

    # We get here if there is no playlist, or there is one, but it failed to load
    if isinstance(media_item, Movie) and media_item.preorder_availability_date:
        preorder_date_str = media_item.preorder_availability_date.strftime("%Y-%m-%d")
        logger.info(PREORDER_MESSAGE.format(movie_name=media_item.name, scraper_name=scraper.name,
                                            preorder_date=preorder_date_str))

    else:
        logger.error("No valid playlist was found.")


def check_for_updates(current_package_version: str) -> None:
    """
    Check and print if a newer version of the package is available, and log accordingly.

    Args:
        current_package_version (str): The current version of the package.
    """
    api_url = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
    logger.debug("Checking for package updates on PyPI...")
    try:
        response = requests.get(
            url=api_url,
            headers={"Accept": "application/json"},
            timeout=5,
        )
        raise_for_status(response)
        response_data = response.json()

        pypi_latest_version = response_data["info"]["version"]

        if pypi_latest_version != current_package_version:
            logger.warning(f"You are currently using version '{current_package_version}' of '{PACKAGE_NAME}', "
                           f"however version '{pypi_latest_version}' is available."
                           f'\nConsider upgrading by running "python3 -m pip install --upgrade {PACKAGE_NAME}"\n')

        else:
            logger.debug(f"Latest version of '{PACKAGE_NAME}' ({current_package_version}) is currently installed.")

    except Exception as e:
        logger.warning(f"Update check failed: {e}")
        logger.debug(f"Stack trace: {e}", exc_info=True)
        return


def generate_project_folders() -> None:
    if not DATA_FOLDER_PATH.is_dir():
        logger.debug(f"'{DATA_FOLDER_PATH}' directory could not be found and will be created.")
        LOG_FILES_PATH.mkdir(parents=True, exist_ok=True)

    else:  # LOG_FILES_PATH is inside DATA_FOLDER_PATH
        if not LOG_FILES_PATH.is_dir():
            logger.debug(f"'{LOG_FILES_PATH}' directory could not be found and will be created.")
            LOG_FILES_PATH.mkdir()

def download_subtitles(scraper: Scraper, media_data: Movie | Episode, download_path: Path,
                       language_filter: list[str] | None = None, convert_to_srt: bool = False,
                       overwrite_existing: bool = True, zip_files: bool = False) -> SubtitlesDownloadResults:
    """
    Download subtitles for the given media data.

    Args:
        scraper (Scraper): A Scraper object to use for downloading subtitles.
        media_data (Movie | Episode): A movie or episode data object.
        download_path (Path): Path to a folder where the subtitles will be downloaded to.
        language_filter (list[str] | None): List of specific languages to download subtitles for.
            None for all languages (no filter). Defaults to None.
        convert_to_srt (bool, optional): Whether to convert the subtitles to SRT format. Defaults to False.
        overwrite_existing (bool, optional): Whether to overwrite existing subtitles. Defaults to True.
        zip_files (bool, optional): Whether to unite the subtitles into a single zip file
            (only if there are multiple subtitles).

    Returns:
        SubtitlesDownloadResults: A SubtitlesDownloadResults object containing the results of the download.
    """
    temp_dir_name = generate_media_folder_name(media_data=media_data, source=scraper.abbreviation)
    temp_download_path = TempDirGenerator.generate(directory_name=temp_dir_name)

    successful_downloads: list[SubtitlesData] = []
    failed_downloads: list[SubtitlesData] = []
    temp_downloads: list[Path] = []

    for subtitles_data in scraper.get_subtitles(main_playlist=media_data.playlist,  # type: ignore[arg-type]
                                                language_filter=language_filter,
                                                subrip_conversion=convert_to_srt):

        language_info = format_subtitles_description(language_code=subtitles_data.language_code,
                                                     language_name=subtitles_data.language_name,
                                                     special_type=subtitles_data.special_type)

        try:
            temp_downloads.append(download_subtitles_to_file(
                media_data=media_data,
                subtitles_data=subtitles_data,
                output_path=temp_download_path,
                source_abbreviation=scraper.abbreviation,
                overwrite=overwrite_existing,
            ))

            logger.info(f"{language_info} subtitles were successfully downloaded.")
            successful_downloads.append(subtitles_data)

        except Exception as e:
            logger.error(f"Error: Failed to download '{language_info}' subtitles: {e}")
            logger.debug("Stack trace:", exc_info=True)
            failed_downloads.append(subtitles_data)
            continue

    if not zip_files or len(temp_downloads) == 1:
        for file_path in temp_downloads:
            if overwrite_existing:
                new_path = download_path / file_path.name

            else:
                new_path = generate_non_conflicting_path(file_path=download_path / file_path.name)

            # str conversion needed only for Python <= 3.8 - https://github.com/python/cpython/issues/76870
            shutil.move(src=str(file_path), dst=new_path)

    elif len(temp_downloads) > 0:
        archive_path = Path(shutil.make_archive(
            base_name=str(temp_download_path.parent / temp_download_path.name),
            format=ARCHIVE_FORMAT,
            root_dir=temp_download_path,
        ))

        file_name = generate_media_folder_name(media_data=media_data,
                                               source=scraper.abbreviation) + f".{ARCHIVE_FORMAT}"

        if overwrite_existing:
            destination_path = download_path / file_name

        else:
            destination_path = generate_non_conflicting_path(file_path=download_path / file_name)

        shutil.move(src=str(archive_path), dst=destination_path)

    return SubtitlesDownloadResults(
        movie_data=media_data,
        successful_subtitles=successful_downloads,
        failed_subtitles=failed_downloads,
        is_zip=zip_files,
    )


def handle_log_rotation(log_rotation_size: int) -> None:
    """
    Handle log rotation and remove old log files if needed.

    Args:
        log_rotation_size (int): Maximum amount of log files to keep.
    """
    sorted_log_files = sorted(LOG_FILES_PATH.glob("*.log"), key=lambda file: file.stat().st_mtime, reverse=True)

    if len(sorted_log_files) > log_rotation_size:
        for log_file in sorted_log_files[log_rotation_size:]:
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
        raise ConfigError("Default config file could not be found.")

    config = Config(config_settings=BASE_CONFIG_SETTINGS)

    logger.debug("Loading default config data...")

    with DEFAULT_CONFIG_PATH.open('r') as data:
        config.loads(config_data=data.read(), check_config=True)

    logger.debug("Default config data loaded and validated successfully.")

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

            with USER_CONFIG_FILE.open('r') as data:
                config.loads(config_data=data.read(), check_config=True)

            logger.debug("User config file loaded and validated successfully.")

    return config


def generate_media_folder_name(media_data: Movie | Episode, source: str | None = None) -> str:
    """
    Generate a folder name for media data.

    Args:
        media_data (Movie | Episode): A movie or episode data object.
        source (str | None, optional): Abbreviation of the source to use for file names. Defaults to None.

    Returns:
        str: A folder name for the media data.
    """
    if isinstance(media_data, Movie):
        return format_release_name(
            title=media_data.name,
            release_date=media_data.release_date,
            media_source=source,
        )

    # elif isinstance(media_data, Episode):
    return format_release_name(
        title=media_data.series_name,
        season_number=media_data.season_number,
        media_source=source,
    )


def generate_temp_media_path(media_data: Movie | Episode, source: str | None = None) -> Path:
    """
    Generate a temporary directory for downloading media data.

    Args:
        media_data (Movie | Episode): A movie or episode data object.
        source (str | None, optional): Abbreviation of the source to use for file names. Defaults to None.

    Returns:
        Path: A path to the temporary folder.
    """
    temp_folder_name = generate_media_folder_name(media_data=media_data, source=source)
    path = generate_non_conflicting_path(file_path=TEMP_FOLDER_PATH / temp_folder_name, has_extension=False)

    return TempDirGenerator.generate(directory_name=path.name)


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
    Scraper.default_proxy = config.scrapers.get("proxy")
    Scraper.default_verify_ssl = config.scrapers.get("verify-ssl", True)

    if not Scraper.default_verify_ssl:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    WebVTTCaption.subrip_alignment_conversion = (
        config.subtitles.get("webvtt", {}).get("subrip-alignment-conversion", False)
    )

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
    logfile_path = generate_non_conflicting_path(file_path=LOG_FILES_PATH / LOG_FILE_NAME)
    logfile_handler = logging.FileHandler(filename=logfile_path, encoding="utf-8")
    logfile_handler.setLevel(file_loglevel)
    logfile_handler.setFormatter(CustomLogFileFormatter())
    logger.addHandler(logfile_handler)


if __name__ == "__main__":
    main()
