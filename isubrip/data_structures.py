from __future__ import annotations

import datetime as dt
from abc import ABC
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple, TYPE_CHECKING

from m3u8 import M3U8

if TYPE_CHECKING:
    from isubrip.scrapers.scraper import Scraper


class SubtitlesDownloadResults(NamedTuple):
    """
    A named tuple containing download results.

    Attributes:
        media_data (MediaData): Media data.
        successful_subtitles (list[SubtitlesData]): List of subtitles that were successfully downloaded.
        failed_subtitles (list[SubtitlesData]): List of subtitles that failed to download.
        is_zip (bool): Whether the subtitles were saved in a zip file.
    """
    media_data: MediaData
    successful_subtitles: list[SubtitlesData]
    failed_subtitles: list[SubtitlesData]
    is_zip: bool


class SubtitlesFormatData(NamedTuple):
    """
    A named tuple for containing metadata about subtitles formats.

    Attributes:
        name (str): Name of the format.
        file_extension (str): File extension of the format.
    """
    name: str
    file_extension: str


class SubtitlesFormat(Enum):
    """
    An Enum representing subtitles formats.

    Attributes:
        SUBRIP (SubtitlesFormatData): SubRip format.
        WEBVTT (SubtitlesFormatData): WebVTT format.
    """
    SUBRIP = SubtitlesFormatData("SubRip", "srt")
    WEBVTT = SubtitlesFormatData("WebVTT", "vtt")


class SubtitlesType(Enum):
    """
    Subtitles special type.

    Attributes:
        CC (SubtitlesType): Closed captions.
        FORCED (SubtitlesType): Forced subtitles.
    """
    CC = "CC"
    FORCED = "Forced"


@dataclass
class SubtitlesData:
    """
    A named tuple containing subtitles metadata.

    Attributes:
        language_code (str): Language code of the language the subtitles are in.
        language_name (str): Name of the language the subtitles are in.
        subtitles_format (SubtitlesFormat): Format of the subtitles.
        content (bytes): Content of the subtitles in binary format.
        special_type (SubtitlesType | None): Type of the subtitles, if they're not regular. Defaults to None.
    """
    language_code: str
    language_name: str
    subtitles_format: SubtitlesFormat
    content: bytes
    special_type: SubtitlesType | None = None

    def __post_init__(self):
        self.language_name = self.language_name.strip()


# TODO: Use `kw_only` on dataclasses, and set default values of None for optional arguments once min version => 3.10

@dataclass
class PlaylistData:
    """
    A named tuple containing playlist metadata.

    Attributes:
        id (str | None): ID of the playlist.
        url (str | None): URL to the playlist.
        data (M3U8): Playlist data.
        duration (timedelta | None, optional): Duration of the playlist. Defaults to None.
    """
    url: str
    data: M3U8
    id: str | None = None
    duration: dt.timedelta | None = None


@dataclass
class MediaData(ABC):
    """
    A base class for media data.

    Attributes:
        id (str | None): ID of the media.
        alt_id (str | None): Alternative ID of the media.
        name (str): Name of the media. (movie or series name)
        release_date (datetime): Release date of the media.
        playlist (PlaylistData | list[PlaylistData] | None): URL to the playlist.
        scraper (Scraper): A reference to the scraper that should be used with the data.
        original_scraper (Scraper): A reference to the scraper that was used to get the data.
        original_data (dict): Original data that was used to create the object.
    """
    id: str | None
    alt_id: str | None
    name: str
    release_date: dt.datetime
    playlist: PlaylistData | list[PlaylistData] | None
    scraper: Scraper
    original_scraper: Scraper
    original_data: dict


@dataclass
class MovieData(MediaData):
    """A named tuple containing movie metadata.

    Attributes:
        duration (timedelta | None, optional): Duration of the movie. Defaults to None.
        preorder_availability_date (datetime | None, optional): Date when the movie will be available for preorder.
            None if not a preorder. Defaults to None.
    """
    duration: dt.timedelta | None = None
    preorder_availability_date: dt.datetime | None = None


@dataclass
class EpisodeData(MediaData):
    """
    A named tuple containing episode metadata.

    Attributes:
        episode_number (int): Episode number.
        season_number (int): Season number.
        episode_name (str | None, optional): Episode name. Defaults to None.
        season_name (str | None, optional): Season name. Defaults to None.
        episode_release_date (datetime | None): Release date of the episode. Defaults to None.
        duration (timedelta | None, optional): Duration of the episode. Defaults to None.
    """
    episode_number: int
    episode_name: str
    season_number: int
    episode_release_date: dt.datetime | None = None
    season_name: str | None = None
    duration: dt.timedelta | None = None



@dataclass
class SeasonData(MediaData):
    """
    A named tuple containing season metadata.

    Attributes:
        season_number (int): Season number.
        season_name (str | None, optional): Season name. Defaults to None.
        season_episodes (list[EpisodeData]): Episodes that belong to the season.
        season_release_date (datetime | None, optional): Release date of the season. Defaults to None.
    """
    season_number: int
    season_episodes: list[EpisodeData]
    season_release_date: dt.datetime | None = None
    season_name: str | None = None


@dataclass
class SeriesData(MediaData):
    """
    A named tuple containing series metadata.

    Attributes:
        series_seasons (list[SeasonData]): Seasons that belong to the series.
    """
    series_seasons: list[SeasonData]
