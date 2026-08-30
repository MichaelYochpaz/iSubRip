from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import logging
import os
import sys
from typing import TYPE_CHECKING, Any

import httpx2
from packaging.version import Version
from pydantic import ValidationError

from isubrip.cli import console
from isubrip.commands.download import download
from isubrip.config import Config
from isubrip.constants import (
    PACKAGE_NAME,
    PACKAGE_VERSION,
    data_folder_path,
    log_files_path,
    user_config_file_path,
)
from isubrip.logger import logger, setup_loggers
from isubrip.scrapers.scraper import Scraper, ScraperFactory
from isubrip.subtitle_formats.webvtt import WebVTTCaptionBlock
from isubrip.utils import (
    convert_log_level,
    format_config_validation_error,
    get_model_field,
    raise_for_status,
    redact_url_query_param,
    single_string_to_list,
)

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


log_rotation_size: int = 15  # Default size, before being updated by the config file.


@dataclass(frozen=True)
class CLIArguments:
    """Validated command-line arguments."""

    urls: list[str]
    dsid: str | None


def main() -> None:
    """A wrapper for the actual main function that handles exceptions and cleanup."""
    exit_code = 1

    try:
        exit_code = 0 if asyncio.run(_main()) else 1

    except Exception as ex:
        logger.error(f"Error: {ex}")
        logger.debug("Debug information:", exc_info=True)

    except KeyboardInterrupt:
        logger.debug("Keyboard interrupt detected, exiting...")
        exit_code = 0

    finally:
        if log_rotation_size > 0:
            handle_log_rotation(rotation_size=log_rotation_size)

        for scraper in ScraperFactory.get_initialized_scrapers():
            logger.debug(f"Requests count for '{scraper.name}' scraper: {scraper.requests_count}")

    if exit_code:
        raise SystemExit(exit_code)


async def _main() -> bool:
    cli_args = parse_cli_args()

    config = parse_config(
        config_file_location=user_config_file_path() if user_config_file_path().is_file() else None,
        dsid_override=cli_args.dsid,
    )

    # Generate the data folder if it doesn't previously exist
    if not data_folder_path().is_dir():
        data_folder_path().mkdir(parents=True)

    setup_loggers(
        stdout_loglevel=convert_log_level(log_level=config.general.log_level),
        stdout_console=console,
        logfile_output=True,
        logfile_output_path=log_files_path(),
        logfile_loglevel=logging.DEBUG,
    )

    logger.debug(f"CLI Command: {format_cli_command_for_logging(cli_args=cli_args)}")
    logger.debug(f"Python version: {sys.version}")
    logger.debug(f"Package version: {PACKAGE_VERSION}")
    logger.debug(f"OS: {sys.platform}")

    update_settings(config=config)

    if config.general.check_for_updates:
        check_for_updates(current_package_version=PACKAGE_VERSION)

    try:
        download_succeeded = await download(
            *single_string_to_list(item=cli_args.urls),
            download_path=config.downloads.folder,
            language_filter=config.downloads.languages,
            convert_to_srt=config.subtitles.convert_to_srt,
            overwrite_existing=config.downloads.overwrite_existing,
            zip=config.downloads.zip,
        )
    
    finally:
        async_cleanup_coroutines = []

        for scraper in ScraperFactory.get_initialized_scrapers():
            async_cleanup_coroutines.append(scraper.async_close())
        
        if async_cleanup_coroutines:
            try:
                await asyncio.gather(*async_cleanup_coroutines)
            except Exception as e:
                logger.warning(f"Error during async cleanup: {e}")
                logger.debug("Cleanup debug info:", exc_info=True)

    if not download_succeeded:
        logger.error("All requested URLs failed.")

    return download_succeeded


def parse_cli_args(args: Sequence[str] | None = None) -> CLIArguments:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        prog=PACKAGE_NAME,
        description="Download subtitles from Apple TV or iTunes movie URLs.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {PACKAGE_VERSION}",
    )
    parser.add_argument(
        "--dsid",
        metavar="DSID",
        help="Optional Apple account DSID fallback to use for owned or rented movies.",
    )
    parser.add_argument(
        "urls",
        metavar="URL",
        nargs="+",
        help="Apple TV or iTunes movie URL to process.",
    )
    parsed_args = parser.parse_args(args)
    return CLIArguments(urls=parsed_args.urls, dsid=parsed_args.dsid)


def format_cli_command_for_logging(cli_args: CLIArguments) -> str:
    """Format CLI arguments for logs without exposing the DSID."""
    command_parts = [PACKAGE_NAME]

    if cli_args.dsid is not None:
        command_parts.extend(("--dsid", "REDACTED"))

    command_parts.extend(redact_url_query_param(url=url, key="dsid") for url in cli_args.urls)
    return " ".join(command_parts)


