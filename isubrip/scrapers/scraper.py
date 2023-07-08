from __future__ import annotations

import asyncio
import importlib
import inspect
import os
import re
import sys
from abc import abstractmethod, ABC
from enum import Enum
from glob import glob
from pathlib import Path
from typing import Any, ClassVar, Iterator, List, Literal, overload, Union, TypeVar

import aiohttp
import m3u8
import requests
import requests.utils
from m3u8 import M3U8, Media, Segment, SegmentList

from isubrip.config import Config, ConfigSetting
from isubrip.constants import PACKAGE_NAME, SCRAPER_MODULES_SUFFIX
from isubrip.data_structures import SubtitlesData, SubtitlesFormatType, SubtitlesType, ScrapedMediaResponse
from isubrip.subtitle_formats.subtitles import Subtitles
from isubrip.utils import merge_dict_values, single_to_list, SingletonMeta


ScraperT = TypeVar("ScraperT", bound="Scraper")


class Scraper(ABC, metaclass=SingletonMeta):
    """
    A base class for scrapers.

    Attributes:
        default_user_agent (str): [Class Attribute]
            Default user agent to use if no other user agent is specified when making requests.
        subtitles_fix_rtl (bool): [Class Attribute] Whether to fix RTL from downloaded subtitles.
        subtitles_fix_rtl_languages (list[str] | None): [Class Attribute]
            A list of languages to fix RTL on. If None, a default list will be used.
        subtitles_remove_duplicates (bool): [Class Attribute]
            Whether to remove duplicate lines from downloaded subtitles.

        id (str): [Class Attribute] ID of the scraper.
        name (str): [Class Attribute] Name of the scraper.
        abbreviation (str): [Class Attribute] Abbreviation of the scraper.
        url_regex (str): [Class Attribute] A RegEx pattern to find URLs matching the service.
        subtitles_class (type[Subtitles]): [Class Attribute] Class of the subtitles format returned by the scraper.
        is_movie_scraper (bool): [Class Attribute] Whether the scraper is for movies.
        is_series_scraper (bool): [Class Attribute] Whether the scraper is for series.
        uses_scrapers (list[str]): [Class Attribute] A list of IDs for other scraper classes that this scraper uses.
            This assures that the config data for the other scrapers is passed as well.
        _session (requests.Session): A requests session to use for making requests.
        config (Config): A Config object containing the scraper's configuration.
    """
    default_user_agent: ClassVar[str] = requests.utils.default_user_agent()
    subtitles_fix_rtl: ClassVar[bool] = False
    subtitles_fix_rtl_languages: ClassVar[list | None] = ["ar", "he"]
    subtitles_remove_duplicates: ClassVar[bool] = True

    id: ClassVar[str]
    name: ClassVar[str]
    abbreviation: ClassVar[str]
    url_regex: ClassVar[str | list[str]]
    subtitles_class: ClassVar[type[Subtitles]]
    is_movie_scraper: ClassVar[bool] = False
    is_series_scraper: ClassVar[bool] = False
    uses_scrapers: ClassVar[list[str]] = []

    def __init__(self, config_data: dict | None = None):
        """
        Initialize a Scraper object.

        Args:
            config_data (dict | None, optional): A dictionary containing scraper's configuration data. Defaults to None.
        """
        self._session = requests.Session()
        self._config_data = config_data
        self.config = Config(config_data=config_data.get(self.id) if config_data else None)

        self.config.add_settings([
            ConfigSetting(
                key="user-agent",
                type=str,
                required=False,
            )],
            check_config=False)

        self._session.headers.update({"User-Agent": self.config.get("user-agent") or self.default_user_agent})

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
        if isinstance(cls.url_regex, str):
            return re.fullmatch(pattern=cls.url_regex, string=url, flags=re.IGNORECASE)

        else:  # isinstance(cls.url_regex, (list, tuple)):
            for url_regex_item in cls.url_regex:
                if result := re.fullmatch(pattern=url_regex_item, string=url, flags=re.IGNORECASE):
                    return result

        if raise_error:
            raise ValueError(f"URL '{url}' doesn't match the URL regex of {cls.name}.")

        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        self._session.close()

    @abstractmethod
    def get_data(self, url: str) -> ScrapedMediaResponse:
        """
        Scrape media information about the media on a URL.

        Args:
            url (str): A URL to get media information about.

        Returns:
            ScrapedMediaResponse: A ScrapedMediaResponse object containing scraped media information.
        """
        pass

    @abstractmethod
    def get_subtitles(self, main_playlist: str | list[str], language_filter: list[str] | None = None,
                      subrip_conversion: bool = False) -> Iterator[SubtitlesData]:
        """
        Find and yield subtitles data from a main_playlist.

        Args:
            main_playlist (M3U8): Main playlist of the media to search for subtitles in.
            language_filter (list[str], optional): A list of languages to filter for.
            subrip_conversion (bool, optional): Whether to convert the subtitles to SubRip format. Defaults to False.

        Yields:
            SubtitlesData: A SubtitlesData object for each subtitle found
                in the main playlist (matching the filters, if given).
        """
        pass


