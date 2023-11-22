from __future__ import annotations

from abc import ABC
import datetime as dt  # noqa: TCH003
from enum import Enum
from typing import Generic, List, NamedTuple, Optional, TypeVar, Union

from pydantic import BaseModel

MediaData = TypeVar("MediaData", bound="MediaBase")


class SubtitlesDownloadResults(NamedTuple):
    """
    A named tuple containing download results.

    Attributes:
        movie_data (Movie): Movie data object.
        successful_subtitles (list[SubtitlesData]): List of subtitles that were successfully downloaded.
        failed_subtitles (list[SubtitlesData]): List of subtitles that failed to download.
        is_zip (bool): Whether the subtitles were saved in a zip file.
    """
    movie_data: Movie
    successful_subtitles: list[SubtitlesData]
    failed_subtitles: list[SubtitlesData]
    is_zip: bool


class SubtitlesFormat(BaseModel):
    """
    An object containing subtitles format data.

    Attributes:
        name (str): Name of the format.
        file_extension (str): File extension of the format.
    """
    name: str
    file_extension: str


class SubtitlesFormatType(Enum):
    """
    An Enum representing subtitles formats.

    Attributes:
        SUBRIP (SubtitlesFormat): SubRip format.
        WEBVTT (SubtitlesFormat): WebVTT format.
    """
    SUBRIP = SubtitlesFormat(name="SubRip", file_extension="srt")
    WEBVTT = SubtitlesFormat(name="WebVTT", file_extension="vtt")


class SubtitlesType(Enum):
    """
    Subtitles special type.

    Attributes:
        CC (SubtitlesType): Closed captions.
        FORCED (SubtitlesType): Forced subtitles.
    """
    CC = "CC"
    FORCED = "Forced"


# TODO: Use `kw_only` on dataclasses, and set default values of None for optional arguments once min version => 3.10

class SubtitlesData(BaseModel):
    """
    An object containing subtitles data and metadata.

    Attributes:
        language_code (str): Language code of the language the subtitles are in.
        language_name (str): Name of the language the subtitles are in.
        subtitles_format (SubtitlesFormatType): Format of the subtitles.
        content (bytes): Content of the subtitles in binary format.
        special_type (SubtitlesType | None): Type of the subtitles, if they're not regular. Defaults to None.
    """
    language_code: str
    language_name: str
    subtitles_format: SubtitlesFormatType
    content: bytes
    special_type: Union[SubtitlesType, None] = None

    class ConfigDict:
        str_strip_whitespace = True


class MediaBase(BaseModel, ABC):
    """A base class for media objects."""


class Movie(MediaBase):
    """
    An object containing movie metadata.

    Attributes:
        id (str | None, optional): ID of the movie on the service it was scraped from. Defaults to None.
        referer_id (str | None, optional): ID of the movie on the original referring service. Defaults to None.
        name (str): Title of the movie.
        release_date (datetime | int | None, optional): Release date (datetime), or year (int) of the movie.
            Defaults to None.
        duration (timedelta | None, optional): Duration of the movie. Defaults to None.
        preorder_availability_date (datetime | None, optional):
            Date when the movie will be available for pre-order on the service it was scraped from.
            None if not a pre-order. Defaults to None.
        playlist (str | None, optional): Main playlist URL(s).
    """
    name: str
    release_date: Union[dt.datetime, int]
    id: Optional[str] = None
    referer_id: Optional[str] = None
    duration: Optional[dt.timedelta] = None
    preorder_availability_date: Optional[dt.datetime] = None
    playlist: Union[str, List[str], None] = None


class Episode(MediaBase):
    """
    An object containing episode metadata.

    Attributes:
        id (str | None, optional): ID of the episode on the service it was scraped from. Defaults to None.
        referer_id (str | None, optional): ID of the episode on the original referring service. Defaults to None.
        series_name (str): Name of the series the episode is from.
        series_release_date (datetime | int | None, optional): Release date (datetime), or year (int) of the series.
            Defaults to None.
        season_number (int): Season number.
        season_name (str | None, optional): Season name. Defaults to None.
        episode_number (int): Episode number.
        episode_name (str | None, optional): Episode name. Defaults to None.
        episode_release_date (datetime | None): Release date of the episode. Defaults to None.
        episode_duration (timedelta | None, optional): Duration of the episode. Defaults to None.
        playlist (str | None, optional): Main playlist URL(s).
    """
    series_name: str
    season_number: int
    episode_number: int
    id: Optional[str] = None
    referer_id: Optional[str] = None
    series_release_date: Union[dt.datetime, int, None] = None
    season_name: Optional[str] = None
    release_date: Optional[dt.datetime] = None
    duration: Optional[dt.timedelta] = None
    episode_name: Optional[str] = None
    episode_release_date: Optional[dt.datetime] = None
    episode_duration: Optional[dt.timedelta] = None
    playlist: Union[str, List[str], None] = None


class Season(MediaBase):
    """
    An object containing season metadata.

    Attributes:
        id (str | None, optional): ID of the season on the service it was scraped from. Defaults to None.
        referer_id (str | None, optional): ID of the season on the original referring service. Defaults to None.
        series_name (str): Name of the series the season is from.
        series_release_date (datetime | int | None, optional): Release date (datetime), or year (int) of the series.
            Defaults to None.
        season_name (str | None, optional): Season name. Defaults to None.
        season_release_date (datetime | None, optional): Release date of the season, or release year. Defaults to None.
        episodes (list[Episode]): A list of episode objects containing metadata about episodes of the season.
    """
    series_name: str
    season_number: int
    id: Optional[str] = None
    referer_id: Optional[str] = None
    series_release_date: Union[dt.datetime, int, None] = None
    season_name: Optional[str] = None
    season_release_date: Union[dt.datetime, int, None] = None
    episodes: List[Episode] = []


class Series(MediaBase):
    """
    An object containing series metadata.

    Attributes:
        id (str | None, optional): ID of the series on the service it was scraped from. Defaults to None.
        series_name (str): Series name.
        referer_id (str | None, optional): ID of the series on the original referring service. Defaults to None.
        series_release_date (datetime | int | None, optional): Release date (datetime), or year (int) of the series.
            Defaults to None.
        seasons (list[Season]): A list of season objects containing metadata about seasons of the series.
    """

    series_name: str
    seasons: List[Season] = []
    id: Optional[str] = None
    referer_id: Optional[str] = None
    series_release_date: Union[dt.datetime, int, None] = None


class ScrapedMediaResponse(BaseModel, Generic[MediaData]):
    """
    An object containing scraped media data and metadata.

    Attributes:
        media_data (Movie | list[Movie] | Episode | list[Episode] | Season | list[Season] | Series | list[Series]):
            An object containing the scraped media data.
        metadata_scraper (str): ID of the scraper that was used to scrape metadata.
        playlist_scraper (str): ID of the scraper that should be used to parse and scrape the playlist.
        original_data (dict): Original raw data from the API that was used to extract media's data.
    """
    media_data: Union[MediaData, List[MediaData]]
    metadata_scraper: str
    playlist_scraper: str
    original_data: dict
