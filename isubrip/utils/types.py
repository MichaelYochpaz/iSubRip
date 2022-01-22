from typing import NamedTuple, Union
from enum import Enum
from m3u8 import M3U8

# ---------------------- Enums --------------------- #
class SubtitlesType(Enum):
    """Subtitles type (Normal / CC / Forced)."""
    NORMAL = 1
    CC = 2
    FORCED = 3


class SubtitlesFormat(Enum):        
    """Subtitles format (srt / vtt)."""
    SRT = 1
    VTT = 2


class ArchiveFormat(Enum):        
    """Archive Format (zip / tar / tar.gz)."""
    ZIP = 1
    TAR = 2
    TAR_GZ = 3
# -------------------------------------------------- #



class MovieData(NamedTuple):
    """A named tuple containing a movie name and it's main M3U8 playlist."""
    name: str
    playlist: Union[M3U8, None]


class SubtitlesData(NamedTuple):
    """A named tuple containing subtitles' language code, language name, subtitles type and playlist URL."""
    language_code: str
    language_name: str
    subtitles_type: SubtitlesType
    playlist_url: str