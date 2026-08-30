from __future__ import annotations

from pathlib import Path
import shutil

from rich.console import Group
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.text import Text

from isubrip.cli import conditional_live, console
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
from isubrip.scrapers.scraper import HLSScraper, PlaylistLoadError, ScraperError, ScraperFactory, SubtitlesDownloadError
from isubrip.ui import MinsAndSecsTimeElapsedColumn
from isubrip.utils import (
    TemporaryDirectory,
    download_subtitles_to_file,
    format_list,
    format_media_description,
    format_release_name,
    generate_non_conflicting_path,
    redact_url_query_param,
)


async def download(*urls: str,
                   download_path: Path,
                   language_filter: list[str] | None = None,
                   convert_to_srt: bool = False,
                   overwrite_existing: bool = True,
                   zip: bool = False) -> bool:
    """
    Download subtitles from given URLs.

    Args:
        urls (list[str]): A list of URLs to download subtitles from.
        download_path (Path): Path to a folder where the subtitles will be downloaded to.
        language_filter (list[str] | None): List of specific languages to download. None for all languages (no filter).
            Defaults to None.
        convert_to_srt (bool, optional): Whether to convert the subtitles to SRT format. Defaults to False.
        overwrite_existing (bool, optional): Whether to overwrite existing subtitles. Defaults to True.
        zip (bool, optional): Whether to zip multiple subtitles. Defaults to False.
    """
    any_url_succeeded = False

    for url in urls:
        url_succeeded = False
        safe_url = redact_url_query_param(url=url, key="dsid")

        try:
            logger.info(f"Scraping [blue]{safe_url}[/blue]")

            scraper = ScraperFactory.get_scraper_instance(url=url)

            try:
                logger.debug(f"Fetching {safe_url}")
                scraper_response: ScrapedMediaResponse = await scraper.get_data(url=url)

            except ScraperError as e:
                safe_error = redact_url_query_param(url=str(e), key="dsid")
                logger.error(f"Error: {safe_error}")
                logger.debug(f"Exception type: {type(e).__name__}")
                continue

            media_data = scraper_response.media_data
            playlist_scraper = ScraperFactory.get_scraper_instance(scraper_id=scraper_response.playlist_scraper)

            if not isinstance(playlist_scraper, HLSScraper):
                logger.error(f"Error: '{scraper_response.playlist_scraper}' is not an HLS playlist scraper.")
                continue

            if not media_data:
                logger.error(f"Error: No supported media was found for {safe_url}.")
                continue

            for media_item in media_data:
                try:
                    logger.info(f"Found {media_item.media_type}: "
                                f"[cyan]{format_media_description(media_data=media_item)}[/cyan]")
                    media_item_succeeded = await download_media(
                        scraper=playlist_scraper,
                        media_item=media_item,
                        download_path=download_path,
                        language_filter=language_filter,
                        convert_to_srt=convert_to_srt,
                        overwrite_existing=overwrite_existing,
                        zip=zip,
                    )
                    url_succeeded = media_item_succeeded or url_succeeded

                except Exception as e:
                    if len(media_data) > 1:
                        safe_error = redact_url_query_param(url=str(e), key="dsid")
                        logger.warning(f"Error scraping media item "
                                    f"'{format_media_description(media_data=media_item)}': {safe_error}\n"
                                    f"Skipping to next media item...")
                        logger.debug(f"Exception type: {type(e).__name__}")
                        continue

                    raise

        except Exception as e:
            safe_error = redact_url_query_param(url=str(e), key="dsid")
            logger.error(f"Error while scraping '{safe_url}': {safe_error}")
            logger.debug(f"Exception type: {type(e).__name__}")

        finally:
            any_url_succeeded = url_succeeded or any_url_succeeded

    return any_url_succeeded


async def download_media(scraper: HLSScraper, media_item: MediaData, download_path: Path,
                              language_filter: list[str] | None = None, convert_to_srt: bool = False,
                              overwrite_existing: bool = True, zip: bool = False) -> bool:
    """
    Download a media item.

    Args:
        scraper (Scraper): A Scraper object to use for downloading subtitles.
        media_item (MediaData): A media data item to download subtitles for.
        download_path (Path): Path to a folder where the subtitles will be downloaded to.
        language_filter (list[str] | None): List of specific languages to download. None for all languages (no filter).
            Defaults to None.
        convert_to_srt (bool, optional): Whether to convert the subtitles to SRT format. Defaults to False.
        overwrite_existing (bool, optional): Whether to overwrite existing subtitles. Defaults to True.
        zip (bool, optional): Whether to zip multiple subtitles. Defaults to False.
    """
    if isinstance(media_item, Series):
        results: list[bool] = []

        for season in media_item.seasons:
            results.append(await download_media(media_item=season, scraper=scraper, download_path=download_path,
                                                language_filter=language_filter, convert_to_srt=convert_to_srt,
                                                overwrite_existing=overwrite_existing, zip=zip))

        return any(results)

    if isinstance(media_item, Season):
        results = []

        for episode in media_item.episodes:
            logger.info(f"{format_media_description(media_data=episode, shortened=True)}:")
            results.append(await download_media_item(media_item=episode, scraper=scraper, download_path=download_path,
                                                     language_filter=language_filter, convert_to_srt=convert_to_srt,
                                                     overwrite_existing=overwrite_existing, zip=zip))

        return any(results)

    if isinstance(media_item, (Movie | Episode)):
        return await download_media_item(media_item=media_item, scraper=scraper, download_path=download_path,
                                         language_filter=language_filter, convert_to_srt=convert_to_srt,
                                         overwrite_existing=overwrite_existing, zip=zip)

    return False


