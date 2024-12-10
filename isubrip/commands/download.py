from __future__ import annotations

from pathlib import Path
import shutil
from typing import TYPE_CHECKING

from isubrip.constants import (
    ARCHIVE_FORMAT,
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
from isubrip.logger import logger
from isubrip.scrapers.scraper import PlaylistLoadError, Scraper, ScraperError, ScraperFactory, SubtitlesDownloadError
from isubrip.utils import (
    TempDirGenerator,
    download_subtitles_to_file,
    format_media_description,
    format_subtitles_description,
    generate_media_folder_name,
    generate_non_conflicting_path,
    get_model_field,
)

if TYPE_CHECKING:
    from isubrip.config import Config


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
            logger.info(f"Scraping [blue]{url}[/blue]")

            scraper = ScraperFactory.get_scraper_instance(url=url, scrapers_configs=scrapers_configs)

            try:
                logger.debug(f"Fetching {url}")
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
                    logger.info(f"Found {media_item.media_type}: "
                                f"[cyan]{format_media_description(media_data=media_item)}[/cyan]")
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
        logger.info(f"[dark_orange]'{media_item.name}' is currently unavailable on {scraper.name}, "
                    "and will be available on "
                    f"{media_item.preorder_availability_date.strftime("%d/%m/%Y")}.[/dark_orange]")

    else:
        if ex:
            logger.error(f"Error: {ex}")

        else:
            logger.error("Error: No valid playlist was found.")


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

            logger.info(f"[magenta]{language_info}[/magenta] subtitles were successfully downloaded.")
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

            shutil.move(src=file_path, dst=new_path)

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
