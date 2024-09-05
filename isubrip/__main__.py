from __future__ import annotations

import asyncio
import logging
import sys
from typing import ClassVar

import httpx
from pydantic import ValidationError

from isubrip.commands.download import download
from isubrip.config import Config
from isubrip.constants import (
    DATA_FOLDER_PATH,
    EVENT_LOOP,
    LOG_FILES_PATH,
    PACKAGE_NAME,
    PACKAGE_VERSION,
)
from isubrip.logger import logger, setup_loggers
from isubrip.scrapers.scraper import Scraper, ScraperFactory
from isubrip.subtitle_formats.webvtt import WebVTTCaptionBlock
from isubrip.utils import (
    TempDirGenerator,
    format_config_validation_error,
    raise_for_status,
    single_string_to_list,
)


class AppSettings:
    log_rotation_size: ClassVar[int | None] = None
    stdout_loglevel: ClassVar[int] = logging.INFO
    file_loglevel: ClassVar[int] = logging.DEBUG


def main() -> None:
    try:
        # Assure at least one argument was passed
        if len(sys.argv) < 2:
            print_usage()
            exit(0)

        if not DATA_FOLDER_PATH.is_dir():
            DATA_FOLDER_PATH.mkdir(parents=True)

        setup_loggers(stdout_loglevel=AppSettings.stdout_loglevel,
                      file_loglevel=AppSettings.file_loglevel)

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

        EVENT_LOOP.run_until_complete(download(urls=single_string_to_list(item=sys.argv[1:]),
                                               config=config))

    except Exception as ex:
        logger.error(f"Error: {ex}")
        logger.debug("Debug information:", exc_info=True)
        exit(1)

    finally:
        if AppSettings.log_rotation_size:
            handle_log_rotation(log_rotation_size=AppSettings.log_rotation_size)

        # NOTE: This will only close scrapers that were initialized using the ScraperFactory.
        async_cleanup_coroutines = []
        for scraper in ScraperFactory.get_initialized_scrapers():
            logger.debug(f"Requests count for '{scraper.name}' scraper: {scraper.requests_count}")
            scraper.close()
            async_cleanup_coroutines.append(scraper.async_close())

        EVENT_LOOP.run_until_complete(asyncio.gather(*async_cleanup_coroutines))
        TempDirGenerator.cleanup()


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
        AppSettings.log_rotation_size = log_rotation


def print_usage() -> None:
    """Print usage information."""
    logger.info(f"Usage: {PACKAGE_NAME} <iTunes movie URL> [iTunes movie URL...]")


if __name__ == "__main__":
    main()