def check_for_updates(current_package_version: str) -> None:
    """
    Check and print if a newer version of the package is available, and log accordingly.

    Args:
        current_package_version (str): The current version of the package.
    """
    api_url = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
    logger.debug("Checking for package updates on PyPI...")
    try:
        response = httpx2.get(
            url=api_url,
            headers={"Accept": "application/json"},
            timeout=5,
        )
        raise_for_status(response)
        response_data = response.json()

        pypi_latest_version = response_data["info"]["version"]

        if Version(pypi_latest_version) > Version(current_package_version):
            logger.warning(f"You are currently using version '{current_package_version}' of '{PACKAGE_NAME}', "
                           f"however version '{pypi_latest_version}' is available."
                           f'\nConsider upgrading by running "pip install --upgrade {PACKAGE_NAME}"')

        elif Version(pypi_latest_version) < Version(current_package_version):
            logger.debug(
                f"Installed version of '{PACKAGE_NAME}' ({current_package_version}) is newer than the latest "
                f"published version ({pypi_latest_version}).",
            )

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
    sorted_log_files = sorted(log_files_path().glob("*.log"), key=lambda file: file.stat().st_mtime, reverse=True)

    if len(sorted_log_files) > rotation_size:
        for log_file in sorted_log_files[rotation_size:]:
            log_file.unlink()


def parse_config(config_file_location: Path | None, dsid_override: str | None = None) -> Config:
    """
    Parse the configuration file and return a Config instance.
    Exit the program (with code 1) if an error occurs while parsing the configuration file.

    Args:
        config_file_location (Path | None): The location of the configuration file, if one exists.
        dsid_override (str | None): A command-line DSID that takes precedence over all other sources.

    Returns:
        Config: An instance of the Config.
    """
    try:
        return load_config(config_file_location=config_file_location, dsid_override=dsid_override)

    except ValidationError as e:
        config_source = format_validation_error_source(
            exc=e,
            config_file_location=config_file_location,
            dsid_override=dsid_override,
        )
        logger.error(
            f"Invalid {config_source}:\n"
            f"{format_config_validation_error(exc=e)}"
            "Update the settings above and try again.",
        )
        logger.debug(f"Configuration validation exception type: {type(e).__name__}")
        raise SystemExit(1) from e


    except tomllib.TOMLDecodeError as e:
        logger.error(f"Error parsing config file: {e}")
        logger.debug("Debug information:", exc_info=True)
        raise SystemExit(1) from e


    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        logger.debug("Debug information:", exc_info=True)
        raise SystemExit(1) from e


def load_config(config_file_location: Path | None, dsid_override: str | None = None) -> Config:
    """Load configuration and apply DSID sources in CLI, environment, then TOML precedence order."""
    config_data: dict[str, Any] = {}

    if config_file_location is not None:
        with config_file_location.open("rb") as file:
            config_data = tomllib.load(file)

    effective_dsid, _ = resolve_dsid_override(dsid_override=dsid_override)

    if effective_dsid is not None:
        scrapers_config = config_data.setdefault("scrapers", {})

        if not isinstance(scrapers_config, dict):
            raise TypeError("The 'scrapers' configuration value must be a TOML table.")

        appletv_config = scrapers_config.setdefault("appletv", {})

        if not isinstance(appletv_config, dict):
            raise TypeError("The 'scrapers.appletv' configuration value must be a TOML table.")

        appletv_config["dsid"] = effective_dsid

    return Config.model_validate(config_data)


def resolve_dsid_override(dsid_override: str | None) -> tuple[str | None, str | None]:
    """Resolve the DSID override value and its user-facing source name."""
    cli_dsid = dsid_override if dsid_override and dsid_override.strip() else None

    if cli_dsid is not None:
        return cli_dsid, "the --dsid option"

    environment_dsid = os.getenv("ISUBRIP_DSID")
    environment_dsid = environment_dsid if environment_dsid and environment_dsid.strip() else None

    if environment_dsid is not None:
        return environment_dsid, "the ISUBRIP_DSID environment variable"

    return None, None


def format_validation_error_source(
    exc: ValidationError,
    config_file_location: Path | None,
    dsid_override: str | None,
) -> str:
    """Describe the source responsible for a configuration validation error."""
    dsid_error = any(tuple(error["loc"])[-3:] == ("scrapers", "appletv", "dsid") for error in exc.errors())

    if dsid_error:
        _, dsid_source = resolve_dsid_override(dsid_override=dsid_override)

        if dsid_source is not None:
            return f"DSID from {dsid_source}"

    if config_file_location is not None:
        return f"configuration file '{config_file_location}'"

    return "configuration"


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


if __name__ == "__main__":
    main()
