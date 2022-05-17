from typing import List, NamedTuple, Type, Union

from isubrip.enums import DataSource, SubtitlesType


class PlaylistData(NamedTuple):
    """A named tuple containing a playlist iTunes ID and URL."""
    itunes_id: str
    url: str


class MovieData(NamedTuple):
    """A named tuple containing a movie name, id, and M3U8 playlist."""
    data_source: DataSource
    name: str
    release_year: int
    playlists: List[PlaylistData]


class SubtitlesData(NamedTuple):
    """A named tuple containing language code, language name, type and playlist URL for subtitles."""
    language_code: str
    language_name: str
    subtitles_type: SubtitlesType
    playlist_url: str


class ConfigSetting(NamedTuple):
    category: str
    key: str
    types: Union[tuple, Type]
