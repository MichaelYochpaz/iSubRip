from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import shutil
import sys

import httpx
from pydantic import ValidationError

from isubrip.config import Config
from isubrip.constants import (
    ARCHIVE_FORMAT,
    DATA_FOLDER_PATH,
    EVENT_LOOP,
    LOG_FILE_NAME,
    LOG_FILES_PATH,
    PACKAGE_NAME,
    PACKAGE_VERSION,
    PREORDER_MESSAGE,
    TEMP_FOLDER_PATH,
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
from isubrip.scrapers.scraper import PlaylistLoadError, Scraper, ScraperError, ScraperFactory, SubtitlesDownloadError
from isubrip.subtitle_formats.webvtt import WebVTTCaptionBlock
from isubrip.utils import (
    TempDirGenerator,
    download_subtitles_to_file,
    format_config_validation_error,
    format_media_description,
    format_release_name,
    format_subtitles_description,
    generate_non_conflicting_path,
    get_model_field,
    raise_for_status,
    single_to_list,
)

LOG_ROTATION_SIZE: int | None = None



def main() -> None:
    try:
        # Assure at least one argument was passed
        if len(sys.argv) < 2:
            print_usage()
            exit(0)

        if not DATA_FOLDER_PATH.is_dir():
            DATA_FOLDER_PATH.mkdir(parents=True)

        setup_loggers(stdout_loglevel=logging.INFO,
                      file_loglevel=logging.DEBUG)

        cli_args = " ".join(sys.argv[1:])
        logger.debug(f"CLI Command: {PACKAGE_NAME} {cli_args}")
        logger.debug(f"Python version: {sys.version}")
        logger.debug(f"Package version: {PACKAGE_VERSION}")
        logger.debug(f"OS: {sys.platform}")

        try:
            config = Config()

        except ValidationError as e:
            logger.error("Invalid configuration - the following errors were found in the configuration file:\n"
                         "---\n" +
                         format_config_validation_error(exc=e) +
                         "---\n"
                         "Please update your configuration to resolve the issue.")
            logger.debug("Debug information:", exc_info=True)
            exit(1)

        update_settings(config=config)

        if config.general.check_for_updates:
            check_for_updates(current_package_version=PACKAGE_VERSION)

        urls = single_to_list(sys.argv[1:])
        EVENT_LOOP.run_until_complete(download(urls=urls, config=config))

    except Exception as ex:
        logger.error(f"Error: {ex}")
        logger.debug("Debug information:", exc_info=True)
        exit(1)

    finally:
        if log_rotation_size := LOG_ROTATION_SIZE:
            handle_log_rotation(log_rotation_size=log_rotation_size)

        # NOTE: This will only close scrapers that were initialized using the ScraperFactory.
        async_cleanup_coroutines = []
        for scraper in ScraperFactory.get_initialized_scrapers():
            logger.debug(f"Requests count for '{scraper.name}' scraper: {scraper.requests_count}")
            scraper.close()
            async_cleanup_coroutines.append(scraper.async_close())

        EVENT_LOOP.run_until_complete(asyncio.gather(*async_cleanup_coroutines))
        TempDirGenerator.cleanup()


async def download(urls: list[str], config: Config) -> None:
    """
    Download subtitles from a given URL.

    Args:
        urls (list[str]): A list of URLs to download subtitles from.
        config (Config): A config to use for downloading subtitles.
    """
    scrapers_configs = {
        scraper_id: get_model_field(config.scrapers, scraper_id) for scraper_id in config.scrapers.model_fields
    }

    for url in urls:
        try:
            logger.info(f"Scraping '{url}'...")

            scraper = ScraperFactory.get_scraper_instance(url=url, scrapers_configs=scrapers_configs)

            try:
                logger.debug(f"Fetching '{url}'...")
                scraper_response: ScrapedMediaResponse = await scraper.get_data(url=url)

            except ScraperError as e:
                logger.error(f"Error: {e}")
                logger.debug("Debug information:", exc_info=True)
                continue

            media_data = scraper_response.media_data
            playlist_scraper = ScraperFactory.get_scraper_instance(scraper_id=scraper_response.playlist_scraper,
                                                                   scrapers_configs=scrapers_configs)

            if not media_data:
                logger.error(f"Error: No supported media was found for {url}.")
                continue

            for media_item in media_data:
                try:
                    logger.info(f"Found {media_item.media_type}: {format_media_description(media_data=media_item)}")
                    await download_media(scraper=playlist_scraper,
                                         media_item=media_item,
                                         download_path=config.downloads.folder,
                                         language_filter=config.downloads.languages,
                                         convert_to_srt=config.subtitles.convert_to_srt,
                                         overwrite_existing=config.downloads.overwrite_existing,
                                         archive=config.downloads.zip)

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


async def download_media(scraper: Scraper, media_item: MediaData, download_path: Path,
                              language_filter: list[str] | None = None, convert_to_srt: bool = False,
                              overwrite_existing: bool = True, archive: bool = False) -> None:
    """
    Download a media item.

    Args:
        scraper (Scraper): A Scraper object to use for downloading subtitles.
        media_item (MediaData): A media data item to download subtitles for.
        download_path (Path): Path to a folder where the subtitles will be downloaded to.
        language_filter (list[str] | None): List of specific languages to download subtitles for.
            None for all languages (no filter). Defaults to None.
        convert_to_srt (bool, optional): Whether to convert the subtitles to SRT format. Defaults to False.
        overwrite_existing (bool, optional): Whether to overwrite existing subtitles. Defaults to True.
        archive (bool, optional): Whether to archive the subtitles into a single zip file
            (only if there are multiple subtitles).
    """
    if isinstance(media_item, Series):
        for season in media_item.seasons:
            await download_media(media_item=season, scraper=scraper, download_path=download_path,
                                 language_filter=language_filter, convert_to_srt=convert_to_srt,
                                 overwrite_existing=overwrite_existing, archive=archive)

    elif isinstance(media_item, Season):
        for episode in media_item.episodes:
            logger.info(f"{format_media_description(media_data=episode, shortened=True)}:")
            await download_media_item(media_item=episode, scraper=scraper, download_path=download_path,
                                 language_filter=language_filter, convert_to_srt=convert_to_srt,
                                 overwrite_existing=overwrite_existing, archive=archive)

    elif isinstance(media_item, (Movie, Episode)):
        await download_media_item(media_item=media_item, scraper=scraper, download_path=download_path,
                                 language_filter=language_filter, convert_to_srt=convert_to_srt,
                                 overwrite_existing=overwrite_existing, archive=archive)


async def download_media_item(scraper: Scraper, media_item: Movie | Episode, download_path: Path,
                              language_filter: list[str] | None = None, convert_to_srt: bool = False,
                              overwrite_existing: bool = True, archive: bool = False) -> None:
    """
    Download subtitles for a single media item.

    Args:
        scraper (Scraper): A Scraper object to use for downloading subtitles.
        media_item (Movie | Episode): A movie or episode data object.
        download_path (Path): Path to a folder where the subtitles will be downloaded to.
        language_filter (list[str] | None): List of specific languages to download subtitles for.
            None for all languages (no filter). Defaults to None.
        convert_to_srt (bool, optional): Whether to convert the subtitles to SRT format. Defaults to False.
        overwrite_existing (bool, optional): Whether to overwrite existing subtitles. Defaults to True.
        archive (bool, optional): Whether to archive the subtitles into a single zip file
            (only if there are multiple subtitles).
    """
    ex: Exception | None = None

    if media_item.playlist:
        try:
            results = await download_subtitles(
                scraper=scraper,
                media_data=media_item,
                download_path=download_path,
                language_filter=language_filter,
                convert_to_srt=convert_to_srt,
                overwrite_existing=overwrite_existing,
                archive=archive,
            )

            success_count = len(results.successful_subtitles)
            failed_count = len(results.failed_subtitles)

            if success_count or failed_count:
                logger.info(f"{success_count}/{success_count + failed_count} matching subtitles "
                            f"were successfully downloaded.")

            else:
                logger.info("No matching subtitles were found.")

            return  # noqa: TRY300

        except PlaylistLoadError as e:
            ex = e

    # We get here if there is no playlist, or there is one, but it failed to load
    if isinstance(media_item, Movie) and media_item.preorder_availability_date:
        preorder_date_str = media_item.preorder_availability_date.strftime("%Y-%m-%d")
        logger.info(PREORDER_MESSAGE.format(movie_name=media_item.name, scraper_name=scraper.name,
                                            preorder_date=preorder_date_str))

    else:
        if ex:
            logger.error(f"Error: {ex}")

        else:
            logger.error("Error: No valid playlist was found.")


def check_for_updates(current_package_version: str) -> None:
    """
    Check and print if a newer version of the package is available, and log accordingly.

    Args:
        current_package_version (str): The current version of the package.
    """
    api_url = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
    logger.debug("Checking for package updates on PyPI...")
    try:
        response = httpx.get(
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
                           f'\nConsider upgrading by running "pip install --upgrade {PACKAGE_NAME}"\n')

        else:
            logger.debug(f"Latest version of '{PACKAGE_NAME}' ({current_package_version}) is currently installed.")

    except Exception as e:
        logger.warning(f"Update check failed: {e}")
        logger.debug("Debug information:", exc_info=True)
        return


async def download_subtitles(scraper: Scraper, media_data: Movie | Episode, download_path: Path,
                             language_filter: list[str] | None = None, convert_to_srt: bool = False,
                             overwrite_existing: bool = True, archive: bool = False) -> SubtitlesDownloadResults:
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
        archive (bool, optional): Whether to archive the subtitles into a single zip file
            (only if there are multiple subtitles).

    Returns:
        SubtitlesDownloadResults: A SubtitlesDownloadResults object containing the results of the download.
    """
    temp_dir_name = generate_media_folder_name(media_data=media_data, source=scraper.abbreviation)
    temp_download_path = TempDirGenerator.generate(directory_name=temp_dir_name)

    successful_downloads: list[SubtitlesData] = []
    failed_downloads: list[SubtitlesDownloadError] = []
    temp_downloads: list[Path] = []

    if not media_data.playlist:
        raise PlaylistLoadError("No playlist was found for provided media data.")

    main_playlist = await scraper.load_playlist(url=media_data.playlist)  # type: ignore[func-returns-value]

    if not main_playlist:
        raise PlaylistLoadError("Failed to load the main playlist.")

    matching_subtitles = scraper.find_matching_subtitles(main_playlist=main_playlist,  # type: ignore[var-annotated]
                                                         language_filter=language_filter)

    logger.debug(f"{len(matching_subtitles)} matching subtitles were found.")

    for matching_subtitles_item in matching_subtitles:
        subtitles_data = await scraper.download_subtitles(media_data=matching_subtitles_item,
                                                          subrip_conversion=convert_to_srt)
        language_info = format_subtitles_description(language_code=subtitles_data.language_code,
                                                     language_name=subtitles_data.language_name,
                                                     special_type=subtitles_data.special_type)

        if isinstance(subtitles_data, SubtitlesDownloadError):
            logger.warning(f"Failed to download '{language_info}' subtitles. Skipping...")
            logger.debug("Debug information:", exc_info=subtitles_data.original_exc)
            failed_downloads.append(subtitles_data)
            continue

        try:
            temp_downloads.append(download_subtitles_to_file(
                media_data=media_data,
                subtitles_data=subtitles_data,
                output_path=temp_download_path,
                source_abbreviation=scraper.abbreviation,
                overwrite=overwrite_existing,
            ))

            logger.info(f"'{language_info}' subtitles were successfully downloaded.")
            successful_downloads.append(subtitles_data)

        except Exception as e:
            logger.error(f"Error: Failed to save '{language_info}' subtitles: {e}")
            logger.debug("Debug information:", exc_info=True)
            failed_downloads.append(
                SubtitlesDownloadError(
                    language_code=subtitles_data.language_code,
                    language_name=subtitles_data.language_name,
                    special_type=subtitles_data.special_type,
                    original_exc=e,
                ),
            )

    if not archive or len(temp_downloads) == 1:
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
        media_data=media_data,
        successful_subtitles=successful_downloads,
        failed_subtitles=failed_downloads,
        is_archive=archive,
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
        episode_number=media_data.episode_number,
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
    Scraper.subtitles_fix_rtl = config.subtitles.fix_rtl
    Scraper.subtitles_remove_duplicates = config.subtitles.remove_duplicates
    Scraper.default_timeout = config.scrapers.default.timeout
    Scraper.default_user_agent = config.scrapers.default.user_agent
    Scraper.default_proxy = config.scrapers.default.proxy
    Scraper.default_verify_ssl = config.scrapers.default.verify_ssl

    WebVTTCaptionBlock.subrip_alignment_conversion = (
        config.subtitles.webvtt.subrip_alignment_conversion
    )

    if log_rotation := config.general.log_rotation_size:
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
    if not LOG_FILES_PATH.is_dir():
        logger.debug("Logs directory could not be found and will be created.")
        LOG_FILES_PATH.mkdir()

    logfile_path = generate_non_conflicting_path(file_path=LOG_FILES_PATH / LOG_FILE_NAME)
    logfile_handler = logging.FileHandler(filename=logfile_path, encoding="utf-8")
    logfile_handler.setLevel(file_loglevel)
    logfile_handler.setFormatter(CustomLogFileFormatter())
    logger.debug(f"Log file location: '{logfile_path}'")
    logger.addHandler(logfile_handler)


if __name__ == "__main__":
    main()
