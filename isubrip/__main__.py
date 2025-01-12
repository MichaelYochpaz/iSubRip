from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

import httpx
from pydantic import ValidationError

from isubrip.cli import console
from isubrip.commands.download import download
from isubrip.config import Config
from isubrip.constants import (
    DATA_FOLDER_PATH,
    EVENT_LOOP,
    LOG_FILES_PATH,
    PACKAGE_NAME,
    PACKAGE_VERSION,
    USER_CONFIG_FILE_PATH,
)
from isubrip.logger import logger, setup_loggers
from isubrip.scrapers.scraper import Scraper, ScraperFactory
from isubrip.subtitle_formats.webvtt import WebVTTCaptionBlock
from isubrip.utils import (
    TempDirGenerator,
    convert_log_level,
    format_config_validation_error,
    get_model_field,
    raise_for_status,
    single_string_to_list,
)

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

if TYPE_CHECKING:
    from pathlib import Path

log_rotation_size: int = 15  # Default size, before being updated by the config file.


def main() -> None:
    """A wrapper for the actual main function that handles exceptions and cleanup."""
    try:
        _main()

    except Exception as ex:
        logger.error(f"Error: {ex}")
        logger.debug("Debug information:", exc_info=True)
        exit(1)
    
    except KeyboardInterrupt:
        logger.debug("Keyboard interrupt detected, exiting...")
        exit(0)

    finally:
        if log_rotation_size > 0:
            handle_log_rotation(rotation_size=log_rotation_size)

        # NOTE: This will only close scrapers initialized using the ScraperFactory.
        async_cleanup_coroutines = []
        for scraper in ScraperFactory.get_initialized_scrapers():
            logger.debug(f"Requests count for '{scraper.name}' scraper: {scraper.requests_count}")
            scraper.close()
            async_cleanup_coroutines.append(scraper.async_close())

        EVENT_LOOP.run_until_complete(asyncio.gather(*async_cleanup_coroutines))
        TempDirGenerator.cleanup()

def _main() -> None:
    # Assure at least one argument was passed
    if len(sys.argv) < 2:
        print_usage()
        exit(0)

    # Generate the data folder if it doesn't previously exist
    if not DATA_FOLDER_PATH.is_dir():
        DATA_FOLDER_PATH.mkdir(parents=True)

    config = parse_config(config_file_location=USER_CONFIG_FILE_PATH)

    setup_loggers(
        stdout_loglevel=convert_log_level(log_level=config.general.log_level),
        stdout_console=console,
        logfile_output=True,
        logfile_loglevel=logging.DEBUG,
    )

    cli_args = " ".join(sys.argv[1:])
    logger.debug(f"CLI Command: {PACKAGE_NAME} {cli_args}")
    logger.debug(f"Python version: {sys.version}")
    logger.debug(f"Package version: {PACKAGE_VERSION}")
    logger.debug(f"OS: {sys.platform}")

    update_settings(config=config)

    if config.general.check_for_updates:
        check_for_updates(current_package_version=PACKAGE_VERSION)

    EVENT_LOOP.run_until_complete(download(urls=single_string_to_list(item=sys.argv[1:]),
                                           config=config))


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
                           f'\nConsider upgrading by running "pip install --upgrade {PACKAGE_NAME}"')

        else:
            logger.debug(f"Latest version of '{PACKAGE_NAME}' ({current_package_version}) is currently installed.")

    except Exception as e:
        logger.warning(f"Update check failed: {e}")
        logger.debug("Debug information:", exc_info=True)
        return


def handle_log_rotation(rotation_size: int) -> None:
    """
    Handle log rotation and remove old log files if needed.

    Args:
        rotation_size (int): Maximum amount of log files to keep.
    """
    sorted_log_files = sorted(LOG_FILES_PATH.glob("*.log"), key=lambda file: file.stat().st_mtime, reverse=True)

    if len(sorted_log_files) > rotation_size:
        for log_file in sorted_log_files[rotation_size:]:
            log_file.unlink()


def parse_config(config_file_location: Path) -> Config:
    """
    Parse the configuration file and return a Config instance.
    Exit the program (with code 1) if an error occurs while parsing the configuration file.

    Args:
        config_file_location (Path): The location of the configuration file.

    Returns:
        Config: An instance of the Config.
    """
    try:
        with config_file_location.open('rb') as file:
            config_data = tomllib.load(file)

        return Config.model_validate(config_data)

    except ValidationError as e:
        logger.error("Invalid configuration - the following errors were found in the configuration file:\n" +
                     format_config_validation_error(exc=e) +
                     "\nPlease update your configuration to resolve this issue.")
        logger.debug("Debug information:", exc_info=True)
        exit(1)


    except tomllib.TOMLDecodeError as e:
        logger.error(f"Error parsing config file: {e}")
        logger.debug("Debug information:", exc_info=True)
        exit(1)


    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        logger.debug("Debug information:", exc_info=True)
        exit(1)


def update_settings(config: Config) -> None:
    """
    Update settings according to config.

    Args:
        config (Config): An instance of a config to set settings according to.
    """
    if config.general.log_level.casefold() == "debug":
        console.is_interactive = False

    Scraper.subtitles_fix_rtl = config.subtitles.fix_rtl
    Scraper.subtitles_remove_duplicates = config.subtitles.remove_duplicates

    Scraper.default_timeout = config.scrapers.default.timeout
    Scraper.default_user_agent = config.scrapers.default.user_agent
    Scraper.default_proxy = config.scrapers.default.proxy
    Scraper.default_verify_ssl = config.scrapers.default.verify_ssl

    for scraper in ScraperFactory.get_scraper_classes():
        if scraper_config := get_model_field(model=config.scrapers, field=scraper.id):
            scraper.config = scraper_config

    WebVTTCaptionBlock.subrip_alignment_conversion = (
        config.subtitles.webvtt.subrip_alignment_conversion
    )

    if config.general.log_rotation_size:
        global log_rotation_size
        log_rotation_size = config.general.log_rotation_size


def print_usage() -> None:
    """Print usage information."""
    logger.info(f"Usage: {PACKAGE_NAME} <iTunes movie URL> [iTunes movie URL...]")


if __name__ == "__main__":
    main()
