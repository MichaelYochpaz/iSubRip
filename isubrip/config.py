from __future__ import annotations

from abc import ABC
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator
from pydantic_core import PydanticCustomError
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, TomlConfigSettingsSource

from isubrip.scrapers.scraper import DefaultScraperConfig, ScraperFactory
from isubrip.utils import normalize_config_name


class ConfigCategory(BaseModel, ABC):
    """A base class for settings categories."""
    model_config = ConfigDict(
        extra='allow',
        alias_generator=normalize_config_name,
    )


class GeneralCategory(ConfigCategory):
    check_for_updates: bool = Field(default=True)
    verbose: bool = Field(default=False)
    log_level: Literal["debug", "info", "warning", "error", "critical"] = Field(default="info")
    log_rotation_size: int = Field(default=15)


class DownloadsCategory(ConfigCategory):
    folder: Path = Field(default=Path.cwd().resolve())
    languages: list[str] = Field(default=[])
    overwrite_existing: bool = Field(default=False)
    zip: bool = Field(default=False)

    @field_validator('folder')
    @classmethod
    def assure_path_exists(cls, value: Path) -> Path:
        if value.exists():
            if not value.is_dir():
                raise PydanticCustomError(
                    "invalid_path",
                    "Path is not a directory.",
                )

        else:
            raise PydanticCustomError(
                "invalid_path",
                "Path does not exist.")

        return value


class WebVTTSubcategory(ConfigCategory):
    subrip_alignment_conversion: bool = Field(default=False)


class SubtitlesCategory(ConfigCategory):
    fix_rtl: bool = Field(default=False)
    remove_duplicates: bool = Field(default=True)
    convert_to_srt: bool = Field(default=False)
    webvtt: WebVTTSubcategory = WebVTTSubcategory()


class ScrapersCategory(ConfigCategory):
    default: DefaultScraperConfig = Field(default_factory=DefaultScraperConfig)


# Resolve mypy errors as mypy doesn't support dynamic models.
if TYPE_CHECKING:
    DynamicScrapersCategory = ScrapersCategory

else:
    # A config model that's dynamically created based on the available scrapers and their configurations.
    DynamicScrapersCategory = create_model(
        'DynamicScrapersCategory',
        __base__=ScrapersCategory,
        **{
            scraper.id: (scraper.ScraperConfig, Field(default_factory=scraper.ScraperConfig))
            for scraper in ScraperFactory.get_scraper_classes()
        },  # type: ignore[call-overload]
    )


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        extra='forbid',
        alias_generator=normalize_config_name,
    )

    general: GeneralCategory = Field(default_factory=GeneralCategory)
    downloads: DownloadsCategory = Field(default_factory=DownloadsCategory)
    subtitles: SubtitlesCategory = Field(default_factory=SubtitlesCategory)
    scrapers: DynamicScrapersCategory = Field(default_factory=DynamicScrapersCategory)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            TomlConfigSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
