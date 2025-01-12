from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from enum import Enum
import importlib
import inspect
from pathlib import Path
import re
import sys
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypeVar, Union, overload

import httpx
import m3u8
from pydantic import AliasGenerator, BaseModel, ConfigDict, Field, create_model

from isubrip.constants import PACKAGE_NAME, SCRAPER_MODULES_SUFFIX
from isubrip.data_structures import (
    MainPlaylist,
    PlaylistMediaItem,
    ScrapedMediaResponse,
    SubtitlesData,
    SubtitlesFormatType,
    SubtitlesType,
)
from isubrip.logger import logger
from isubrip.utils import (
    SingletonMeta,
    format_subtitles_description,
    get_model_field,
    merge_dict_values,
    return_first_valid,
    single_string_to_list,
)

if TYPE_CHECKING:
    from types import TracebackType

    from isubrip.subtitle_formats.subtitles import Subtitles


ScraperT = TypeVar("ScraperT", bound="Scraper")


class ScraperConfigBase(BaseModel, ABC):
    """
    A Pydantic BaseModel for base class for scraper's configuration classes.
    Also serves for setting default configuration settings for all scrapers.

    Attributes:
        timeout (int | float): Timeout to use when making requests.
        user_agent (st): User agent to use when making requests.
        proxy (str | None): Proxy to use when making requests.
        verify_ssl (bool): Whether to verify SSL certificates.
    """
    model_config = ConfigDict(
        extra='forbid',
        alias_generator=AliasGenerator(
            validation_alias=lambda field_name: field_name.replace('_', '-'),
        ),
    )

    timeout: int | float | None = Field(default=None)
    user_agent: str | None = Field(default=None)
    proxy: str | None = Field(default=None)
    verify_ssl: bool | None = Field(default=None)


class DefaultScraperConfig(ScraperConfigBase):
    """
    A Pydantic BaseModel for scraper's configuration classes.
    Also serves as a default configuration for all scrapers.

    Attributes:
        timeout (int | float): Timeout to use when making requests.
        user_agent (st): User agent to use when making requests.
        proxy (str | None): Proxy to use when making requests.
        verify_ssl (bool): Whether to verify SSL certificates.
    """
    timeout: int | float = Field(default=10)
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",    # noqa: E501
    )
    proxy: str | None = Field(default=None)
    verify_ssl: bool = Field(default=True)


class ScraperConfigSubcategory(BaseModel, ABC):
    """A Pydantic BaseModel for a scraper's configuration subcategory (which can be set under 'ScraperConfig')."""
    model_config = ConfigDict(
        extra='forbid',
        alias_generator=AliasGenerator(
            validation_alias=lambda field_name: field_name.replace('_', '-'),
        ),
    )