async def download_media_item(scraper: HLSScraper, media_item: Movie | Episode, download_path: Path,
                              language_filter: list[str] | None = None, convert_to_srt: bool = False,
                              overwrite_existing: bool = True, zip: bool = False) -> bool:
    """
    Download subtitles for a single media item.

    Args:
        scraper (Scraper): A Scraper object to use for downloading subtitles.
        media_item (Movie | Episode): A movie or episode data object.
        download_path (Path): Path to a folder where the subtitles will be downloaded to.
        language_filter (list[str] | None): List of specific languages to download. None for all languages (no filter).
            Defaults to None.
        convert_to_srt (bool, optional): Whether to convert the subtitles to SRT format. Defaults to False.
        overwrite_existing (bool, optional): Whether to overwrite existing subtitles. Defaults to True.
        zip (bool, optional): Whether to zip multiple subtitles. Defaults to False.
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
                zip=zip,
            )

            success_count = len(results.successful_subtitles)
            failed_count = len(results.failed_subtitles)

            if success_count or failed_count:
                logger.info(f"{success_count}/{success_count + failed_count} subtitles were successfully downloaded.")

            else:
                logger.info("No matching subtitles were found.")

            return success_count > 0  # noqa: TRY300

        except PlaylistLoadError as e:
            ex = e

    # We get here if there is no playlist, or there is one, but it failed to load
    has_future_rental_date = False

    if isinstance(media_item, Movie) and media_item.preorder_availability_date:
        has_future_rental_date = True
        logger.info(
            f"[gold1]Apple lists '{media_item.name}' as available to rent on "
            f"{media_item.preorder_availability_date.strftime(r'%B %e, %Y')}.[/gold1]",
        )

    if ex:
        logger.error(f"Error: {redact_url_query_param(url=str(ex), key='dsid')}")

    elif not has_future_rental_date:
        logger.error("Error: No valid playlist was found.")

    return False


async def download_subtitles(scraper: HLSScraper, media_data: Movie | Episode, download_path: Path,
                             language_filter: list[str] | None = None, convert_to_srt: bool = False,
                             overwrite_existing: bool = True, zip: bool = False) -> SubtitlesDownloadResults:
    """
    Download subtitles for the given media data.

    Args:
        scraper (Scraper): A Scraper object to use for downloading subtitles.
        media_data (Movie | Episode): A movie or episode data object.
        download_path (Path): Path to a folder where the subtitles will be downloaded to.
        language_filter (list[str] | None): List of specific languages to download. None for all languages (no filter).
            Defaults to None.
        convert_to_srt (bool, optional): Whether to convert the subtitles to SRT format. Defaults to False.
        overwrite_existing (bool, optional): Whether to overwrite existing subtitles. Defaults to True.
        zip (bool, optional): Whether to zip multiple subtitles. Defaults to False.

    Returns:
        SubtitlesDownloadResults: A SubtitlesDownloadResults object containing the results of the download.
    """
    temp_dir_name = format_release_name(
        title=media_data.name if isinstance(media_data, Movie) else media_data.series_name,
        release_date=media_data.release_date,
        season_number=None if isinstance(media_data, Movie) else media_data.season_number,
        episode_number=None if isinstance(media_data, Movie) else media_data.episode_number,
        episode_name=None if isinstance(media_data, Movie) else media_data.episode_name,
        media_source=scraper.abbreviation,
    )
    successful_downloads: list[SubtitlesData] = []
    failed_downloads: list[SubtitlesDownloadError] = []

    with TemporaryDirectory(directory_name=temp_dir_name) as temp_download_path:
        temp_downloads: list[Path] = []

        if not media_data.playlist:
            raise PlaylistLoadError("No playlist was found for provided media data.")

        main_playlist = await scraper.load_playlist(url=media_data.playlist)

        matching_subtitle_groups = scraper.find_matching_subtitle_groups(
            main_playlist=main_playlist,
            language_filter=language_filter,
        )

        # If no matching subtitles were found, there's no need to continue
        if not matching_subtitle_groups:
            return SubtitlesDownloadResults(
                media_data=media_data,
                successful_subtitles=successful_downloads,
                failed_subtitles=failed_downloads,
                is_zip=zip,
            )

        logger.info(
            f"{len(matching_subtitle_groups)} matching subtitles were found.",
            extra={"hide_when_interactive": True},
        )
        downloaded_subtitles: list[str] = []

        progress_log = Text(
            f"Downloaded subtitles ({len(downloaded_subtitles)}/{len(matching_subtitle_groups)}):",
        )
        downloads_list = Text()
        progress_bar = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage][yellow]{task.percentage:>3.0f}%[/yellow]"),
            TextColumn("[yellow]{task.completed}/{task.total}[/yellow]"),
            MinsAndSecsTimeElapsedColumn(),
            console=console,
        )
        task = progress_bar.add_task("Starting download", total=len(matching_subtitle_groups))

        with conditional_live(
            Group(progress_log, downloads_list, Text(), progress_bar),  # Empty 'Text' for line spacing
        ) as live:
            for matching_subtitle_group in matching_subtitle_groups:
                matching_subtitles_item = matching_subtitle_group.primary
                language_info = scraper.format_subtitles_description(
                    subtitles_media=matching_subtitles_item,
                )

                if live:
                    progress_bar.update(task, advance=1, description=f"Processing [magenta]{language_info}[/magenta]")

                try:
                    subtitles_data = await scraper.download_subtitle_group(
                        media_group=matching_subtitle_group,
                        subrip_conversion=convert_to_srt,
                    )

                except Exception as e:
                    if isinstance(e, SubtitlesDownloadError):
                        failed_downloads.append(e)
                        original_error = e.original_exc

                    else:
                        original_error = e

                    logger.warning(f"Failed to download '{language_info}' subtitles: {original_error}")
                    logger.debug("Debug information:", exc_info=original_error)
                    continue

                try:
                    temp_downloads.append(download_subtitles_to_file(
                        media_data=media_data,
                        subtitles_data=subtitles_data,
                        output_path=temp_download_path,
                        source_abbreviation=scraper.abbreviation,
                        overwrite=overwrite_existing,
                    ))

                    downloaded_subtitles.append(f"• {language_info}")

                    if live:
                        progress_log.plain = (f"Downloaded subtitles "
                                             f"({len(downloaded_subtitles)}/{len(matching_subtitle_groups)}):")
                        downloads_list.plain = f"{format_list(downloaded_subtitles, width=live.console.width)}"

                    logger.info(f"{language_info} subtitles were successfully downloaded.",
                                extra={"hide_when_interactive": True})
                    successful_downloads.append(subtitles_data)

                except Exception as e:
                    logger.warning(f"Failed to save '{language_info}' subtitles: {e}")
                    logger.debug("Debug information:", exc_info=True)
                    failed_downloads.append(
                        SubtitlesDownloadError(
                            language_code=subtitles_data.language_code,
                            language_name=subtitles_data.language_name,
                            special_type=subtitles_data.special_type,
                            original_exc=e,
                        ),
                    )

            if live:
                progress_bar.update(task, visible=False)

        if not zip or len(temp_downloads) == 1:
            for file_path in temp_downloads:
                if overwrite_existing:
                    new_path = download_path / file_path.name

                else:
                    new_path = generate_non_conflicting_path(file_path=download_path / file_path.name)

                shutil.move(src=file_path, dst=new_path)

        elif len(temp_downloads) > 0:
            zip_path = Path(shutil.make_archive(
                base_name=str(temp_download_path.parent / temp_download_path.name),
                format="zip",
                root_dir=temp_download_path,
            ))

            file_name = format_release_name(
                title=media_data.name if isinstance(media_data, Movie) else media_data.series_name,
                release_date=media_data.release_date,
                season_number=None if isinstance(media_data, Movie) else media_data.season_number,
                episode_number=None if isinstance(media_data, Movie) else media_data.episode_number,
                episode_name=None if isinstance(media_data, Movie) else media_data.episode_name,
                media_source=scraper.abbreviation,
                file_format="zip",
                )

            if overwrite_existing:
                destination_path = download_path / file_name

            else:
                destination_path = generate_non_conflicting_path(file_path=download_path / file_name)

            shutil.move(src=zip_path, dst=destination_path)

    return SubtitlesDownloadResults(
        media_data=media_data,
        successful_subtitles=successful_downloads,
        failed_subtitles=failed_downloads,
        is_zip=zip,
    )
