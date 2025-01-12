from __future__ import annotations

from pathlib import Path
import shutil

from rich.console import Group
from rich.live import Live
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.text import Text

from isubrip.cli import console
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
    format_list,
    format_media_description,
    generate_media_folder_name,
    generate_non_conflicting_path,
)


async def download(*urls: str,
                   download_path: Path,
                   language_filter: list[str] | None = None,
                   convert_to_srt: bool = False,
                   overwrite_existing: bool = True,
                   zip: bool = False) -> None:
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
    for url in urls:
        try:
            logger.info(f"Scraping [blue]{url}[/blue]")

            scraper = ScraperFactory.get_scraper_instance(url=url)

            try:
                logger.debug(f"Fetching {url}")
                scraper_response: ScrapedMediaResponse = await scraper.get_data(url=url)

            except ScraperError as e:
                logger.error(f"Error: {e}")
                logger.debug("Debug information:", exc_info=True)
                continue

            media_data = scraper_response.media_data
            playlist_scraper = ScraperFactory.get_scraper_instance(scraper_id=scraper_response.playlist_scraper)

            if not media_data:
                logger.error(f"Error: No supported media was found for {url}.")
                continue

            for media_item in media_data:
                try:
                    logger.info(f"Found {media_item.media_type}: "
                                f"[cyan]{format_media_description(media_data=media_item)}[/cyan]")
                    await download_media(scraper=playlist_scraper,
                                        media_item=media_item,
                                        download_path=download_path,
                                        language_filter=language_filter,
                                        convert_to_srt=convert_to_srt,
                                        overwrite_existing=overwrite_existing,
                                        zip=zip)

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
                              overwrite_existing: bool = True, zip: bool = False) -> None:
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
        for season in media_item.seasons:
            await download_media(media_item=season, scraper=scraper, download_path=download_path,
                                 language_filter=language_filter, convert_to_srt=convert_to_srt,
                                 overwrite_existing=overwrite_existing, zip=zip)

    elif isinstance(media_item, Season):
        for episode in media_item.episodes:
            logger.info(f"{format_media_description(media_data=episode, shortened=True)}:")
            await download_media_item(media_item=episode, scraper=scraper, download_path=download_path,
                                 language_filter=language_filter, convert_to_srt=convert_to_srt,
                                 overwrite_existing=overwrite_existing, zip=zip)

    elif isinstance(media_item, (Movie, Episode)):
        await download_media_item(media_item=media_item, scraper=scraper, download_path=download_path,
                                 language_filter=language_filter, convert_to_srt=convert_to_srt,
                                 overwrite_existing=overwrite_existing, zip=zip)


async def download_media_item(scraper: Scraper, media_item: Movie | Episode, download_path: Path,
                              language_filter: list[str] | None = None, convert_to_srt: bool = False,
                              overwrite_existing: bool = True, zip: bool = False) -> None:
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

            return  # noqa: TRY300

        except PlaylistLoadError as e:
            ex = e

    # We get here if there is no playlist, or there is one, but it failed to load
    if isinstance(media_item, Movie) and media_item.preorder_availability_date:
        logger.info(f"[gold1]'{media_item.name}' is currently unavailable on {scraper.name}, "
                    f"and will be available on {media_item.preorder_availability_date.strftime("%d/%m/%Y")}.[/gold1]")

    else:
        if ex:
            logger.error(f"Error: {ex}")

        else:
            logger.error("Error: No valid playlist was found.")


async def download_subtitles(scraper: Scraper, media_data: Movie | Episode, download_path: Path,
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
    downloaded_subtitles: list[str] = []
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage][yellow]{task.percentage:>3.0f}%[/yellow]"),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    )
    
    task = progress.add_task("Downloading subtitles...", total=len(matching_subtitles))
    downloaded_list = Text(f"Downloaded subtitles ({len(downloaded_subtitles)}/{len(matching_subtitles)}):")

    with Live(
        Group(downloaded_list, progress),
        console=console,
    ):
        for matching_subtitles_item in matching_subtitles:
            language_info = scraper.format_subtitles_description(
                subtitles_media=matching_subtitles_item,
            )
            progress.update(task, advance=1, description=f"Processing [magenta]{language_info}[/magenta]")

            try:
                subtitles_data = await scraper.download_subtitles(media_data=matching_subtitles_item,
                                                                  subrip_conversion=convert_to_srt)

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
                downloaded_list.plain = (
                    f"Downloaded subtitles ({len(downloaded_subtitles)}/{len(matching_subtitles)}):\n"
                    f"{format_list(downloaded_subtitles, width=console.width)}"
                )
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

        file_name = generate_media_folder_name(media_data=media_data,
                                               source=scraper.abbreviation) + ".zip"

        if overwrite_existing:
            destination_path = download_path / file_name

        else:
            destination_path = generate_non_conflicting_path(file_path=download_path / file_name)

        shutil.move(src=str(zip_path), dst=destination_path)

    return SubtitlesDownloadResults(
        media_data=media_data,
        successful_subtitles=successful_downloads,
        failed_subtitles=failed_downloads,
        is_zip=zip,
    )