class Scraper(ABC, metaclass=SingletonMeta):
    """
    A base class for scrapers.

    Attributes:
        default_user_agent (str): [Class Attribute]
            Default user agent to use if no other user agent is specified when making requests.
        default_proxy (str | None): [Class Attribute] Default proxy to use when making requests.
        default_verify_ssl (bool): [Class Attribute] Whether to verify SSL certificates by default.
        subtitles_fix_rtl (bool): [Class Attribute] Whether to fix RTL from downloaded subtitles.
            A list of languages to fix RTL on. If None, a default list will be used.
        subtitles_remove_duplicates (bool): [Class Attribute]
            Whether to remove duplicate lines from downloaded subtitles.

        id (str): [Class Attribute] ID of the scraper (must be unique).
        name (str): [Class Attribute] Name of the scraper.
        abbreviation (str): [Class Attribute] Abbreviation of the scraper.
        url_regex (re.Pattern | list[re.Pattern]): [Class Attribute] A RegEx pattern to find URLs matching the service.
        subtitles_class (type[Subtitles]): [Class Attribute] Class of the subtitles format returned by the scraper.
        is_movie_scraper (bool): [Class Attribute] Whether the scraper is for movies.
        is_series_scraper (bool): [Class Attribute] Whether the scraper is for series.
        uses_scrapers (list[str]): [Class Attribute] A list of IDs for other scraper classes that this scraper uses.
            This assures that the config data for the other scrapers is passed as well.
        config (ScraperConfig | None): [Class Attribute] A ScraperConfig instance for the scraper,
            containing configurations.
        _session (httpx.Client): A synchronous HTTP client session.
        _async_session (httpx.AsyncClient): An asynchronous HTTP client session.

    Notes:
        Each scraper implements its own `ScraperConfig` class (which can be overridden and updated),
         inheriting from `ScraperConfigBase`, which sets configurable options for the scraper.
    """

    class ScraperConfig(ScraperConfigBase):
        """A class representing scraper's configuration settings.
           Can be overridden to create a custom configuration with overridden default values,
           and additional settings."""
    
    default_timeout: ClassVar[int | float] = 10
    default_user_agent: ClassVar[str] = httpx._client.USER_AGENT  # noqa: SLF001
    default_proxy: ClassVar[str | None] = None
    default_verify_ssl: ClassVar[bool] = True
    subtitles_fix_rtl: ClassVar[bool] = False
    subtitles_remove_duplicates: ClassVar[bool] = True

    id: ClassVar[str]
    name: ClassVar[str]
    abbreviation: ClassVar[str]
    url_regex: ClassVar[re.Pattern | list[re.Pattern]]
    subtitles_class: ClassVar[type[Subtitles]]
    is_movie_scraper: ClassVar[bool] = False
    is_series_scraper: ClassVar[bool] = False
    uses_scrapers: ClassVar[list[str]] = []
    config: ClassVar[ScraperConfig | None] = None

    def __init__(self, timeout: int | float | None = None, user_agent: str | None = None,
                 proxy: str | None = None, verify_ssl: bool | None = None):
        """
        Initialize a Scraper object.

        Args:
            timeout (int | float | None, optional): A timeout to use when making requests. Defaults to None.
            user_agent (str | None, optional): A user agent to use when making requests. Defaults to None.
            proxy (str | None, optional): A proxy to use when making requests. Defaults to None.
            verify_ssl (bool | None, optional): Whether to verify SSL certificates. Defaults to None.
        """
        self._timeout = return_first_valid(timeout,
                                           get_model_field(model=self.config, field='timeout'),
                                           self.default_timeout,
                                           raise_error=True)
        self._user_agent = return_first_valid(user_agent,
                                              get_model_field(model=self.config, field='user_agent'),
                                              self.default_user_agent,
                                              raise_error=True)
        self._proxy = return_first_valid(proxy,
                                         get_model_field(model=self.config, field='proxy'),
                                         self.default_proxy)
        self._verify_ssl = return_first_valid(verify_ssl,
                                              get_model_field(model=self.config, field='verify_ssl'),
                                              self.default_verify_ssl,
                                              raise_error=True)

        if self._timeout != self.default_timeout:
            logger.debug(f"Initializing '{self.name}' scraper with custom timeout: '{self._timeout}'.")

        if self._user_agent != self.default_user_agent:
            logger.debug(f"Initializing '{self.name}' scraper with custom user-agent: '{self._user_agent}'.")

        if self._proxy != self.default_proxy:
            logger.debug(f"Initializing '{self.name}' scraper with proxy: '{self._proxy}'.")

        if self._verify_ssl != self.default_verify_ssl:
            logger.debug(f"Initializing '{self.name}' scraper with SSL verification set to: '{self._verify_ssl}'.")

        self._requests_counter = 0
        clients_params: dict[str, Any] = {
            "headers": {"User-Agent": self._user_agent},
            "verify": self._verify_ssl,
            "proxy": self._proxy,
            "timeout": float(self._timeout),
        }
        self._session = httpx.Client(
            **clients_params,
            event_hooks={
                "request": [self._increment_requests_counter],
            },
        )
        self._async_session = httpx.AsyncClient(
            **clients_params,
            event_hooks={
                "request": [self._async_increment_requests_counter],
            },
        )

        # Update session settings according to configurations
        self._session.headers.update({"User-Agent": self._user_agent})
        self._async_session.headers.update({"User-Agent": self._user_agent})

    def _increment_requests_counter(self, request: httpx.Request) -> None:  # noqa: ARG002
        self._requests_counter += 1

    async def _async_increment_requests_counter(self, request: httpx.Request) -> None:  # noqa: ARG002
        self._requests_counter += 1

    @property
    def requests_count(self) -> int:
        return self._requests_counter

    @classmethod
    @overload
    def match_url(cls, url: str, raise_error: Literal[True] = ...) -> re.Match:
        ...

    @classmethod
    @overload
    def match_url(cls, url: str, raise_error: Literal[False] = ...) -> re.Match | None:
        ...

    @classmethod
    def match_url(cls, url: str, raise_error: bool = False) -> re.Match | None:
        """
        Checks if a URL matches scraper's url regex.

        Args:
            url (str): A URL to check against the regex.
            raise_error (bool, optional): Whether to raise an error instead of returning None if the URL doesn't match.

        Returns:
            re.Match | None: A Match object if the URL matches the regex, None otherwise (if raise_error is False).

        Raises:
            ValueError: If the URL doesn't match the regex and raise_error is True.
        """
        if isinstance(cls.url_regex, re.Pattern) and (match_result := re.fullmatch(pattern=cls.url_regex, string=url)):
            return match_result

        if isinstance(cls.url_regex, list):
            for url_regex_item in cls.url_regex:
                if result := re.fullmatch(pattern=url_regex_item, string=url):
                    return result

        if raise_error:
            raise ValueError(f"URL '{url}' doesn't match the URL regex of {cls.name}.")

        return None

    def __enter__(self) -> Scraper:
        return self

    def __exit__(self, exc_type: type[BaseException] | None,
                 exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        self.close()

    async def async_close(self) -> None:
        await self._async_session.aclose()

    def close(self) -> None:
        self._session.close()

    @abstractmethod
    async def get_data(self, url: str) -> ScrapedMediaResponse:
        """
        Scrape media information about the media on a URL.

        Args:
            url (str): A URL to get media information about.

        Returns:
            ScrapedMediaResponse: A ScrapedMediaResponse object containing scraped media information.
        """

    @abstractmethod
    async def download_subtitles(self, media_data: PlaylistMediaItem, subrip_conversion: bool = False) -> SubtitlesData:
        """
        Download subtitles from a media object.

        Args:
            media_data (PlaylistMediaItem): A media object to download subtitles from.
            subrip_conversion (bool, optional): Whether to convert the subtitles to SubRip format. Defaults to False.

        Returns:
            SubtitlesData: A SubtitlesData object containing downloaded subtitles.
        
        Raises:
            SubtitlesDownloadError: If the subtitles failed to download.
        """

    @abstractmethod
    def find_matching_media(self, main_playlist: MainPlaylist,
                            filters: dict[str, str | list[str]] | None = None) -> list:
        """
        Find media items that match the given filters in the main playlist (or all media items if no filters are given).

        Args:
            main_playlist (MainPlaylist): Main playlist to search for media items in.
            filters (dict[str, str | list[str]] | None, optional): A dictionary of filters to match media items against.
                Defaults to None.

        Returns:
            list: A list of media items that match the given filters.
        """

    @abstractmethod
    def find_matching_subtitles(self, main_playlist: MainPlaylist,
                                language_filter: list[str] | None = None) -> list[PlaylistMediaItem]:
        """
        Find subtitles that match the given language filter in the main playlist.

        Args:
            main_playlist (MainPlaylist): Main playlist to search for subtitles in.
            language_filter (list[str] | None, optional): A list of language codes to filter subtitles by.
                Defaults to None.

        Returns:
            list[PlaylistMediaItem]: A list of subtitles media objects that match the given language filter.
        """

    @abstractmethod
    async def load_playlist(self, url: str | list[str], headers: dict | None = None) -> MainPlaylist | None:
        """
        Load a playlist from a URL to a representing object.
        Multiple URLs can be given, in which case the first one that loads successfully will be returned.

        Args:
            url (str | list[str]): URL of the M3U8 playlist to load. Can also be a list of URLs (for redundancy).
            headers (dict | None, optional): A dictionary of headers to use when making the request.
                Defaults to None (results in using session's configured headers).

        Returns:
            MainPlaylist | None: A playlist object (matching the type), or None if the playlist couldn't be loaded.
        """


    @staticmethod
    @abstractmethod
    def detect_subtitles_type(subtitles_media: PlaylistMediaItem) -> SubtitlesType | None:
        """
        Detect the subtitles type (Closed Captions, Forced, etc.) from a media object.

        Args:
            subtitles_media (PlaylistMediaItem): Subtitles media object to detect the type of.

        Returns:
            SubtitlesType | None: The type of the subtitles, None for regular subtitles.
        """


    @classmethod
    @abstractmethod
    def format_subtitles_description(cls, subtitles_media: PlaylistMediaItem) -> str:
        """
        Format a description of the subtitles media object.
        
        Args:
            subtitles_media (PlaylistMediaItem): Subtitles media object to format the description of.
        
        Returns:
            str: A formatted description of the subtitles media object.

        Raises:
            ValueError: If minimal required data is missing from the media object.
        """


class HLSScraper(Scraper, ABC):
    """A base class for HLS (m3u8) scrapers."""
    class M3U8Attribute(Enum):
        """
        An enum representing all possible M3U8 attributes.
        Names / Keys represent M3U8 Media object attributes (should be converted to lowercase),
        and values represent the name of the key for config usage.
        """
        ASSOC_LANGUAGE = "assoc-language"
        AUTOSELECT = "autoselect"
        CHARACTERISTICS = "characteristics"
        CHANNELS = "channels"
        DEFAULT = "default"
        FORCED = "forced"
        GROUP_ID = "group-id"
        INSTREAM_ID = "instream-id"
        LANGUAGE = "language"
        NAME = "name"
        STABLE_RENDITION_ID = "stable-rendition-id"
        TYPE = "type"

    default_playlist_filters: ClassVar[dict[str, str | list[str] | None] | None] = None

    _subtitles_filters: dict[str, str | list[str]] = {
        M3U8Attribute.TYPE.value: "SUBTITLES",
    }

    # Resolve mypy errors as mypy doesn't support dynamic models.
    if TYPE_CHECKING:
        PlaylistFiltersSubcategory = ScraperConfigSubcategory

    else:
        PlaylistFiltersSubcategory = create_model(
            "PlaylistFiltersSubcategory",
            __base__=ScraperConfigSubcategory,
            **{
                m3u8_attribute.value: (Union[str, list[str], None],
                                       Field(default=None))
                for m3u8_attribute in M3U8Attribute
            },  # type: ignore[call-overload]
        )


    class ScraperConfig(Scraper.ScraperConfig):
        playlist_filters: HLSScraper.PlaylistFiltersSubcategory = Field(  # type: ignore[valid-type]
            default_factory=lambda: HLSScraper.PlaylistFiltersSubcategory(),
        )


    def __init__(self, playlist_filters: dict[str, str | list[str] | None] | None = None,
                 *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._playlist_filters = return_first_valid(playlist_filters,
                                                    get_model_field(model=self.config,
                                                                    field='playlist_filters',
                                                                    convert_to_dict=True),
                                                    self.default_playlist_filters)

        if self._playlist_filters:
            # Remove None values from the filters (mainly caused by config defaults)
            self._playlist_filters = {key: value for key, value in self._playlist_filters.items() if value is not None}

            if self._playlist_filters:  # If there are any filters left
                logger.debug(f"Scraper '{self.name}' initialized with playlist filters: {self._playlist_filters}.")

    @staticmethod
    def parse_language_name(media_data: m3u8.Media) -> str | None:
        """
        Parse the language name from an M3U8 Media object.
        Can be overridden in subclasses for normalization.

        Args:
            media_data (m3u8.Media): Media object to parse the language name from.

        Returns:
            str | None: The language name if found, None otherwise.
        """
        name: str | None = media_data.name
        return name

    async def load_playlist(self, url: str | list[str], headers: dict | None = None) -> m3u8.M3U8 | None:
        _headers = headers or self._session.headers
        result: m3u8.M3U8 | None = None

        for url_item in single_string_to_list(item=url):
            try:
                response = await self._async_session.get(url=url_item, headers=_headers, timeout=5)

            except Exception as e:
                logger.debug(f"Failed to load M3U8 playlist '{url_item}': {e}")
                continue

            if not response.text:
                raise PlaylistLoadError("Received empty response for playlist from server.")

            result = m3u8.loads(content=response.text, uri=url_item)
            break

        return result

    @staticmethod
    def detect_subtitles_type(subtitles_media: m3u8.Media) -> SubtitlesType | None:
        """
        Detect the subtitles type (Closed Captions, Forced, etc.) from an M3U8 Media object.

        Args:
            subtitles_media (m3u8.Media): Subtitles Media object to detect the type of.

        Returns:
            SubtitlesType | None: The type of the subtitles, None for regular subtitles.
        """
        if subtitles_media.forced == "YES":
            return SubtitlesType.FORCED

        if subtitles_media.characteristics is not None and "public.accessibility" in subtitles_media.characteristics:
            return SubtitlesType.CC

        return None

    async def download_subtitles(self, media_data: m3u8.Media, subrip_conversion: bool = False) -> SubtitlesData:
        try:
            playlist_m3u8 = await self.load_playlist(url=media_data.absolute_uri)

            if playlist_m3u8 is None:
                raise PlaylistLoadError("Could not load subtitles M3U8 playlist.")  # noqa: TRY301

            if not media_data.language:
                raise ValueError("Language code not found in media data.")  # noqa: TRY301

            downloaded_segments = await self.download_segments(playlist=playlist_m3u8)
            subtitles = self.subtitles_class(data=downloaded_segments[0], language_code=media_data.language)

            if len(downloaded_segments) > 1:
                for segment_data in downloaded_segments[1:]:
                    segment_subtitles_obj = self.subtitles_class(data=segment_data, language_code=media_data.language)
                    subtitles.append_subtitles(segment_subtitles_obj)

            subtitles.polish(
                fix_rtl=self.subtitles_fix_rtl,
                remove_duplicates=self.subtitles_remove_duplicates,
            )

            if subrip_conversion:
                subtitles_format = SubtitlesFormatType.SUBRIP
                content = subtitles.to_srt().dump()

            else:
                subtitles_format = SubtitlesFormatType.WEBVTT
                content = subtitles.dump()

            return SubtitlesData(
                language_code=media_data.language,
                language_name=self.parse_language_name(media_data=media_data),
                subtitles_format=subtitles_format,
                content=content,
                content_encoding=subtitles.encoding,
                special_type=self.detect_subtitles_type(subtitles_media=media_data),
            )
    
        except Exception as e:
            raise SubtitlesDownloadError(
                language_code=media_data.language,
                language_name=self.parse_language_name(media_data=media_data),
                special_type=self.detect_subtitles_type(subtitles_media=media_data),
                original_exc=e,
            ) from e

    async def download_segments(self, playlist: m3u8.M3U8) -> list[bytes]:
        responses = await asyncio.gather(
            *[
                self._async_session.get(url=segment.absolute_uri)
                for segment in playlist.segments
            ],
        )

        responses_data = []

        for result in responses:
            try:
                result.raise_for_status()
                responses_data.append(result.content)

            except Exception as e:
                raise DownloadError("One of the subtitles segments failed to download.") from e

        return responses_data

    def find_matching_media(self, main_playlist: m3u8.M3U8,
                            filters: dict[str, str | list[str]] | None = None) -> list[m3u8.Media]:
        results: list[m3u8.Media] = []
        playlist_filters: dict[str, Union[str, list[str]]] | None

        if self._playlist_filters:
            # Merge filtering dictionaries into a single dictionary
            playlist_filters = merge_dict_values(
                *[dict_item for dict_item in (filters, self._playlist_filters)
                  if dict_item is not None],
            )

        else:
            playlist_filters = filters

        for media in main_playlist.media:
            if not playlist_filters:
                results.append(media)
                continue

            is_valid = True

            for filter_name, filter_value in playlist_filters.items():
                # Skip filter if its value is None
                if filter_value is None:
                    continue

                try:
                    filter_name_enum = HLSScraper.M3U8Attribute(filter_name)
                    attribute_value = getattr(media, filter_name_enum.name.lower(), None)

                    if (attribute_value is None) or (
                            isinstance(filter_value, list) and
                            attribute_value.casefold() not in (x.casefold() for x in filter_value)
                    ) or (
                            isinstance(filter_value, str) and filter_value.casefold() != attribute_value.casefold()
                    ):
                        is_valid = False
                        break

                except Exception:
                    is_valid = False

            if is_valid:
                results.append(media)

        return results

    def find_matching_subtitles(self, main_playlist: m3u8.M3U8,
                                language_filter: list[str] | None = None) -> list[m3u8.Media]:
        _filters = self._subtitles_filters

        if language_filter:
            _filters[self.M3U8Attribute.LANGUAGE.value] = language_filter

        return self.find_matching_media(main_playlist=main_playlist, filters=_filters)
    
    @classmethod
    def format_subtitles_description(cls, subtitles_media: m3u8.Media) -> str:
        return format_subtitles_description(
            language_code=subtitles_media.language,
            language_name=cls.parse_language_name(media_data=subtitles_media),
            special_type=cls.detect_subtitles_type(subtitles_media=subtitles_media),
            )


class ScraperFactory:
    _scraper_classes_cache: list[type[Scraper]] | None = None
    _scraper_instances_cache: dict[type[Scraper], Scraper] = {}
    _currently_initializing: list[type[Scraper]] = []  # Used to prevent infinite recursion

    @classmethod
    def get_initialized_scrapers(cls) -> list[Scraper]:
        """
        Get a list of all previously initialized scrapers.

        Returns:
            list[Scraper]: A list of initialized scrapers.
        """
        return list(cls._scraper_instances_cache.values())

    @classmethod
    def get_scraper_classes(cls) -> list[type[Scraper]]:
        """
        Find all scraper classes in the scrapers directory.

        Returns:
            list[Scraper]: A Scraper subclass.
        """
        if cls._scraper_classes_cache is not None:
            return cls._scraper_classes_cache

        cls._scraper_classes_cache = []
        scraper_modules_paths = Path(__file__).parent.glob(f"*{SCRAPER_MODULES_SUFFIX}.py")

        for scraper_module_path in scraper_modules_paths:
            sys.path.append(str(scraper_module_path))

            module = importlib.import_module(f"{PACKAGE_NAME}.scrapers.{scraper_module_path.stem}")

            # Find all 'Scraper' subclasses
            for _, obj in inspect.getmembers(module,
                                             predicate=lambda x: inspect.isclass(x) and issubclass(x, Scraper)):
                # Skip object if it's an abstract or imported from another module
                if not inspect.isabstract(obj) and obj.__module__ == module.__name__:
                    cls._scraper_classes_cache.append(obj)

        return cls._scraper_classes_cache

    @classmethod
    def _get_scraper_instance(cls, scraper_class: type[ScraperT], kwargs: dict | None = None) -> ScraperT:
        """
        Initialize and return a scraper instance.

        Args:
            scraper_class (type[ScraperT]): A scraper class to initialize.
            kwargs (dict | None, optional): A dictionary containing parameters to pass to the scraper's constructor.
                Defaults to None.

        Returns:
            Scraper: An instance of the given scraper class.
        """
        logger.debug(f"Initializing '{scraper_class.name}' scraper...")
        kwargs = kwargs or {}

        if scraper_class not in cls._scraper_instances_cache:
            logger.debug(f"'{scraper_class.name}' scraper not found in cache, creating a new instance...")

            if scraper_class in cls._currently_initializing:
                raise ScraperError(f"'{scraper_class.name}' scraper is already being initialized.\n"
                                   f"Make sure there are no circular dependencies between scrapers.")

            cls._currently_initializing.append(scraper_class)

            cls._scraper_instances_cache[scraper_class] = scraper_class(**kwargs)
            cls._currently_initializing.remove(scraper_class)

        else:
            logger.debug(f"Cached '{scraper_class.name}' scraper instance found and will be used.")

        return cls._scraper_instances_cache[scraper_class]  # type: ignore[return-value]

    @classmethod
    @overload
    def get_scraper_instance(cls, scraper_class: type[ScraperT], scraper_id: str | None = ...,
                             url: str | None = ..., kwargs: dict | None = ...,
                             raise_error: Literal[True] = ...) -> ScraperT:
        ...

    @classmethod
    @overload
    def get_scraper_instance(cls, scraper_class: type[ScraperT], scraper_id: str | None = ...,
                             url: str | None = ..., kwargs: dict | None = ...,
                             raise_error: Literal[False] = ...) -> ScraperT | None:
        ...

    @classmethod
    @overload
    def get_scraper_instance(cls, scraper_class: None = ..., scraper_id: str | None = ...,
                             url: str | None = ..., kwargs: dict | None = ...,
                             raise_error: Literal[True] = ...) -> Scraper:
        ...

    @classmethod
    @overload
    def get_scraper_instance(cls, scraper_class: None = ..., scraper_id: str | None = ...,
                             url: str | None = ..., kwargs: dict | None = ...,
                             raise_error: Literal[False] = ...) -> Scraper | None:
        ...

    @classmethod
    def get_scraper_instance(cls, scraper_class: type[Scraper] | None = None, scraper_id: str | None = None,
                             url: str | None = None, kwargs: dict | None = None,
                             raise_error: bool = True) -> Scraper | None:
        """
        Find, initialize and return a scraper that matches the given URL or ID.

        Args:
            scraper_class (type[ScraperT] | None, optional): A scraper class to initialize. Defaults to None.
            scraper_id (str | None, optional): ID of a scraper to initialize. Defaults to None.
            url (str | None, optional): A URL to match a scraper for to initialize. Defaults to None.
            kwargs (dict | None, optional): A dictionary containing parameters to pass to the scraper's constructor.
                Defaults to None.
            raise_error (bool, optional): Whether to raise an error if no scraper was found. Defaults to False.

        Returns:
            ScraperT | Scraper | None: An instance of a scraper that matches the given URL or ID,
                None otherwise (if raise_error is False).

        Raises:
            ValueError: If no scraper was found and 'raise_error' is True.
        """
        if not any((scraper_class, scraper_id, url)):
            raise ValueError("At least one of: 'scraper_class', 'scraper_id', or 'url' must be provided.")

        if scraper_class:
            return cls._get_scraper_instance(
                scraper_class=scraper_class,
                kwargs=kwargs,
            )

        if scraper_id:
            logger.debug(f"Searching for a scraper object with ID '{scraper_id}'...")
            for scraper in cls.get_scraper_classes():
                if scraper.id == scraper_id:
                    return cls._get_scraper_instance(
                        scraper_class=scraper,
                        kwargs=kwargs,
                    )

        elif url:
            logger.debug(f"Searching for a scraper object that matches URL '{url}'...")
            for scraper in cls.get_scraper_classes():
                if scraper.match_url(url) is not None:
                    return cls._get_scraper_instance(
                        scraper_class=scraper,
                        kwargs=kwargs,
                    )

        error_message = "No matching scraper was found."

        if raise_error:
            raise ValueError(error_message)

        logger.debug(error_message)
        return None


class ScraperError(Exception):
    pass


class DownloadError(ScraperError):
    pass


class PlaylistLoadError(ScraperError):
    pass


class SubtitlesDownloadError(ScraperError):
    def __init__(self, language_code: str | None, language_name: str | None = None,
                 special_type: SubtitlesType | None = None, original_exc: Exception | None = None,
                 *args: Any, **kwargs: dict[str, Any]):
        """
        Initialize a SubtitlesDownloadError instance.

        Args:
            language_code (str | None, optional): Language code of the subtitles that failed to download.
            language_name (str | None, optional): Language name of the subtitles that failed to download.
            special_type (SubtitlesType | None, optional): Type of the subtitles that failed to download.
            original_exc (Exception | None, optional): The original exception that caused the error.
        """
        super().__init__(*args, **kwargs)
        self.language_code = language_code
        self.language_name = language_name
        self.special_type = special_type
        self.original_exc = original_exc