class MovieScraper(Scraper, ABC):
    """A base class for movie scrapers."""
    is_movie_scraper = True


class SeriesScraper(Scraper, ABC):
    """A base class for series scrapers."""
    is_series_scraper = True


class AsyncScraper(Scraper, ABC):
    """A base class for scrapers that utilize async requests."""
    def __init__(self, config_data: dict | None = None):
        super().__init__(config_data)
        self.async_session = aiohttp.ClientSession()
        self.async_session.headers.update(self._session.headers)

    def close(self):
        asyncio.get_event_loop().run_until_complete(self._async_close())
        super().close()

    async def _async_close(self):
        await self.async_session.close()


class M3U8Scraper(AsyncScraper, ABC):
    """A base class for M3U8 scrapers."""
    playlist_filters_config_category = "playlist-filters"

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

    def __init__(self, config_data: dict | None = None):
        super().__init__(config_data)

        if self.config is None:
            self.config = Config()

        # Add M3U8 filters settings
        self.config.add_settings([
            ConfigSetting(
                category=self.playlist_filters_config_category,
                key=m3u8_attribute.value,
                type=Union[str, List[str]],
                required=False,
            ) for m3u8_attribute in self.M3U8Attribute],
            check_config=False)

        self._m3u8_cache: dict[str, M3U8] = {}

    def _download_segments_async(self, segments: SegmentList[Segment]) -> list[bytes]:
        """
        Download M3U8 segments asynchronously.

        Args:
            segments (m3u8.SegmentList[m3u8.Segment]): List of segments to download.

        Returns:
            list[bytes]: List of downloaded segments.
        """
        loop = asyncio.get_event_loop()
        async_tasks = [loop.create_task(self._download_segment_async(segment.absolute_uri)) for segment in segments]
        segments_bytes = loop.run_until_complete(asyncio.gather(*async_tasks))

        return list(segments_bytes)

    async def _download_segment_async(self, url: str) -> bytes:
        """
        Download an M3U8 segment asynchronously.

        Args:
            url (str): URL of the segment to download.

        Returns:
            bytes: Downloaded segment.
        """
        async with self.async_session.get(url) as response:
            return await response.read()

    @overload
    def load_m3u8(self, url: str | list[str], raise_error: Literal[True] = ...) -> M3U8:
        ...

    @overload
    def load_m3u8(self, url: str | list[str], raise_error: Literal[False] = ...) -> M3U8 | None:
        ...

    def load_m3u8(self, url: str | list[str], raise_error: bool = False) -> M3U8 | None:
        """
        Load an M3U8 playlist from a URL to an M3U8 object.
        Multiple URLs can be given, in which case the first one that loads successfully will be returned.
        The method uses caching to avoid loading the same playlist multiple times.

        Args:
            url (str | list[str]: URL of the M3U8 playlist to load.
            raise_error (bool, optional): Whether to raise an error if none of the playlists loaded successfully.
                If set to false, a None value will be returned instead. Defaults to False.

        Returns:
            m3u8.M3U8: An M3U8 object representing the playlist.
        """
        errors = {}

        for _url in single_to_list(url):
            if _url in self._m3u8_cache:
                return self._m3u8_cache[_url]

            else:
                try:
                    self._m3u8_cache[_url] = m3u8.load(uri=_url, timeout=5)
                    return self._m3u8_cache[_url]

                except Exception as e:
                    errors[_url] = e
                    continue

        if raise_error:
            errors_str = "\n".join([f"{url}: {error}" for url, error in errors.items()])
            raise ScraperException(f"Failed to load M3U8 playlist: {url}:\n{errors_str}")

        return None

    def _map_session_data(self, playlist_data: M3U8) -> dict[str, Any]:
        """
        Create and return a dictionary of session data from an M3U8 playlist.

        Args:
            playlist_data (m3u8.M3U8): M3U8 playlist to map session data from.

        Returns:
            dict[str, Any]: Dictionary of session data.
        """
        session_data = {}

        if playlist_data.session_data:
            for session_data_item in playlist_data.session_data:
                session_data[session_data_item.data_id] = session_data_item.value

        return session_data


    @staticmethod
    def detect_subtitles_type(subtitles_media: Media) -> SubtitlesType | None:
        """
        Detect the subtitles type (Closed Captions, Forced, etc.) from an M3U8 Media object.

        Args:
            subtitles_media (m3u8.Media): Subtitles Media object to detect the type of.

        Returns:
            SubtitlesType | None: The type of the subtitles, None for regular subtitles.
        """
        if subtitles_media.forced == "YES":
            return SubtitlesType.FORCED

        elif subtitles_media.characteristics is not None and "public.accessibility" in subtitles_media.characteristics:
            return SubtitlesType.CC

        return None

    def find_valid_playlist(self, playlists: list[str] | str) -> M3U8 | None:
        """
        Find and return a valid M3U8 playlist from a list of playlists.

        Args:
            playlists (list[str] | str): List of playlists to check (list[str]). Can also be a single playlist (str).

        Returns:
            m3u8.M3U8 | None: A successfully loaded M3U8 playlist, or None if none of the playlists loaded successfully.
        """
        for playlist in single_to_list(playlists):  # type: str
            try:
                return self.load_m3u8(playlist)

            except Exception:
                continue

        return None

    def get_media_playlists(self, main_playlist: M3U8,
                            playlist_filters: dict[str, str | list[str]] | None = None,
                            include_default_filters: bool = True) -> list[Media]:
        """
        Find and yield playlists of media within an M3U8 main_playlist using optional filters.

        Args:
            main_playlist (m3u8.M3U8): An M3U8 object of the main main_playlist.
            playlist_filters (dict[str, str | list[str], optional):
                A dictionary of filters to use when searching for subtitles.
                Will be added to filters set by the config (unless `include_default_filters` is set to false).
                Defaults to None.
            include_default_filters (bool, optional): Whether to include the default filters set by the config or not.
                Defaults to True.

        Returns:
            list[Media]: A list of  matching Media objects.
        """
        results = []
        default_filters: dict | None = self.config.get(M3U8Scraper.playlist_filters_config_category)

        if include_default_filters and default_filters:
            if not playlist_filters:
                playlist_filters = default_filters

            else:
                playlist_filters = merge_dict_values(default_filters, playlist_filters)

        for media in main_playlist.media:
            if not playlist_filters:
                results.append(media)
                continue

            is_valid = True

            for filter_name, filter_value in playlist_filters.items():
                try:
                    filter_name_enum = M3U8Scraper.M3U8Attribute(filter_name)
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

    def get_subtitles(self, main_playlist: str | list[str], language_filter: list[str] | str | None = None,
                      subrip_conversion: bool = False) -> Iterator[SubtitlesData]:
        """
        Find and yield subtitles for a movie using optional filters.

        Args:
            main_playlist(str | list[str]): A URL or a list of URLs (for redundancy) of the main playlist.
            language_filter (list[str] | str | None, optional):
                A language or a list of languages to filter for. Defaults to None.
            subrip_conversion (bool, optional): Whether to convert and return the subtitles as an SRT file or not.
                Defaults to False.

        Yields:
            SubtitlesData: A SubtitlesData NamedTuple with a matching playlist, and it's metadata.
        """
        playlist_filters = {self.M3U8Attribute.LANGUAGE.value: language_filter} if language_filter else None
        main_playlist_m3u8 = self.find_valid_playlist(main_playlist)

        if main_playlist_m3u8 is None:
            raise ScraperException("Failed to load main playlist.")

        matched_media_items = self.get_media_playlists(main_playlist=main_playlist_m3u8,
                                                       playlist_filters=playlist_filters)

        for matched_media in matched_media_items:
            try:
                matched_media_playlist = m3u8.load(matched_media.absolute_uri)
                subtitles = self.subtitles_class(language_code=matched_media.language)
                for segment in self._download_segments_async(matched_media_playlist.segments):
                    subtitles.append_subtitles(subtitles.loads(segment.decode("utf-8")))

                subtitles.polish(
                    fix_rtl=self.subtitles_fix_rtl,
                    rtl_languages=self.subtitles_fix_rtl_languages,
                    remove_duplicates=self.subtitles_remove_duplicates,
                )

                yield SubtitlesData(
                    language_code=matched_media.language,
                    language_name=matched_media.name,
                    subtitles_format=SubtitlesFormatType.SUBRIP if subrip_conversion else SubtitlesFormatType.WEBVTT,
                    content=subtitles.to_srt().dump() if subrip_conversion else subtitles.dump(),
                    special_type=self.detect_subtitles_type(matched_media),
                )

            except Exception:
                continue


