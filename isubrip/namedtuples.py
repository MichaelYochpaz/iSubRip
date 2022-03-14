from typing import NamedTuple, Type, Union

from isubrip.enums import SubtitlesType


class MovieData(NamedTuple):
    """A named tuple containing a movie name, id, and M3U8 playlist."""
    id: str
    name: str
    release_year: int
    playlist: Union[str, None]


class SubtitlesData(NamedTuple):
    """A named tuple containing language code, language name, type and playlist URL for subtitles."""
    language_code: str
    language_name: str
    subtitles_type: SubtitlesType
    playlist_url: str


class ConfigSetting(NamedTuple):
    category: str
    key: str
    type: Type