class ScraperFactory(metaclass=SingletonMeta):
    def __init__(self):
        self._scraper_classes_cache: list[type[Scraper]] | None = None
        self._scraper_instances_cache: dict[type[Scraper], Scraper] = {}
        self._currently_initializing: list[type[Scraper]] = []  # Used to prevent infinite recursion

    def get_initialized_scrapers(self) -> list[Scraper]:
        """
        Get a list of all previously initialized scrapers.

        Returns:
            list[Scraper]: A list of initialized scrapers.
        """
        return list(self._scraper_instances_cache.values())

    def get_scraper_classes(self) -> Iterator[type[Scraper]]:
        """
        Iterate over all scraper classes.

        Yields:
            type[Scraper]: A Scraper subclass.
        """
        if self._scraper_classes_cache is not None:
            return self._scraper_classes_cache

        else:
            scraper_modules_paths = glob(os.path.dirname(__file__) + f"/*{SCRAPER_MODULES_SUFFIX}.py")

            for scraper_module_path in scraper_modules_paths:
                sys.path.append(scraper_module_path)

                module = importlib.import_module(f"{PACKAGE_NAME}.scrapers.{Path(scraper_module_path).stem}")

                # Find all 'Scraper' subclasses
                for _, obj in inspect.getmembers(module,
                                                 predicate=lambda x: inspect.isclass(x) and issubclass(x, Scraper)):
                    # Skip object if it's an abstract or imported from another module
                    if not inspect.isabstract(obj) and obj.__module__ == module.__name__:
                        if any((obj.is_movie_scraper, obj.is_series_scraper)):
                            yield obj

            return

    def _get_scraper_instance(self, scraper_class: type[ScraperT],
                              scrapers_config_data: dict | None = None) -> ScraperT:
        """
        Initialize and return a scraper instance.

        Args:
            scraper_class (type[ScraperT]): A scraper class to initialize.
            scrapers_config_data (dict, optional): A dictionary containing scrapers config data to use
                when creating a new scraper. Defaults to None.

        Returns:
            Scraper: An instance of the given scraper class.
        """
        if scraper_class not in self._scraper_instances_cache:
            if scraper_class in self._currently_initializing:
                raise ScraperException(f"Scraper '{scraper_class.id}' is already being initialized.\n"
                                       f"Make sure there are no circular dependencies between scrapers.")

            self._currently_initializing.append(scraper_class)

            # Set config data for the scraper and its dependencies, if any
            if not scrapers_config_data:
                config_data = None

            else:
                required_scrapers_ids = [scraper_class.id] + scraper_class.uses_scrapers
                config_data = \
                    {scraper_id: scrapers_config_data[scraper_id] for scraper_id in required_scrapers_ids
                     if scrapers_config_data.get(scraper_id)}

            self._scraper_instances_cache[scraper_class] = scraper_class(config_data=config_data)
            self._currently_initializing.remove(scraper_class)

        return self._scraper_instances_cache[scraper_class]  # type: ignore[return-value]

    @overload
    def get_scraper_instance(self, scraper_class: type[ScraperT], scraper_id: str | None = ...,
                             url: str | None = ..., config_data: dict | None = ...,
                             raise_error: Literal[True] = ...) -> ScraperT:
        ...

    @overload
    def get_scraper_instance(self, scraper_class: type[ScraperT], scraper_id: str | None = ...,
                             url: str | None = ..., config_data: dict | None = ...,
                             raise_error: Literal[False] = ...) -> ScraperT | None:
        ...

    @overload
    def get_scraper_instance(self, scraper_class: None = ..., scraper_id: str | None = ...,
                             url: str | None = ..., config_data: dict | None = ...,
                             raise_error: Literal[True] = ...) -> Scraper:
        ...

    @overload
    def get_scraper_instance(self, scraper_class: None = ..., scraper_id: str | None = ...,
                             url: str | None = ..., config_data: dict | None = ...,
                             raise_error: Literal[False] = ...) -> Scraper | None:
        ...

    def get_scraper_instance(self, scraper_class: type[Scraper] | None = None, scraper_id: str | None = None,
                             url: str | None = None, config_data: dict | None = None,
                             raise_error: bool = True) -> Scraper | None:
        """
        Find, initialize and return a scraper that matches the given URL or ID.

        Args:
            scraper_class (type[ScraperT] | None, optional): A scraper class to initialize. Defaults to None.
            scraper_id (str | None, optional): ID of a scraper to initialize. Defaults to None.
            url (str | None, optional): A URL to match a scraper for to initialize. Defaults to None.
            config_data (dict, optional): A dictionary containing scrapers config data to use
                when creating a new scraper. Defaults to None.
            raise_error (bool, optional): Whether to raise an error if no scraper was found. Defaults to False.

        Returns:
            ScraperT | Scraper | None: An instance of a scraper that matches the given URL or ID,
                None otherwise (if raise_error is False).

        Raises:
            ValueError: If no scraper was found and raise_error is True.
        """
        if scraper_class:
            return self._get_scraper_instance(scraper_class=scraper_class,
                                              scrapers_config_data=config_data)

        elif scraper_id or url:
            for scraper in self.get_scraper_classes():
                if (scraper_id and scraper.id == scraper_id) or (url and scraper.match_url(url) is not None):
                    return self._get_scraper_instance(scraper_class=scraper, scrapers_config_data=config_data)

            if raise_error:
                raise ValueError(f"No matching scraper was found for URL '{url}'")

            return None

        else:
            raise ValueError("At least one of: 'scraper_class', 'scraper_id', or 'url' must be provided.")


class ScraperException(Exception):
    pass
